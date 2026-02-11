"""Unit tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from terminal_gpt.infrastructure.llm_providers import (
    LLMProvider,
    OpenRouterProvider,
    LLMResponse,
    create_llm_provider,
)
from terminal_gpt.domain.exceptions import (
    ConfigurationError,
    LLMError,
    LLMAuthenticationError,
    LLMQuotaExceededError,
    LLMServiceUnavailableError,
    LLMInvalidRequestError,
    LLMContentFilterError,
)


class TestLLMResponse:
    """Test LLMResponse model."""

    def test_valid_response(self):
        """Test creating a valid LLM response."""
        response = LLMResponse(
            content="Hello world",
            model="gpt-3.5-turbo",
            finish_reason="stop",
            usage={"total_tokens": 150},
            tool_calls=None,
        )

        assert response.content == "Hello world"
        assert response.model == "gpt-3.5-turbo"
        assert response.finish_reason == "stop"
        assert response.usage == {"total_tokens": 150}
        assert response.tool_calls is None

    def test_response_with_tool_calls(self):
        """Test response with tool calls."""
        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'},
            }
        ]

        response = LLMResponse(content="", model="gpt-3.5-turbo", tool_calls=tool_calls)

        assert response.tool_calls == tool_calls


class TestCreateLLMProvider:
    """Test LLM provider factory."""

    def test_create_openrouter_provider(self):
        """Test creating OpenRouter provider."""
        provider = create_llm_provider("openrouter", "test-key", model="gpt-4")

        assert isinstance(provider, OpenRouterProvider)
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4"

    def test_create_unknown_provider(self):
        """Test creating unknown provider raises error."""
        with pytest.raises(ConfigurationError):
            create_llm_provider("unknown", "test-key")


class TestOpenRouterProvider:
    """Test OpenRouter provider implementation."""

    def test_initialization_valid(self):
        """Test provider initialization with valid parameters."""
        provider = OpenRouterProvider(api_key="test-key", model="gpt-4", max_retries=5)

        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4"
        assert provider.max_retries == 5

    def test_initialization_invalid_api_key(self):
        """Test provider initialization with invalid API key."""
        with pytest.raises(ConfigurationError):
            OpenRouterProvider(api_key="")

        with pytest.raises(ConfigurationError):
            OpenRouterProvider(api_key="   ")

    def test_headers(self):
        """Test HTTP headers generation."""
        provider = OpenRouterProvider("test-key")
        headers = provider._get_headers()

        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    def test_generate_without_client(self):
        """Test generate method without initialized client."""
        provider = OpenRouterProvider("test-key")

        with pytest.raises(LLMError):
            # This would need to be awaited, but we're testing the error case

            async def test():
                await provider.generate([])

            # Run in event loop for test
            import asyncio

            asyncio.run(test())

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Test successful LLM generation."""
        provider = OpenRouterProvider("test-key")

        # Mock response data
        mock_response_data = {
            "model": "openai/gpt-3.5-turbo",
            "choices": [
                {
                    "message": {"content": "Hello from AI", "role": "assistant"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "total_tokens": 150,
                "prompt_tokens": 50,
                "completion_tokens": 100,
            },
        }

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(provider, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            async with provider:
                result = await provider.generate([{"role": "user", "content": "Hello"}])

            assert result.content == "Hello from AI"
            assert result.model == "openai/gpt-3.5-turbo"
            assert result.finish_reason == "stop"
            assert result.usage == mock_response_data["usage"]
            assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_generation_with_tools(self):
        """Test generation with tool definitions."""
        provider = OpenRouterProvider("test-key")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ]

        mock_response_data = {
            "model": "openai/gpt-3.5-turbo",
            "choices": [
                {
                    "message": {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "test.txt"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"total_tokens": 200},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch.object(provider, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            async with provider:
                result = await provider.generate(
                    [{"role": "user", "content": "Read a file"}], tools=tools
                )

            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0]["function"]["name"] == "read_file"

    def test_error_handling_401(self):
        """Test authentication error handling."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}

        with pytest.raises(LLMAuthenticationError):
            provider._handle_error(mock_response)

    def test_error_handling_429(self):
        """Test rate limit error handling."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "30"}
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}

        with pytest.raises(LLMQuotaExceededError) as exc_info:
            provider._handle_error(mock_response)

        assert exc_info.value.retry_after == 30

    def test_error_handling_500(self):
        """Test server error handling."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": {"message": "Internal server error"}
        }

        with pytest.raises(LLMServiceUnavailableError):
            provider._handle_error(mock_response)

    def test_error_handling_400(self):
        """Test bad request error handling."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Invalid request"}}

        with pytest.raises(LLMInvalidRequestError):
            provider._handle_error(mock_response)

    def test_error_handling_content_filter(self):
        """Test content filter error handling."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"code": "content_filter", "message": "Content filtered"}
        }

        with pytest.raises(LLMContentFilterError):
            provider._handle_error(mock_response)

    def test_error_handling_malformed_json(self):
        """Test handling of malformed error responses."""
        provider = OpenRouterProvider("test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Internal Server Error"

        with pytest.raises(LLMServiceUnavailableError):
            provider._handle_error(mock_response)

    def test_parse_response_invalid_format(self):
        """Test parsing invalid response format."""
        provider = OpenRouterProvider("test-key")

        # Missing choices
        invalid_data = {"model": "gpt-3.5-turbo"}

        with pytest.raises(LLMError):
            provider._parse_response(invalid_data)

    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic for transient failures."""
        provider = OpenRouterProvider("test-key", max_retries=2)

        # First two calls fail with 500, third succeeds
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.json.return_value = {"error": {"message": "Server error"}}
                raise LLMServiceUnavailableError("Server error")

            # Success response
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "model": "gpt-3.5-turbo",
                "choices": [
                    {
                        "message": {"content": "Success", "role": "assistant"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 100},
            }
            return mock_resp

        with patch.object(provider, "_client") as mock_client:
            mock_client.post = mock_post

            async with provider:
                result = await provider.generate([{"role": "user", "content": "test"}])

            assert call_count == 3  # Two retries + one success
            assert result.content == "Success"

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        """Test that authentication errors are not retried."""
        provider = OpenRouterProvider("test-key", max_retries=3)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": {"message": "Invalid key"}}
            raise LLMAuthenticationError("Invalid key")

        with patch.object(provider, "_client") as mock_client:
            mock_client.post = mock_post

            async with provider:
                with pytest.raises(LLMAuthenticationError):
                    await provider.generate([{"role": "user", "content": "test"}])

            assert call_count == 1  # No retries for auth errors

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager behavior."""
        provider = OpenRouterProvider("test-key")

        # Before entering context
        assert provider._client is None

        async with provider:
            assert provider._client is not None

        # After exiting context
        assert provider._client is None
