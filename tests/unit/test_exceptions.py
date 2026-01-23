"""Unit tests for exception hierarchy."""

import pytest
from terminal_gpt.domain.exceptions import (
    TerminalGPTError,
    ValidationError,
    PluginError,
    LLMError,
    ConfigurationError,
    ResourceLimitError,
    SessionError,
    LLMAuthenticationError,
    LLMQuotaExceededError,
    LLMServiceUnavailableError,
    PluginValidationError,
    PluginExecutionError,
    PluginTimeoutError,
    ConversationTooLongError,
    ConversationInvalidStateError,
    MessageTooLargeError,
    MessageInvalidFormatError,
    format_error_response
)


class TestExceptionHierarchy:
    """Test exception class hierarchy and initialization."""

    def test_base_exception_creation(self):
        """Test TerminalGPTError base class."""
        error = TerminalGPTError("Test message", {"code": "TEST"})

        assert error.message == "Test message"
        assert error.details == {"code": "TEST"}
        assert str(error) == "Test message"

    def test_base_exception_empty_details(self):
        """Test TerminalGPTError with no details."""
        error = TerminalGPTError("Test message")

        assert error.message == "Test message"
        assert error.details == {}

    def test_validation_error(self):
        """Test ValidationError subclass."""
        error = ValidationError("Invalid input")

        assert isinstance(error, TerminalGPTError)
        assert error.message == "Invalid input"

    def test_plugin_error_with_name(self):
        """Test PluginError with plugin name."""
        error = PluginError("Plugin failed", plugin_name="calculator")

        assert isinstance(error, TerminalGPTError)
        assert error.message == "Plugin failed"
        assert error.plugin_name == "calculator"

    def test_plugin_error_without_name(self):
        """Test PluginError without plugin name."""
        error = PluginError("Plugin failed")

        assert error.plugin_name is None

    def test_llm_error_with_provider(self):
        """Test LLMError with provider information."""
        error = LLMError("LLM failed", provider="openai", retryable=True)

        assert isinstance(error, TerminalGPTError)
        assert error.message == "LLM failed"
        assert error.provider == "openai"
        assert error.retryable is True

    def test_llm_error_defaults(self):
        """Test LLMError default values."""
        error = LLMError("LLM failed")

        assert error.provider is None
        assert error.retryable is False

    def test_specific_llm_errors(self):
        """Test specific LLM error subclasses."""
        auth_error = LLMAuthenticationError("Auth failed", provider="openai")
        quota_error = LLMQuotaExceededError("Quota exceeded", provider="openai",
                                           retry_after=60)
        service_error = LLMServiceUnavailableError("Service down", provider="openai")

        assert isinstance(auth_error, LLMError)
        assert isinstance(quota_error, LLMError)
        assert isinstance(service_error, LLMError)

        assert auth_error.retryable is False  # Auth errors are not retryable
        assert quota_error.retryable is True  # Quota errors are retryable
        assert service_error.retryable is True  # Service errors are retryable

        assert quota_error.retry_after == 60

    def test_plugin_specific_errors(self):
        """Test plugin-specific error subclasses."""
        validation_error = PluginValidationError("Invalid input", plugin_name="calc")
        execution_error = PluginExecutionError("Exec failed", plugin_name="calc",
                                              exit_code=1)
        timeout_error = PluginTimeoutError("Timeout", plugin_name="calc",
                                          timeout_seconds=30)

        assert isinstance(validation_error, PluginError)
        assert isinstance(execution_error, PluginError)
        assert isinstance(timeout_error, PluginError)

        assert execution_error.exit_code == 1
        assert timeout_error.timeout_seconds == 30

    def test_conversation_errors(self):
        """Test conversation-specific errors."""
        too_long_error = ConversationTooLongError("Conversation too long")
        invalid_state_error = ConversationInvalidStateError("Invalid state")

        assert isinstance(too_long_error, TerminalGPTError)
        assert isinstance(invalid_state_error, TerminalGPTError)

    def test_message_errors(self):
        """Test message-specific errors."""
        too_large_error = MessageTooLargeError("Message too large")
        invalid_format_error = MessageInvalidFormatError("Invalid format")

        assert isinstance(too_large_error, TerminalGPTError)
        assert isinstance(invalid_format_error, TerminalGPTError)

    def test_other_errors(self):
        """Test configuration and resource errors."""
        config_error = ConfigurationError("Config invalid")
        resource_error = ResourceLimitError("Resource limit exceeded")
        session_error = SessionError("Session error")

        assert isinstance(config_error, TerminalGPTError)
        assert isinstance(resource_error, TerminalGPTError)
        assert isinstance(session_error, TerminalGPTError)


class TestErrorFormatting:
    """Test error response formatting for APIs."""

    def test_format_base_error(self):
        """Test formatting a basic error."""
        error = TerminalGPTError("Something went wrong", {"code": "TEST"})

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "TerminalGPTError",
                "message": "Something went wrong",
                "details": {"code": "TEST"}
            }
        }

        assert response == expected

    def test_format_error_without_details(self):
        """Test formatting error without details."""
        error = TerminalGPTError("Error message")

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "TerminalGPTError",
                "message": "Error message",
                "details": {}
            }
        }

        assert response == expected

    def test_format_plugin_error(self):
        """Test formatting plugin error with name."""
        error = PluginError("Plugin failed", plugin_name="calculator",
                           details={"input": "invalid"})

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "PluginError",
                "message": "Plugin failed",
                "details": {"input": "invalid"},
                "plugin_name": "calculator"
            }
        }

        assert response == expected

    def test_format_plugin_error_no_name(self):
        """Test formatting plugin error without name."""
        error = PluginError("Plugin failed")

        response = format_error_response(error)

        assert "plugin_name" not in response["error"]

    def test_format_llm_error_full(self):
        """Test formatting LLM error with all fields."""
        error = LLMError("LLM failed", provider="openai", retryable=True,
                        details={"request_id": "123"})

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "LLMError",
                "message": "LLM failed",
                "details": {"request_id": "123"},
                "provider": "openai",
                "retryable": "true"
            }
        }

        assert response == expected

    def test_format_llm_error_minimal(self):
        """Test formatting minimal LLM error."""
        error = LLMError("LLM failed")

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "LLMError",
                "message": "LLM failed",
                "details": {},
                "retryable": "false"
            }
        }

        assert response == expected

    def test_format_quota_error_with_retry(self):
        """Test formatting quota error with retry information."""
        error = LLMQuotaExceededError("Quota exceeded", provider="openai",
                                     retry_after=300)

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "LLMQuotaExceededError",
                "message": "Quota exceeded",
                "details": {},
                "provider": "openai",
                "retryable": "true",
                "retry_after_seconds": "300"
            }
        }

        assert response == expected

    def test_format_quota_error_no_retry(self):
        """Test formatting quota error without retry info."""
        error = LLMQuotaExceededError("Quota exceeded")

        response = format_error_response(error)

        assert "retry_after_seconds" not in response["error"]

    def test_format_complex_error(self):
        """Test formatting a complex error with all fields."""
        error = PluginExecutionError(
            "Plugin execution failed",
            plugin_name="calculator",
            exit_code=2,
            details={
                "input": "2 + 2",
                "expected": "4",
                "got": "error"
            }
        )

        response = format_error_response(error)

        expected = {
            "error": {
                "type": "PluginExecutionError",
                "message": "Plugin execution failed",
                "details": {
                    "input": "2 + 2",
                    "expected": "4",
                    "got": "error"
                },
                "plugin_name": "calculator"
            }
        }

        assert response == expected
