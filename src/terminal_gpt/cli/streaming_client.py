"""Streaming CLI client for Terminal GPT with WebSocket support."""

import asyncio
import json
from datetime import datetime
from typing import Optional

import typer
import websockets
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from ..infrastructure.logging import get_logger

logger = get_logger("terminal_gpt.streaming_cli")

# Custom theme for terminal
console = Console()

# Global state
current_session: Optional[str] = None
api_base_url = "ws://localhost:8000"


class StreamingUI:
    """Terminal UI for streaming chat interactions."""

    def __init__(self):
        self.console = console

    def print_welcome(self):
        """Print welcome message."""
        welcome_text = Text("🤖 Terminal GPT (Streaming)", style="bold cyan")
        welcome_panel = Panel(
            "[dim]Real-time AI chat with streaming responses[/dim]\n\n"
            "[dim cyan]Type your message and press Enter to chat.[/dim cyan]\n"
            "[dim cyan]Use /help for available commands.[/dim cyan]",
            title=welcome_text,
            border_style="cyan"
        )
        self.console.print(welcome_panel)

    def print_message(self, role: str, content: str, session_id: Optional[str] = None):
        """Print a chat message with appropriate formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if role == "user":
            header = f"[blue bold]You[/blue bold] ({timestamp})"
            style = "blue"
        elif role == "assistant":
            header = f"[magenta]Assistant[/magenta] ({timestamp})"
            style = "magenta"
            # Render as markdown for better formatting
            content = Markdown(content)
        elif role == "system":
            header = f"[dim cyan]System[/dim cyan] ({timestamp})"
            style = "dim cyan"
        elif role == "tool":
            header = f"[yellow italic]Tool Result[/yellow italic] ({timestamp})"
            style = "yellow"
        else:
            header = f"[{role}] ({timestamp})"
            style = "dim"

        panel = Panel(
            content,
            title=header,
            border_style=style,
            title_align="left"
        )
        self.console.print(panel)

    def print_error(self, message: str, details: Optional[str] = None):
        """Print an error message."""
        error_text = Text(f"❌ {message}", style="red")
        if details:
            error_text.append(f"\n[bold]{details}[/bold]")
        self.console.print(error_text)

    def print_success(self, message: str):
        """Print a success message."""
        self.console.print(f"[green]✅ {message}[/green]")

    def print_info(self, message: str):
        """Print an info message."""
        self.console.print(f"[cyan]ℹ️  {message}[/cyan]")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[yellow]⚠️  {message}[/yellow]")


# Global UI instance
ui = StreamingUI()


async def send_streaming_message(session_id: str, message: str):
    """Send a message and stream the response."""
    websocket_url = f"{api_base_url}/ws/chat/{session_id}"

    try:
        async with websockets.connect(websocket_url) as websocket:
            # Send the message
            await websocket.send(json.dumps({"message": message}))

            # Receive and display streaming response
            full_response = ""
            first_chunk = True

            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)

                    if data["type"] == "chunk":
                        content = data.get("content", "")
                        if content:
                            if first_chunk:
                                # Print the start of the response
                                ui.console.print("\n[bold magenta]Assistant:[/bold magenta]")
                                first_chunk = False

                            # Print the chunk content
                            ui.console.print(content, end="")
                            full_response += content

                    elif data["type"] == "complete":
                        # Response completed
                        processing_time = data.get("processing_time_ms", 0)
                        ui.console.print(f"\n\n[dim]Response time: {processing_time}ms[/dim]")
                        break

                    elif data["type"] == "error":
                        # Handle error
                        error_msg = data.get("error", "Unknown error")
                        ui.print_error("AI Response Error", error_msg)
                        break

                except websockets.exceptions.ConnectionClosed:
                    ui.print_error("Connection closed by server")
                    break

            return full_response

    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 404:
            ui.print_error("Session not found", f"Session '{session_id}' does not exist")
        elif e.status_code == 500:
            ui.print_error("Server error", "The server encountered an error")
        else:
            ui.print_error(f"WebSocket connection failed (Status {e.status_code})", str(e))
        return None
    except websockets.exceptions.InvalidURI as e:
        ui.print_error("Invalid WebSocket URL", str(e))
        return None
    except Exception as e:
        ui.print_error("Connection failed", f"Could not connect to WebSocket: {e}")
        return None


def show_help():
    """Show help information."""
    help_text = """
[bold cyan]Terminal GPT Streaming Commands:[/bold cyan]

[bold]/help[/bold]              Show this help message
[bold]/clear[/bold]             Clear the terminal screen
[bold]/session <id>[/bold]      Switch to a different session
[bold]/new <id>[/bold]          Create a new conversation session
[bold]/quit[/bold] or [bold]/exit[/bold]   Exit the application

[bold]Chat Features:[/bold]
- Real-time streaming responses as AI generates text
- Type any message to chat with the AI
- Use Ctrl+C to cancel current input
- Streaming responses appear character by character

[bold]Benefits:[/bold]
- Immediate feedback as AI generates responses
- Better user experience with real-time updates
- More natural conversation flow
- Reduced perceived latency
"""
    console.print(Panel(help_text, title="Help", border_style="cyan"))


async def handle_command(command: str) -> bool:
    """Handle special commands. Returns True if should continue, False to exit."""
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd == "/help":
        show_help()
    elif cmd == "/clear":
        console.clear()
        ui.print_welcome()
    elif cmd == "/session" and len(parts) > 1:
        await handle_switch_session(parts[1])
    elif cmd == "/new" and len(parts) > 1:
        await handle_new_session(parts[1])
    elif cmd in ["/quit", "/exit"]:
        return False
    else:
        ui.print_warning(f"Unknown command: {cmd}. Type /help for available commands.")

    return True


async def handle_switch_session(session_id: str):
    """Handle session switching."""
    global current_session

    # For streaming, we'll just switch the session ID
    # The WebSocket will handle session creation automatically
    current_session = session_id
    ui.print_success(f"Switched to session: {session_id}")


async def handle_new_session(session_id: str):
    """Handle new session creation."""
    global current_session

    current_session = session_id
    ui.print_success(f"Switched to new session: {session_id}")


async def chat_loop():
    """Main streaming chat interaction loop."""
    global current_session

    # Initialize with default session if none set
    if not current_session:
        current_session = f"session_{int(datetime.now().timestamp())}"
        ui.print_info(f"Started new session: {current_session}")

    ui.print_info(f"Current session: {current_session}")
    ui.print_info("Connected to streaming WebSocket endpoint")

    while True:
        try:
            # Get user input
            user_input = Prompt.ask(f"[blue bold]{current_session}[/blue bold]").strip()

            if not user_input:
                continue

            # Check if it's a command
            if user_input.startswith("/"):
                should_continue = await handle_command(user_input)
                if not should_continue:
                    break
                continue

            # Send chat message and stream response
            ui.print_message("user", user_input)

            # Show typing indicator
            ui.console.print("\n[bold cyan]AI is typing...[/bold cyan]")

            # Send message and stream response
            response = await send_streaming_message(current_session, user_input)

            if response:
                ui.console.print("\n")  # Add spacing after response
            else:
                ui.print_error("Failed to get response from AI")

        except KeyboardInterrupt:
            ui.print_warning("Input cancelled. Type /quit to exit or continue chatting.")
        except EOFError:
            break
        except Exception as e:
            ui.print_error(f"Unexpected error: {e}")
            logger.error("Chat loop error", error=str(e))


# CLI app
app = typer.Typer(
    name="terminal-gpt-streaming",
    help="Real-time AI chat with streaming responses via WebSocket",
    rich_markup_mode="rich"
)


@app.command()
def chat(
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to use"),
    api_url: str = typer.Option("ws://localhost:8000", "--api-url", help="WebSocket API base URL")
):
    """Start interactive streaming chat session."""
    global current_session, api_base_url

    # Set global variables
    if session:
        current_session = session
    api_base_url = api_url.rstrip("/")

    async def main():
        try:
            # Welcome message
            console.clear()
            ui.print_welcome()

            # Start chat loop
            await chat_loop()

            # Goodbye message
            ui.print_info("Goodbye! 👋")

        except KeyboardInterrupt:
            ui.print_info("Interrupted. Goodbye! 👋")
        except Exception as e:
            ui.print_error(f"Fatal error: {e}")
            logger.error("Fatal CLI error", error=str(e))

    # Run async main
    asyncio.run(main())


if __name__ == "__main__":
    app()