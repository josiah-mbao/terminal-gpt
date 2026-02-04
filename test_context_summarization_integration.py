#!/usr/bin/env python3
"""Test script to verify context summarization integration."""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from terminal_gpt.infrastructure.context_summarizer import ContextSummarizer
from terminal_gpt.domain.models import Message, ConversationState
from terminal_gpt.infrastructure.llm_providers import LLMProvider


async def test_context_summarization():
    """Test the context summarization integration."""
    print("Testing Context Summarization Integration...")
    
    try:
        # Create a mock LLM provider for testing
        class MockLLMProvider:
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            
            async def generate(self, messages, tools=None, config=None):
                # Mock response
                class MockResponse:
                    def __init__(self):
                        self.content = "This is a mock summary of the conversation."
                        self.usage = {"total_tokens": 50}
                        self.tool_calls = []
                
                return MockResponse()
        
        # Create context summarizer
        llm_provider = MockLLMProvider()
        summarizer = ContextSummarizer(
            llm_provider=llm_provider,
            summarization_threshold=0.5,  # Lower threshold for testing
            max_summary_length=300
        )
        
        # Create a long conversation for testing
        messages = []
        
        # Add system message
        messages.append(Message(role="system", content="Test system prompt"))
        
        # Add user messages
        for i in range(25):
            messages.append(Message(role="user", content=f"User message {i+1}: This is a test message about coding and debugging."))
            messages.append(Message(role="assistant", content=f"Assistant response {i+1}: I understand your question about coding."))
        
        # Add some tool messages
        messages.append(Message(role="tool", content="Tool result: File operation completed successfully", name="read_file"))
        
        conversation = ConversationState(session_id="test_session", messages=messages)
        
        print(f"Created test conversation with {len(conversation.messages)} messages")
        
        # Test if summarization should be triggered
        should_summarize = await summarizer.should_summarize(conversation)
        print(f"Should summarize: {should_summarize}")
        
        if should_summarize:
            # Test summarization
            summary, recent_messages = await summarizer.summarize_conversation(conversation)
            
            print(f"Summary generated: {len(summary.summary_text)} characters")
            print(f"Recent messages kept: {len(recent_messages)}")
            print(f"Original messages: {len(conversation.messages)}")
            
            # Convert summary to message
            summary_message = summary.to_message()
            print(f"Summary message role: {summary_message.role}")
            print(f"Summary message content preview: {summary_message.content[:100]}...")
            
            # Create summarized conversation
            summarized_messages = [summary_message] + recent_messages
            summarized_conversation = ConversationState(
                session_id=conversation.session_id,
                messages=summarized_messages
            )
            
            print(f"Summarized conversation has {len(summarized_conversation.messages)} messages")
            print("✅ Context summarization integration test PASSED!")
            
        else:
            print("❌ Summarization threshold not met for test")
            
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_context_summarization())