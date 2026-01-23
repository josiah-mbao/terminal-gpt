#!/usr/bin/env python3
"""
Demo script for Terminal GPT.

This script demonstrates how to use the Terminal GPT system
with a simple chat interface and mocked LLM responses.
"""

import asyncio
import os
import sys
from terminal_gpt.application.orchestrator import ConversationOrchestrator
from terminal_gpt.infrastructure.logging import configure_logging


class MockLLMProvider:
    """Mock LLM provider for demo purposes."""

    def __init__(self):
        self.model = "mock-gpt-3.5-turbo"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def generate(self, messages, tools=None, config=None):
        """Generate mock responses based on input."""
        from terminal_gpt.infrastructure.llm_providers import LLMResponse

        # Get the last user message
        last_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_message = msg["content"]
                break

        # Generate mock response based on input
        if "hello" in last_message.lower() or "hi" in last_message.lower():
            content = "Hello! I'm Terminal GPT, your AI assistant with plugin support. How can I help you today?"
        elif "calculator" in last_message.lower() or "calculate" in last_message.lower():
            content = "I can help you with calculations! Try asking me to calculate something specific, like 'What is 2 + 2?'"
        elif "+" in last_message or "-" in last_message or "*" in last_message or "/" in last_message:
            # This would normally trigger a tool call
            content = f"I see you want to do math! Let me calculate that for you using my calculator plugin."
        elif "file" in last_message.lower() or "read" in last_message.lower():
            content = "I can help you read files! Try asking me to read a specific file, like 'Read the README.md file'."
        else:
            content = f"I understand you said: '{last_message}'. I'm an AI assistant with access to various tools including file operations, calculations, and more. What would you like to do?"

        return LLMResponse(
            content=content,
            model=self.model,
            usage={"total_tokens": len(content.split()) * 2}
        )


async def demo_chat():
    """Run a simple chat demo."""
    print("🤖 Terminal GPT Demo")
    print("=" * 50)

    # Configure logging
    configure_logging(level="INFO")

    # Create mock LLM provider
    llm_provider = MockLLMProvider()

    # Create orchestrator
    orchestrator = ConversationOrchestrator(
        llm_provider=llm_provider,
        max_conversation_length=50,
        sliding_window_size=20
    )

    print("\n💬 Starting conversation...")
    print("Type 'quit' to exit, 'help' for commands\n")

    session_id = "demo-session"

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            if user_input.lower() == 'help':
                print("\n📖 Commands:")
                print("  quit/exit/q - Exit the demo")
                print("  help - Show this help")
                print("  sessions - Show active sessions")
                print("  stats - Show system statistics")
                print("\n💡 Try asking me to:")
                print("  - Calculate something (e.g., 'What is 15 * 7?')")
                print("  - Read a file (e.g., 'Read the README.md file')")
                print("  - Say hello")
                print()
                continue

            if user_input.lower() == 'sessions':
                sessions = orchestrator.list_conversations()
                if sessions:
                    print(f"\n📋 Active sessions: {list(sessions.keys())}")
                else:
                    print("\n📋 No active sessions")
                continue

            if user_input.lower() == 'stats':
                stats = orchestrator.get_stats()
                print("\n📊 System Stats:")
                for key, value in stats.items():
                    print(f"  {key}: {value}")
                continue

            # Process the message
            print("\n🤔 Thinking...", end=" ", flush=True)

            response = await orchestrator.process_user_message(session_id, user_input)

            print("Done!")

            # Display response
            print(f"\n🤖 Assistant: {response}")

            # Show conversation stats
            conversation = orchestrator.get_conversation(session_id)
            if conversation:
                print(f"\n📝 Conversation: {conversation.get_message_count()} messages")

        except KeyboardInterrupt:
            print("\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Continuing...")

    # Show final stats
    print("\n" + "=" * 50)
    print("🏁 Demo Complete!")
    final_stats = orchestrator.get_stats()
    print(f"Total conversations: {final_stats['active_conversations']}")
    print(f"Total messages: {final_stats['total_messages']}")


def main():
    """Main entry point."""
    print("🚀 Starting Terminal GPT Demo...")

    # Check if we should run the real API
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--api":
        print("🌐 Starting API server...")
        import uvicorn
        uvicorn.run(
            "src.terminal_gpt.api.routes:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    elif len(os.sys.argv) > 1 and os.sys.argv[1] == "--cli":
        print("💻 Starting CLI...")
        from src.terminal_gpt.cli.terminal import app
        app()
    else:
        # Run demo
        asyncio.run(demo_chat())


if __name__ == "__main__":
    main()
