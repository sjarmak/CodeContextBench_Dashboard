"""Tests for Agent-as-a-Judge evaluator."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from src.evaluation.agent_judge import (
    AgentJudge,
    HarborResult,
    JudgmentResult,
    LLMBackend,
    RateLimitConfig,
    RateLimiter,
    RequirementScore,
)


class TestHarborResult:
    """Tests for HarborResult dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating HarborResult with all fields."""
        result = HarborResult(
            task_id="task-001",
            task_description="Implement a sorting function",
            agent_output="def sort(arr): return sorted(arr)",
            ground_truth="def sort(arr): return sorted(arr)",
            metadata={"difficulty": "easy"},
        )
        assert result.task_id == "task-001"
        assert result.task_description == "Implement a sorting function"
        assert result.ground_truth == "def sort(arr): return sorted(arr)"
        assert result.metadata["difficulty"] == "easy"

    def test_creation_with_minimal_fields(self) -> None:
        """Test creating HarborResult with minimal fields."""
        result = HarborResult(
            task_id="task-002",
            task_description="Test task",
            agent_output="output",
        )
        assert result.task_id == "task-002"
        assert result.ground_truth is None
        assert result.metadata == {}

    def test_from_dict(self) -> None:
        """Test creating HarborResult from dictionary."""
        data = {
            "task_id": "task-003",
            "task_description": "Test task",
            "agent_output": "output",
            "ground_truth": "expected",
            "metadata": {"key": "value"},
        }
        result = HarborResult.from_dict(data)
        assert result.task_id == "task-003"
        assert result.ground_truth == "expected"
        assert result.metadata["key"] == "value"

    def test_from_dict_alternative_keys(self) -> None:
        """Test from_dict handles alternative key names."""
        data = {
            "id": "task-004",
            "description": "Test task",
            "output": "output",
        }
        result = HarborResult.from_dict(data)
        assert result.task_id == "task-004"
        assert result.task_description == "Test task"
        assert result.agent_output == "output"

    def test_to_dict(self) -> None:
        """Test converting HarborResult to dictionary."""
        result = HarborResult(
            task_id="task-005",
            task_description="Test",
            agent_output="output",
            ground_truth="expected",
            metadata={"key": "value"},
        )
        data = result.to_dict()
        assert data["task_id"] == "task-005"
        assert data["ground_truth"] == "expected"
        assert data["metadata"]["key"] == "value"


class TestRequirementScore:
    """Tests for RequirementScore dataclass."""

    def test_creation(self) -> None:
        """Test creating RequirementScore."""
        score = RequirementScore(
            criterion_id="C001",
            criterion_description="Code compiles",
            satisfied=True,
            score=1.0,
            reasoning="Code compiles successfully",
            evidence="No compilation errors",
        )
        assert score.criterion_id == "C001"
        assert score.satisfied is True
        assert score.score == 1.0

    def test_to_dict(self) -> None:
        """Test converting RequirementScore to dictionary."""
        score = RequirementScore(
            criterion_id="C002",
            criterion_description="Tests pass",
            satisfied=False,
            score=0.5,
            reasoning="Some tests fail",
            evidence="3 of 6 tests pass",
        )
        data = score.to_dict()
        assert data["criterion_id"] == "C002"
        assert data["satisfied"] is False
        assert data["score"] == 0.5
        assert data["reasoning"] == "Some tests fail"


class TestJudgmentResult:
    """Tests for JudgmentResult dataclass."""

    @pytest.fixture
    def sample_judgment(self) -> JudgmentResult:
        """Create a sample judgment for testing."""
        return JudgmentResult(
            overall_score=0.75,
            requirement_scores={
                "C001": RequirementScore(
                    criterion_id="C001",
                    criterion_description="Code compiles",
                    satisfied=True,
                    score=1.0,
                    reasoning="OK",
                ),
                "C002": RequirementScore(
                    criterion_id="C002",
                    criterion_description="Tests pass",
                    satisfied=False,
                    score=0.5,
                    reasoning="Partial",
                ),
            },
            reasoning="Good overall",
            confidence=0.8,
            raw_response='{"overall_score": 0.75}',
            metadata={"model": "test"},
        )

    def test_to_dict(self, sample_judgment: JudgmentResult) -> None:
        """Test converting JudgmentResult to dictionary."""
        data = sample_judgment.to_dict()
        assert data["overall_score"] == 0.75
        assert data["confidence"] == 0.8
        assert "C001" in data["requirement_scores"]
        assert data["requirement_scores"]["C001"]["satisfied"] is True
        assert data["metadata"]["model"] == "test"

    def test_from_dict(self) -> None:
        """Test creating JudgmentResult from dictionary."""
        data = {
            "overall_score": 0.6,
            "requirement_scores": {
                "C001": {
                    "criterion_id": "C001",
                    "criterion_description": "Test",
                    "satisfied": True,
                    "score": 0.8,
                    "reasoning": "Good",
                    "evidence": "",
                }
            },
            "reasoning": "Overall good",
            "confidence": 0.7,
            "raw_response": "{}",
            "metadata": {},
        }
        result = JudgmentResult.from_dict(data)
        assert result.overall_score == 0.6
        assert result.confidence == 0.7
        assert result.requirement_scores["C001"].satisfied is True


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 50
        assert config.max_retries == 3
        assert config.base_delay_seconds == 1.0
        assert config.max_delay_seconds == 60.0
        assert config.backoff_multiplier == 2.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_minute=100,
            max_retries=5,
            base_delay_seconds=2.0,
        )
        assert config.requests_per_minute == 100
        assert config.max_retries == 5
        assert config.base_delay_seconds == 2.0


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_initialization(self) -> None:
        """Test rate limiter initialization."""
        limiter = RateLimiter()
        assert limiter.config.requests_per_minute == 50

    def test_custom_config(self) -> None:
        """Test rate limiter with custom config."""
        config = RateLimitConfig(requests_per_minute=10)
        limiter = RateLimiter(config)
        assert limiter.config.requests_per_minute == 10

    def test_get_retry_delay_exponential_backoff(self) -> None:
        """Test retry delay uses exponential backoff."""
        config = RateLimitConfig(
            base_delay_seconds=1.0,
            backoff_multiplier=2.0,
            max_delay_seconds=60.0,
        )
        limiter = RateLimiter(config)

        assert limiter.get_retry_delay(0) == 1.0
        assert limiter.get_retry_delay(1) == 2.0
        assert limiter.get_retry_delay(2) == 4.0
        assert limiter.get_retry_delay(3) == 8.0

    def test_get_retry_delay_respects_max(self) -> None:
        """Test retry delay respects maximum."""
        config = RateLimitConfig(
            base_delay_seconds=1.0,
            backoff_multiplier=2.0,
            max_delay_seconds=5.0,
        )
        limiter = RateLimiter(config)

        assert limiter.get_retry_delay(10) == 5.0


class TestAgentJudge:
    """Tests for AgentJudge class."""

    @pytest.fixture
    def mock_env_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up Anthropic API key in environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")

    @pytest.fixture
    def mock_env_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up OpenAI API key in environment."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

    def test_detect_backend_anthropic(
        self, mock_env_anthropic: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test backend detection prefers Anthropic when both available."""
        monkeypatch.setenv("OPENAI_API_KEY", "also-set")
        judge = AgentJudge()
        assert judge.backend == LLMBackend.ANTHROPIC

    def test_detect_backend_openai(self, mock_env_openai: None) -> None:
        """Test backend detection falls back to OpenAI."""
        judge = AgentJudge()
        assert judge.backend == LLMBackend.OPENAI

    def test_detect_backend_no_key_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error when no API key available."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="No API key found"):
            AgentJudge()

    def test_explicit_backend(self, mock_env_anthropic: None) -> None:
        """Test explicit backend selection."""
        judge = AgentJudge(backend=LLMBackend.ANTHROPIC)
        assert judge.backend == LLMBackend.ANTHROPIC

    def test_default_model_anthropic(self, mock_env_anthropic: None) -> None:
        """Test default model for Anthropic backend."""
        judge = AgentJudge(backend=LLMBackend.ANTHROPIC)
        assert judge.model == AgentJudge.DEFAULT_ANTHROPIC_MODEL

    def test_default_model_openai(self, mock_env_openai: None) -> None:
        """Test default model for OpenAI backend."""
        judge = AgentJudge(backend=LLMBackend.OPENAI)
        assert judge.model == AgentJudge.DEFAULT_OPENAI_MODEL

    def test_custom_model(self, mock_env_anthropic: None) -> None:
        """Test custom model selection."""
        judge = AgentJudge(model="custom-model")
        assert judge.model == "custom-model"

    def test_evaluate_result_empty_criteria_raises(
        self, mock_env_anthropic: None
    ) -> None:
        """Test error when criteria list is empty."""
        judge = AgentJudge()
        task = HarborResult(
            task_id="test",
            task_description="Test task",
            agent_output="output",
        )

        with pytest.raises(ValueError, match="Criteria list cannot be empty"):
            judge.evaluate_result(task, [])


class TestAgentJudgeIntegration:
    """Integration tests for AgentJudge with mocked LLM."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    @pytest.fixture
    def mock_llm_response(self) -> dict[str, Any]:
        """Create a mock LLM response."""
        return {
            "criteria_evaluations": [
                {
                    "criterion_id": "C001",
                    "satisfied": True,
                    "score": 1.0,
                    "reasoning": "Code compiles successfully",
                    "evidence": "No errors",
                },
                {
                    "criterion_id": "C002",
                    "satisfied": False,
                    "score": 0.5,
                    "reasoning": "Some tests fail",
                    "evidence": "3/6 pass",
                },
            ],
            "overall_score": 0.75,
            "reasoning": "Good overall performance",
            "confidence": 0.85,
        }

    def test_evaluate_result_success(
        self, mock_env: None, mock_llm_response: dict[str, Any]
    ) -> None:
        """Test successful evaluation with mocked LLM."""
        judge = AgentJudge()

        # Mock the LLM call
        with patch.object(judge, "_call_llm_with_retry") as mock_call:
            mock_call.return_value = json.dumps(mock_llm_response)

            task = HarborResult(
                task_id="test-001",
                task_description="Implement sorting",
                agent_output="def sort(x): return sorted(x)",
            )
            criteria = ["Code compiles", "All tests pass"]

            result = judge.evaluate_result(task, criteria)

            assert result.overall_score == 0.75
            assert result.confidence == 0.85
            assert len(result.requirement_scores) == 2
            assert result.requirement_scores["C001"].satisfied is True
            assert result.requirement_scores["C002"].satisfied is False

    def test_evaluate_result_json_in_markdown(
        self, mock_env: None, mock_llm_response: dict[str, Any]
    ) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        judge = AgentJudge()

        # Mock response with markdown code block
        markdown_response = f"```json\n{json.dumps(mock_llm_response)}\n```"

        with patch.object(judge, "_call_llm_with_retry") as mock_call:
            mock_call.return_value = markdown_response

            task = HarborResult(
                task_id="test-001",
                task_description="Test",
                agent_output="output",
            )

            result = judge.evaluate_result(task, ["Criterion 1", "Criterion 2"])

            assert result.overall_score == 0.75

    def test_evaluate_result_parse_failure(self, mock_env: None) -> None:
        """Test handling of unparseable LLM response."""
        judge = AgentJudge()

        with patch.object(judge, "_call_llm_with_retry") as mock_call:
            mock_call.return_value = "This is not valid JSON at all"

            task = HarborResult(
                task_id="test-001",
                task_description="Test",
                agent_output="output",
            )

            result = judge.evaluate_result(task, ["Criterion 1"])

            assert result.overall_score == 0.0
            assert result.confidence == 0.0
            assert result.metadata.get("parse_error") is True

    def test_evaluate_batch(
        self, mock_env: None, mock_llm_response: dict[str, Any]
    ) -> None:
        """Test batch evaluation."""
        judge = AgentJudge()

        with patch.object(judge, "_call_llm_with_retry") as mock_call:
            mock_call.return_value = json.dumps(mock_llm_response)

            tasks = [
                HarborResult(
                    task_id=f"task-{i}",
                    task_description=f"Task {i}",
                    agent_output=f"Output {i}",
                )
                for i in range(3)
            ]
            criteria = ["Criterion 1", "Criterion 2"]

            results = judge.evaluate_batch(tasks, criteria)

            assert len(results) == 3
            assert all(r.overall_score == 0.75 for r in results)

    def test_evaluate_batch_with_progress(
        self, mock_env: None, mock_llm_response: dict[str, Any]
    ) -> None:
        """Test batch evaluation with progress callback."""
        judge = AgentJudge()
        progress_calls: list[tuple[int, int]] = []

        def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        with patch.object(judge, "_call_llm_with_retry") as mock_call:
            mock_call.return_value = json.dumps(mock_llm_response)

            tasks = [
                HarborResult(
                    task_id=f"task-{i}",
                    task_description=f"Task {i}",
                    agent_output=f"Output {i}",
                )
                for i in range(2)
            ]

            judge.evaluate_batch(tasks, ["Criterion"], on_progress=on_progress)

            assert progress_calls == [(0, 2), (1, 2), (2, 2)]


class TestAgentJudgeJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def test_extract_json_raw(self, mock_env: None) -> None:
        """Test extracting raw JSON."""
        judge = AgentJudge()
        text = '{"key": "value"}'
        result = judge._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_with_prefix(self, mock_env: None) -> None:
        """Test extracting JSON with text prefix."""
        judge = AgentJudge()
        text = 'Here is my response: {"key": "value"}'
        result = judge._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_markdown_block(self, mock_env: None) -> None:
        """Test extracting JSON from markdown code block."""
        judge = AgentJudge()
        text = '```json\n{"key": "value"}\n```'
        result = judge._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_plain_code_block(self, mock_env: None) -> None:
        """Test extracting JSON from plain code block."""
        judge = AgentJudge()
        text = '```\n{"key": "value"}\n```'
        result = judge._extract_json(text)
        assert result == '{"key": "value"}'

    def test_extract_json_nested(self, mock_env: None) -> None:
        """Test extracting nested JSON object."""
        judge = AgentJudge()
        text = 'Response: {"outer": {"inner": "value"}, "array": [1, 2]}'
        result = judge._extract_json(text)
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == "value"
        assert parsed["array"] == [1, 2]


class TestAgentJudgeRetryLogic:
    """Tests for retry logic."""

    @pytest.fixture
    def mock_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def test_retry_on_failure(self, mock_env: None) -> None:
        """Test retry on transient failure."""
        judge = AgentJudge(
            rate_limit_config=RateLimitConfig(
                max_retries=3,
                base_delay_seconds=0.01,
            )
        )

        call_count = 0

        def mock_call(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return '{"overall_score": 1.0}'

        with patch.object(judge, "_call_llm", side_effect=mock_call):
            result = judge._call_llm_with_retry("test prompt")
            assert result == '{"overall_score": 1.0}'
            assert call_count == 3

    def test_max_retries_exceeded(self, mock_env: None) -> None:
        """Test error after max retries exceeded."""
        judge = AgentJudge(
            rate_limit_config=RateLimitConfig(
                max_retries=2,
                base_delay_seconds=0.01,
            )
        )

        def always_fail(prompt: str) -> str:
            raise Exception("Permanent error")

        with patch.object(judge, "_call_llm", side_effect=always_fail):
            with pytest.raises(RuntimeError, match="failed after 2 retries"):
                judge._call_llm_with_retry("test prompt")


class TestLLMBackendEnum:
    """Tests for LLMBackend enum."""

    def test_anthropic_value(self) -> None:
        """Test Anthropic backend value."""
        assert LLMBackend.ANTHROPIC.value == "anthropic"

    def test_openai_value(self) -> None:
        """Test OpenAI backend value."""
        assert LLMBackend.OPENAI.value == "openai"
