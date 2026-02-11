"""Custom exceptions for Terminal GPT domain layer."""

from typing import Optional


class TerminalGPTError(Exception):
    """Base exception for all Terminal GPT errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(TerminalGPTError):
    """Raised when input validation fails."""

    pass


class ConversationError(TerminalGPTError):
    """Raised when conversation state is invalid."""

    pass


class MessageError(TerminalGPTError):
    """Raised when message processing fails."""

    pass


class PluginError(TerminalGPTError):
    """Raised when plugin execution fails."""

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.plugin_name = plugin_name


class LLMError(TerminalGPTError):
    """Raised when LLM API calls fail."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retryable: bool = False,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.provider = provider
        self.retryable = retryable


class ConfigurationError(TerminalGPTError):
    """Raised when configuration is invalid or missing."""

    pass


class ResourceLimitError(TerminalGPTError):
    """Raised when resource limits are exceeded."""

    pass


class SessionError(TerminalGPTError):
    """Raised when session operations fail."""

    pass


# Specific LLM-related errors
class LLMAuthenticationError(LLMError):
    """Raised when LLM authentication fails."""

    pass


class LLMQuotaExceededError(LLMError):
    """Raised when LLM quota/rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, provider, retryable=True, details=details)
        self.retry_after = retry_after


class LLMServiceUnavailableError(LLMError):
    """Raised when LLM service is temporarily unavailable."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, provider, retryable=True, details=details)


class LLMInvalidRequestError(LLMError):
    """Raised when LLM request is malformed."""

    pass


class LLMContentFilterError(LLMError):
    """Raised when LLM content filter blocks the request."""

    pass


# Specific plugin-related errors
class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found."""

    pass


class PluginValidationError(PluginError):
    """Raised when plugin input/output validation fails."""

    pass


class PluginExecutionError(PluginError):
    """Raised when plugin execution fails."""

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        exit_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, plugin_name, details)
        self.exit_code = exit_code


class PluginTimeoutError(PluginError):
    """Raised when plugin execution times out."""

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, plugin_name, details)
        self.timeout_seconds = timeout_seconds


# Conversation-specific errors
class ConversationTooLongError(ConversationError):
    """Raised when conversation exceeds length limits."""

    pass


class ConversationInvalidStateError(ConversationError):
    """Raised when conversation state becomes invalid."""

    pass


# Message-specific errors
class MessageTooLargeError(MessageError):
    """Raised when message content is too large."""

    pass


class MessageInvalidFormatError(MessageError):
    """Raised when message format is invalid."""

    pass


def format_error_response(error: TerminalGPTError) -> dict:
    """Format an error for API responses."""
    response = {
        "error": {
            "type": type(error).__name__,
            "message": error.message,
        }
    }

    if error.details:
        response["error"]["details"] = error.details

    # Add specific fields for certain error types
    if isinstance(error, PluginError) and error.plugin_name:
        response["error"]["plugin_name"] = error.plugin_name

    if isinstance(error, LLMError):
        if error.provider:
            response["error"]["provider"] = error.provider
        response["error"]["retryable"] = str(error.retryable).lower()

    if isinstance(error, LLMQuotaExceededError) and error.retry_after:
        response["error"]["retry_after_seconds"] = str(error.retry_after)

    return response
