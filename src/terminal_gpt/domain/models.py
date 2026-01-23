"""Core domain models for Terminal GPT."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """A message in a conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        """Ensure content is not empty and reasonably sized."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        if len(v) > 100000:  # 100KB limit
            raise ValueError("Message content too large (>100KB)")
        return v.strip()

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate tool names when present."""
        if v is not None and not v.strip():
            raise ValueError("Name cannot be empty if provided")
        return v.strip() if v else None

    class Config:
        """Pydantic configuration."""
        frozen = True  # Immutable messages


class ConversationState(BaseModel):
    """The state of a conversation session."""

    session_id: str = Field(..., min_length=1, max_length=100)
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        """Ensure session ID is valid."""
        if not v or not v.strip():
            raise ValueError("Session ID cannot be empty")
        # Basic sanitization - only allow alphanumeric, hyphens, underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Session ID contains invalid characters")
        return v.strip()

    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        """Ensure messages are in chronological order and valid."""
        if not v:
            return v

        # Check chronological order
        for i in range(1, len(v)):
            if v[i].timestamp < v[i-1].timestamp:
                raise ValueError("Messages must be in chronological order")

        # Check for reasonable conversation length
        if len(v) > 1000:  # Hard limit to prevent memory issues
            raise ValueError("Conversation too long (>1000 messages)")

        return v

    def add_message(self, message: Message) -> 'ConversationState':
        """Add a message to the conversation (immutable update)."""
        new_messages = self.messages + [message]
        return self.copy(
            update={
                'messages': new_messages,
                'updated_at': datetime.utcnow()
            }
        )

    def get_recent_messages(self, limit: int = 50) -> list[Message]:
        """Get the most recent messages for context."""
        return self.messages[-limit:] if self.messages else []

    def get_message_count(self) -> int:
        """Get the total number of messages."""
        return len(self.messages)

    class Config:
        """Pydantic configuration."""
        validate_assignment = True


class ConversationSummary(BaseModel):
    """A summary of conversation state for context management."""

    session_id: str
    message_count: int
    last_activity: datetime
    total_tokens_estimate: int = Field(default=0)

    @classmethod
    def from_conversation(cls, conversation: ConversationState) -> 'ConversationSummary':
        """Create a summary from a conversation state."""
        # Rough token estimation (4 chars per token average)
        total_chars = sum(len(msg.content) for msg in conversation.messages)
        token_estimate = total_chars // 4

        return cls(
            session_id=conversation.session_id,
            message_count=len(conversation.messages),
            last_activity=conversation.updated_at,
            total_tokens_estimate=token_estimate
        )
