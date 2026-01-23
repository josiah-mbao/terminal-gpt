"""Unit tests for conversation orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from terminal_gpt.application.orchestrator import ConversationOrchestrator
from terminal_gpt.infrastructure.llm_providers import LLMResponse, OpenRouterProvider
from terminal_gpt.domain.models import ConversationState, Message
from terminal_gpt.domain.exceptions import ValidationError, LLMError, PluginError
from terminal_gpt.domain.plugins import plugin_registry


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider for testing."""
    provider = MagicMock(spec=OpenRouterProvider)

    # Mock the async context manager
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=None)

    # Mock the generate method
    provider.generate = AsyncMock()

    return provider


@pytest.fixture
def orchestrator(mock_llm_provider):
    """Create an orchestrator instance for testing."""
    return ConversationOrchestrator(
        llm_provider=mock_llm_provider,
        max_conversation_length=10,
        sliding_window_size=5
    )


class TestConversationOrchestrator:
    """Test conversation orchestrator functionality."""

    def test_initialization(self, mock_llm_provider):
        """Test orchestrator initialization."""
        orch = ConversationOrchestrator(
            llm_provider=mock_llm_provider,
            max_conversation_length=50,
            sliding_window_size=20,
            enable_summarization=True
        )

        assert orch.llm_provider == mock_llm_provider
        assert orch.max_conversation_length == 50
        assert orch.sliding_window_size == 20
        assert orch.enable_summarization is True
        assert orch._conversations == {}

    @pytest.mark.asyncio
    async def test_start_conversation(self, orchestrator):
        """Test starting a new conversation."""
        session_id = "test-session"
        conversation = await orchestrator.start_conversation(session_id)

        assert isinstance(conversation, ConversationState)
        assert conversation.session_id == session_id
        assert len(conversation.messages) == 0
        assert session_id in orchestrator._conversations

    @pytest.mark.asyncio
    async def test_start_conversation_duplicate(self, orchestrator):
        """Test starting a conversation that already exists."""
        session_id = "test-session"
        await orchestrator.start_conversation(session_id)

        with pytest.raises(ValidationError):
            await orchestrator.start_conversation(session_id)

    @pytest.mark.asyncio
    async def test_process_user_message_new_conversation(self, orchestrator, mock_llm_provider):
        """Test processing user message in new conversation."""
        # Mock LLM response
        mock_response = LLMResponse(
            content="Hello! How can I help you?",
            model="gpt-3.5-turbo",
            usage={"total_tokens": 20}
        )
        mock_llm_provider.generate.return_value = mock_response

        session_id = "test-session"
        user_message = "Hello"

        response = await orchestrator.process_user_message(session_id, user_message)

        assert response == "Hello! How can I help you?"
        assert session_id in orchestrator._conversations

        conversation = orchestrator._conversations[session_id]
        assert len(conversation.messages) == 2  # user + assistant

        # Check message order and content
        assert conversation.messages[0].role == "user"
        assert conversation.messages[0].content == user_message
        assert conversation.messages[1].role == "assistant"
        assert conversation.messages[1].content == response

    @pytest.mark.asyncio
    async def test_process_user_message_with_tools(self, orchestrator, mock_llm_provider):
        """Test processing message that triggers tool usage."""
        # Mock tool call response
        tool_call_response = LLMResponse(
            content="",
            model="gpt-3.5-turbo",
            usage={"total_tokens": 50},
            tool_calls=[{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "calculator",
                    "arguments": '{"expression": "2 + 2"}'
                }
            }]
        )

        # Mock final response after tool execution
        final_response = LLMResponse(
            content="2 + 2 equals 4",
            model="gpt-3.5-turbo",
            usage={"total_tokens": 70}
        )

        # Configure mock to return tool call first, then final response
        mock_llm_provider.generate.side_effect = [tool_call_response, final_response]

        # Mock plugin execution
        with patch.object(plugin_registry, 'execute_tool_call') as mock_execute:
            mock_execute.return_value = {"result": 4, "expression": "2 + 2"}

            session_id = "test-session"
            response = await orchestrator.process_user_message(
                session_id, "What is 2 + 2?"
            )

            assert response == "2 + 2 equals 4"

            # Verify tool was executed
            mock_execute.assert_called_once_with("calculator", {"expression": "2 + 2"})

            # Check conversation has tool message
            conversation = orchestrator._conversations[session_id]
            tool_messages = [msg for msg in conversation.messages if msg.role == "tool"]
            assert len(tool_messages) == 1

    @pytest.mark.asyncio
    async def test_process_user_message_llm_error(self, orchestrator, mock_llm_provider):
        """Test handling LLM errors gracefully."""
        mock_llm_provider.generate.side_effect = LLMError("Service unavailable")

        session_id = "test-session"
        response = await orchestrator.process_user_message(session_id, "Hello")

        assert "apologize" in response.lower()
        assert "trouble" in response.lower()

    def test_prepare_context_messages_within_window(self, orchestrator):
        """Test context preparation within sliding window."""
        conversation = ConversationState(session_id="test")

        # Add messages within window size
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]

        for msg in messages:
            conversation = conversation.add_message(msg)

        context = orchestrator._prepare_context_messages(conversation)

        assert len(context) == 3
        assert context[0]["role"] == "system"
        assert context[1]["role"] == "user"
        assert context[2]["role"] == "assistant"

    def test_prepare_context_messages_sliding_window(self, orchestrator):
        """Test context preparation with sliding window."""
        conversation = ConversationState(session_id="test")

        # Add more messages than window size (5)
        for i in range(8):
            msg = Message(role="user", content=f"Message {i}")
            conversation = conversation.add_message(msg)

        context = orchestrator._prepare_context_messages(conversation)

        # Should only have last 5 messages (sliding window)
        assert len(context) == 5
        assert context[0]["content"] == "Message 3"
        assert context[4]["content"] == "Message 7"

    def test_prepare_context_preserves_system_messages(self, orchestrator):
        """Test that system messages are preserved in sliding window."""
        conversation = ConversationState(session_id="test")

        # Add system message first
        sys_msg = Message(role="system", content="You are helpful")
        conversation = conversation.add_message(sys_msg)

        # Add many user messages
        for i in range(10):
            msg = Message(role="user", content=f"Message {i}")
            conversation = conversation.add_message(msg)

        context = orchestrator._prepare_context_messages(conversation)

        # Should include system message + last 5 user messages
        assert len(context) == 6
        assert context[0]["role"] == "system"
        assert context[0]["content"] == "You are helpful"
        assert all(msg["role"] == "user" for msg in context[1:])

    def test_get_available_tools(self, orchestrator):
        """Test getting available tools."""
        with patch.object(plugin_registry, 'list_tools') as mock_list:
            mock_list.return_value = [{"name": "test_tool"}]
            tools = orchestrator._get_available_tools()
            assert tools == [{"name": "test_tool"}]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_success(self, orchestrator):
        """Test successful tool execution."""
        tool_calls = [{
            "function": {
                "name": "calculator",
                "arguments": '{"expression": "1 + 1"}'
            }
        }]

        with patch.object(plugin_registry, 'execute_tool_call') as mock_execute:
            mock_execute.return_value = {"result": 2}

            results = await orchestrator._execute_tool_calls("session-123", tool_calls)

            assert len(results) == 1
            assert results[0]["tool_name"] == "calculator"
            assert results[0]["success"] is True
            assert "2" in results[0]["result"]

    @pytest.mark.asyncio
    async def test_execute_tool_calls_plugin_error(self, orchestrator):
        """Test tool execution with plugin error."""
        tool_calls = [{
            "function": {
                "name": "calculator",
                "arguments": '{"expression": "invalid"}'
            }
        }]

        with patch.object(plugin_registry, 'execute_tool_call') as mock_execute:
            mock_execute.side_effect = PluginError("Invalid expression")

            results = await orchestrator._execute_tool_calls("session-123", tool_calls)

            assert len(results) == 1
            assert results[0]["success"] is False
            assert "error" in results[0]["result"].lower()

    @pytest.mark.asyncio
    async def test_manage_conversation_length_no_action(self, orchestrator):
        """Test conversation length management when under limit."""
        conversation = ConversationState(session_id="test")

        # Add messages under limit
        for i in range(5):
            msg = Message(role="user", content=f"Message {i}")
            conversation = conversation.add_message(msg)

        result = await orchestrator._manage_conversation_length(conversation)

        assert result == conversation
        assert len(result.messages) == 5

    @pytest.mark.asyncio
    async def test_manage_conversation_length_truncation(self, orchestrator):
        """Test conversation length management with truncation."""
        conversation = ConversationState(session_id="test")

        # Add messages over limit (10)
        for i in range(15):
            msg = Message(role="user", content=f"Message {i}")
            conversation = conversation.add_message(msg)

        result = await orchestrator._manage_conversation_length(conversation)

        # Should keep only the last 10 messages
        assert len(result.messages) == 10
        assert result.messages[0].content == "Message 5"
        assert result.messages[9].content == "Message 14"

    def test_get_conversation(self, orchestrator):
        """Test getting a conversation by ID."""
        # Non-existent conversation
        assert orchestrator.get_conversation("nonexistent") is None

        # Create conversation manually for testing
        conv = ConversationState(session_id="test")
        orchestrator._conversations["test"] = conv

        retrieved = orchestrator.get_conversation("test")
        assert retrieved == conv

    def test_list_conversations(self, orchestrator):
        """Test listing conversation summaries."""
        # Create test conversations
        conv1 = ConversationState(session_id="session1")
        conv1 = conv1.add_message(Message(role="user", content="Hi"))

        conv2 = ConversationState(session_id="session2")
        conv2 = conv2.add_message(Message(role="user", content="Hello"))
        conv2 = conv2.add_message(Message(role="assistant", content="Hi there"))

        orchestrator._conversations = {
            "session1": conv1,
            "session2": conv2
        }

        summaries = orchestrator.list_conversations()

        assert len(summaries) == 2
        assert summaries["session1"].message_count == 1
        assert summaries["session2"].message_count == 2

    @pytest.mark.asyncio
    async def test_end_conversation(self, orchestrator):
        """Test ending a conversation."""
        # Create conversation
        await orchestrator.start_conversation("test-session")
        assert "test-session" in orchestrator._conversations

        await orchestrator.end_conversation("test-session")
        assert "test-session" not in orchestrator._conversations

    def test_get_stats(self, orchestrator):
        """Test getting orchestrator statistics."""
        # Create test conversations
        conv1 = ConversationState(session_id="s1")
        conv1 = conv1.add_message(Message(role="user", content="Hi"))

        conv2 = ConversationState(session_id="s2")
        for i in range(3):
            conv2 = conv2.add_message(Message(role="user", content=f"Msg {i}"))

        orchestrator._conversations = {"s1": conv1, "s2": conv2}

        stats = orchestrator.get_stats()

        assert stats["active_conversations"] == 2
        assert stats["total_messages"] == 4  # 1 + 3
        assert stats["max_conversation_length"] == 10
        assert stats["sliding_window_size"] == 5
        assert stats["summarization_enabled"] is False

    @pytest.mark.asyncio
    async def test_max_iterations_prevention(self, orchestrator, mock_llm_provider):
        """Test prevention of infinite loops with max iterations."""
        # Always return tool calls (would cause infinite loop without limit)
        tool_call_response = LLMResponse(
            content="",
            model="gpt-3.5-turbo",
            usage={"total_tokens": 50},
            tool_calls=[{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "calculator",
                    "arguments": '{"expression": "1 + 1"}'
                }
            }]
        )

        mock_llm_provider.generate.return_value = tool_call_response

        # Mock successful tool execution
        with patch.object(plugin_registry, 'execute_tool_call') as mock_execute:
            mock_execute.return_value = {"result": 2}

            session_id = "test-session"
            response = await orchestrator.process_user_message(session_id, "Calculate")

            # Should return max iterations message
            assert "too complex" in response.lower()

    @pytest.mark.asyncio
    async def test_error_event_publishing(self, orchestrator, mock_llm_provider):
        """Test that errors are properly published as events."""
        mock_llm_provider.generate.side_effect = Exception("Unexpected error")

        session_id = "test-session"

        with patch('terminal_gpt.application.orchestrator.publish_conversation_error') as mock_publish:
            try:
                await orchestrator.process_user_message(session_id, "Hello")
            except:
                pass  # Expected to raise

            # Should have published error event
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert call_args[1]["session_id"] == session_id
            assert "Exception" in call_args[1]["error_type"]
