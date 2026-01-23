"""Plugin architecture for Terminal GPT.

This module defines the formal plugin interfaces and base classes
for tool-augmented reasoning.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type
from pydantic import BaseModel

from .exceptions import PluginError, PluginValidationError


class Plugin(ABC):
    """Abstract base class for all plugins.

    Plugins extend Terminal GPT's capabilities through tool-augmented reasoning.
    Each plugin must define:
    - name: Unique identifier
    - description: Human-readable description
    - input_model: Pydantic model for input validation
    - output_model: Pydantic model for output validation
    """

    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]

    def __init__(self):
        """Validate plugin configuration on initialization."""
        if not hasattr(self, 'name') or not self.name:
            raise PluginValidationError("Plugin must define a non-empty name")
        if not hasattr(self, 'description') or not self.description:
            raise PluginValidationError("Plugin must define a description")
        if not hasattr(self, 'input_model') or not self.input_model:
            raise PluginValidationError("Plugin must define an input_model")
        if not hasattr(self, 'output_model') or not self.output_model:
            raise PluginValidationError("Plugin must define an output_model")

        # Validate that models are Pydantic BaseModel subclasses
        if not (isinstance(self.input_model, type) and
                issubclass(self.input_model, BaseModel)):
            raise PluginValidationError("input_model must be a Pydantic BaseModel subclass")

        if not (isinstance(self.output_model, type) and
                issubclass(self.output_model, BaseModel)):
            raise PluginValidationError("output_model must be a Pydantic BaseModel subclass")

    @abstractmethod
    async def run(self, input_data: BaseModel) -> BaseModel:
        """Execute the plugin with validated input.

        Args:
            input_data: Validated input data matching input_model schema

        Returns:
            Validated output data matching output_model schema

        Raises:
            PluginError: If plugin execution fails
        """
        pass

    def get_tool_definition(self) -> Dict[str, Any]:
        """Generate LLM tool definition from Pydantic schemas.

        Returns:
            OpenAI-compatible tool definition for LLM function calling
        """
        try:
            input_schema = self.input_model.model_json_schema()

            # Convert Pydantic schema to OpenAI tool format
            properties = {}
            required = []

            for field_name, field_info in input_schema.get('properties', {}).items():
                # Convert field to OpenAI format
                prop_def = {
                    'type': field_info.get('type', 'string'),
                    'description': field_info.get('description', ''),
                }

                # Handle special types
                if field_info.get('type') == 'array':
                    prop_def['items'] = field_info.get('items', {'type': 'string'})
                elif field_info.get('type') == 'object':
                    prop_def['properties'] = field_info.get('properties', {})

                properties[field_name] = prop_def

                # Check if field is required
                if field_name in input_schema.get('required', []):
                    required.append(field_name)

            tool_def = {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }

            return tool_def

        except Exception as e:
            raise PluginValidationError(
                f"Failed to generate tool definition for plugin {self.name}: {e}"
            )

    async def validate_and_run(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input, run plugin, and validate output.

        This is the main entry point for plugin execution.

        Args:
            raw_input: Raw input data from LLM tool call

        Returns:
            Validated output data as dictionary

        Raises:
            PluginValidationError: If input/output validation fails
            PluginError: If plugin execution fails
        """
        try:
            # Validate input against schema
            validated_input = self.input_model(**raw_input)

        except Exception as e:
            raise PluginValidationError(
                f"Input validation failed for plugin {self.name}: {e}",
                plugin_name=self.name
            )

        try:
            # Execute plugin
            result = await self.run(validated_input)

        except PluginError:
            # Re-raise plugin errors as-is
            raise
        except Exception as e:
            # Wrap other exceptions in PluginError
            raise PluginError(
                f"Plugin {self.name} execution failed: {e}",
                plugin_name=self.name
            ) from e

        try:
            # Validate output (should be BaseModel, convert to dict)
            if isinstance(result, BaseModel):
                return result.model_dump()
            elif isinstance(result, dict):
                # Validate dict against output schema
                validated_output = self.output_model(**result)
                return validated_output.model_dump()
            else:
                raise PluginValidationError(
                    f"Plugin {self.name} returned invalid output type: {type(result)}",
                    plugin_name=self.name
                )

        except Exception as e:
            raise PluginValidationError(
                f"Output validation failed for plugin {self.name}: {e}",
                plugin_name=self.name
            )


class PluginRegistry:
    """Registry for managing plugin instances."""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance.

        Args:
            plugin: Plugin instance to register

        Raises:
            PluginValidationError: If plugin name conflicts
        """
        if plugin.name in self._plugins:
            raise PluginValidationError(
                f"Plugin with name '{plugin.name}' already registered"
            )

        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin:
        """Get a registered plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance

        Raises:
            PluginValidationError: If plugin not found
        """
        if name not in self._plugins:
            raise PluginValidationError(f"Plugin '{name}' not found")

        return self._plugins[name]

    def list_plugins(self) -> Dict[str, str]:
        """List all registered plugins with descriptions.

        Returns:
            Dict mapping plugin names to descriptions
        """
        return {name: plugin.description for name, plugin in self._plugins.items()}

    def list_tools(self) -> list[Dict[str, Any]]:
        """Generate tool definitions for all registered plugins.

        Returns:
            List of OpenAI-compatible tool definitions
        """
        return [plugin.get_tool_definition() for plugin in self._plugins.values()]

    def has_plugin(self, name: str) -> bool:
        """Check if a plugin is registered.

        Args:
            name: Plugin name

        Returns:
            True if plugin exists
        """
        return name in self._plugins

    async def execute_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call by name with arguments.

        Args:
            tool_name: Name of the plugin/tool to execute
            arguments: Arguments for the tool call

        Returns:
            Tool execution result

        Raises:
            PluginValidationError: If tool not found or validation fails
            PluginError: If tool execution fails
        """
        plugin = self.get(tool_name)
        return await plugin.validate_and_run(arguments)


# Global plugin registry instance
plugin_registry = PluginRegistry()
