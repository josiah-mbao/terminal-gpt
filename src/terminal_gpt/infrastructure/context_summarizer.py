"""Context summarization for Terminal GPT.

This module provides intelligent conversation summarization to preserve
essential context while managing token usage in long conversations.
"""

import json
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime

from ..domain.models import Message, ConversationState
from ..infrastructure.logging import get_logger
from ..infrastructure.llm_providers import LLMProvider

logger = get_logger("terminal_gpt.context_summarizer")


class ContextSummary:
    """Represents a summarized context entry."""

    def __init__(
        self,
        summary_text: str,
        preserved_context: Dict[str, Any],
        timestamp: datetime,
        original_message_count: int
    ):
        self.summary_text = summary_text
        self.preserved_context = preserved_context
        self.timestamp = timestamp
        self.original_message_count = original_message_count

    def to_message(self) -> Message:
        """Convert summary to a system message."""
        content = (
            f"Conversation Summary ({self.timestamp.strftime('%H:%M:%S')}):\n\n"
        )
        content += f"{self.summary_text}\n\n"
        content += "Preserved Context:\n"
        content += json.dumps(self.preserved_context, indent=2)

        return Message(
            role="system",
            content=content
        )


class ContextSummarizer:
    """Intelligent context summarization for long conversations."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        summarization_threshold: float = 0.7,
        max_summary_length: int = 500,
        preserve_user_preferences: bool = True,
        preserve_tool_results: bool = True,
        preserve_file_context: bool = True
    ):
        """
        Initialize context summarizer.

        Args:
            llm_provider: LLM provider for generating summaries
            summarization_threshold: When to trigger summarization (0.0-1.0)
            max_summary_length: Maximum length of summary in characters
            preserve_user_preferences: Whether to preserve user preferences
            preserve_tool_results: Whether to preserve tool execution results
            preserve_file_context: Whether to preserve file operation context
        """
        self.llm_provider = llm_provider
        self.summarization_threshold = summarization_threshold
        self.max_summary_length = max_summary_length
        self.preserve_user_preferences = preserve_user_preferences
        self.preserve_tool_results = preserve_tool_results
        self.preserve_file_context = preserve_file_context

    async def should_summarize(self, conversation: ConversationState) -> bool:
        """
        Determine if conversation should be summarized.

        Args:
            conversation: Current conversation state

        Returns:
            True if summarization should be triggered
        """
        total_messages = len(conversation.messages)
        if total_messages < 20:  # Don't summarize very short conversations
            return False

        # Check if we're approaching the max conversation length
        max_length = 100  # From orchestrator config
        current_ratio = total_messages / max_length

        should_summarize = current_ratio >= self.summarization_threshold

        if should_summarize:
            logger.info(
                "Summarization triggered",
                session_id=conversation.session_id,
                current_messages=total_messages,
                threshold_ratio=current_ratio,
                threshold=self.summarization_threshold
            )

        return should_summarize

    async def summarize_conversation(
        self,
        conversation: ConversationState
    ) -> Tuple[ContextSummary, List[Message]]:
        """
        Generate intelligent summary of conversation.

        Args:
            conversation: Conversation to summarize

        Returns:
            Tuple of (summary object, messages to keep)
        """
        logger.info(
            "Starting conversation summarization",
            session_id=conversation.session_id,
            total_messages=len(conversation.messages)
        )

        # Extract different types of context
        user_preferences = self._extract_user_preferences(conversation.messages)
        tool_results = self._extract_tool_results(conversation.messages)
        file_context = self._extract_file_context(conversation.messages)
        technical_context = self._extract_technical_context(conversation.messages)

        # Create preserved context dictionary
        preserved_context = {
            "user_preferences": user_preferences,
            "tool_results": tool_results,
            "file_context": file_context,
            "technical_context": technical_context
        }

        # Generate summary text using LLM
        summary_text = await self._generate_summary_text(
            conversation.messages,
            preserved_context
        )

        # Create summary object
        summary = ContextSummary(
            summary_text=summary_text,
            preserved_context=preserved_context,
            timestamp=datetime.utcnow(),
            original_message_count=len(conversation.messages)
        )

        # Determine which recent messages to keep
        recent_messages = self._select_recent_messages(conversation.messages)

        logger.info(
            "Conversation summarization completed",
            session_id=conversation.session_id,
            summary_length=len(summary_text),
            preserved_context_size=len(json.dumps(preserved_context)),
            messages_kept=len(recent_messages)
        )

        return summary, recent_messages

    def _extract_user_preferences(self, messages: List[Message]) -> Dict[str, Any]:
        """Extract user preferences and important information."""
        if not self.preserve_user_preferences:
            return {}

        preferences = {
            "coding_languages": [],
            "project_types": [],
            "study_topics": [],
            "sports_interests": [],
            "system_info": {},
            "preferences": []
        }

        for message in messages:
            if message.role == "user":
                content = message.content.lower()

                # Extract coding languages
                lang_patterns = [
                    r'\b(python|javascript|java|rust|go|c\+\+|c#|typescript)\b',
                    r'\b(aws|azure|gcp|kubernetes|docker)\b'
                ]

                for pattern in lang_patterns:
                    matches = re.findall(pattern, content)
                    preferences["coding_languages"].extend(matches)

                # Extract study topics
                if any(topic in content for topic in ['aws', 'cka', 'certification', 'study']):
                    preferences["study_topics"].append(content[:100])

                # Extract sports interests
                if any(sport in content for sport in ['epl', 'nba', 'football', 'basketball']):
                    preferences["sports_interests"].append(content[:100])

                # Extract system information
                if any(info in content for info in ['macbook', 'm1', 'slow', 'performance']):
                    preferences["system_info"]["performance_issues"] = True

        # Remove duplicates and clean up
        preferences["coding_languages"] = list(set(preferences["coding_languages"]))
        preferences["study_topics"] = list(set(preferences["study_topics"]))
        preferences["sports_interests"] = list(set(preferences["sports_interests"]))

        return preferences

    def _extract_tool_results(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Extract important tool execution results."""
        if not self.preserve_tool_results:
            return []

        tool_results = []

        for i, message in enumerate(messages):
            if message.role == "tool":
                # Extract key information from tool results
                result_info = {
                    "tool_name": message.name,
                    "content_preview": message.content[:200],
                    "timestamp": message.timestamp.isoformat(),
                    "is_important": self._is_tool_result_important(message)
                }

                if result_info["is_important"]:
                    tool_results.append(result_info)

        return tool_results

    def _extract_file_context(self, messages: List[Message]) -> Dict[str, Any]:
        """Extract file operation context."""
        if not self.preserve_file_context:
            return {}

        file_context = {
            "recent_files": [],
            "file_operations": [],
            "important_paths": []
        }

        for message in messages:
            if message.role in ["user", "assistant"]:
                content = message.content

                # Extract file paths
                path_patterns = [
                    r'([/\w\-\.]+\.(py|js|ts|java|rust|go|json|md))',
                    r'(/Users/[^/\s]+/[\w/\-]+)',
                    r'(src/[\w/\-]+\.\w+)'
                ]

                for pattern in path_patterns:
                    matches = re.findall(pattern, content)
                    file_context["important_paths"].extend(matches)

                # Extract file operations
                if any(op in content.lower() for op in ['read file', 'write file', 'list directory']):
                    file_context["file_operations"].append({
                        "operation": content[:100],
                        "timestamp": message.timestamp.isoformat()
                    })

        file_context["important_paths"] = list(set(file_context["important_paths"]))
        return file_context

    def _extract_technical_context(self, messages: List[Message]) -> Dict[str, Any]:
        """Extract technical context and problem-solving threads."""
        technical_context = {
            "current_problems": [],
            "solutions_attempted": [],
            "code_snippets": [],
            "error_messages": []
        }

        for message in messages[-20:]:  # Focus on recent messages
            content = message.content

            # Extract error messages
            error_patterns = [
                r'Error:\s*(.+)',
                r'Exception:\s*(.+)',
                r'Failed:\s*(.+)',
                r'Cannot\s*(.+)'
            ]

            for pattern in error_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                technical_context["error_messages"].extend(matches)

            # Extract code snippets (simplified)
            if '```' in content:
                technical_context["code_snippets"].append(content[:300])

            # Extract problem descriptions
            if any(keyword in content.lower() for keyword in ['debug', 'issue', 'problem', 'help']):
                technical_context["current_problems"].append(content[:150])

        return technical_context

    def _is_tool_result_important(self, message: Message) -> bool:
        """Determine if a tool result is important enough to preserve."""
        content = message.content.lower()

        # Important tool results typically contain:
        # - File contents (especially code)
        # - Calculation results
        # - Sports scores/stats
        # - Directory listings

        important_indicators = [
            'content:', 'result:', 'score:', 'stat:', 'path:', 'file:',
            'calculation:', 'directory:', 'list:', 'read_file', 'write_file'
        ]

        return any(indicator in content for indicator in important_indicators)

    def _select_recent_messages(self, messages: List[Message]) -> List[Message]:
        """
        Select recent messages to keep after summarization.

        Keeps:
        - Last 10 user messages
        - Last 5 assistant messages
        - All tool messages from last 15 messages
        """
        recent_messages = []

        # Get last 15 messages
        recent_window = messages[-15:] if len(messages) >= 15 else messages

        user_messages = []
        assistant_messages = []
        tool_messages = []

        for message in recent_window:
            if message.role == "user":
                user_messages.append(message)
            elif message.role == "assistant":
                assistant_messages.append(message)
            elif message.role == "tool":
                tool_messages.append(message)

        # Keep last 10 user messages
        recent_messages.extend(user_messages[-10:])

        # Keep last 5 assistant messages
        recent_messages.extend(assistant_messages[-5:])

        # Keep all tool messages from recent window
        recent_messages.extend(tool_messages)

        # Sort by timestamp to maintain order
        recent_messages.sort(key=lambda m: m.timestamp)

        return recent_messages

    async def _generate_summary_text(
        self,
        messages: List[Message],
        preserved_context: Dict[str, Any]
    ) -> str:
        """
        Generate summary text using LLM.

        Args:
            messages: Messages to summarize
            preserved_context: Extracted context information

        Returns:
            Generated summary text
        """
        # Create a concise summary of the conversation
        conversation_preview = []
        for message in messages[-10:]:  # Last 10 messages
            role = message.role.upper()
            content_preview = message.content[:100]
            conversation_preview.append(f"{role}: {content_preview}...")

        preview_text = "\n".join(conversation_preview)

        # Create prompt for LLM
        prompt = f"""
Please create a concise summary of this conversation for context preservation.

Conversation Preview (Last 10 Messages):
{preview_text}

Preserved Context:
{json.dumps(preserved_context, indent=2)}

Please create a summary that:
1. Captures the main topics discussed
2. Preserves important user preferences and context
3. Is concise (under {self.max_summary_length} characters)
4. Maintains conversation continuity

Summary:
"""

        try:
            async with self.llm_provider:
                response = await self.llm_provider.generate(
                    messages=[{"role": "user", "content": prompt}],
                    config={"temperature": 0.3, "max_tokens": 200}
                )

            summary = response.content.strip()

            # Truncate if too long
            if len(summary) > self.max_summary_length:
                summary = summary[:self.max_summary_length].strip() + "..."

            return summary

        except Exception as e:
            logger.error(
                "Failed to generate LLM summary, using fallback",
                error=str(e)
            )
            return self._generate_fallback_summary(messages, preserved_context)

    def _generate_fallback_summary(
        self,
        messages: List[Message],
        preserved_context: Dict[str, Any]
    ) -> str:
        """Generate fallback summary without LLM."""
        summary_parts = []

        # Add user preferences
        if preserved_context.get("user_preferences", {}).get("coding_languages"):
            langs = ", ".join(
                preserved_context["user_preferences"]["coding_languages"]
            )
            summary_parts.append(f"User interested in: {langs}")

        # Add recent activity
        if messages:
            last_user_msg = next(
                (m for m in reversed(messages) if m.role == "user"), None
            )
            if last_user_msg:
                summary_parts.append(f"Recent topic: {last_user_msg.content[:50]}...")

        # Add technical context
        if preserved_context.get("technical_context", {}).get("current_problems"):
            problems = preserved_context["technical_context"]["current_problems"][-1:]
            if problems:
                summary_parts.append(f"Current issue: {problems[0][:50]}...")

        summary = " | ".join(summary_parts)
        return summary if summary else "Conversation summary generated from preserved context."