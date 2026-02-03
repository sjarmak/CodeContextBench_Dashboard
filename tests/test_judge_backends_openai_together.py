"""Unit tests for OpenAI and Together judge backends."""

from __future__ import annotations

import logging
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Together SDK mock setup ---
# Together SDK may not be installed; create a mock module so imports work.
_together_mock_needed = "together" not in sys.modules

if _together_mock_needed:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

import together  # noqa: E402

from src.judge.backends.openai import OpenAIBackend, OpenAIBackendConfig  # noqa: E402
from src.judge.backends.protocol import JudgeBackend  # noqa: E402
from src.judge.backends.together import (  # noqa: E402
    TogetherBackend,
    TogetherBackendConfig,
)


# --- OpenAI Backend Tests ---


class TestOpenAIBackendConfig:
    def test_defaults(self):
        config = OpenAIBackendConfig()
        assert config.model == "gpt-4o"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.rpm_limit == 60

    def test_custom_values(self):
        config = OpenAIBackendConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2048,
            max_retries=5,
            rpm_limit=30,
        )
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.max_retries == 5
        assert config.rpm_limit == 30

    def test_is_frozen(self):
        config = OpenAIBackendConfig()
        with pytest.raises(AttributeError):
            config.model = "other"  # type: ignore[misc]


class TestOpenAIBackend:
    def _make_mock_response(
        self,
        text: str = "response",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
    ):
        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return SimpleNamespace(choices=[choice], usage=usage)

    def _make_backend(self, config=None, mock_client=None):
        client = mock_client or AsyncMock()
        return OpenAIBackend(config=config, client=client)

    def test_implements_protocol(self):
        backend = OpenAIBackend.__new__(OpenAIBackend)
        assert isinstance(backend, JudgeBackend)

    def test_model_id_default(self):
        backend = self._make_backend()
        assert backend.model_id == "gpt-4o"

    def test_model_id_custom(self):
        config = OpenAIBackendConfig(model="gpt-4o-mini")
        backend = self._make_backend(config=config)
        assert backend.model_id == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response(text="Judge says: pass")
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(
            prompt="Evaluate this code",
            system_prompt="You are a judge",
        )

        assert result == "Judge says: pass"
        mock_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_passes_correct_params(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = OpenAIBackendConfig(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=1024,
        )
        backend = self._make_backend(config=config, mock_client=mock_client)
        await backend.evaluate(prompt="test prompt", system_prompt="test system")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "test system"},
            {"role": "user", "content": "test prompt"},
        ]

    @pytest.mark.asyncio
    async def test_evaluate_config_overrides(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        await backend.evaluate(
            prompt="test",
            system_prompt="system",
            config={"temperature": 0.8, "max_tokens": 512},
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.8
        assert call_kwargs["max_tokens"] == 512

    @pytest.mark.asyncio
    async def test_evaluate_retries_on_rate_limit(self):
        import openai as openai_module

        mock_client = AsyncMock()
        rate_limit_error = openai_module.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_response = self._make_mock_response(text="success after retry")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[rate_limit_error, mock_response]
        )

        config = OpenAIBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await backend.evaluate(prompt="test", system_prompt="system")

        assert result == "success after retry"
        assert mock_client.chat.completions.create.await_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_exhausts_retries(self):
        import openai as openai_module

        mock_client = AsyncMock()
        rate_limit_error = openai_module.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[rate_limit_error, rate_limit_error, rate_limit_error]
        )

        config = OpenAIBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(openai_module.RateLimitError):
                await backend.evaluate(prompt="test", system_prompt="system")

        assert mock_client.chat.completions.create.await_count == 3

    @pytest.mark.asyncio
    async def test_evaluate_logs_api_call(self, caplog):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response(
            text="ok", prompt_tokens=200, completion_tokens=80
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)

        with caplog.at_level(logging.INFO, logger="src.judge.backends.openai"):
            await backend.evaluate(prompt="test", system_prompt="system")

        assert any("OpenAI API call" in record.message for record in caplog.records)
        assert any("input_tokens=200" in record.message for record in caplog.records)
        assert any("output_tokens=80" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_evaluate_handles_none_content(self):
        mock_client = AsyncMock()
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=0)
        mock_response = SimpleNamespace(choices=[choice], usage=usage)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(prompt="test", system_prompt="system")
        assert result == ""

    @pytest.mark.asyncio
    async def test_evaluate_handles_none_usage(self):
        mock_client = AsyncMock()
        message = SimpleNamespace(content="ok")
        choice = SimpleNamespace(message=message)
        mock_response = SimpleNamespace(choices=[choice], usage=None)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(prompt="test", system_prompt="system")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = OpenAIBackendConfig(rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        await backend.evaluate(prompt="test", system_prompt="system")
        assert backend._last_request_time > 0


# --- Together Backend Tests ---


class TestTogetherBackendConfig:
    def test_defaults(self):
        config = TogetherBackendConfig()
        assert config.model == "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.rpm_limit == 60

    def test_custom_values(self):
        config = TogetherBackendConfig(
            model="my-fine-tuned-model-v1",
            temperature=0.5,
            max_tokens=2048,
            max_retries=5,
            rpm_limit=30,
        )
        assert config.model == "my-fine-tuned-model-v1"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.max_retries == 5
        assert config.rpm_limit == 30

    def test_is_frozen(self):
        config = TogetherBackendConfig()
        with pytest.raises(AttributeError):
            config.model = "other"  # type: ignore[misc]

    def test_supports_fine_tuned_model_id(self):
        config = TogetherBackendConfig(model="ft:user/my-custom-judge-v2")
        assert config.model == "ft:user/my-custom-judge-v2"


class TestTogetherBackend:
    def _make_mock_response(
        self,
        text: str = "response",
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
    ):
        message = SimpleNamespace(content=text)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return SimpleNamespace(choices=[choice], usage=usage)

    def _make_backend(self, config=None, mock_client=None):
        client = mock_client or AsyncMock()
        return TogetherBackend(config=config, client=client)

    def test_implements_protocol(self):
        backend = TogetherBackend.__new__(TogetherBackend)
        assert isinstance(backend, JudgeBackend)

    def test_model_id_default(self):
        backend = self._make_backend()
        assert backend.model_id == "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"

    def test_model_id_custom(self):
        config = TogetherBackendConfig(model="ft:my-judge")
        backend = self._make_backend(config=config)
        assert backend.model_id == "ft:my-judge"

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response(text="Judge says: pass")
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(
            prompt="Evaluate this code",
            system_prompt="You are a judge",
        )

        assert result == "Judge says: pass"
        mock_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_evaluate_passes_correct_params(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = TogetherBackendConfig(
            model="ft:my-judge",
            temperature=0.3,
            max_tokens=1024,
        )
        backend = self._make_backend(config=config, mock_client=mock_client)
        await backend.evaluate(prompt="test prompt", system_prompt="test system")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "ft:my-judge"
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "test system"},
            {"role": "user", "content": "test prompt"},
        ]

    @pytest.mark.asyncio
    async def test_evaluate_config_overrides(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        await backend.evaluate(
            prompt="test",
            system_prompt="system",
            config={"temperature": 0.8, "max_tokens": 512},
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.8
        assert call_kwargs["max_tokens"] == 512

    @pytest.mark.asyncio
    async def test_evaluate_retries_on_rate_limit(self):
        mock_client = AsyncMock()
        rate_limit_error = together.error.RateLimitError("rate limited")
        mock_response = self._make_mock_response(text="success after retry")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[rate_limit_error, mock_response]
        )

        config = TogetherBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await backend.evaluate(prompt="test", system_prompt="system")

        assert result == "success after retry"
        assert mock_client.chat.completions.create.await_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_exhausts_retries(self):
        mock_client = AsyncMock()
        rate_limit_error = together.error.RateLimitError("rate limited")
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[rate_limit_error, rate_limit_error, rate_limit_error]
        )

        config = TogetherBackendConfig(max_retries=3, rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(together.error.RateLimitError):
                await backend.evaluate(prompt="test", system_prompt="system")

        assert mock_client.chat.completions.create.await_count == 3

    @pytest.mark.asyncio
    async def test_evaluate_logs_api_call(self, caplog):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response(
            text="ok", prompt_tokens=200, completion_tokens=80
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)

        with caplog.at_level(logging.INFO, logger="src.judge.backends.together"):
            await backend.evaluate(prompt="test", system_prompt="system")

        assert any("Together API call" in record.message for record in caplog.records)
        assert any("input_tokens=200" in record.message for record in caplog.records)
        assert any("output_tokens=80" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_evaluate_handles_none_content(self):
        mock_client = AsyncMock()
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=0)
        mock_response = SimpleNamespace(choices=[choice], usage=usage)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(prompt="test", system_prompt="system")
        assert result == ""

    @pytest.mark.asyncio
    async def test_evaluate_handles_none_usage(self):
        mock_client = AsyncMock()
        message = SimpleNamespace(content="ok")
        choice = SimpleNamespace(message=message)
        mock_response = SimpleNamespace(choices=[choice], usage=None)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = self._make_backend(mock_client=mock_client)
        result = await backend.evaluate(prompt="test", system_prompt="system")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        mock_client = AsyncMock()
        mock_response = self._make_mock_response()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        config = TogetherBackendConfig(rpm_limit=10000)
        backend = self._make_backend(config=config, mock_client=mock_client)

        await backend.evaluate(prompt="test", system_prompt="system")
        assert backend._last_request_time > 0


# --- Export Tests ---


class TestNewBackendExports:
    def test_imports_from_backends_init(self):
        from src.judge.backends import (
            OpenAIBackend,
            OpenAIBackendConfig,
            TogetherBackend,
            TogetherBackendConfig,
        )

        assert OpenAIBackend is not None
        assert OpenAIBackendConfig is not None
        assert TogetherBackend is not None
        assert TogetherBackendConfig is not None

    def test_imports_from_judge_init(self):
        from src.judge import (
            OpenAIBackend,
            OpenAIBackendConfig,
            TogetherBackend,
            TogetherBackendConfig,
        )

        assert OpenAIBackend is not None
        assert OpenAIBackendConfig is not None
        assert TogetherBackend is not None
        assert TogetherBackendConfig is not None
