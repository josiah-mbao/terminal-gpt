"""LLM provider implementations for Terminal GPT."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from ..domain.exceptions import (
    LLMError, LLMAuthenticationError, LLMQuotaExceededError,
    LLMServiceUnavailableError, LLMInvalidRequestError,
    LLMContentFilterError, ConfigurationError
)
from ..infrastructure.logging import get_logger
from ..application.events import publish_llm_call


logger = get_logger("terminal_gpt.llm")


class LLMResponse(BaseModel):
    """Standardized LLM response format."""

    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str = "openai/gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=60.0),
            headers=self._get_headers()
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API error responses."""
        pass


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider with comprehensive error handling."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-3.5-turbo",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        max_retry_delay: float = 60.0
    ):
        super().__init__(api_key, model)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay

        if not api_key or not api_key.strip():
            raise ConfigurationError("OpenRouter API key is required")

    def _get_headers(self) -> Dict[str, str]:
        """Get OpenRouter API headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/josiah-mbao/terminal-gpt",
            "X-Title": "Terminal GPT",
        }

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Generate response from OpenRouter with retry logic."""
        if not self._client:
            raise LLMError("Provider not properly initialized. Use async context manager.")

        config = config or {}
        start_time = time.time()

        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
            "top_p": config.get("top_p", 1.0),
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                # Make API request
                response = await self._client.post(
                    f"{self.BASE_URL}/chat/completions",
                    json=payload
                )

                # Handle HTTP errors
                if response.status_code != 200:
                    self._handle_error(response)
                    continue  # Should not reach here due to exception

                # Parse successful response
                response_data = response.json()
                result = self._parse_response(response_data)

                # Publish success event
                duration_ms = int((time.time() - start_time) * 1000)
                await publish_llm_call(
                    provider="openrouter",
                    model=self.model,
                    tokens_used=result.usage.get("total_tokens", 0) if result.usage else 0,
                    success=True,
                    duration_ms=duration_ms
                )

                return result

            except (LLMAuthenticationError, LLMInvalidRequestError) as e:
                # Don't retry these errors
                await publish_llm_call(
                    provider="openrouter",
                    model=self.model,
                    tokens_used=0,
                    success=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                    error=str(e)
                )
                raise

            except (LLMQuotaExceededError, LLMServiceUnavailableError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = min(
                        self.retry_delay * (2 ** attempt),
                        self.max_retry_delay
                    )
                    logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Publish failure event
                    await publish_llm_call(
                        provider="openrouter",
                        model=self.model,
                        tokens_used=0,
                        success=False,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error=str(e)
                    )
                    raise

            except Exception as e:
                last_exception = LLMError(f"Unexpected error: {e}")
                if attempt < self.max_retries:
                    delay = min(
                        self.retry_delay * (2 ** attempt),
                        self.max_retry_delay
                    )
                    logger.warning(
                        f"Unexpected LLM error (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    await publish_llm_call(
                        provider="openrouter",
                        model=self.model,
                        tokens_used=0,
                        success=False,
                        duration_ms=int((time.time() - start_time) * 1000),
                        error=str(e)
                    )
                    raise last_exception

        # Should not reach here
        raise last_exception or LLMError("All retry attempts exhausted")

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle OpenRouter API error responses."""
        try:
            error_data = response.json()
            error_code = error_data.get("error", {}).get("code", "unknown")
            error_message = error_data.get("error", {}).get("message", "Unknown error")
        except:
            error_code = "unknown"
            error_message = f"HTTP {response.status_code}: {response.text[:200]}"

        # Map error codes to appropriate exceptions
        if response.status_code == 401:
            raise LLMAuthenticationError(f"Authentication failed: {error_message}")
        elif response.status_code == 429:
            # Try to extract retry-after header
            retry_after = None
            if "retry-after" in response.headers:
                try:
                    retry_after = int(response.headers["retry-after"])
                except ValueError:
                    pass

            raise LLMQuotaExceededError(
                f"Rate limit exceeded: {error_message}",
                provider="openrouter",
                retry_after=retry_after
            )
        elif response.status_code >= 500:
            raise LLMServiceUnavailableError(
                f"OpenRouter service error: {error_message}",
                provider="openrouter"
            )
        elif response.status_code == 400:
            raise LLMInvalidRequestError(f"Invalid request: {error_message}")
        elif error_code == "content_filter":
            raise LLMContentFilterError(f"Content filter triggered: {error_message}")
        else:
            raise LLMError(
                f"OpenRouter API error ({response.status_code}): {error_message}",
                provider="openrouter"
            )

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse OpenRouter API response."""
        try:
            choice = response_data["choices"][0]
            message = choice["message"]

            # Extract tool calls if present
            tool_calls = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    }
                    for tc in message["tool_calls"]
                ]

            return LLMResponse(
                content=message.get("content", ""),
                model=response_data.get("model", self.model),
                finish_reason=choice.get("finish_reason"),
                usage=response_data.get("usage"),
                tool_calls=tool_calls
            )

        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response format from OpenRouter: {e}")


# Provider factory
def create_llm_provider(
    provider_name: str,
    api_key: str,
    model: str = "openai/gpt-3.5-turbo",
    **kwargs
) -> LLMProvider:
    """Factory function to create LLM providers."""
    if provider_name.lower() == "openrouter":
        return OpenRouterProvider(api_key=api_key, model=model, **kwargs)
    else:
        raise ConfigurationError(f"Unknown LLM provider: {provider_name}")


__all__ = [
    "LLMProvider",
    "OpenRouterProvider",
    "LLMResponse",
    "create_llm_provider",
]
