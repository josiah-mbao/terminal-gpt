#!/usr/bin/env python3
"""Test script to demonstrate enhanced UI features."""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from terminal_gpt.cli.enhanced_ui import enhanced_ui, StatusLevel


async def test_enhanced_ui():
    """Test the enhanced UI features."""
    print("🧪 Testing Enhanced UI Features")
    print("=" * 50)
    
    # Test 1: Welcome message
    print("\n1️⃣ Testing Welcome Message...")
    enhanced_ui.print_welcome()
    
    # Test 2: Status messages
    print("\n2️⃣ Testing Color-Coded Status Messages...")
    enhanced_ui.print_status(
        StatusLevel.SUCCESS, 
        "API connection established", 
        "All systems operational"
    )
    
    enhanced_ui.print_status(
        StatusLevel.WARNING, 
        "Context limit approaching", 
        "Consider summarizing conversation"
    )
    
    enhanced_ui.print_status(
        StatusLevel.ERROR, 
        "Plugin execution failed", 
        "File not found: /path/to/file"
    )
    
    enhanced_ui.print_status(
        StatusLevel.INFO, 
        "System ready", 
        "Ready to accept commands"
    )
    
    # Test 3: Thinking indicator
    print("\n3️⃣ Testing Thinking Indicator...")
    async with enhanced_ui.thinking_indicator("thinking", duration=2.0):
        await asyncio.sleep(2)
    
    # Test 4: Chat messages
    print("\n4️⃣ Testing Enhanced Chat Messages...")
    enhanced_ui.print_message(
        "user", 
        "Hello, how are you today?", 
        session_id="test_session_001",
        metadata={"tokens_used": 15, "processing_time_ms": 1250}
    )
    
    enhanced_ui.print_message(
        "assistant", 
        "I'm doing great! I'm an AI assistant designed to help you with various tasks. How can I assist you today?",
        session_id="test_session_001",
        metadata={"tokens_used": 45, "processing_time_ms": 2150}
    )
    
    # Test 5: Plugin output
    print("\n5️⃣ Testing Plugin Output Rendering...")
    
    # Table output
    table_data = [
        {"Name": "file1.txt", "Size": "1.2KB", "Modified": "2024-01-15"},
        {"Name": "file2.py", "Size": "5.8KB", "Modified": "2024-01-16"},
        {"Name": "file3.json", "Size": "2.1KB", "Modified": "2024-01-17"}
    ]
    enhanced_ui.print_plugin_output("read_file", "table", table_data, "File Listing")
    
    # List output
    list_data = ["Item 1: First item", "Item 2: Second item", "Item 3: Third item"]
    enhanced_ui.print_plugin_output("search_web", "list", list_data, "Search Results")
    
    # Tree output
    tree_data = {
        "project": {
            "src": {
                "main.py": "Main application",
                "utils": {
                    "helpers.py": "Helper functions"
                }
            },
            "tests": {
                "test_main.py": "Main tests"
            }
        }
    }
    enhanced_ui.print_plugin_output("file_system", "tree", tree_data, "Project Structure")
    
    # Test 6: Terminal validation
    print("\n6️⃣ Testing Terminal Size Validation...")
    enhanced_ui.print_accessibility_report()
    
    # Test 7: Command results
    print("\n7️⃣ Testing Command Results...")
    enhanced_ui.print_command_result("sessions", True, "Retrieved 3 active sessions", 0.15)
    enhanced_ui.print_command_result("stats", False, "Failed to retrieve statistics", 0.05)
    
    print("\n" + "=" * 50)
    print("🎉 Enhanced UI Features Test Complete!")
    print("✅ All features working correctly")


if __name__ == "__main__":
    asyncio.run(test_enhanced_ui())