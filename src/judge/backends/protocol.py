"""JudgeBackend protocol for pluggable LLM provider support.

Defines the interface that all judge backends must implement.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JudgeBackend(Protocol):
    """Protocol for LLM backends used by the unified judge.

    All backends must implement async evaluate() and expose a model_id property.
    """

    @property
    def model_id(self) -> str:
        """Return the model identifier string."""
        ...

    async def evaluate(
        self,
        prompt: str,
        system_prompt: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Send a prompt to the LLM and return the response text.

        Args:
            prompt: The user prompt to evaluate.
            system_prompt: The system prompt for the LLM.
            config: Optional configuration overrides (temperature, max_tokens, etc.).

        Returns:
            The raw text response from the LLM.
        """
        ...
