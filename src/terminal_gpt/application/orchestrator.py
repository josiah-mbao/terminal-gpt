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

logger = get_logger("terminal_gpt.orchestrator")


class ConversationOrchestrator:
    """Orchestrates intelligent conversations between users, LLMs, and plugins."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_conversation_length: int = 100,
        sliding_window_size: int = 50,
        enable_summarization: bool = False
    ):
        """
        Initialize the conversation orchestrator.

        Args:
            llm_provider: LLM provider for generating responses
            max_conversation_length: Maximum messages in conversation
            sliding_window_size: Size of context window for LLM
            enable_summarization: Whether to enable conversation summarization
        """
        self.llm_provider = llm_provider
        self.max_conversation_length = max_conversation_length
        self.sliding_window_size = sliding_window_size
        self.enable_summarization = enable_summarization

        # Active conversations (in production, this would be persistent storage)
        self._conversations: Dict[str, ConversationState] = {}

    async def start_conversation(self, session_id: str) -> ConversationState:
        """Start a new conversation session."""
        if session_id in self._conversations:
            raise ValidationError(f"Conversation {session_id} already exists")

        conversation = ConversationState(session_id=session_id)
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
                llm_response = await self.llm_provider.generate(
                    messages=messages,
                    tools=tools,
                    config={"temperature": 0.7, "max_tokens": 4096}
                )
                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "LLM response generated",
                    session_id=conversation.session_id,
                    duration_ms=duration_ms,
                    tokens_used=llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0
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
                    iteration=current_iteration
                )
                # For now, return a helpful error message
                # In production, you might want different strategies
                return f"I apologize, but I'm having trouble generating a response right now. Please try again."

        # Max iterations reached
        logger.warning(
            "Max iterations reached in conversation",
            session_id=conversation.session_id,
            max_iterations=max_iterations
        )
        return "I'm sorry, but this conversation has become too complex. Please start a new conversation."

    def _prepare_context_messages(self, conversation: ConversationState) -> List[Dict[str, Any]]:
        """Prepare messages for LLM context, managing sliding window."""
        all_messages = conversation.messages

        # If conversation is within sliding window, use all messages
        if len(all_messages) <= self.sliding_window_size:
            return [
                {"role": msg.role, "content": msg.content}
                for msg in all_messages
            ]

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
        final_messages = context_messages + recent_messages

        logger.info(
            "Using sliding window context",
            session_id=conversation.session_id,
            total_messages=len(all_messages),
            context_messages=len(final_messages)
        )

        return [
            {"role": msg.role, "content": msg.content}
            for msg in final_messages
        ]

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for available plugins."""
        return plugin_registry.list_tools()

    async def _execute_tool_calls(
        self,
        session_id: str,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]

            try:
                # Parse tool arguments
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
                    "result": result_content,
                    "success": True
                })

                logger.info(
                    "Plugin executed successfully",
                    session_id=session_id,
                    plugin_name=tool_name,
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
                    "result": error_result,
                    "success": False
                })

                logger.error(
                    "Plugin execution failed",
                    session_id=session_id,
                    plugin_name=tool_name,
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
                    "result": error_result,
                    "success": False
                })

                logger.error(
                    "Unexpected plugin error",
                    session_id=session_id,
                    plugin_name=tool_name,
                    error=str(e)
                )

        return results

    async def _manage_conversation_length(self, conversation: ConversationState) -> ConversationState:
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
            # Future: Implement summarization
            # For now, just truncate
            pass

        # Simple truncation: keep recent messages
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
