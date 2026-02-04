# Terminal GPT Plugin System

## Overview

Terminal GPT features a robust, extensible plugin system that allows the AI to interact with external tools and services. Plugins are first-class citizens in the architecture, providing seamless integration between LLM capabilities and real-world functionality.

## 🏗️ Architecture

### Plugin Interface

All plugins implement the `Plugin` interface defined in `src/terminal_gpt/domain/plugins.py`:

```python
@dataclass
class Plugin:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable[..., Any]
    validate_parameters: Optional[Callable[[Dict[str, Any]], bool]] = None
    get_usage_examples: Optional[Callable[[], List[str]]] = None
```

### Key Components

1. **Plugin Discovery** (`src/terminal_gpt/infrastructure/builtin_plugins.py`)
   - Automatic plugin discovery from the `plugins` directory
   - Dynamic loading with error handling
   - Environment-based enablement/disablement

2. **Plugin Execution** (`src/terminal_gpt/application/orchestrator.py`)
   - Central plugin management in the orchestrator
   - Integration with LLM providers
   - Error handling and result formatting

3. **Plugin Output Rendering** (`src/terminal_gpt/cli/enhanced_ui.py`)
   - Standardized output formatting
   - Rich text formatting with color coding
   - Multiple output formats (table, list, tree, text)

## 📦 Built-in Plugins

### File Operations

#### `read_file`
- **Description**: Read and display file contents
- **Parameters**: `path` (string, required), `lines` (integer, optional)
- **Usage**: `Read the contents of src/main.py`
- **Output**: Formatted file content with syntax highlighting

#### `write_file`
- **Description**: Write content to a file
- **Parameters**: `path` (string, required), `content` (string, required)
- **Usage**: `Write "Hello World" to test.txt`
- **Output**: Success/failure status with file path

#### `list_files`
- **Description**: List files and directories
- **Parameters**: `path` (string, required), `recursive` (boolean, optional)
- **Usage**: `List files in the src directory`
- **Output**: Hierarchical file tree or flat list

#### `search_files`
- **Description**: Search for content across files
- **Parameters**: `path` (string, required), `regex` (string, required), `file_pattern` (string, optional)
- **Usage**: `Search for "function" in *.js files`
- **Output**: Table of matching files with context

### Web Services

#### `search_web`
- **Description**: Perform web searches
- **Parameters**: `query` (string, required), `num_results` (integer, optional)
- **Usage**: `Search for latest Python news`
- **Output**: List of search results with URLs

#### `sports`
- **Description**: Get sports scores and schedules
- **Parameters**: `sport` (string, required), `team` (string, optional)
- **Usage**: `Get NBA scores`
- **Output**: Table of games with scores and times

### Calculations

#### `calculate`
- **Description**: Perform mathematical calculations
- **Parameters**: `expression` (string, required)
- **Usage**: `Calculate 2 + 2 * 3`
- **Output**: Calculation result with expression

### System Tools

#### `get_current_time`
- **Description**: Get current time in various formats
- **Parameters**: `timezone` (string, optional), `format` (string, optional)
- **Usage**: `Get current time in New York`
- **Output**: Formatted time string

#### `get_weather`
- **Description**: Get current weather information for any location worldwide
- **Parameters**: `location` (string, required), `units` (string, optional: 'metric', 'imperial', 'kelvin')
- **Usage**: `What's the weather in London?`
- **Output**: Detailed weather information including temperature, conditions, humidity, and wind

## 🌤️ New Plugin: `get_weather`

### Description
Get current weather information for any location worldwide.

### Parameters
- `location` (string, required): City name, coordinates, or postal code
- `units` (string, optional): Temperature units ('metric', 'imperial', 'kelvin')

### Usage Examples
- `What's the weather in London?`
- `Get weather for New York`
- `Show me the temperature in Tokyo`

### Output
Formatted weather information including temperature, conditions, humidity, and wind.

## 🔌 Plugin Development

### Creating a New Plugin

1. **Define the Plugin Function**
```python
def my_plugin_function(param1: str, param2: int) -> str:
    """Description of what the plugin does."""
    # Implementation logic
    return "Result"
```

2. **Create Plugin Registration**
```python
{
    "name": "my_plugin",
    "description": "Description of the plugin",
    "function": my_plugin_function,
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "First parameter"
            },
            "param2": {
                "type": "integer",
                "description": "Second parameter"
            }
        },
        "required": ["param1"]
    }
}
```

3. **Add to Plugin Registry**
Add the plugin to the `PLUGINS` list in `builtin_plugins.py`.

### Plugin Best Practices

#### ✅ Do
- Use clear, descriptive parameter names
- Include comprehensive parameter descriptions
- Handle errors gracefully with informative messages
- Validate input parameters
- Return structured, formatted output
- Follow existing plugin patterns

#### ❌ Don't
- Make blocking network calls without timeouts
- Return raw, unformatted data
- Ignore error conditions
- Use overly complex parameter structures
- Hardcode external service URLs

### Plugin Testing

#### Unit Tests
```python
def test_my_plugin():
    result = my_plugin_function("test", 42)
    assert "expected result" in result
```

#### Integration Tests
```python
def test_plugin_integration():
    # Test plugin through the orchestrator
    response = orchestrator.execute_plugin("my_plugin", {"param1": "test"})
    assert response.success
```

## 🔧 Configuration

### Environment Variables

- `ENABLE_PLUGINS`: Comma-separated list of enabled plugins (default: all)
- `DISABLE_PLUGINS`: Comma-separated list of disabled plugins
- `PLUGIN_TIMEOUT`: Plugin execution timeout in seconds (default: 30)

### Example Configuration
```bash
# Enable only file operations and weather
ENABLE_PLUGINS=read_file,write_file,list_files,get_weather

# Disable web search
DISABLE_PLUGINS=search_web

# Set 60-second timeout
PLUGIN_TIMEOUT=60
```

## 🚀 Plugin Output System

### Output Formats

#### Table Output
For structured data with multiple rows and columns:
```python
ui.print_plugin_output("plugin_name", "table", data, "Title")
```

#### List Output
For sequential data or search results:
```python
ui.print_plugin_output("plugin_name", "list", items, "Results")
```

#### Tree Output
For hierarchical data:
```python
ui.print_plugin_output("plugin_name", "tree", hierarchy, "Structure")
```

#### Text Output
For simple text or JSON data:
```python
ui.print_plugin_output("plugin_name", "text", content, "Output")
```

### Output Styling

- **Color-coded**: Different colors for different plugin types
- **Rich formatting**: Professional appearance with borders and headers
- **Responsive**: Adapts to terminal size
- **Accessible**: Works with various terminal configurations

## 📊 Plugin Metrics

### Performance Monitoring

- **Execution Time**: Track plugin response times
- **Success Rate**: Monitor plugin reliability
- **Usage Frequency**: Track which plugins are most popular
- **Error Patterns**: Identify common failure modes

### Logging

Plugins automatically log:
- Execution start/end times
- Parameter values (sanitized)
- Error conditions with stack traces
- Success/failure status

## 🔮 Future Plugin Ideas

### System Monitoring
- `system_status`: CPU, memory, disk usage
- `process_list`: Running processes
- `network_info`: Network connections and bandwidth

### Development Tools
- `git_status`: Git repository status
- `code_analysis`: Static code analysis
- `dependency_check`: Check for outdated dependencies

### Communication
- `send_email`: Send emails
- `slack_message`: Post to Slack channels
- `discord_message`: Post to Discord channels

### Productivity
- `calendar_events`: Calendar integration
- `task_manager`: Task/todo management
- `note_taker`: Note taking and retrieval

## 🤝 Contributing

### Plugin Submission Process

1. **Create Plugin**: Follow the plugin development guidelines
2. **Write Tests**: Include unit and integration tests
3. **Documentation**: Add usage examples and parameter descriptions
4. **Submit PR**: Create a pull request with your plugin

### Review Criteria

- **Code Quality**: Follow existing patterns and best practices
- **Error Handling**: Robust error handling and user feedback
- **Testing**: Comprehensive test coverage
- **Documentation**: Clear usage examples and parameter descriptions
- **Performance**: Efficient implementation with appropriate timeouts

## 📚 Additional Resources

- [Plugin Interface Documentation](src/terminal_gpt/domain/plugins.py)
- [Built-in Plugin Examples](src/terminal_gpt/infrastructure/builtin_plugins.py)
- [Plugin Testing Examples](tests/unit/test_plugins.py)
- [Plugin Output System](src/terminal_gpt/cli/enhanced_ui.py)

---

**Note**: This plugin system is designed to be extensible and maintainable. New plugins can be added with minimal changes to the core architecture, making it easy to expand Terminal GPT's capabilities over time.