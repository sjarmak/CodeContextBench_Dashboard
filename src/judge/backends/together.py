"""Together.ai backend for the unified judge system.

Uses the Together SDK to call hosted or fine-tuned models for evaluation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import together

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TogetherBackendConfig:
    """Configuration for the Together.ai backend.

    Supports both hosted API models and fine-tuned custom models via model ID.
    """

    model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    temperature: float = 0.0
    max_tokens: int = 4096
    max_retries: int = 3
    rpm_limit: int = 60


class TogetherBackend:
    """Together.ai LLM backend using the together SDK.

    Supports hosted models and fine-tuned custom models via model ID.
    Implements exponential backoff retry on rate limit errors.
    """

    def __init__(
        self,
        config: TogetherBackendConfig | None = None,
        client: together.AsyncTogether | None = None,
    ) -> None:
        self._config = config or TogetherBackendConfig()
        self._client = client or together.AsyncTogether()
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
        """Send a prompt to Together.ai and return the response text.

        Implements rate limiting and exponential backoff on rate limit errors.

        Args:
            prompt: The user prompt to evaluate.
            system_prompt: The system prompt for the LLM.
            config: Optional overrides for temperature and max_tokens.

        Returns:
            The raw text response from the model.

        Raises:
            together.error.RateLimitError: If all retries are exhausted.
        """
        overrides = config or {}
        temperature = overrides.get("temperature", self._config.temperature)
        max_tokens = overrides.get("max_tokens", self._config.max_tokens)

        await self._rate_limit()

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries):
            start_time = time.monotonic()
            try:
                response = await self._client.chat.completions.create(
                    model=self._config.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                )
                latency_ms = (time.monotonic() - start_time) * 1000
                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0

                logger.info(
                    "Together API call: model=%s latency_ms=%.1f "
                    "input_tokens=%d output_tokens=%d",
                    self._config.model,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                )

                return response.choices[0].message.content or ""

            except together.error.RateLimitError as exc:
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
