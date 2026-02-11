"""Unit tests for domain models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from terminal_gpt.domain.models import Message, ConversationState, ConversationSummary


class TestMessage:
    """Test Message model validation and immutability."""

    def test_valid_message_creation(self):
        """Test creating a valid message."""
        msg = Message(role="user", content="Hello world")

        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.name is None
        assert isinstance(msg.timestamp, datetime)
        assert msg.model_config.get("frozen") is True

    def test_message_immutability(self):
        """Test that messages are immutable."""
        msg = Message(role="user", content="Hello")

        with pytest.raises((TypeError, ValidationError)):
            msg.content = "Modified"

    def test_empty_content_validation(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            Message(role="user", content="")

        with pytest.raises(ValidationError):
            Message(role="user", content="   ")

    def test_content_too_large(self):
        """Test that overly large content is rejected."""
        large_content = "x" * 100001  # 100KB + 1
        with pytest.raises(ValidationError):
            Message(role="user", content=large_content)

    def test_invalid_role(self):
        """Test that invalid roles are rejected."""
        with pytest.raises(ValidationError):
            Message(role="invalid", content="Hello")

    def test_tool_message_with_name(self):
        """Test tool messages can have names."""
        msg = Message(role="tool", content="Result", name="calculator")
        assert msg.name == "calculator"

    def test_empty_name_validation(self):
        """Test that empty names are rejected when provided."""
        with pytest.raises(ValidationError):
            Message(role="tool", content="Result", name="")

        with pytest.raises(ValidationError):
            Message(role="tool", content="Result", name="   ")


class TestConversationState:
    """Test ConversationState model and conversation management."""

    def test_valid_conversation_creation(self):
        """Test creating a valid conversation state."""
        conv = ConversationState(session_id="test-session-123")

        assert conv.session_id == "test-session-123"
        assert conv.messages == []
        assert isinstance(conv.created_at, datetime)
        assert isinstance(conv.updated_at, datetime)

    def test_invalid_session_id(self):
        """Test that invalid session IDs are rejected."""
        with pytest.raises(ValidationError):
            ConversationState(session_id="")

        with pytest.raises(ValidationError):
            ConversationState(session_id="invalid@session!")

    def test_session_id_length_limits(self):
        """Test session ID length constraints."""
        # Should work
        ConversationState(session_id="a" * 100)

        # Should fail - too long
        with pytest.raises(ValidationError):
            ConversationState(session_id="a" * 101)

    def test_conversation_immutability(self):
        """Test that conversations are updated immutably."""
        conv1 = ConversationState(session_id="test")
        msg = Message(role="user", content="Hello")

        conv2 = conv1.add_message(msg)

        # Original should be unchanged
        assert len(conv1.messages) == 0
        assert len(conv2.messages) == 1
        assert conv2.messages[0] == msg

        # Timestamps should be updated
        assert conv2.updated_at >= conv2.created_at

    def test_message_chronological_order(self):
        """Test that messages must be in chronological order."""
        past_time = datetime(2023, 1, 1)
        future_time = datetime(2023, 1, 2)

        msg1 = Message(role="user", content="First", timestamp=future_time)
        msg2 = Message(role="assistant", content="Second", timestamp=past_time)

        # This should fail validation
        with pytest.raises(ValidationError):
            ConversationState(session_id="test", messages=[msg1, msg2])

    def test_conversation_size_limits(self):
        """Test conversation size limits."""
        messages = [
            Message(role="user", content=f"Message {i}")
            for i in range(1001)  # Over limit
        ]

        with pytest.raises(ValidationError):
            ConversationState(session_id="test", messages=messages)

    def test_conversation_methods(self):
        """Test conversation utility methods."""
        conv = ConversationState(session_id="test")

        # Empty conversation
        assert conv.get_message_count() == 0
        assert conv.get_recent_messages() == []
        assert conv.get_recent_messages(5) == []

        # Add messages
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="User message 1"),
            Message(role="assistant", content="Assistant response 1"),
            Message(role="user", content="User message 2"),
            Message(role="assistant", content="Assistant response 2"),
        ]

        for msg in messages:
            conv = conv.add_message(msg)

        assert conv.get_message_count() == 5

        # Test recent messages
        recent = conv.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0].content == "Assistant response 1"
        assert recent[1].content == "User message 2"
        assert recent[2].content == "Assistant response 2"

    def test_conversation_summary(self):
        """Test conversation summary creation."""
        conv = ConversationState(session_id="test-session")

        messages = [
            Message(role="user", content="Hello world"),  # 11 chars
            Message(role="assistant", content="Hi there!"),  # 9 chars
        ]

        for msg in messages:
            conv = conv.add_message(msg)

        summary = ConversationSummary.from_conversation(conv)

        assert summary.session_id == "test-session"
        assert summary.message_count == 2
        assert summary.last_activity == conv.updated_at
        # Rough token estimation: (11 + 9) / 4 ≈ 5
        assert summary.total_tokens_estimate >= 4


class TestConversationSummary:
    """Test ConversationSummary model."""

    def test_summary_creation(self):
        """Test creating a conversation summary."""
        summary = ConversationSummary(
            session_id="test",
            message_count=5,
            last_activity=datetime.utcnow(),
            total_tokens_estimate=150,
        )

        assert summary.session_id == "test"
        assert summary.message_count == 5
        assert summary.total_tokens_estimate == 150

    def test_from_conversation_empty(self):
        """Test summary from empty conversation."""
        conv = ConversationState(session_id="empty")
        summary = ConversationSummary.from_conversation(conv)

        assert summary.message_count == 0
        assert summary.total_tokens_estimate == 0
