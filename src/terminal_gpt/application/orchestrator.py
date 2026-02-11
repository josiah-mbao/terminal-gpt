"""Intelligent conversation orchestrator for Terminal GPT."""

import json
import time
from typing import Dict, List, Optional, Any

from ..domain.models import Message, ConversationState, ConversationSummary
from ..domain.exceptions import LLMError, PluginError, ValidationError
from ..infrastructure.llm_providers import LLMProvider
from ..domain.plugins import plugin_registry
from ..application.events import (
    publish_user_message, publish_assistant_response,
    publish_plugin_execution, publish_conversation_error
)
from ..infrastructure.logging import get_logger
from ..infrastructure.prompt_manager import get_system_prompt
from ..infrastructure.context_summarizer import ContextSummarizer

logger = get_logger("terminal_gpt.orchestrator")

# Terminal intents that should short-circuit tool calling
TERMINAL_INTENTS = {
    "quit", "exit", "bye", "goodbye", "thanks", "thank you",
    "no", "stop", "end", "close", "later", "see ya", "cya"
}


def is_terminal_intent(message: str) -> bool:
    """Check if user message is a terminal/farewell intent."""
    normalized = message.lower().strip().rstrip("!.")
    # Check exact match or if message starts with terminal phrase
    if normalized in TERMINAL_INTENTS:
        return True
    # Check for phrases like "thanks a bunch", "thanks anyway"
    for intent in TERMINAL_INTENTS:
        if normalized.startswith(intent):
            return True
    return False


class ConversationOrchestrator:
    """Orchestrates intelligent conversations between users, LLMs, and plugins."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_conversation_length: int = 100,
        sliding_window_size: int = 50,
        enable_summarization: bool = False,
        system_prompt: Optional[str] = None
    ):
        """
        Initialize the conversation orchestrator.

        Args:
            llm_provider: LLM provider for generating responses
            max_conversation_length: Maximum messages in conversation
            sliding_window_size: Size of context window for LLM
            enable_summarization: Whether to enable conversation summarization
            system_prompt: Optional system prompt to add to conversations
        """
        self.llm_provider = llm_provider
        self.max_conversation_length = max_conversation_length
        self.sliding_window_size = sliding_window_size
        self.enable_summarization = enable_summarization
        self.system_prompt = system_prompt

        # Active conversations (in production, this would be persistent storage)
        self._conversations: Dict[str, ConversationState] = {}

    async def start_conversation(self, session_id: str) -> ConversationState:
        """Start a new conversation session."""
        if session_id in self._conversations:
            raise ValidationError(f"Conversation {session_id} already exists")

        conversation = ConversationState(session_id=session_id)

        # Add system prompt if configured
        system_prompt = get_system_prompt()
        if system_prompt:
            system_message = Message(
                role="system", content=system_prompt
            )
            conversation = conversation.add_message(system_message)
            logger.info(
                "Added system prompt to conversation",
                session_id=session_id
            )

        self._conversations[session_id] = conversation

        logger.info("Started new conversation", session_id=session_id)
        return conversation

    async def process_user_message(
        self,
        session_id: str,
        user_content: str
    ) -> str:
        """
        Process a user message and return the assistant's response.

        This is the main entry point for conversation processing.
        """
        try:
            # Get or create conversation
            if session_id not in self._conversations:
                await self.start_conversation(session_id)

            conversation = self._conversations[session_id]

            # Add user message
            user_message = Message(role="user", content=user_content)
            conversation = conversation.add_message(user_message)

            # Publish user message event
            await publish_user_message(session_id, user_content)

            # Generate assistant response
            response_content = await self._generate_assistant_response(conversation)

            # Add assistant response
            assistant_message = Message(role="assistant", content=response_content)
            conversation = conversation.add_message(assistant_message)

            # Update conversation state
            self._conversations[session_id] = conversation

            # Publish assistant response event
            await publish_assistant_response(session_id, response_content)

            # Manage conversation length
            conversation = await self._manage_conversation_length(conversation)
            self._conversations[session_id] = conversation

            return response_content

        except Exception as e:
            # Publish conversation error event
            await publish_conversation_error(
                session_id=session_id,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise

    async def process_user_message_stream(
        self,
        session_id: str,
        user_content: str
    ):
        """
        Process a user message and stream the assistant's response.

        This is the main entry point for streaming conversation processing.
        """
        try:
            # Get or create conversation
            if session_id not in self._conversations:
                await self.start_conversation(session_id)

            conversation = self._conversations[session_id]

            # Check for terminal intent BEFORE adding message or calling LLM
            if is_terminal_intent(user_content):
                logger.info(
                    "Terminal intent detected, skipping tool calls",
                    session_id=session_id,
                    user_content=user_content
                )
                # Reset tool cycle and mark awaiting user
                conversation = conversation.copy(
                    update={
                        'tool_cycle_count': 0,
                        'awaiting_user': True,
                        'active_task': None
                    }
                )
                # Add user message
                user_message = Message(role="user", content=user_content)
                conversation = conversation.add_message(user_message)
                
                # Yield a simple farewell response
                farewell_responses = [
                    "👋 Catch you later!",
                    "No worries, talk soon!",
                    "All good, see ya!",
                    "Later! Hit me up if you need anything."
                ]
                import secrets
                farewell = secrets.choice(farewell_responses)
                
                yield {
                    "content": farewell,
                    "finish_reason": "stop",
                    "model": "terminal-gpt",
                    "usage": {},
                    "tool_calls": []
                }
                
                # Add assistant response to conversation
                assistant_message = Message(role="assistant", content=farewell)
                conversation = conversation.add_message(assistant_message)
                self._conversations[session_id] = conversation
                return

            # Reset tool cycle count for new user turn
            conversation = conversation.copy(
                update={
                    'tool_cycle_count': 0,
                    'awaiting_user': False
                }
            )

            # Add user message
            user_message = Message(role="user", content=user_content)
            conversation = conversation.add_message(user_message)

            # Publish user message event
            await publish_user_message(session_id, user_content)

            # Generate assistant response with streaming
            async for chunk in self._generate_assistant_response_stream(conversation):
                yield chunk

            # Manage conversation length
            conversation = await self._manage_conversation_length(conversation)
            self._conversations[session_id] = conversation

        except Exception as e:
            # Publish conversation error event
            await publish_conversation_error(
                session_id=session_id,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise

    async def _generate_assistant_response(self, conversation: ConversationState) -> str:
        """Generate an assistant response, potentially involving tool calls."""
        max_iterations = 5  # Prevent infinite loops
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1

            # Prepare context for LLM
            messages = self._prepare_context_messages(conversation)
            tools = self._get_available_tools()

            try:
                # Generate LLM response
                start_time = time.time()
                async with self.llm_provider:
                    llm_response = await self.llm_provider.generate(
                        messages=messages,
                        tools=tools,
                        config={
                            "temperature": 0.7,
                            "max_tokens": 4096
                        }
                    )
                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "LLM response generated",
                    session_id=conversation.session_id,
                    duration_ms=duration_ms,
                    tokens_used=(
                        llm_response.usage.get("total_tokens", 0)
                        if llm_response.usage else 0
                    )
                )

                # Check for tool calls
                if llm_response.tool_calls:
                    tool_results = await self._execute_tool_calls(
                        conversation.session_id,
                        llm_response.tool_calls
                    )

                    # Add tool results to conversation
                    for tool_result in tool_results:
                        tool_message = Message(
                            role="tool",
                            content=tool_result["result"],
                            name=tool_result["tool_name"]
                        )
                        conversation = conversation.add_message(tool_message)

                    # Continue the loop to get final response
                    continue
                else:
                    # No tool calls, return the response
                    return llm_response.content

            except LLMError as e:
                logger.error(
                    "LLM generation failed",
                    session_id=conversation.session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    iteration=current_iteration
                )
                # For now, return a helpful error message
                # In production, you might want different strategies
                return (
                    "I apologize, but I'm having trouble generating a response "
                    "right now. Please try again."
                )

        # Max iterations reached
        logger.warning(
            "Max iterations reached in conversation",
            session_id=conversation.session_id,
            max_iterations=max_iterations
        )
        return "I'm sorry, but this conversation has become too complex. Please start a new conversation."

    async def _generate_assistant_response_stream(self, conversation: ConversationState):
        """Generate an assistant response with streaming, potentially involving tool calls.
        
        Enforces one tool cycle per user message to prevent runaway loops.
        """
        max_iterations = 3  # Reduced from 5 - one tool cycle + final answer max
        current_iteration = 0
        has_completed_tool_cycle = False

        while current_iteration < max_iterations:
            current_iteration += 1

            # Enforce one tool cycle limit
            if has_completed_tool_cycle:
                logger.info(
                    "Tool cycle already completed, forcing final answer",
                    session_id=conversation.session_id
                )
                # Disable tools for final answer
                tools = None
            else:
                tools = self._get_available_tools()

            # Prepare context for LLM
            messages = self._prepare_context_messages(conversation)

            try:
                # Generate LLM response with streaming
                start_time = time.time()
                full_response = ""
                tool_calls_found = None

                async with self.llm_provider:
                    async for chunk in self.llm_provider.generate_stream(
                        messages=messages,
                        tools=tools,
                        config={
                            "temperature": 0.7,
                            "max_tokens": 4096
                        }
                    ):
                        # Yield the chunk for UI display
                        yield chunk
                        full_response += chunk.content

                        # Capture tool calls if present
                        if chunk.tool_calls and tool_calls_found is None:
                            tool_calls_found = chunk.tool_calls

                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "LLM streaming response completed",
                    session_id=conversation.session_id,
                    duration_ms=duration_ms,
                    has_tool_calls=tool_calls_found is not None
                )

                # Handle tool calls if found
                if tool_calls_found:
                    logger.info(
                        "Tool calls detected in streaming response",
                        session_id=conversation.session_id,
                        tool_count=len(tool_calls_found)
                    )

                    # CRITICAL: First add assistant message with tool_calls to conversation
                    # This establishes the linkage for the tool results
                    assistant_tool_message = Message(
                        role="assistant",
                        content=full_response if full_response else None,
                        tool_calls=tool_calls_found
                    )
                    conversation = conversation.add_message(assistant_tool_message)

                    # Execute tool calls
                    tool_results = await self._execute_tool_calls(
                        conversation.session_id,
                        tool_calls_found
                    )

                    # Add tool results to conversation with tool_call_id linkage
                    for tool_result in tool_results:
                        # Validate tool_call_id exists - fail loudly if missing
                        tool_call_id = tool_result.get("tool_call_id")
                        if not tool_call_id:
                            logger.error(
                                "CRITICAL: tool_call_id is missing from tool result",
                                session_id=conversation.session_id,
                                tool_name=tool_result["tool_name"]
                            )
                            raise LLMError(
                                f"tool_call_id is required but missing for tool: "
                                f"{tool_result['tool_name']}"
                            )

                        tool_message = Message(
                            role="tool",
                            content=tool_result["result"],
                            name=tool_result["tool_name"],
                            tool_call_id=tool_call_id
                        )
                        conversation = conversation.add_message(tool_message)

                    # Mark that we've completed a tool cycle
                    has_completed_tool_cycle = True
                    
                    # Continue the loop to get final response after tool execution
                    continue
                else:
                    # No tool calls, add assistant response to conversation
                    if full_response:
                        assistant_message = Message(
                            role="assistant",
                            content=full_response
                        )
                        conversation = conversation.add_message(assistant_message)
                    # Streaming is complete
                    break

            except LLMError as e:
                logger.error(
                    "LLM streaming generation failed",
                    session_id=conversation.session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    iteration=current_iteration
                )
                yield {
                    "content": (
                        "I apologize, but I'm having trouble generating a "
                        "response right now. Please try again."
                    ),
                    "finish_reason": "error",
                    "model": self.llm_provider.model,
                    "usage": {},
                    "tool_calls": []
                }
                break

        # Max iterations reached
        if current_iteration >= max_iterations:
            logger.warning(
                "Max iterations reached in streaming conversation",
                session_id=conversation.session_id,
                max_iterations=max_iterations
            )
            yield {
                "content": (
                    "I'm sorry, but this conversation has become too complex. "
                    "Please start a new conversation."
                ),
                "finish_reason": "length",
                "model": self.llm_provider.model,
                "usage": {},
                "tool_calls": []
            }

    def _prepare_context_messages(self, conversation: ConversationState) -> List[Dict[str, Any]]:
        """Prepare messages for LLM context, managing sliding window.
        
        Properly formats tool calling messages with tool_calls and tool_call_id.
        """
        all_messages = conversation.messages

        # If conversation is within sliding window, use all messages
        if len(all_messages) <= self.sliding_window_size:
            selected_messages = all_messages
        else:
            # Use sliding window approach
            # Always include system message if present
            context_messages = []
            regular_messages = []

            for msg in all_messages:
                if msg.role == "system":
                    context_messages.append(msg)
                else:
                    regular_messages.append(msg)

            # Take most recent messages within window size
            recent_messages = regular_messages[-self.sliding_window_size:]

            # Combine system messages with recent conversation
            selected_messages = context_messages + recent_messages

            logger.info(
                "Using sliding window context",
                session_id=conversation.session_id,
                total_messages=len(all_messages),
                context_messages=len(selected_messages)
            )

        # Format messages for LLM API, including tool calling fields
        formatted_messages = []
        for msg in selected_messages:
            formatted_msg: Dict[str, Any] = {"role": msg.role}
            
            # Handle content (can be None for assistant with tool_calls)
            if msg.content is not None:
                formatted_msg["content"] = msg.content
            else:
                formatted_msg["content"] = None
            
            # Include tool_calls for assistant messages
            if msg.role == "assistant" and msg.tool_calls is not None:
                formatted_msg["tool_calls"] = msg.tool_calls
            
            # Include tool_call_id and name for tool messages
            if msg.role == "tool":
                if msg.tool_call_id:
                    formatted_msg["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    formatted_msg["name"] = msg.name
            
            formatted_messages.append(formatted_msg)

        return formatted_messages

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for available plugins."""
        tools = plugin_registry.list_tools()
        logger.info(
            "Available tools for LLM",
            tool_count=len(tools),
            tool_names=[t.get("function", {}).get("name", "unknown") for t in tools]
        )
        return tools

    async def _execute_tool_calls(
        self,
        session_id: str,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute tool calls and return results with tool_call_id."""
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]
            tool_call_id = tool_call.get("id")

            # Fail loudly if tool_call_id is missing
            if not tool_call_id:
                logger.error(
                    "CRITICAL: tool_call_id missing from tool_call",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_call=tool_call
                )
                raise LLMError(
                    f"tool_call_id is required but missing for tool: {tool_name}"
                )

            try:
                # Parse tool arguments (JSON string to dict)
                tool_args = json.loads(tool_args_str)

                # Execute tool
                start_time = time.time()
                result = await plugin_registry.execute_tool_call(tool_name, tool_args)
                duration_ms = int((time.time() - start_time) * 1000)

                # Publish plugin execution event
                await publish_plugin_execution(
                    plugin_name=tool_name,
                    execution_time_ms=duration_ms,
                    success=True,
                    session_id=session_id
                )

                # Format result for LLM
                result_content = json.dumps(result, indent=2)

                results.append({
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "result": result_content,
                    "success": True
                })

                logger.info(
                    "Plugin executed successfully",
                    session_id=session_id,
                    plugin_name=tool_name,
                    tool_call_id=tool_call_id,
                    duration_ms=duration_ms
                )

            except PluginError as e:
                # Publish failed plugin execution event
                await publish_plugin_execution(
                    plugin_name=tool_name,
                    execution_time_ms=0,
                    success=False,
                    session_id=session_id
                )

                # Return error result to LLM
                error_result = json.dumps({
                    "error": str(e),
                    "plugin_name": tool_name
                }, indent=2)

                results.append({
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "result": error_result,
                    "success": False
                })

                logger.error(
                    "Plugin execution failed",
                    session_id=session_id,
                    plugin_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=str(e)
                )

            except Exception as e:
                # Unexpected error
                await publish_plugin_execution(
                    plugin_name=tool_name,
                    execution_time_ms=0,
                    success=False,
                    session_id=session_id
                )

                error_result = json.dumps({
                    "error": f"Unexpected error in {tool_name}: {str(e)}",
                    "plugin_name": tool_name
                }, indent=2)

                results.append({
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "result": error_result,
                    "success": False
                })

                logger.error(
                    "Unexpected plugin error",
                    session_id=session_id,
                    plugin_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=str(e)
                )

        return results

    async def _manage_conversation_length(
        self, conversation: ConversationState
    ) -> ConversationState:
        """Manage conversation length through truncation or summarization."""
        if len(conversation.messages) <= self.max_conversation_length:
            return conversation

        logger.info(
            "Conversation length management triggered",
            session_id=conversation.session_id,
            current_length=len(conversation.messages),
            max_length=self.max_conversation_length
        )

        if self.enable_summarization:
            try:
                # Initialize context summarizer with LLM provider
                context_summarizer = ContextSummarizer(
                    llm_provider=self.llm_provider,
                    summarization_threshold=0.7,
                    max_summary_length=500,
                    preserve_user_preferences=True,
                    preserve_tool_results=True,
                    preserve_file_context=True
                )

                # Check if summarization should be triggered
                should_summarize = await context_summarizer.should_summarize(
                    conversation
                )

                if should_summarize:
                    # Generate summary and get recent messages to keep
                    summary, recent_messages = await (
                        context_summarizer.summarize_conversation(
                            conversation
                        )
                    )

                    # Convert summary to system message
                    summary_message = summary.to_message()

                    # Create new conversation with summary + recent messages
                    summarized_messages = [summary_message] + recent_messages
                    summarized_conversation = ConversationState(
                        session_id=conversation.session_id,
                        messages=summarized_messages
                    )

                    logger.info(
                        "Conversation summarized",
                        session_id=conversation.session_id,
                        original_length=len(conversation.messages),
                        new_length=len(summarized_conversation.messages),
                        summary_length=len(summary.summary_text)
                    )

                    return summarized_conversation

            except Exception as e:
                # Log summarization failure and fall back to truncation
                logger.error(
                    "Conversation summarization failed, falling back to truncation",
                    session_id=conversation.session_id,
                    error=str(e),
                    error_type=type(e).__name__
                )

        # Fallback to simple truncation
        keep_count = min(self.max_conversation_length, len(conversation.messages))
        recent_messages = conversation.messages[-keep_count:]

        # Create new conversation with truncated history
        truncated_conversation = ConversationState(
            session_id=conversation.session_id,
            messages=recent_messages
        )

        logger.info(
            "Conversation truncated",
            session_id=conversation.session_id,
            original_length=len(conversation.messages),
            new_length=len(truncated_conversation.messages)
        )

        return truncated_conversation

    def get_conversation(self, session_id: str) -> Optional[ConversationState]:
        """Get a conversation by session ID."""
        return self._conversations.get(session_id)

    def list_conversations(self) -> Dict[str, ConversationSummary]:
        """Get summaries of all active conversations."""
        return {
            session_id: ConversationSummary.from_conversation(conv)
            for session_id, conv in self._conversations.items()
        }

    async def end_conversation(self, session_id: str) -> None:
        """End a conversation and clean up resources."""
        if session_id in self._conversations:
            del self._conversations[session_id]
            logger.info("Conversation ended", session_id=session_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        total_messages = sum(len(conv.messages) for conv in self._conversations.values())
        return {
            "active_conversations": len(self._conversations),
            "total_messages": total_messages,
            "max_conversation_length": self.max_conversation_length,
            "sliding_window_size": self.sliding_window_size,
            "summarization_enabled": self.enable_summarization,
        }
