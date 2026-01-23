"""Unit tests for plugin system."""

import pytest
from pydantic import BaseModel

from terminal_gpt.domain.plugins import Plugin, PluginRegistry, plugin_registry
from terminal_gpt.domain.exceptions import PluginValidationError, PluginError


class MockInput(BaseModel):
    """Mock input for testing."""
    value: str


class MockOutput(BaseModel):
    """Mock output for testing."""
    result: str


class MockPlugin(Plugin):
    """Mock plugin for testing."""

    name = "mock_plugin"
    description = "A mock plugin for testing"
    input_model = MockInput
    output_model = MockOutput

    def __init__(self):
        super().__init__()
        self.run_called = False
        self.last_input = None

    async def run(self, input_data: MockInput) -> MockOutput:
        self.run_called = True
        self.last_input = input_data
        return MockOutput(result=f"processed: {input_data.value}")


class TestPlugin:
    """Test basic plugin functionality."""

    def test_plugin_creation(self):
        """Test plugin creation and validation."""
        plugin = MockPlugin()

        assert plugin.name == "mock_plugin"
        assert plugin.description == "A mock plugin for testing"
        assert plugin.input_model == MockInput
        assert plugin.output_model == MockOutput

    def test_plugin_tool_definition(self):
        """Test tool definition generation."""
        plugin = MockPlugin()
        tool_def = plugin.get_tool_definition()

        expected = {
            "type": "function",
            "function": {
                "name": "mock_plugin",
                "description": "A mock plugin for testing",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "description": "",
                        }
                    },
                    "required": ["value"]
                }
            }
        }

        assert tool_def == expected

    @pytest.mark.asyncio
    async def test_plugin_execution(self):
        """Test plugin execution."""
        plugin = MockPlugin()
        input_data = MockInput(value="test input")

        result = await plugin.run(input_data)

        assert plugin.run_called
        assert plugin.last_input == input_data
        assert result.result == "processed: test input"

    @pytest.mark.asyncio
    async def test_plugin_validate_and_run(self):
        """Test validate_and_run method."""
        plugin = MockPlugin()
        raw_input = {"value": "test input"}

        result = await plugin.validate_and_run(raw_input)

        assert result == {"result": "processed: test input"}

    @pytest.mark.asyncio
    async def test_plugin_validation_error(self):
        """Test input validation error."""
        plugin = MockPlugin()

        with pytest.raises(PluginValidationError):
            await plugin.validate_and_run({"invalid_field": "value"})

    @pytest.mark.asyncio
    async def test_plugin_execution_error(self):
        """Test plugin execution error."""

        class FailingPlugin(MockPlugin):
            async def run(self, input_data: MockInput) -> MockOutput:
                raise ValueError("Plugin failed")

        plugin = FailingPlugin()

        with pytest.raises(PluginError):
            await plugin.validate_and_run({"value": "test"})


class TestPluginRegistry:
    """Test plugin registry functionality."""

    def test_registry_creation(self):
        """Test registry creation."""
        registry = PluginRegistry()
        assert len(registry.list_plugins()) == 0

    def test_plugin_registration(self):
        """Test plugin registration."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)

        assert registry.has_plugin("mock_plugin")
        assert registry.list_plugins() == {"mock_plugin": "A mock plugin for testing"}

    def test_duplicate_registration(self):
        """Test duplicate plugin registration fails."""
        registry = PluginRegistry()
        plugin1 = MockPlugin()
        plugin2 = MockPlugin()

        registry.register(plugin1)

        with pytest.raises(PluginValidationError):
            registry.register(plugin2)

    def test_plugin_retrieval(self):
        """Test plugin retrieval."""
        registry = PluginRegistry()
        plugin = MockPlugin()
        registry.register(plugin)

        retrieved = registry.get("mock_plugin")
        assert retrieved is plugin

    def test_missing_plugin_retrieval(self):
        """Test retrieving non-existent plugin fails."""
        registry = PluginRegistry()

        with pytest.raises(PluginValidationError):
            registry.get("non_existent")

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test tool execution through registry."""
        registry = PluginRegistry()
        plugin = MockPlugin()
        registry.register(plugin)

        result = await registry.execute_tool_call("mock_plugin", {"value": "test"})

        assert result == {"result": "processed: test"}

    @pytest.mark.asyncio
    async def test_invalid_tool_execution(self):
        """Test executing invalid tool fails."""
        registry = PluginRegistry()

        with pytest.raises(PluginValidationError):
            await registry.execute_tool_call("invalid_tool", {})

    def test_tool_definitions(self):
        """Test tool definitions generation."""
        registry = PluginRegistry()
        plugin = MockPlugin()
        registry.register(plugin)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "mock_plugin"


class TestGlobalRegistry:
    """Test global plugin registry."""

    def test_global_registry_exists(self):
        """Test global registry is available."""
        assert isinstance(plugin_registry, PluginRegistry)
        # Should be empty initially
        assert len(plugin_registry.list_plugins()) == 0
