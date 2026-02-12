"""LLM provider implementations for Terminal GPT."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from pydantic import BaseModel

from ..application.events import publish_llm_call
from ..domain.exceptions import (
    ConfigurationError,
    LLMAuthenticationError,
    LLMContentFilterError,
    LLMError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMServiceUnavailableError,
)
from ..infrastructure.logging import get_logger

logger = get_logger("terminal_gpt.llm")


class LLMResponse(BaseModel):
    """Standardized LLM response format."""

    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None  # OpenRouter returns complex nested data
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str, model: str = "openai/gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        # Increased timeouts for long streaming responses (Session Stability Fix)
        timeout = httpx.Timeout(60.0, read=180.0)  # 60s connect, 180s read
        self._client = httpx.AsyncClient(timeout=timeout, headers=self._get_headers())
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
        config: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate response from LLM."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate streaming response from LLM."""
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
        max_retry_delay: float = 60.0,
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
        config: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate response from OpenRouter with retry logic."""
        if not self._client:
            raise LLMError(
                "Provider not properly initialized. Use async context manager."
            )

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
                logger.debug(
                    "Making OpenRouter API request",
                    attempt=attempt + 1,
                    model=self.model,
                    messages_count=len(messages),
                    tools_count=len(tools) if tools else 0,
                )

                # Make API request
                response = await self._client.post(
                    f"{self.BASE_URL}/chat/completions", json=payload
                )

                logger.debug(
                    "OpenRouter API response received",
                    status_code=response.status_code,
                    attempt=attempt + 1,
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
                    tokens_used=(
                        result.usage.get("total_tokens", 0) if result.usage else 0
                    ),
                    success=True,
                    duration_ms=duration_ms,
                )

                return result

            except (LLMAuthenticationError, LLMInvalidRequestError):
                # Don't retry these errors
                await publish_llm_call(
                    provider="openrouter",
                    model=self.model,
                    tokens_used=0,
                    success=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                raise

            except (LLMQuotaExceededError, LLMServiceUnavailableError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = min(self.retry_delay * (2**attempt), self.max_retry_delay)
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
                    )
                    raise

            except Exception as e:
                last_exception = LLMError(f"Unexpected error: {e}")
                if attempt < self.max_retries:
                    delay = min(self.retry_delay * (2**attempt), self.max_retry_delay)
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
                    )
                    raise last_exception

        # Should not reach here
        raise last_exception or LLMError("All retry attempts exhausted")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate streaming response from OpenRouter with retry logic."""
        if not self._client:
            raise LLMError(
                "Provider not properly initialized. Use async context manager."
            )

        config = config or {}
        start_time = time.time()

        # Prepare request payload with streaming enabled
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096),
            "top_p": config.get("top_p", 1.0),
            "stream": True,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Log API key validation
        logger.info(
            "OpenRouter provider initialized",
            model=self.model,
            api_key_preview=f"{self.api_key[:8]}...",
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
        )

        # Log the request payload (sanitized)
        logger.info(
            "OpenRouter streaming request payload",
            model=payload["model"],
            messages_count=len(messages),
            tools_count=len(tools) if tools else 0,
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
            stream=payload["stream"],
        )

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.warning(
                    f"Making OpenRouter streaming API request "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})",
                    attempt=attempt + 1,
                    model=self.model,
                    messages_count=len(messages),
                    tools_count=len(tools) if tools else 0,
                )

                # Make streaming API request
                response = await self._client.post(
                    f"{self.BASE_URL}/chat/completions", json=payload
                )

                # Log full response details including headers for rate limit debugging
                logger.warning(
                    "OpenRouter streaming API response received",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    headers=dict(response.headers),
                    url=str(response.url),
                )

                # Log rate limit headers specifically
                rate_limit_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if "rate" in k.lower()
                    or "limit" in k.lower()
                    or "retry" in k.lower()
                }
                if rate_limit_headers:
                    logger.error(
                        "Rate limit headers detected",
                        rate_limit_headers=rate_limit_headers,
                    )

                # Handle HTTP errors
                if response.status_code != 200:
                    self._handle_error(response)
                    continue  # Should not reach here due to exception

                # Process streaming response
                async for chunk in self._parse_stream_response(response):
                    yield chunk

                # Publish success event
                duration_ms = int((time.time() - start_time) * 1000)
                await publish_llm_call(
                    provider="openrouter",
                    model=self.model,
                    tokens_used=0,  # Streaming doesn't provide usage until end
                    success=True,
                    duration_ms=duration_ms,
                )

                return

            except (LLMAuthenticationError, LLMInvalidRequestError):
                # Don't retry these errors
                await publish_llm_call(
                    provider="openrouter",
                    model=self.model,
                    tokens_used=0,
                    success=False,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                raise

            except (LLMQuotaExceededError, LLMServiceUnavailableError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = min(self.retry_delay * (2**attempt), self.max_retry_delay)
                    logger.warning(
                        f"LLM streaming request failed (attempt {attempt + 1}/{self.max_retries + 1}), "
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
                    )
                    raise

            except Exception as e:
                last_exception = LLMError(f"Unexpected error: {e}")
                if attempt < self.max_retries:
                    delay = min(self.retry_delay * (2**attempt), self.max_retry_delay)
                    logger.warning(
                        f"Unexpected LLM streaming error (attempt {attempt + 1}/{self.max_retries + 1}), "
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
                    )
                    raise last_exception

        # Should not reach here
        raise last_exception or LLMError("All retry attempts exhausted")

    async def _parse_stream_response(
        self, response: httpx.Response
    ) -> AsyncGenerator[LLMResponse, None]:
        """Parse OpenRouter streaming response with tool call accumulation."""

        # Buffer for accumulating fragmented tool calls across chunks
        # Keyed by tool call index to handle multiple parallel tool calls
        tool_call_buffers: Dict[int, Dict[str, Any]] = {}

        async for line in response.aiter_lines():
            if not line:
                continue

            # Handle Server-Sent Events format
            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix

                if data == "[DONE]":
                    break

                try:
                    # Parse JSON data
                    parsed_data = json.loads(data)

                    # Handle mid-stream errors
                    if "error" in parsed_data:
                        error_msg = parsed_data["error"].get(
                            "message", "Unknown streaming error"
                        )
                        raise LLMError(f"Streaming error: {error_msg}")

                    # Extract content from chunk
                    choice = parsed_data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})

                    content = delta.get("content", "")
                    finish_reason = choice.get("finish_reason")

                    # Accumulate tool calls from delta
                    if "tool_calls" in delta and delta["tool_calls"]:
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)

                            # Initialize buffer for this tool call index if not exists
                            if idx not in tool_call_buffers:
                                tool_call_buffers[idx] = {
                                    "id": tc.get(
                                        "id", f"call_{idx}_{int(time.time() * 1000)}"
                                    ),
                                    "type": tc.get("type", "function"),
                                    "function": {"name": "", "arguments": ""},
                                }

                            # Accumulate function name and arguments incrementally
                            fn = tc.get("function", {})
                            if "name" in fn:
                                tool_call_buffers[idx]["function"]["name"] = fn["name"]
                            if "arguments" in fn:
                                tool_call_buffers[idx]["function"]["arguments"] += fn[
                                    "arguments"
                                ]

                    # Yield chunk if it has content
                    if content:
                        yield LLMResponse(
                            content=content,
                            model=parsed_data.get("model", self.model),
                            finish_reason=None,  # Don't signal finish until we know it's complete
                            usage=parsed_data.get("usage"),
                            tool_calls=None,  # Don't yield partial tool calls
                        )

                    # When finish_reason is tool_calls, yield the complete accumulated tool calls
                    if finish_reason == "tool_calls":
                        if tool_call_buffers:
                            yield LLMResponse(
                                content="",
                                model=parsed_data.get("model", self.model),
                                finish_reason=finish_reason,
                                usage=parsed_data.get("usage"),
                                tool_calls=list(tool_call_buffers.values()),
                            )
                        else:
                            # Unexpected: finish_reason is tool_calls but no tool calls accumulated
                            logger.warning(
                                "finish_reason is 'tool_calls' but no tool calls were accumulated"
                            )
                    elif finish_reason:
                        # Other finish reasons (stop, length, etc.)
                        yield LLMResponse(
                            content="",
                            model=parsed_data.get("model", self.model),
                            finish_reason=finish_reason,
                            usage=parsed_data.get("usage"),
                            tool_calls=None,
                        )

                except json.JSONDecodeError:
                    # Skip invalid JSON lines (like SSE comments)
                    continue
                except Exception as e:
                    raise LLMError(f"Error parsing streaming response: {e}")

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle OpenRouter API error responses."""
        try:
            error_data = response.json()
            error_code = error_data.get("error", {}).get("code", "unknown")
            error_message = error_data.get("error", {}).get("message", "Unknown error")
        except Exception:
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
                retry_after=retry_after,
            )
        elif response.status_code >= 500:
            raise LLMServiceUnavailableError(
                f"OpenRouter service error: {error_message}", provider="openrouter"
            )
        elif response.status_code == 400:
            raise LLMInvalidRequestError(f"Invalid request: {error_message}")
        elif error_code == "content_filter":
            raise LLMContentFilterError(f"Content filter triggered: {error_message}")
        else:
            raise LLMError(
                f"OpenRouter API error ({response.status_code}): {error_message}",
                provider="openrouter",
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
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in message["tool_calls"]
                ]

            return LLMResponse(
                content=message.get("content", ""),
                model=response_data.get("model", self.model),
                finish_reason=choice.get("finish_reason"),
                usage=response_data.get("usage"),
                tool_calls=tool_calls,
            )

        except (KeyError, IndexError):
            raise LLMError("Invalid response format from OpenRouter")


# Provider factory
def create_llm_provider(
    provider_name: str, api_key: str, model: str = "openai/gpt-3.5-turbo", **kwargs
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
