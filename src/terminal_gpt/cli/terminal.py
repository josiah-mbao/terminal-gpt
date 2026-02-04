"""Terminal CLI interface for Terminal GPT."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from ..infrastructure.logging import get_logger
from .enhanced_ui import enhanced_ui, StatusLevel

logger = get_logger("terminal_gpt.cli")

# Custom theme for terminal
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "user": "blue bold",
    "assistant": "magenta",
    "system": "dim cyan",
    "tool": "yellow italic",
})

console = Console(theme=custom_theme)

# Global state
current_session: Optional[str] = None
api_base_url = "http://localhost:8000"
client = httpx.AsyncClient(timeout=60.0)


class TerminalUI:
    """Terminal UI for chat interactions."""

    def __init__(self):
        self.console = console

    def print_welcome(self):
        """Print welcome message."""
        welcome_text = Text("🤖 Terminal GPT", style="bold cyan")
        welcome_panel = Panel(
            "[dim]AI-powered chat system with plugin support[/dim]\n\n"
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
            header = f"[user]You[/user] ({timestamp})"
            style = "user"
        elif role == "assistant":
            header = f"[assistant]Assistant[/assistant] ({timestamp})"
            style = "assistant"
            # Render as markdown for better formatting
            content = Markdown(content)
        elif role == "system":
            header = f"[system]System[/system] ({timestamp})"
            style = "system"
        elif role == "tool":
            header = f"[tool]Tool Result[/tool] ({timestamp})"
            style = "tool"
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
        error_text = Text(f"❌ {message}", style="error")
        if details:
            error_text.append(f"\n[bold]{details}[/bold]")
        self.console.print(error_text)

    def print_success(self, message: str):
        """Print a success message."""
        self.console.print(f"[success]✅ {message}[/success]")

    def print_info(self, message: str):
        """Print an info message."""
        self.console.print(f"[info]ℹ️  {message}[/info]")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[warning]⚠️  {message}[/warning]")

    def create_status_table(self, stats: dict) -> Table:
        """Create a status table from stats."""
        table = Table(title="System Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        for key, value in stats.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        return table

    async def show_spinner(self, message: str, coro):
        """Show a spinner while executing an async operation."""
        with self.console.status(f"[bold green]{message}...") as status:
            result = await coro
        return result


# Global UI instance - use enhanced UI
ui = enhanced_ui


async def check_api_health() -> bool:
    """Check if the API is healthy and running."""
    try:
        response = await client.get(f"{api_base_url}/health")
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy"
        return False
    except Exception:
        return False


async def send_chat_message(session_id: str, message: str) -> Optional[dict]:
    """Send a chat message to the API."""
    try:
        payload = {
            "session_id": session_id,
            "message": message
        }

        response = await client.post(
            f"{api_base_url}/chat",
            json=payload,
            timeout=60.0
        )

        if response.status_code == 200:
            return response.json()
        else:
            error_data = response.json()
            ui.print_status(
                StatusLevel.ERROR,
                f"API Error ({response.status_code})",
                error_data.get("error", {}).get("message", "Unknown error")
            )
            return None

    except httpx.TimeoutException:
        ui.print_status(StatusLevel.ERROR, "Request timed out", "The API took too long to respond")
        return None
    except Exception as e:
        ui.print_status(StatusLevel.ERROR, "Connection failed", f"Could not connect to API: {e}")
        return None


async def get_sessions() -> Optional[dict]:
    """Get list of active sessions."""
    try:
        response = await client.get(f"{api_base_url}/sessions")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


async def create_session(session_id: str) -> bool:
    """Create a new session."""
    try:
        response = await client.post(f"{api_base_url}/sessions/{session_id}")
        return response.status_code == 200
    except Exception:
        return False


async def get_stats() -> Optional[dict]:
    """Get system statistics."""
    try:
        response = await client.get(f"{api_base_url}/stats")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def show_help():
    """Show help information."""
    help_text = """
[bold cyan]Terminal GPT Commands:[/bold cyan]

[bold]/help[/bold]              Show this help message
[bold]/clear[/bold]             Clear the terminal screen
[bold]/sessions[/bold]          List active conversation sessions
[bold]/session <id>[/bold]      Switch to a different session
[bold]/new <id>[/bold]          Create a new conversation session
[bold]/stats[/bold]             Show system statistics
[bold]/status[/bold]            Check API connection status
[bold]/quit[/bold] or [bold]/exit[/bold]   Exit the application

[bold]Chat Commands:[/bold]
- Type any message to chat with the AI
- Use Ctrl+C to cancel current input
- Use Ctrl+D (on some systems) to send multi-line messages

[bold]Features:[/bold]
- AI-powered conversations with plugin support
- File operations, calculations, and more
- Persistent conversation sessions
- Real-time status monitoring
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
    elif cmd == "/sessions":
        await handle_sessions_command()
    elif cmd == "/session" and len(parts) > 1:
        await handle_switch_session(parts[1])
    elif cmd == "/new" and len(parts) > 1:
        await handle_new_session(parts[1])
    elif cmd == "/stats":
        await handle_stats_command()
    elif cmd == "/status":
        await handle_status_command()
    elif cmd in ["/quit", "/exit"]:
        return False
    else:
        ui.print_warning(f"Unknown command: {cmd}. Type /help for available commands.")

    return True


async def handle_sessions_command():
    """Handle /sessions command."""
    sessions = await get_sessions()
    if sessions is None:
        ui.print_status(StatusLevel.ERROR, "Could not retrieve sessions")
        return

    if not sessions:
        ui.print_status(StatusLevel.INFO, "No active sessions")
        return

    table = Table(title="Active Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Messages", style="magenta")
    table.add_column("Last Activity", style="green")

    for session_id, info in sessions.items():
        table.add_row(
            session_id,
            str(info["message_count"]),
            info["last_activity"]
        )

    console.print(table)


async def handle_switch_session(session_id: str):
    """Handle session switching."""
    global current_session

    # Check if session exists
    sessions = await get_sessions()
    if sessions and session_id in sessions:
        current_session = session_id
        ui.print_status(StatusLevel.SUCCESS, f"Switched to session: {session_id}")
    else:
        ui.print_status(StatusLevel.WARNING, f"Session '{session_id}' not found. Use /new {session_id} to create it.")


async def handle_new_session(session_id: str):
    """Handle new session creation."""
    global current_session

    if await create_session(session_id):
        current_session = session_id
        ui.print_status(StatusLevel.SUCCESS, f"Created and switched to new session: {session_id}")
    else:
        ui.print_status(StatusLevel.ERROR, f"Failed to create session: {session_id}")


async def handle_stats_command():
    """Handle /stats command."""
    stats = await get_stats()
    if stats is None:
        ui.print_status(StatusLevel.ERROR, "Could not retrieve statistics")
        return

    table = ui.create_status_table(stats)
    console.print(table)


async def handle_status_command():
    """Handle /status command."""
    if await check_api_health():
        ui.print_status(StatusLevel.SUCCESS, "API is healthy and responding")
    else:
        ui.print_status(
            StatusLevel.ERROR, 
            "API is not responding", 
            "Make sure the API server is running on http://localhost:8000"
        )


async def chat_loop():
    """Main chat interaction loop."""
    global current_session

    # Initialize with default session if none set
    if not current_session:
        current_session = f"session_{int(datetime.now().timestamp())}"
    if await create_session(current_session):
        ui.print_status(StatusLevel.INFO, f"Started new session: {current_session}")
    else:
        ui.print_status(StatusLevel.ERROR, "Failed to create session")
        return

    ui.print_status(StatusLevel.INFO, f"Current session: {current_session}")

    while True:
        try:
            # Get user input
            user_input = Prompt.ask(f"[user]{current_session}[/user]").strip()

            if not user_input:
                continue

            # Check if it's a command
            if user_input.startswith("/"):
                should_continue = await handle_command(user_input)
                if not should_continue:
                    break
                continue

            # Send chat message
            ui.print_message("user", user_input)

            # Show typing indicator
            async with ui.thinking_indicator("thinking") as thinking:
                response = await send_chat_message(current_session, user_input)

            if response:
                # Display AI response
                ui.print_message("assistant", response["reply"])

                # Show metadata if available
                if response.get("tokens_used"):
                    ui.print_status(
                        StatusLevel.INFO, 
                        f"Tokens used: {response['tokens_used']}"
                    )
                if response.get("processing_time_ms"):
                    ui.print_status(
                        StatusLevel.INFO, 
                        f"Response time: {response['processing_time_ms']}ms"
                    )

                # Show status
                status = response.get("status", "unknown")
                if status == "degraded":
                    ui.print_status(StatusLevel.WARNING, "Response generated in degraded mode")
                elif status == "error":
                    ui.print_status(StatusLevel.ERROR, "Response generated with errors")

            else:
                ui.print_status(StatusLevel.ERROR, "Failed to get response from AI")

        except KeyboardInterrupt:
            ui.print_status(StatusLevel.WARNING, "Input cancelled. Type /quit to exit or continue chatting.")
        except EOFError:
            break
        except Exception as e:
            ui.print_status(StatusLevel.ERROR, f"Unexpected error: {e}")
            logger.error("Chat loop error", error=str(e))


async def startup_checks():
    """Perform startup checks."""
    ui.print_status(StatusLevel.INFO, "Checking API connection...")

    if not await check_api_health():
        ui.print_status(StatusLevel.ERROR, "API server is not running or not healthy")
        ui.print_status(StatusLevel.INFO, "Make sure to start the API server first:")
        ui.print_status(StatusLevel.INFO, "  uvicorn src.terminal_gpt.api.routes:app --reload")
        return False

    ui.print_status(StatusLevel.SUCCESS, "API connection established")
    
    # Check terminal compatibility
    ui.print_status(StatusLevel.INFO, "Validating terminal compatibility...")
    validation = ui.validate_terminal_size()
    
    if not validation["is_compatible"]:
        ui.print_accessibility_report()
        ui.print_status(
            StatusLevel.WARNING, 
            "Consider adjusting terminal size for optimal experience",
            persistent=True
        )
    else:
        ui.print_status(StatusLevel.SUCCESS, "Terminal compatibility verified")
    
    return True


# CLI app
app = typer.Typer(
    name="terminal-gpt",
    help="AI-powered terminal chat with plugin support",
    rich_markup_mode="rich"
)


@app.command()
def chat(
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to use"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API base URL")
):
    """Start interactive chat session."""
    global current_session, api_base_url

    # Set global variables
    if session:
        current_session = session
    api_base_url = api_url.rstrip("/")

    async def main():
        try:
            # Startup checks
            if not await startup_checks():
                return

            # Welcome message
            console.clear()
            ui.print_welcome()

            # Start chat loop
            await chat_loop()

            # Goodbye message
            ui.print_status(StatusLevel.INFO, "Goodbye! 👋")

        except KeyboardInterrupt:
            ui.print_status(StatusLevel.INFO, "Interrupted. Goodbye! 👋")
        except Exception as e:
            ui.print_status(StatusLevel.ERROR, f"Fatal error: {e}")
            logger.error("Fatal CLI error", error=str(e))
        finally:
            await client.aclose()

    # Run async main
    asyncio.run(main())


@app.command()
def sessions(api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API base URL")):
    """List active conversation sessions."""
    global api_base_url
    api_base_url = api_url.rstrip("/")

    async def main():
        if not await startup_checks():
            return

        await handle_sessions_command()

    asyncio.run(main())


@app.command()
def stats(api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API base URL")):
    """Show system statistics."""
    global api_base_url
    api_base_url = api_url.rstrip("/")

    async def main():
        if not await startup_checks():
            return

        await handle_stats_command()

    asyncio.run(main())


if __name__ == "__main__":
    app()
