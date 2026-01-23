# Terminal GPT

A terminal & web-ready LLM chat system with a formal plugin architecture, built with Python and FastAPI.

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Terminal GPT is a modular, extensible LLM-powered chat platform designed to run initially as a terminal application, with a clear and intentional path to a web/browser-based UI. It integrates with OpenRouter to access free and low-cost LLMs and supports tool-augmented reasoning via a formal plugin architecture.

### Key Features

- **Multi-turn conversational chat** with persistent sessions
- **Plugin architecture** for tool-augmented reasoning
- **OpenRouter integration** for flexible LLM access
- **Terminal-first UI** with rich formatting
- **FastAPI backend** enabling web UI development
- **Append-only conversations** with intelligent context management
- **Failure-resilient design** with graceful degradation
- **Security-first** with input validation and sandboxing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Terminal UI (CLI)                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Rich Terminal Display  │  Input Handling  │  Commands  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP/WebSocket
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  REST API  │  WebSocket  │  Session Mgmt  │  Health     │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Async Method Calls
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Chat Orchestrator                           │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  State Mgmt │  Tool Reg  │  Prompt Asm  │  Exec Flow    │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Structured Data
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Domain Layer                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  Conversation│  Plugin   │  Message     │  Validation   │  │
│  │  State       │  System   │  Schemas     │  & Security   │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Abstract Interfaces
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Infrastructure Layer                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  OpenRouter │  Config   │  Logging      │  Storage      │  │
│  │  Provider   │  Mgmt     │  & Monitoring │  (Future)     │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

- **UI-agnostic backend**: Clean separation enables multiple frontends
- **LLM-first architecture**: Built around conversational AI capabilities
- **Formal plugin contracts**: Pydantic schemas ensure type safety
- **FastAPI-native async**: Modern Python async throughout
- **Web portability**: Backend ready for browser-based UI
- **Failure-first design**: Reliability built into every component
- **Append-only conversations**: Immutable history with event-driven failures

## Installation

### Prerequisites

- Python 3.11 or higher
- OpenRouter API key ([get one here](https://openrouter.ai/))

### Quick Start

1. **Clone and setup:**
   ```bash
   git clone https://github.com/josiah-mbao/terminal-gpt.git
   cd terminal-gpt
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your OPENROUTER_API_KEY
   ```

3. **Run the terminal chat:**
   ```bash
   terminal-gpt
   ```

### Development Setup

```bash
pip install -e ".[dev]"
pre-commit install
pytest
```

## Usage

### Terminal Interface

Start a conversation:
```bash
terminal-gpt
```

The interface supports:
- Multi-line input (Ctrl+D to send)
- Rich formatting for responses
- Command shortcuts
- Error display with recovery options

### API Server

Run the FastAPI server:
```bash
uvicorn src.terminal_gpt.api.routes:app --reload
```

API endpoints:
- `POST /chat` - Send messages
- `GET /health` - Health check
- `WebSocket /ws/chat` - Real-time chat (future)

### Example Conversation

```
You: Hello! Can you help me read a file?

Assistant: I'd be happy to help you read a file. I have access to a read_file tool that can help with that. Could you please tell me the path to the file you'd like me to read?

You: /path/to/my/file.txt

Assistant: Let me read that file for you.

[Tool Call: read_file]
Reading file: /path/to/my/file.txt

[Tool Result]
Content:
This is the content of your file.
It has multiple lines.
And some interesting text.

Assistant: I've successfully read the file. Here's what it contains:

```
This is the content of your file.
It has multiple lines.
And some interesting text.
```

Is there anything else you'd like me to help you with?
```

## Plugin Architecture

### Overview

Plugins extend the system's capabilities through tool-augmented reasoning. Each plugin:

- Has formal input/output schemas (Pydantic models)
- Is automatically registered with the LLM
- Executes in isolated, validated environments
- Returns structured results injected into conversations

### Built-in Plugins

- **read_file**: Read text files from disk
- **write_file**: Write content to files
- **list_directory**: List directory contents
- **calculator**: Perform mathematical calculations

### Developing Plugins

Create a plugin by implementing the `Plugin` interface:

```python
from pydantic import BaseModel
from terminal_gpt.domain.plugins import Plugin

class ReadFileInput(BaseModel):
    path: str

class ReadFileOutput(BaseModel):
    content: str

class ReadFilePlugin(Plugin):
    name = "read_file"
    description = "Reads a text file from disk"
    input_model = ReadFileInput
    output_model = ReadFileOutput

    async def run(self, input: ReadFileInput) -> ReadFileOutput:
        content = Path(input.path).read_text()
        return ReadFileOutput(content=content)
```

Register in `src/terminal_gpt/infrastructure/config.py`:

```python
PLUGINS = [
    ReadFilePlugin(),
    # ... other plugins
]
```

## Configuration

Environment variables control system behavior:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | *Required* |
| `DEFAULT_MODEL` | LLM model to use | `openai/gpt-3.5-turbo` |
| `MAX_TOKENS` | Maximum response tokens | `4096` |
| `TEMPERATURE` | Response creativity (0.0-1.0) | `0.7` |
| `MAX_CONVERSATION_LENGTH` | Max messages in history | `100` |
| `SLIDING_WINDOW_SIZE` | Context window size | `50` |

## API Reference

### Chat Endpoint

```http
POST /chat
Content-Type: application/json

{
  "session_id": "string",
  "message": "string"
}
```

Response:
```json
{
  "reply": "Assistant response with any tool results",
  "session_id": "string",
  "tools_used": ["tool_name"],
  "status": "success|degraded|error"
}
```

### Error Handling

The system uses structured error responses:

```json
{
  "error": {
    "type": "validation_error|llm_error|plugin_error",
    "message": "Human-readable error description",
    "details": {
      "field": "specific_field_name",
      "value": "provided_value"
    }
  },
  "session_id": "string"
}
```

## Development

### Project Structure

```
terminal-gpt/
├── src/terminal_gpt/
│   ├── domain/           # Core business logic
│   │   ├── models.py     # Data models & schemas
│   │   ├── plugins.py    # Plugin interfaces
│   │   └── exceptions.py # Custom exceptions
│   ├── infrastructure/   # External integrations
│   │   ├── llm_providers.py
│   │   └── config.py
│   ├── application/      # Use cases & orchestration
│   │   ├── orchestrator.py
│   │   └── events.py
│   ├── api/             # FastAPI routes & deps
│   └── cli/             # Terminal interface
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] Web UI implementation
- [ ] Persistent conversation storage
- [ ] User authentication & multi-tenancy
- [ ] Advanced plugin marketplace
- [ ] Voice input/output support
- [ ] Multi-language support
- [ ] Plugin permission system
