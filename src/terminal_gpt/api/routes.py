"""FastAPI routes for Terminal GPT."""

import os
import time
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..application.orchestrator import ConversationOrchestrator
from ..infrastructure.llm_providers import create_llm_provider
from ..infrastructure.logging import configure_logging, get_logger
from ..domain.exceptions import (
    TerminalGPTError, ValidationError, LLMError,
    ConfigurationError, format_error_response
)
from ..application.events import event_bus, publish_health_check
from ..config import load_config, get_openrouter_config
from ..infrastructure.builtin_plugins import register_builtin_plugins

# Configure logging
configure_logging()
logger = get_logger("terminal_gpt.api")

# Global orchestrator instance (in production, use dependency injection)
_orchestrator: Optional[ConversationOrchestrator] = None


def get_orchestrator() -> ConversationOrchestrator:
    """Dependency injection for orchestrator."""
    if _orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service not initialized"
        )
    return _orchestrator


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str = Field(..., description="Conversation session ID")
    message: str = Field(..., description="User message to process")
    model: Optional[str] = Field(None, description="LLM model to use")
    temperature: Optional[float] = Field(None, description="Response creativity (0.0-1.0)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    reply: str
    status: str = Field(..., description="Response status: success, degraded, error")
    tokens_used: Optional[int] = None
    tools_used: Optional[list[str]] = None
    processing_time_ms: Optional[int] = None


class SessionInfo(BaseModel):
    """Session information response."""
    session_id: str
    message_count: int
    last_activity: datetime
    created_at: datetime


class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    version: str
    services: Dict[str, str]
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: Dict[str, Any]


# Create FastAPI app
app = FastAPI(
    title="Terminal GPT API",
    description="AI-powered chat system with plugin support",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global _orchestrator

    try:
        # Register built-in plugins first
        register_builtin_plugins()
        
        # Load configuration
        config = load_config()

        # Load API key from environment
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "OPENROUTER_API_KEY environment variable is required. "
                "Get your key from https://openrouter.ai/ and set it with: "
                "export OPENROUTER_API_KEY='your-key-here'"
            )

        # Initialize LLM provider
        openrouter_config = get_openrouter_config()
        llm_provider = create_llm_provider(
            "openrouter",
            api_key,
            model="anthropic/claude-3.5-sonnet"
        )

        # Initialize orchestrator with Juice's personality
        _orchestrator = ConversationOrchestrator(
            llm_provider=llm_provider,
            max_conversation_length=config["max_conversation_length"],
            sliding_window_size=config["sliding_window_size"],
            enable_summarization=config["enable_summarization"],
            system_prompt=config["system_prompt"]
        )

        # Start event bus
        await event_bus.start()

        logger.info("Terminal GPT API started successfully")

        # Publish health check
        await publish_health_check("api", "healthy", {"endpoints": 3})

    except Exception as e:
        logger.error("Failed to initialize Terminal GPT API", error=str(e))
        await publish_health_check("api", "unhealthy", {"error": str(e)})
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    if _orchestrator:
        # End all active conversations
        summaries = _orchestrator.list_conversations()
        for session_id in summaries.keys():
            await _orchestrator.end_conversation(session_id)

    # Stop event bus
    await event_bus.stop()

    logger.info("Terminal GPT API shut down")


@app.exception_handler(TerminalGPTError)
async def terminal_gpt_exception_handler(request, exc: TerminalGPTError):
    """Handle TerminalGPTError exceptions."""
    logger.warning(
        "API error occurred",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path
    )

    response_data = format_error_response(exc)

    # Map error types to HTTP status codes
    if isinstance(exc, ValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, LLMError):
        status_code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, ConfigurationError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=status_code,
        content=response_data
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        "Unexpected API error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    services_status = {
        "orchestrator": "healthy" if _orchestrator else "unhealthy",
        "event_bus": "healthy" if event_bus._running else "unhealthy",
    }

    overall_status = "healthy"
    if "unhealthy" in services_status.values():
        overall_status = "unhealthy"
    elif "degraded" in services_status.values():
        overall_status = "degraded"

    # Get version from package
    try:
        from .. import __version__
        version = __version__
    except ImportError:
        version = "unknown"

    response = HealthResponse(
        status=overall_status,
        version=version,
        services=services_status,
        timestamp=datetime.utcnow()
    )

    # Publish health check event
    await publish_health_check("api", overall_status, services_status)

    return response


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """Process a chat message and return AI response."""
    start_time = time.time()

    try:
        logger.info(
            "Chat request received",
            session_id=request.session_id,
            message_length=len(request.message)
        )

        # Process the message
        response_text = await orchestrator.process_user_message(
            request.session_id,
            request.message
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Get conversation info for response
        conversation = orchestrator.get_conversation(request.session_id)
        if conversation:
            message_count = conversation.get_message_count()
            # Estimate tokens used (rough calculation)
            total_chars = sum(len(msg.content) for msg in conversation.messages)
            tokens_used = total_chars // 4
        else:
            message_count = 0
            tokens_used = None

        # Determine response status
        # In a more sophisticated implementation, this could check for degraded services
        response_status = "success"

        logger.info(
            "Chat response sent",
            session_id=request.session_id,
            response_length=len(response_text),
            processing_time_ms=processing_time_ms
        )

        return ChatResponse(
            session_id=request.session_id,
            reply=response_text,
            status=response_status,
            tokens_used=tokens_used,
            processing_time_ms=processing_time_ms
        )

    except LLMError:
        # LLM-specific error - mark as degraded but still functional
        processing_time_ms = int((time.time() - start_time) * 1000)

        return ChatResponse(
            session_id=request.session_id,
            reply="I'm sorry, but I'm having trouble connecting to my AI services right now. Please try again in a moment.",
            status="degraded",
            processing_time_ms=processing_time_ms
        )

    except Exception as e:
        # Unexpected error
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "Chat processing failed",
            session_id=request.session_id,
            error=str(e),
            processing_time_ms=processing_time_ms
        )

        return ChatResponse(
            session_id=request.session_id,
            reply="I'm sorry, but an unexpected error occurred. Please try again.",
            status="error",
            processing_time_ms=processing_time_ms
        )


@app.get("/sessions", response_model=Dict[str, SessionInfo])
async def list_sessions(
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """List all active conversation sessions."""
    summaries = orchestrator.list_conversations()

    sessions = {}
    for session_id, summary in summaries.items():
        sessions[session_id] = SessionInfo(
            session_id=session_id,
            message_count=summary.message_count,
            last_activity=summary.last_activity,
            created_at=summary.last_activity  # Would need to track separately in production
        )

    return sessions


@app.post("/sessions/{session_id}")
async def create_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """Create a new conversation session."""
    try:
        await orchestrator.start_conversation(session_id)
        return {"status": "created", "session_id": session_id}
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.delete("/sessions/{session_id}")
async def end_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """End a conversation session."""
    await orchestrator.end_conversation(session_id)
    return {"status": "ended", "session_id": session_id}


@app.get("/stats")
async def get_stats(
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """Get system statistics."""
    stats = orchestrator.get_stats()
    return stats


@app.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator)
):
    """WebSocket endpoint for real-time streaming chat responses."""
    await websocket.accept()
    
    try:
        # Receive the user message
        message_data = await websocket.receive_json()
        user_message = message_data.get("message")
        
        if not user_message:
            await websocket.send_json({
                "type": "error",
                "error": "No message provided"
            })
            return

        logger.info(
            "WebSocket chat request received",
            session_id=session_id,
            message_length=len(user_message),
            message_preview=user_message[:50] + "..." if len(user_message) > 50 else user_message
        )

        # Process the message with streaming
        start_time = time.time()
        tool_calls_logged = []

        try:
            # Get the streaming response from orchestrator
            async for chunk in orchestrator.process_user_message_stream(
                session_id, user_message
            ):
                # Handle both LLMResponse objects and dictionary chunks
                if hasattr(chunk, 'content'):
                    # LLMResponse object
                    tools_used = chunk.tool_calls
                    response_data = {
                        "type": "chunk",
                        "content": chunk.content,
                        "finish_reason": chunk.finish_reason,
                        "model": chunk.model,
                        "usage": chunk.usage,
                        "tools_used": tools_used
                    }
                else:
                    # Dictionary chunk (from error handling)
                    tools_used = chunk.get("tool_calls")
                    response_data = {
                        "type": "chunk",
                        "content": chunk.get("content", ""),
                        "finish_reason": chunk.get("finish_reason"),
                        "model": chunk.get("model"),
                        "usage": chunk.get("usage"),
                        "tools_used": tools_used
                    }

                # Log when tool calls are received
                if tools_used and tools_used not in tool_calls_logged:
                    tool_calls_logged.append(tools_used)
                    logger.info(
                        "Tool calls received",
                        session_id=session_id,
                        tool_calls=tools_used
                    )

                await websocket.send_json(response_data)

            # Send completion message
            processing_time_ms = int((time.time() - start_time) * 1000)
            await websocket.send_json({
                "type": "complete",
                "processing_time_ms": processing_time_ms
            })

        except LLMError as e:
            # Handle LLM errors gracefully
            await websocket.send_json({
                "type": "error",
                "error": "I'm having trouble connecting to my AI services right now. Please try again in a moment.",
                "error_details": str(e)
            })

        except Exception as e:
            # Handle unexpected errors
            logger.error(
                "WebSocket chat processing failed",
                session_id=session_id,
                error=str(e)
            )
            
            await websocket.send_json({
                "type": "error",
                "error": "An unexpected error occurred. Please try again.",
                "error_details": str(e)
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(
            "WebSocket error",
            session_id=session_id,
            error=str(e)
        )
