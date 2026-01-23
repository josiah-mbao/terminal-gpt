"""Security-first structured logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional, Any

import structlog
from pythonjsonlogger import jsonlogger

from ..domain.exceptions import ConfigurationError


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format ('json' or 'text')
        log_file: Optional file path for file logging
        enable_console: Whether to enable console logging

    Raises:
        ConfigurationError: If logging configuration is invalid
    """
    try:
        # Convert string level to logging constant
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ConfigurationError(f"Invalid log level: {level}")

        # Configure standard library logging
        logging.basicConfig(
            level=numeric_level,
            format="%(message)s",  # structlog handles formatting
            stream=sys.stdout if enable_console else None,
            force=True  # Override any existing configuration
        )

        # Shared processors for both formats
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_request_id,
            _sanitize_sensitive_data,
            structlog.processors.JSONRenderer()
            if format_type == "json"
            else structlog.processors.KeyValueRenderer(key_order=[
                "timestamp", "level", "request_id", "event", "logger"
            ]),
        ]

        # Configure structlog
        structlog.configure(
            processors=shared_processors,
            wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
            context_class=dict,
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure file logging if specified
        if log_file:
            _configure_file_logging(log_file, format_type, numeric_level)

        # Suppress noisy third-party logs
        _suppress_third_party_logs()

    except Exception as e:
        # Fallback to basic logging if configuration fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logging.error(f"Failed to configure structured logging: {e}")
        raise ConfigurationError(f"Logging configuration failed: {e}")


def _add_request_id(logger, method_name, event_dict):
    """Add request ID to log entries if available."""
    # This would be populated by middleware in a web context
    # For now, we'll use a simple session-based approach
    import threading
    request_id = getattr(threading.current_thread(), 'request_id', None)
    if request_id:
        event_dict['request_id'] = request_id
    return event_dict


def _sanitize_sensitive_data(logger, method_name, event_dict):
    """
    Sanitize sensitive data from log entries.

    This prevents accidental logging of API keys, passwords, etc.
    """
    sensitive_keys = {
        'api_key', 'apikey', 'password', 'token', 'secret',
        'authorization', 'bearer', 'openrouter_api_key'
    }

    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"

    # Also check nested dictionaries
    for key, value in event_dict.items():
        if isinstance(value, dict):
            event_dict[key] = _sanitize_dict(value, sensitive_keys)

    return event_dict


def _sanitize_dict(data: dict, sensitive_keys: set) -> dict:
    """Recursively sanitize a dictionary."""
    sanitized = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_dict(value, sensitive_keys)
        else:
            sanitized[key] = value
    return sanitized


def _configure_file_logging(log_file: str, format_type: str, level: int) -> None:
    """Configure file logging."""
    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)

        if format_type == "json":
            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s"
            )
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    except Exception as e:
        logging.warning(f"Failed to configure file logging: {e}")


def _suppress_third_party_logs():
    """Suppress noisy logs from third-party libraries."""
    # Common noisy libraries
    noisy_loggers = [
        "httpx",
        "urllib3",
        "urllib3.connectionpool",
        "openai",
        "asyncio",
        "websockets",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


# Convenience functions for structured logging
def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_request_start(request_id: str, method: str, path: str, **kwargs):
    """Log the start of a request."""
    logger = get_logger("terminal_gpt.api")
    logger.info(
        "Request started",
        request_id=request_id,
        method=method,
        path=path,
        **kwargs
    )


def log_request_end(request_id: str, status_code: int, duration_ms: float, **kwargs):
    """Log the end of a request."""
    logger = get_logger("terminal_gpt.api")
    level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
    getattr(logger, level)(
        "Request completed",
        request_id=request_id,
        status_code=status_code,
        duration_ms=duration_ms,
        **kwargs
    )


def log_plugin_execution(plugin_name: str, success: bool, duration_ms: float, **kwargs):
    """Log plugin execution."""
    logger = get_logger("terminal_gpt.plugin")
    level = "info" if success else "error"
    getattr(logger, level)(
        "Plugin executed",
        plugin_name=plugin_name,
        success=success,
        duration_ms=duration_ms,
        **kwargs
    )


def log_llm_call(provider: str, success: bool,
                 tokens_used: Optional[int] = None, **kwargs):
    """Log LLM API calls."""
    logger = get_logger("terminal_gpt.llm")
    level = "info" if success else "warning"
    log_data = {
        "provider": provider,
        "success": success,
        **kwargs
    }
    if tokens_used is not None:
        log_data["tokens_used"] = tokens_used

    getattr(logger, level)("LLM call completed", **log_data)
