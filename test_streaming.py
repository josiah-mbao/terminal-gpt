#!/usr/bin/env python3
"""Test script for streaming response functionality."""

import asyncio
import json
import sys
from datetime import datetime

import websockets
from rich.console import Console
from rich.panel import Panel

console = Console()


async def test_streaming_endpoint():
    """Test the WebSocket streaming endpoint."""
    console.print(Panel("🧪 Testing Streaming Response Functionality", border_style="cyan"))

    # Test parameters
    session_id = f"test_session_{int(datetime.now().timestamp())}"
    test_message = (
        "Hello! This is a test message for streaming responses. "
        "Please provide a detailed response about the benefits of streaming AI responses in terminal applications."
    )
    websocket_url = "ws://localhost:8000/ws/chat/test_streaming"

    console.print(f"[cyan]Session ID:[/cyan] {session_id[:20]}...")
    console.print(f"[cyan]Test Message:[/cyan] {test_message[:50]}...")
    console.print(f"[cyan]WebSocket URL:[/cyan] {websocket_url}")
    console.print()

    try:
        # Test WebSocket connection
        console.print("[bold green]Connecting to WebSocket...[/bold green]")
        async with websockets.connect(websocket_url) as websocket:
            console.print("[bold green]✅ Connected successfully![/bold green]")
            console.print()

            # Send test message
            console.print(f"[bold blue]Sending message:[/bold blue] {test_message}")
            await websocket.send(json.dumps({"message": test_message}))
            console.print("[bold cyan]Message sent, waiting for streaming response...[/bold cyan]")
            console.print()

            # Receive streaming response
            full_response = ""
            chunk_count = 0
            start_time = datetime.now()

            console.print("[bold magenta]Assistant Response:[/bold magenta]")
            console.print("-" * 50)

            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)

                    if data["type"] == "chunk":
                        content = data.get("content", "")
                        if content:
                            chunk_count += 1
                            console.print(content, end="")
                            full_response += content

                    elif data["type"] == "complete":
                        # Response completed
                        end_time = datetime.now()
                        processing_time = (end_time - start_time).total_seconds() * 1000
                        console.print()
                        console.print()
                        console.print(f"[dim]Response completed in {processing_time:.0f}ms[/dim]")
                        console.print(f"[dim]Total chunks received: {chunk_count}[/dim]")
                        break

                    elif data["type"] == "error":
                        # Handle error
                        error_msg = data.get("error", "Unknown error")
                        console.print(f"[bold red]❌ Error:[/bold red] {error_msg}")
                        return False

                except asyncio.TimeoutError:
                    console.print("[bold red]❌ Timeout:[/bold red] No response received within 30 seconds")
                    return False
                except websockets.exceptions.ConnectionClosed:
                    console.print("[bold red]❌ Connection closed by server[/bold red]")
                    return False

            console.print()
            console.print("-" * 50)
            console.print(f"[bold green]✅ Streaming test completed successfully![/bold green]")
            console.print(f"[cyan]Total response length:[/cyan] {len(full_response)} characters")
            console.print(f"[cyan]Chunks received:[/cyan] {chunk_count}")

            return True

    except websockets.exceptions.InvalidStatusCode as e:
        console.print(f"[bold red]❌ WebSocket Error:[/bold red] Status {e.status_code}")
        console.print(f"[dim]{e}[/dim]")
        return False
    except websockets.exceptions.InvalidURI as e:
        console.print(f"[bold red]❌ Invalid URL:[/bold red] {e}")
        return False
    except ConnectionRefusedError:
        console.print("[bold red]❌ Connection Refused:[/bold red] Make sure the API server is running on http://localhost:8000")
        return False
    except Exception as e:
        console.print(f"[bold red]❌ Unexpected Error:[/bold red] {e}")
        return False


async def test_multiple_sessions():
    """Test multiple concurrent sessions."""
    console.print(Panel("🔄 Testing Multiple Sessions", border_style="yellow"))

    sessions = [
        ("session_1", "Hello, this is session 1"),
        ("session_2", "Hello, this is session 2"),
        ("session_3", "Hello, this is session 3"),
    ]

    results = []

    for session_id, message in sessions:
        console.print(f"[bold blue]Testing session:[/bold blue] {session_id}")
        websocket_url = f"ws://localhost:8000/ws/chat/{session_id}"

        try:
            async with websockets.connect(websocket_url) as websocket:
                await websocket.send(json.dumps({"message": message}))

                response = ""
                while True:
                    data = json.loads(await websocket.recv())
                    if data["type"] == "chunk":
                        response += data.get("content", "")
                    elif data["type"] == "complete":
                        break

                results.append((session_id, len(response)))
                console.print(f"  ✅ Session {session_id}: {len(response)} characters")

        except Exception as e:
            results.append((session_id, 0))
            console.print(f"  ❌ Session {session_id}: Failed - {e}")

    console.print()
    console.print("[bold green]Session Test Results:[/bold green]")
    for session_id, length in results:
        status = "✅" if length > 0 else "❌"
        console.print(f"  {status} {session_id}: {length} characters")

    return all(length > 0 for _, length in results)


async def test_error_handling():
    """Test error handling scenarios."""
    console.print(Panel("⚠️  Testing Error Handling", border_style="red"))

    test_cases = [
        {
            "name": "Invalid Session",
            "url": "ws://localhost:8000/ws/chat/invalid_session",
            "message": "Test message",
            "expected_error": True
        },
        {
            "name": "Empty Message",
            "url": "ws://localhost:8000/ws/chat/test_empty",
            "message": "",
            "expected_error": True
        },
        {
            "name": "Valid Message",
            "url": "ws://localhost:8000/ws/chat/test_valid",
            "message": "Hello",
            "expected_error": False
        }
    ]

    results = []

    for test_case in test_cases:
        console.print(f"[bold blue]Testing:[/bold blue] {test_case['name']}")
        console.print(f"  URL: {test_case['url']}")
        console.print(f"  Message: '{test_case['message']}'")

        try:
            async with websockets.connect(test_case["url"]) as websocket:
                await websocket.send(json.dumps({"message": test_case["message"]}))

                response = ""
                error_occurred = False

                while True:
                    data = json.loads(await websocket.recv())
                    if data["type"] == "chunk":
                        response += data.get("content", "")
                    elif data["type"] == "complete":
                        break
                    elif data["type"] == "error":
                        error_occurred = True
                        console.print(f"  [bold red]Error:[/bold red] {data.get('error', 'Unknown error')}")
                        break

                success = not error_occurred if test_case["expected_error"] else error_occurred
                results.append((test_case["name"], success))
                console.print(f"  {'✅' if success else '❌'} Expected error: {test_case['expected_error']}, Got error: {error_occurred}")

        except Exception as e:
            if test_case["expected_error"]:
                console.print(f"  ✅ Expected error occurred: {e}")
                results.append((test_case["name"], True))
            else:
                console.print(f"  ❌ Unexpected error: {e}")
                results.append((test_case["name"], False))

        console.print()

    console.print("[bold green]Error Handling Test Results:[/bold green]")
    for test_name, success in results:
        status = "✅" if success else "❌"
        console.print(f"  {status} {test_name}")

    return all(success for _, success in results)


async def main():
    """Run all tests."""
    console.print("[bold cyan]🚀 Starting Streaming Response Tests[/bold cyan]")
    console.print()

    # Check if server is running
    console.print("[bold yellow]Checking API server status...[/bold yellow]")
    try:
        import httpx
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        if response.status_code == 200:
            console.print("[bold green]✅ API server is running[/bold green]")
        else:
            console.print("[bold red]❌ API server returned non-200 status[/bold red]")
            console.print("Please start the API server with:")
            console.print("  uvicorn src.terminal_gpt.api.routes:app --reload")
            return
    except Exception as e:
        console.print("[bold red]❌ Could not connect to API server[/bold red]")
        console.print(f"Error: {e}")
        console.print("Please start the API server with:")
        console.print("  uvicorn src.terminal_gpt.api.routes:app --reload")
        return

    console.print()

    # Run tests
    tests = [
        ("Streaming Response", test_streaming_endpoint),
        ("Multiple Sessions", test_multiple_sessions),
        ("Error Handling", test_error_handling),
    ]

    results = []

    for test_name, test_func in tests:
        console.print(f"[bold cyan]Running {test_name} Test...[/bold cyan]")
        try:
            result = await test_func()
            results.append((test_name, result))
            console.print(f"[bold green]{'✅' if result else '❌'} {test_name} Test: {'PASSED' if result else 'FAILED'}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ {test_name} Test: FAILED[/bold red]")
            console.print(f"[dim]Error: {e}[/dim]")
            results.append((test_name, False))
        console.print()

    # Summary
    console.print(Panel("📊 Test Summary", border_style="cyan"))
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        console.print(f"  {status}: {test_name}")

    console.print()
    console.print(f"[bold]Overall Result: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print("[bold green]🎉 All tests passed! Streaming functionality is working correctly.[/bold green]")
    else:
        console.print("[bold red]❌ Some tests failed. Please check the implementation.[/bold red]")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)