"""Streaming CLI client for Terminal GPT with WebSocket support."""

import asyncio
import json
from datetime import datetime
from typing import Optional, List

import typer
import websockets
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from ..infrastructure.logging import get_logger
from ..cli.enhanced_ui import enhanced_ui

logger = get_logger("terminal_gpt.streaming_cli")

# Global state
current_session: Optional[str] = None
api_base_url = "ws://localhost:8000"

# Use enhanced UI
ui = enhanced_ui

# Session stability configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAYS = [1, 2, 4]
CONNECTION_TIMEOUT = 30.0
PACING_ENABLED = True

# Conversation history for display
conversation_history: List[dict] = []


async def send_streaming_message(session_id: str, message: str):
    """Send a message and stream the response."""
    websocket_url = f"{api_base_url}/ws/chat/{session_id}"

    try:
        async with websockets.connect(
            websocket_url, open_timeout=CONNECTION_TIMEOUT, close_timeout=10.0
        ) as websocket:
            # Send the message
            await websocket.send(json.dumps({"message": message}))

            # Receive and display streaming response
            full_response = ""
            first_chunk = True

            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=300.0)
                    data = json.loads(response)

                    if data["type"] == "chunk":
                        content = data.get("content", "")
                        if content:
                            if first_chunk:
                                # Print assistant header
                                ui.console.print(
                                    "\n[bold magenta]🤖 Jengo[/bold magenta]"
                                )
                                first_chunk = False

                            # Print the chunk content
                            for char in content:
                                ui.console.print(char, end="", soft_wrap=True)
                                full_response += char

                                # Reduced pacing for readability
                                if PACING_ENABLED:
                                    if char in ".!?":
                                        await asyncio.sleep(0.02)
                                    elif char in ",;:":
                                        await asyncio.sleep(0.01)
                                    else:
                                        await asyncio.sleep(0.001)

                    elif data["type"] == "complete":
                        # Response completed
                        processing_time = data.get("processing_time_ms", 0)
                        # Add to conversation history
                        conversation_history.append(
                            {
                                "role": "assistant",
                                "content": full_response,
                                "time": datetime.now(),
                            }
                        )
                        # Trim history if too long
                        if len(conversation_history) > 6:
                            (
                                conversation_history.pop(0)
                                if conversation_history[0]["role"] == "user"
                                else None
                            )
                        ui.console.print(f"\n[dim]⚡ {processing_time}ms[/dim]")
                        break

                    elif data["type"] == "error":
                        error_msg = data.get("error", "Unknown error")
                        ui.print_error("AI Response Error", error_msg)
                        break

                except asyncio.TimeoutError:
                    ui.print_error("Response timeout", "No data received")
                    break
                except websockets.exceptions.ConnectionClosed:
                    ui.print_error("Connection closed by server")
                    break

            return full_response

    except Exception as e:
        status_code = getattr(e, "status_code", None)
        if status_code == 404:
            ui.print_error("Session not found", f"Session '{session_id}' not found")
        elif status_code == 500:
            ui.print_error("Server error", "The server encountered an error")
        elif status_code:
            ui.print_error(f"Connection failed (Status {status_code})", str(e))
        else:
            ui.print_error("Connection failed", str(e))
        return None


async def send_streaming_message_with_retry(
    session_id: str, message: str, max_retries: int = MAX_RETRY_ATTEMPTS
) -> Optional[str]:
    """Send a message with automatic reconnection on failure."""
    retry_delays = RETRY_DELAYS[:max_retries]

    for attempt, delay in enumerate(retry_delays):
        try:
            return await send_streaming_message(session_id, message)

        except websockets.exceptions.ConnectionClosed:
            if attempt < len(retry_delays) - 1:
                logger.warning(f"Connection closed, retrying in {delay}s...")
                ui.print_warning(f"Connection lost. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                continue
            else:
                ui.print_error("Connection failed", "Unable to reconnect")
                return None

        except Exception as e:
            if attempt < len(retry_delays) - 1:
                logger.warning(f"Connection error: {e}, retrying in {delay}s...")
                await asyncio.sleep(delay)
                continue
            else:
                ui.print_error("Connection failed", str(e))
                return None

    return None


def show_help():
    """Show help information."""
    help_text = """
[bold cyan]📚 Commands:[/bold cyan]
  /help     Show this help
  /clear    Clear screen
  /quit     Exit application

[bold cyan]💡 Tips:[/bold cyan]
  • Type naturally to chat with Jengo
  • Streaming responses appear in real-time
  • Use /clear to refresh the display
"""
    ui.console.print(Panel(help_text, title="Help", border_style="cyan"))


async def handle_command(command: str) -> bool:
    """Handle special commands."""
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd == "/help":
        show_help()
    elif cmd == "/clear":
        ui.console.clear()
        conversation_history.clear()
        ui.print_welcome()
    elif cmd == "/quit":
        return False
    else:
        ui.print_warning(f"Unknown command: {cmd}")

    return True


async def handle_new_session(session_id: str):
    """Handle new session creation."""
    global current_session, conversation_history
    current_session = session_id
    conversation_history = []
    ui.print_success(f"Started new session")


async def chat_loop():
    """Main streaming chat interaction loop."""
    global current_session

    if not current_session:
        current_session = f"session_{int(datetime.now().timestamp())}"

    while True:
        try:
            # Get user input with clean prompt
            user_input = Prompt.ask(">>>").strip()

            if not user_input:
                continue

            # Check if it's a command
            if user_input.startswith("/"):
                should_continue = await handle_command(user_input)
                if not should_continue:
                    break
                continue

            # Add user message to history
            conversation_history.append(
                {"role": "user", "content": user_input, "time": datetime.now()}
            )

            # Show thinking animation
            with Live(refresh_per_second=8) as live:
                frames = [
                    "Jengo is thinking.  ",
                    "Jengo is thinking.. ",
                    "Jengo is thinking...",
                ]
                frame_idx = 0
                for _ in range(24):  # Up to 6 seconds
                    if (
                        conversation_history
                        and conversation_history[-1].get("role") == "user"
                    ):
                        live.update(Text(frames[frame_idx], style="bold cyan"))
                        frame_idx = (frame_idx + 1) % len(frames)
                        await asyncio.sleep(0.25)
                    else:
                        break

            # Send message and get response
            if conversation_history and conversation_history[-1].get("role") == "user":
                response = await send_streaming_message_with_retry(
                    current_session, user_input
                )
                if not response:
                    conversation_history.pop()

        except KeyboardInterrupt:
            ui.print_warning("Type /quit to exit or continue chatting.")
        except EOFError:
            break
        except Exception as e:
            ui.print_error(f"Unexpected error: {e}")
            logger.error("Chat loop error", error=str(e))


# CLI app
app = typer.Typer(
    name="Jengo", help="AI chat with streaming responses", rich_markup_mode="rich"
)


@app.command()
def chat(
    session: Optional[str] = typer.Option(
        None, "--session", "-s", help="Session ID to use"
    ),
    api_url: str = typer.Option(
        "ws://localhost:8000", "--api-url", help="WebSocket API base URL"
    ),
):
    """Start interactive streaming chat session."""
    global current_session, api_base_url

    if session:
        current_session = session
    api_base_url = api_url.rstrip("/")

    async def main():
        try:
            ui.console.clear()
            ui.print_welcome()
            await chat_loop()
            ui.print_info("Goodbye! 👋")
        except KeyboardInterrupt:
            ui.print_info("Goodbye! 👋")
        except Exception as e:
            ui.print_error(f"Fatal error: {e}")
            logger.error("Fatal CLI error", error=str(e))

    asyncio.run(main())


if __name__ == "__main__":
    app()
