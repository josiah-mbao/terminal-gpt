"""Main entry point for Terminal GPT with simplified CLI commands."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


app = typer.Typer(
    name="terminal-gpt",
    help="🤖 AI-powered terminal chat with enhanced UI",
    rich_markup_mode="rich",
)


@app.command()
def server(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Host to bind the server to"
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to"),
    reload: bool = typer.Option(True, "--reload", help="Enable auto-reload"),
):
    """Start the FastAPI server."""
    import uvicorn

    console.print(
        Panel(
            Text("🚀 Starting Terminal GPT Server", style="bold green"),
            border_style="green",
        )
    )

    console.print(f"📡 Server will run at: http://{host}:{port}")
    console.print(f"🔄 Auto-reload: {'Enabled' if reload else 'Disabled'}")
    console.print("\nPress Ctrl+C to stop the server\n")

    uvicorn.run("src.terminal_gpt.api.routes:app", host=host, port=port, reload=reload)


@app.command()
def chat(
    session: str = typer.Option(None, "--session", "-s", help="Session ID to use"),
    api_url: str = typer.Option(
        "http://localhost:8000", "--api-url", help="API base URL"
    ),
):
    """Start the enhanced terminal chat interface."""
    console.print(
        Panel(
            Text("💬 Starting Enhanced Terminal Chat", style="bold blue"),
            border_style="blue",
        )
    )

    console.print(f"🔗 Connecting to API: {api_url}")
    if session:
        console.print(f"🆔 Using session: {session}")

    console.print("\nType /help for available commands\n")

    # Run the terminal chat with the provided options
    from .cli.terminal import chat as terminal_chat

    terminal_chat(session=session, api_url=api_url)


@app.command()
def streaming(
    session: str = typer.Option(None, "--session", "-s", help="Session ID to use"),
    api_url: str = typer.Option(
        "ws://localhost:8000", "--api-url", help="WebSocket API URL"
    ),
):
    """Start the enhanced streaming chat interface."""
    console.print(
        Panel(
            Text("⚡ Starting Enhanced Streaming Chat", style="bold magenta"),
            border_style="magenta",
        )
    )

    console.print(f"🔗 Connecting to WebSocket: {api_url}")
    if session:
        console.print(f"🆔 Using session: {session}")

    console.print("\nType /help for available commands\n")

    # Import and run the streaming client directly
    from .cli.streaming_client import chat as streaming_chat

    # Set environment variables for the streaming client
    import os

    if session:
        os.environ["TERMINAL_GPT_SESSION"] = session
    if api_url:
        os.environ["TERMINAL_GPT_API_URL"] = api_url

    # Run the streaming client
    streaming_chat(session=session, api_url=api_url)


@app.command()
def setup():
    """Display setup instructions and check dependencies."""
    console.print(
        Panel(Text("⚙️ Terminal GPT Setup", style="bold yellow"), border_style="yellow")
    )

    console.print("\n[bold]1. Install Dependencies:[/bold]")
    console.print("   pip install -r requirements.txt")

    console.print("\n[bold]2. Set up Environment:[/bold]")
    console.print("   cp .env.example .env")
    console.print("   # Edit .env with your API keys")

    console.print("\n[bold]3. Start Server (Terminal 1):[/bold]")
    console.print("   python -m terminal_gpt server")

    console.print("\n[bold]4. Start Chat (Terminal 2):[/bold]")
    console.print("   python -m terminal_gpt streaming  # Enhanced UI (recommended)")
    console.print("   python -m terminal_gpt chat       # Standard terminal")

    console.print("\n[bold]✨ Enhanced Features:[/bold]")
    console.print("   • Rich color-coded status messages")
    console.print("   • Professional welcome screens")
    console.print("   • Real-time thinking indicators")
    console.print("   • Plugin output with syntax highlighting")
    console.print("   • Terminal size validation")


@app.command()
def info():
    """Display information about Terminal GPT."""
    console.print(
        Panel(
            Text("🤖 Terminal GPT Information", style="bold cyan"), border_style="cyan"
        )
    )

    console.print("\n[bold]Features:[/bold]")
    console.print("   • AI-powered conversations with plugin support")
    console.print("   • Real-time streaming responses")
    console.print("   • Enhanced UI with rich formatting")
    console.print("   • Multi-session support")
    console.print("   • File operations, web search, calculations")

    console.print("\n[bold]Commands:[/bold]")
    console.print("   • /help - Show available commands")
    console.print("   • /sessions - List active sessions")
    console.print("   • /session <id> - Switch sessions")
    console.print("   • /stats - Show system statistics")
    console.print("   • /clear - Clear screen")
    console.print("   • /quit - Exit application")


if __name__ == "__main__":
    app()
