# Streaming Responses Feature

This document describes the streaming responses functionality added to Terminal GPT, which provides real-time AI responses via WebSocket connections.

## Overview

The streaming responses feature enables real-time communication between the Terminal GPT CLI client and the backend API server. Instead of waiting for the complete response to be generated, users receive immediate feedback as the AI generates text character by character, creating a more natural and responsive conversation experience.

## Architecture

### Components

1. **WebSocket API Endpoint** (`/ws/chat/{session_id}`)
   - Located in `src/terminal_gpt/api/routes.py`
   - Handles real-time bidirectional communication
   - Supports JSON message format with `{"message": "user input"}`

2. **Streaming LLM Provider** (`OpenRouterProvider.generate_stream()`)
   - Located in `src/terminal_gpt/infrastructure/llm_providers.py`
   - Provides asynchronous streaming responses from OpenRouter API
   - Handles retry logic and error management

3. **Streaming Orchestrator** (`ConversationOrchestrator.process_user_message_stream()`)
   - Located in `src/terminal_gpt/application/orchestrator.py`
   - Manages conversation state for streaming responses
   - Handles tool calls and context management

4. **Streaming CLI Client** (`src/terminal_gpt/cli/streaming_client.py`)
   - Provides interactive terminal interface with real-time responses
   - Displays streaming output character by character
   - Supports session management and error handling

5. **Test Suite** (`test_streaming.py`)
   - Comprehensive testing of streaming functionality
   - Tests WebSocket connections, multiple sessions, and error scenarios
   - Provides performance metrics and validation

## Usage

### Starting the API Server

```bash
# Start the API server with streaming support
uvicorn src.terminal_gpt.api.routes:app --reload --host 0.0.0.0 --port 8000
```

### Using the Streaming CLI Client

```bash
# Start streaming chat session
python -m src.terminal_gpt.cli.streaming_client chat

# Start with specific session
python -m src.terminal_gpt.cli.streaming_client chat --session my_session

# Use custom WebSocket URL
python -m src.terminal_gpt.cli.streaming_client chat --api-url ws://localhost:8000
```

### Available Commands

- `/help` - Show help information
- `/clear` - Clear the terminal screen
- `/session <id>` - Switch to a different session
- `/new <id>` - Create a new conversation session
- `/quit` or `/exit` - Exit the application

## Message Format

### Client to Server

```json
{
  "message": "Your message here"
}
```

### Server to Client

#### Response Chunks

```json
{
  "type": "chunk",
  "content": "Generated text chunk",
  "finish_reason": null,
  "model": "openai/gpt-3.5-turbo",
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  },
  "tools_used": []
}
```

#### Completion

```json
{
  "type": "complete",
  "processing_time_ms": 2500
}
```

#### Errors

```json
{
  "type": "error",
  "error": "Error message",
  "error_details": "Additional error information"
}
```

## Benefits

### User Experience
- **Immediate Feedback**: Users see responses as they're generated
- **Reduced Perceived Latency**: No waiting for complete response
- **Natural Conversation Flow**: Mimics real-time human conversation
- **Better Engagement**: More interactive and responsive interface

### Technical Advantages
- **Resource Efficiency**: No need to buffer entire responses
- **Scalability**: Better handling of long responses
- **Error Handling**: Real-time error detection and reporting
- **Session Management**: Persistent conversation state across requests

## Implementation Details

### WebSocket Connection Management

The streaming client establishes a persistent WebSocket connection to the server:

```python
async with websockets.connect(websocket_url) as websocket:
    await websocket.send(json.dumps({"message": user_input}))
    
    while True:
        response = await websocket.recv()
        data = json.loads(response)
        
        if data["type"] == "chunk":
            # Display streaming content
            print(data["content"], end="", flush=True)
        elif data["type"] == "complete":
            # Response finished
            break
```

### Error Handling

The implementation includes comprehensive error handling for:

- **Connection Issues**: Server unavailable, network problems
- **Invalid Sessions**: Non-existent or expired sessions
- **Empty Messages**: Validation of user input
- **Timeouts**: Response time limits and graceful handling
- **Protocol Errors**: Invalid WebSocket messages or format issues

### Session Management

Sessions are managed through the session ID in the WebSocket URL path:

- Sessions are automatically created when first accessed
- Session state persists across multiple messages
- Conversation history is maintained for context
- Sessions can be switched or created on demand

## Testing

### Running Tests

```bash
# Run comprehensive streaming tests
python test_streaming.py

# Test specific functionality
python test_streaming.py --test streaming_response
python test_streaming.py --test multiple_sessions
python test_streaming.py --test error_handling
```

### Test Coverage

The test suite covers:

- **WebSocket Connectivity**: Connection establishment and message exchange
- **Streaming Response**: Real-time content delivery and display
- **Multiple Sessions**: Concurrent session handling
- **Error Scenarios**: Invalid inputs, connection failures, timeouts
- **Performance**: Response times and throughput metrics

### Test Results

Tests provide detailed output including:

- Connection status and timing
- Response chunk counts and content validation
- Error handling verification
- Performance metrics (processing time, throughput)
- Overall test pass/fail status

## Performance Considerations

### Network Efficiency
- WebSocket connections reduce HTTP overhead
- Streaming reduces memory usage for large responses
- Real-time updates minimize latency

### Resource Management
- Connection pooling for multiple sessions
- Proper cleanup of WebSocket connections
- Memory management for long conversations

### Scalability
- Stateless design allows horizontal scaling
- Session persistence through external storage
- Load balancing support for WebSocket connections

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure API server is running on correct port
   - Check firewall settings for WebSocket traffic
   - Verify WebSocket URL format

2. **Session Not Found**
   - Sessions are created automatically on first use
   - Check session ID format and length
   - Verify session persistence configuration

3. **Streaming Interruptions**
   - Check network stability
   - Monitor server resource usage
   - Review WebSocket timeout settings

4. **Performance Issues**
   - Monitor API response times
   - Check network bandwidth
   - Review LLM provider rate limits

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Multi-Model Support**: Support for different LLM providers with streaming
- **Advanced Tool Calls**: Streaming support for tool execution results
- **Rich Media**: Support for images, code blocks, and formatted content
- **Voice Integration**: Text-to-speech for streaming responses
- **Mobile Support**: WebSocket client for mobile applications

### Performance Improvements
- **Compression**: Enable WebSocket message compression
- **Caching**: Implement response caching for common queries
- **Preloading**: Predictive content loading based on conversation context
- **Optimization**: Fine-tune streaming parameters for different use cases

## Integration

### With Existing CLI
The streaming client can coexist with the existing REST API client:

```bash
# Traditional REST API client
python -m src.terminal_gpt.cli.terminal chat

# Streaming WebSocket client
python -m src.terminal_gpt.cli.streaming_client chat
```

### API Compatibility
The streaming endpoint maintains compatibility with existing REST endpoints:

- Same session management
- Same authentication mechanisms
- Same error handling patterns
- Same plugin and tool integration

## Security Considerations

### WebSocket Security
- Use HTTPS/WSS for production deployments
- Implement proper authentication for WebSocket connections
- Validate and sanitize all incoming messages
- Monitor for WebSocket-specific attack vectors

### Data Privacy
- Ensure conversation privacy in streaming context
- Implement proper session isolation
- Handle sensitive data appropriately in real-time context

This streaming responses feature significantly enhances the user experience of Terminal GPT by providing immediate, real-time feedback during AI conversations, making interactions feel more natural and responsive.