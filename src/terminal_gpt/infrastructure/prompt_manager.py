"""Prompt management and caching for Terminal GPT.

This module provides system prompt caching and management to reduce
token usage and improve performance.
"""

import hashlib
import json
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from ..config import load_config
from ..infrastructure.logging import get_logger

logger = get_logger("terminal_gpt.prompt_manager")


class PromptCache:
    """Cache for system prompts to avoid repeated processing."""

    def __init__(self, max_age_minutes: int = 60):
        """
        Initialize prompt cache.

        Args:
            max_age_minutes: Maximum age of cached prompts in minutes
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_age = timedelta(minutes=max_age_minutes)

    def get(self, prompt_key: str) -> Optional[str]:
        """
        Get cached prompt if it exists and is not expired.

        Args:
            prompt_key: Hash key for the prompt

        Returns:
            Cached prompt content or None if not found or expired
        """
        if prompt_key not in self._cache:
            return None

        cached_data = self._cache[prompt_key]
        age = datetime.utcnow() - cached_data["timestamp"]

        if age > self._max_age:
            # Expired, remove from cache
            del self._cache[prompt_key]
            return None

        return cached_data["content"]

    def set(self, prompt_key: str, content: str) -> None:
        """
        Cache a prompt.

        Args:
            prompt_key: Hash key for the prompt
            content: Prompt content to cache
        """
        self._cache[prompt_key] = {
            "content": content,
            "timestamp": datetime.utcnow()
        }

    def clear(self) -> None:
        """Clear all cached prompts."""
        self._cache.clear()


class PromptManager:
    """Manager for system prompts with caching capabilities."""

    def __init__(self):
        """Initialize prompt manager with cache."""
        self._cache = PromptCache()
        self._config = load_config()

    def get_system_prompt(self) -> str:
        """
        Get the current system prompt with caching.

        Returns:
            System prompt content
        """
        # Create cache key based on configuration
        cache_key = self._generate_cache_key()

        # Try to get from cache first
        cached_prompt = self._cache.get(cache_key)
        if cached_prompt:
            logger.debug("Retrieved system prompt from cache")
            return cached_prompt

        # Load fresh prompt from configuration
        prompt = self._config.get("system_prompt", "")

        # Cache the prompt
        self._cache.set(cache_key, prompt)

        logger.info("Loaded and cached system prompt")
        return prompt

    def _generate_cache_key(self) -> str:
        """
        Generate cache key based on current configuration.

        Returns:
            Hash string for cache key
        """
        # Create a hash of relevant configuration options
        config_data = {
            "use_optimized_prompt": self._config.get(
                "use_optimized_prompt", True
            ),
            "max_conversation_length": self._config.get(
                "max_conversation_length", 100
            ),
            "sliding_window_size": self._config.get(
                "sliding_window_size", 50
            ),
        }

        config_str = json.dumps(config_data, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def invalidate_cache(self) -> None:
        """Invalidate all cached prompts."""
        self._cache.clear()
        logger.info("Invalidated prompt cache")

    def get_prompt_info(self) -> Dict[str, Any]:
        """
        Get information about the current prompt.

        Returns:
            Dictionary with prompt information
        """
        prompt = self.get_system_prompt()
        return {
            "length": len(prompt),
            "lines": len(prompt.split('\n')),
            "tokens_estimate": len(prompt) // 4,  # Rough token estimation
            "cache_size": len(self._cache._cache),
        }

    def is_optimized_prompt_enabled(self) -> bool:
        """Check if optimized prompt is currently enabled."""
        return self._config.get("use_optimized_prompt", True)


# Global prompt manager instance
prompt_manager = PromptManager()


def get_system_prompt() -> str:
    """
    Get the current system prompt.

    This is the main entry point for getting system prompts throughout
    the application.

    Returns:
        System prompt content
    """
    return prompt_manager.get_system_prompt()


def invalidate_prompt_cache() -> None:
    """Invalidate the prompt cache."""
    prompt_manager.invalidate_cache()


def get_prompt_info() -> Dict[str, Any]:
    """
    Get information about the current prompt.

    Returns:
        Dictionary with prompt information
    """
    return prompt_manager.get_prompt_info()