"""Event-driven communication system for Terminal GPT.

This module provides an async event system for decoupled component communication.
Events are used for cross-cutting concerns like logging, monitoring, and component
coordination without tight coupling.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Type, TypeVar, Generic
from enum import Enum


class EventPriority(Enum):
    """Priority levels for event processing."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventCategory(Enum):
    """Categories for organizing events."""

    SYSTEM = "system"
    USER = "user"
    PLUGIN = "plugin"
    LLM = "llm"
    API = "api"
    CONVERSATION = "conversation"


@dataclass(frozen=True)
class Event:
    """Base event class.

    All events should inherit from this class and add their specific data.
    """

    event_id: str
    category: EventCategory
    priority: EventPriority
    timestamp: datetime
    source: str  # Component that generated the event
    data: Dict[str, Any]

    def __post_init__(self):
        """Validate event data."""
        if not self.event_id:
            raise ValueError("Event ID cannot be empty")
        if not self.source:
            raise ValueError("Event source cannot be empty")


# Specific event types
@dataclass(frozen=True)
class UserMessageReceived(Event):
    """Event fired when a user message is received."""

    session_id: str
    message_content: str


@dataclass(frozen=True)
class AssistantMessageGenerated(Event):
    """Event fired when an assistant response is generated."""

    session_id: str
    response_content: str
    tokens_used: Optional[int] = None


@dataclass(frozen=True)
class PluginExecuted(Event):
    """Event fired when a plugin is executed."""

    plugin_name: str
    execution_time_ms: float
    success: bool
    session_id: Optional[str] = None


@dataclass(frozen=True)
class LLMCallCompleted(Event):
    """Event fired when an LLM API call completes."""

    provider: str
    model: str
    tokens_used: int
    success: bool
    duration_ms: float


@dataclass(frozen=True)
class ConversationErrorOccurred(Event):
    """Event fired when a conversation error occurs."""

    session_id: str
    error_type: str
    error_message: str


@dataclass(frozen=True)
class SystemHealthCheck(Event):
    """Event fired during system health checks."""

    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    metrics: Dict[str, Any]


EventType = TypeVar("EventType", bound=Event)


class EventHandler(Generic[EventType], ABC):
    """Abstract base class for event handlers."""

    @abstractmethod
    async def handle(self, event: EventType) -> None:
        """Handle an event asynchronously."""
        pass

    @property
    @abstractmethod
    def event_type(self) -> Type[EventType]:
        """Return the type of event this handler processes."""
        pass


class EventBus:
    """Central event bus for publishing and subscribing to events."""

    def __init__(self):
        self._handlers: Dict[Type[Event], List[EventHandler]] = {}
        self._middleware: List[Callable[[Event], None]] = []
        self._running = False
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the event processing loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_events())
        await self.publish(
            SystemHealthCheck(
                event_id=f"system-start-{datetime.utcnow().isoformat()}",
                category=EventCategory.SYSTEM,
                priority=EventPriority.NORMAL,
                timestamp=datetime.utcnow(),
                source="event_bus",
                data={"status": "started"},
                component="event_bus",
                status="healthy",
                metrics={"handlers_registered": len(self._handlers)},
            )
        )

    async def stop(self) -> None:
        """Stop the event processing loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def register_handler(self, handler: EventHandler) -> None:
        """Register an event handler."""
        event_type = handler.event_type
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unregister_handler(self, handler: EventHandler) -> None:
        """Unregister an event handler."""
        event_type = handler.event_type
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            if not self._handlers[event_type]:
                del self._handlers[event_type]

    def add_middleware(self, middleware: Callable[[Event], None]) -> None:
        """Add middleware that runs on all events."""
        self._middleware.append(middleware)

    async def publish(self, event: Event) -> None:
        """Publish an event to all registered handlers."""
        if not self._running:
            # If not running, process synchronously for startup/shutdown events
            await self._process_event(event)
            return

        await self._queue.put(event)

    async def _process_events(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await self._queue.get()
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log event processing errors (would use proper logging in real impl)
                print(f"Error processing event: {e}")

    async def _process_event(self, event: Event) -> None:
        """Process a single event through middleware and handlers."""
        # Apply middleware
        for middleware in self._middleware:
            try:
                middleware(event)
            except Exception as e:
                print(f"Middleware error: {e}")

        # Find and call handlers
        event_type = type(event)
        if event_type in self._handlers:
            handlers = self._handlers[event_type]
            # Process handlers concurrently
            tasks = [
                handler.handle(event)
                for handler in handlers
                if isinstance(event, handler.event_type)
            ]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)


# Global event bus instance
event_bus = EventBus()


# Convenience functions for common event publishing
async def publish_user_message(session_id: str, content: str) -> None:
    """Publish a user message received event."""
    await event_bus.publish(
        UserMessageReceived(
            event_id=f"user-msg-{session_id}-{datetime.utcnow().isoformat()}",
            category=EventCategory.USER,
            priority=EventPriority.NORMAL,
            timestamp=datetime.utcnow(),
            source="conversation_manager",
            data={"session_id": session_id, "content_length": len(content)},
            session_id=session_id,
            message_content=content,
        )
    )


async def publish_assistant_response(
    session_id: str, content: str, tokens_used: Optional[int] = None
) -> None:
    """Publish an assistant response generated event."""
    await event_bus.publish(
        AssistantMessageGenerated(
            event_id=f"assistant-msg-{session_id}-{datetime.utcnow().isoformat()}",
            category=EventCategory.CONVERSATION,
            priority=EventPriority.NORMAL,
            timestamp=datetime.utcnow(),
            source="orchestrator",
            data={"session_id": session_id, "content_length": len(content)},
            session_id=session_id,
            response_content=content,
            tokens_used=tokens_used,
        )
    )


async def publish_plugin_execution(
    plugin_name: str,
    execution_time_ms: float,
    success: bool,
    session_id: Optional[str] = None,
) -> None:
    """Publish a plugin execution event."""
    priority = EventPriority.HIGH if not success else EventPriority.NORMAL
    await event_bus.publish(
        PluginExecuted(
            event_id=f"plugin-{plugin_name}-{datetime.utcnow().isoformat()}",
            category=EventCategory.PLUGIN,
            priority=priority,
            timestamp=datetime.utcnow(),
            source="plugin_system",
            data={"plugin_name": plugin_name, "execution_time_ms": execution_time_ms},
            plugin_name=plugin_name,
            execution_time_ms=execution_time_ms,
            success=success,
            session_id=session_id,
        )
    )


async def publish_llm_call(
    provider: str, model: str, tokens_used: int, success: bool, duration_ms: float
) -> None:
    """Publish an LLM call completion event."""
    priority = EventPriority.HIGH if not success else EventPriority.NORMAL
    await event_bus.publish(
        LLMCallCompleted(
            event_id=f"llm-{provider}-{datetime.utcnow().isoformat()}",
            category=EventCategory.LLM,
            priority=priority,
            timestamp=datetime.utcnow(),
            source="llm_provider",
            data={"provider": provider, "model": model, "tokens_used": tokens_used},
            provider=provider,
            model=model,
            tokens_used=tokens_used,
            success=success,
            duration_ms=duration_ms,
        )
    )


async def publish_conversation_error(
    session_id: str, error_type: str, error_message: str
) -> None:
    """Publish a conversation error event."""
    await event_bus.publish(
        ConversationErrorOccurred(
            event_id=f"error-{session_id}-{datetime.utcnow().isoformat()}",
            category=EventCategory.CONVERSATION,
            priority=EventPriority.HIGH,
            timestamp=datetime.utcnow(),
            source="conversation_manager",
            data={"session_id": session_id, "error_type": error_type},
            session_id=session_id,
            error_type=error_type,
            error_message=error_message,
        )
    )


async def publish_health_check(
    component: str, status: str, metrics: Dict[str, Any]
) -> None:
    """Publish a system health check event."""
    priority = EventPriority.CRITICAL if status == "unhealthy" else EventPriority.LOW
    await event_bus.publish(
        SystemHealthCheck(
            event_id=f"health-{component}-{datetime.utcnow().isoformat()}",
            category=EventCategory.SYSTEM,
            priority=priority,
            timestamp=datetime.utcnow(),
            source="health_monitor",
            data={"component": component, "status": status, **metrics},
            component=component,
            status=status,
            metrics=metrics,
        )
    )
