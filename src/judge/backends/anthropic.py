"""Anthropic backend for the unified judge system.

Uses the Anthropic SDK to call Claude models for evaluation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnthropicBackendConfig:
    """Configuration for the Anthropic backend."""

    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 3
    rpm_limit: int = 60


class AnthropicBackend:
    """Anthropic LLM backend using the anthropic SDK.

    Supports configurable model, temperature, max_tokens, and rate limiting.
    Implements exponential backoff retry on rate limit errors.
    """

    def __init__(
        self,
        config: AnthropicBackendConfig | None = None,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._config = config or AnthropicBackendConfig()
        self._client = client or anthropic.AsyncAnthropic()
        self._last_request_time: float = 0.0
        self._min_request_interval: float = 60.0 / self._config.rpm_limit

    @property
    def model_id(self) -> str:
        """Return the configured model identifier."""
        return self._config.model

    async def evaluate(
        self,
        prompt: str,
        system_prompt: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Send a prompt to Anthropic and return the response text.

        Implements rate limiting and exponential backoff on rate limit errors.

        Args:
            prompt: The user prompt to evaluate.
            system_prompt: The system prompt for the LLM.
            config: Optional overrides for temperature and max_tokens.

        Returns:
            The raw text response from Claude.

        Raises:
            anthropic.APIError: If all retries are exhausted.
        """
        overrides = config or {}
        temperature = overrides.get("temperature", self._config.temperature)
        max_tokens = overrides.get("max_tokens", self._config.max_tokens)

        await self._rate_limit()

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries):
            start_time = time.monotonic()
            try:
                response = await self._client.messages.create(
                    model=self._config.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                latency_ms = (time.monotonic() - start_time) * 1000
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                logger.info(
                    "Anthropic API call: model=%s latency_ms=%.1f "
                    "input_tokens=%d output_tokens=%d",
                    self._config.model,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                )

                return response.content[0].text

            except anthropic.RateLimitError as exc:
                last_error = exc
                backoff = 2**attempt
                logger.warning(
                    "Rate limited (attempt %d/%d), backing off %ds",
                    attempt + 1,
                    self._config.max_retries,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise last_error  # type: ignore[misc]

    async def _rate_limit(self) -> None:
        """Enforce minimum interval between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.monotonic()
