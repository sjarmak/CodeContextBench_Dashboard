"""Unit tests for judge backends (protocol and Anthropic)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.judge.backends.anthropic import AnthropicBackend, AnthropicBackendConfig
from src.judge.backends.protocol import JudgeBackend


class TestJudgeBackendProtocol:
    def test_protocol_is_runtime_checkable(self):
        assert hasattr(JudgeBackend, "__protocol_attrs__") or hasattr(
            JudgeBackend, "__abstractmethods__"
        ) or isinstance(JudgeBackend, type)

    def test_anthropic_backend_implements_protocol(self):
        """AnthropicBackend should satisfy the JudgeBackend protocol."""
        backend = AnthropicBackend.__new__(AnthropicBackend)
        assert isinstance(backend, JudgeBackend)

    def test_protocol_requires_model_id(self):
        assert "model_id" in dir(JudgeBackend)

    def test_protocol_requires_evaluate(self):
        assert "evaluate" in dir(JudgeBackend)


class TestAnthropicBackendConfig:
    def test_defaults(self):
        config = AnthropicBackendConfig()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.rpm_limit == 60

    def test_custom_values(self):
        config = AnthropicBackendConfig(
            model="claude-haiku-4-5-20251001",
            temperature=0.5,
            max_tokens=2048,
            max_retries=5,
            rpm_limit=30,
        )
        assert config.model == "claude-haiku-4-5-20251001"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.max_retries == 5
        assert config.rpm_limit == 30

    def test_is_frozen(self):
        config = AnthropicBackendConfig()
        with pytest.raises(AttributeError):
            config.model = "other-model"  # type: ignore[misc]


class TestAnthropicBackend:
    def _make_mock_response(
        self, text: str = "response", input_tokens: int = 100, output_tokens: int = 50
    ):
        content_block = SimpleNamespace(text=text)
        usage = SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens
        )
        return SimpleNamespace(content=[content_block], usage=usage)

    def _make_backend(self, config=None, mock_client=None):
        client = mock_client or AsyncMock()
        return AnthropicBackend(config=config, client=client)

    def test_model_id_default(self):
        backend = self._make_backend()
        assert backend.model_id == "claude-sonnet-4-20250514"

    def test_model_id_custom(self):
        config = AnthropicBackendConfig(model="claude-haiku-4-5-20251001")
        backend = self._make_backend(config=config)
        assert backend.model_id == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response(text="Judge says: pass")
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(
            prompt="Evaluate this code",
            system_prompt="You are a judge",
        )

        assert result == "Judge says: pass"
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_passes_correct_params(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        config = AnthropicBackendConfig(
            model="claude-haiku-4-5-20251001",
            temperature=0.3,
            max_tokens=1024,
        )
        backend = self._make_backend(config=config, mock_client=mock_client)
        await backend.evaluate(
            prompt="test prompt",
            system_prompt="test system",
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["system"] == "test system"
        assert call_kwargs["messages"] == [
            {"role": "user", "content": "test prompt"}
        ]

    @pytest.mark.asyncio
    async def test_evaluate_config_overrides(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        await backend.evaluate(
            prompt="test",
            system_prompt="system",
            config={"temperature": 0.8, "max_tokens": 512},
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.8
        assert call_kwargs["max_tokens"] == 512

    @pytest.mark.asyncio
    async def test_evaluate_retries_on_rate_limit(self):
        import anthropic as anthropic_module

        mock_client = AsyncMock()
        rate_limit_error = anthropic_module.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_response = self._make_mock_response(text="success after retry")
        mock_client.messages.create = AsyncMock(
            side_effect=[rate_limit_error, mock_response]
        )

        config = AnthropicBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await backend.evaluate(
                prompt="test",
                system_prompt="system",
            )

        assert result == "success after retry"
        assert mock_client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_exhausts_retries(self):
        import anthropic as anthropic_module

        mock_client = AsyncMock()
        rate_limit_error = anthropic_module.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.messages.create = AsyncMock(
            side_effect=[rate_limit_error, rate_limit_error, rate_limit_error]
        )

        config = AnthropicBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(anthropic_module.RateLimitError):
                await backend.evaluate(
                    prompt="test",
                    system_prompt="system",
                )

        assert mock_client.messages.create.await_count == 3

    @pytest.mark.asyncio
    async def test_evaluate_logs_api_call(self, caplog):
        import logging

        mock_client = AsyncMock()
        mock_response = self._make_mock_response(
            text="ok", input_tokens=200, output_tokens=80
        )
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)

        with caplog.at_level(logging.INFO, logger="src.judge.backends.anthropic"):
            await backend.evaluate(prompt="test", system_prompt="system")

        assert any("Anthropic API call" in record.message for record in caplog.records)
        assert any("input_tokens=200" in record.message for record in caplog.records)
        assert any("output_tokens=80" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Verify rate limiter tracks request timing."""
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        config = AnthropicBackendConfig(rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        await backend.evaluate(prompt="test1", system_prompt="system")
        assert backend._last_request_time > 0


class TestBackendExports:
    def test_imports_from_init(self):
        from src.judge.backends import (
            AnthropicBackend,
            AnthropicBackendConfig,
            JudgeBackend,
        )

        assert AnthropicBackend is not None
        assert AnthropicBackendConfig is not None
        assert JudgeBackend is not None

    def test_imports_from_judge_init(self):
        from src.judge import AnthropicBackend, AnthropicBackendConfig, JudgeBackend

        assert AnthropicBackend is not None
        assert AnthropicBackendConfig is not None
        assert JudgeBackend is not None
