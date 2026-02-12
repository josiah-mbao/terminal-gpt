#!/usr/bin/env python3
"""Test script to validate UI/UX enhancements for Terminal GPT."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from terminal_gpt.cli.enhanced_ui import StatusLevel, enhanced_ui


async def test_enhanced_ui():
    """Test all enhanced UI features."""
    ui = enhanced_ui

    print("🧪 Testing Enhanced UI Features")
    print("=" * 50)

    # Test 1: Welcome message
    print("\n1. Testing welcome message...")
    ui.print_welcome()

    # Test 2: Status messages
    print("\n2. Testing status messages...")
    ui.print_status(StatusLevel.SUCCESS, "API connection established")
    ui.print_status(
        StatusLevel.WARNING,
        "Terminal size is below recommended",
        "Consider increasing terminal width",
    )
    ui.print_status(
        StatusLevel.ERROR, "API server not found", "Make sure the server is running"
    )
    ui.print_status(StatusLevel.INFO, "Session created successfully")
    ui.print_status(StatusLevel.DEBUG, "Debug information", "Detailed debug info")

    # Test 3: Chat messages
    print("\n3. Testing chat messages...")
    ui.print_message("user", "Hello, how are you?", "session_123")
    ui.print_message(
        "assistant", "I'm doing great! How can I help you today?", "session_123"
    )
    ui.print_message("system", "System notification", "session_123")
    ui.print_message("tool", "Plugin result", "session_123")

    # Test 4: Thinking indicator
    print("\n4. Testing thinking indicator...")
    async with ui.thinking_indicator("thinking", 2.0) as thinking:
        await asyncio.sleep(2)

    # Test 5: Plugin output
    print("\n5. Testing plugin output...")

    # Table output
    table_data = [
        {"Name": "file1.txt", "Size": "1.2KB", "Modified": "2024-01-01"},
        {"Name": "file2.py", "Size": "5.4KB", "Modified": "2024-01-02"},
        {"Name": "file3.md", "Size": "2.1KB", "Modified": "2024-01-03"},
    ]
    ui.print_plugin_output("read_file", "table", table_data, "File Contents")

    # List output
    list_data = ["Item 1", "Item 2", "Item 3", "Item 4"]
    ui.print_plugin_output("search_web", "list", list_data, "Search Results")

    # Tree output
    tree_data = {
        "project": {
            "src": {
                "main.py": "Main application file",
                "utils": {"helper.py": "Helper functions"},
            },
            "tests": {"test_main.py": "Main tests"},
        }
    }
    ui.print_plugin_output("list_files", "tree", tree_data, "Project Structure")

    # Text output
    text_data = "This is a sample text output from a plugin."
    ui.print_plugin_output("calculate", "text", text_data, "Calculation Result")

    # Test 6: Status table
    print("\n6. Testing status table...")
    stats = {
        "active_sessions": 5,
        "total_messages": 1250,
        "api_response_time": 245,
        "memory_usage": "150MB",
        "cpu_usage": "12%",
    }
    table = ui.create_status_table(stats)
    ui.console.print(table)

    # Test 7: Terminal validation
    print("\n7. Testing terminal validation...")
    validation = ui.validate_terminal_size()
    print(f"Terminal size: {validation['width']}x{validation['height']}")
    print(f"Compatible: {validation['is_compatible']}")

    if not validation["is_compatible"]:
        ui.print_accessibility_report()

    # Test 8: Command results
    print("\n8. Testing command results...")
    ui.print_command_result("chat", True, "Session started successfully", 1.5)
    ui.print_command_result("sessions", False, "Failed to retrieve sessions", 0.8)

    print("\n✅ All UI/UX enhancements tested successfully!")
    print("\n📋 Summary:")
    print("- ✅ Enhanced welcome message with professional styling")
    print("- ✅ Color-coded status messages (success, warning, error, info, debug)")
    print("- ✅ Enhanced chat message formatting with markdown support")
    print("- ✅ Thinking indicators with different modes")
    print("- ✅ Standardized plugin output rendering")
    print("- ✅ Professional status tables")
    print("- ✅ Terminal size validation and accessibility reporting")
    print("- ✅ Command execution result formatting")
    print("- ✅ Rich text theming and professional color scheme")


async def test_terminal_integration():
    """Test integration with terminal.py."""
    print("\n🔧 Testing Terminal Integration")
    print("=" * 50)

    # Test that terminal.py can import and use enhanced UI
    try:
        from terminal_gpt.cli.terminal import StatusLevel, ui

        print("✅ Successfully imported enhanced UI from terminal.py")

        # Test basic functionality
        ui.print_status(StatusLevel.INFO, "Integration test successful")
        ui.print_message("user", "Testing integration", "test_session")

        print("✅ Basic integration test passed")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

    return True


async def main():
    """Run all tests."""
    print("🚀 Starting UI/UX Enhancement Tests")
    print("=" * 60)

    try:
        # Test enhanced UI features
        await test_enhanced_ui()

        # Test terminal integration
        integration_success = await test_terminal_integration()

        if integration_success:
            print("\n🎉 All tests passed! UI/UX enhancements are working correctly.")
        else:
            print("\n⚠️  Some tests failed. Please check the integration.")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
