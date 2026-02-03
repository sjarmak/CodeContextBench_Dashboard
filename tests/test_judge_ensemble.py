"""Tests for the EnsembleJudge with consensus voting."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- Together SDK mock setup (needed because src.judge.__init__ imports backends) ---
if "together" not in sys.modules:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

from src.judge.engine import JudgeConfig, JudgeError, UnifiedJudge
from src.judge.ensemble import (
    EnsembleConfig,
    EnsembleError,
    EnsembleJudge,
    _compute_ensemble_confidence,
    _majority_vote,
    _weighted_average,
)
from src.judge.models import (
    DimensionScore,
    DirectInput,
    EnsembleVerdict,
    EvaluationMode,
    JudgeVerdict,
    PairwiseInput,
)


# ---------- Helpers ----------


def _make_mock_backend(
    model_id: str = "test-model",
) -> MagicMock:
    """Create a mock JudgeBackend."""
    backend = MagicMock()
    backend.model_id = model_id
    backend.evaluate = AsyncMock(return_value="{}")
    return backend


def _make_verdict(
    overall_score: float = 0.8,
    model_id: str = "model-a",
    confidence: float = 0.9,
) -> JudgeVerdict:
    """Create a JudgeVerdict for testing."""
    return JudgeVerdict(
        mode=EvaluationMode.DIRECT,
        scores={
            "Correctness": DimensionScore(
                dimension="Correctness",
                score=overall_score,
                weight=1.0,
                evidence="test evidence",
                reasoning="test reasoning",
            )
        },
        overall_score=overall_score,
        reasoning="Test reasoning",
        evidence=["evidence"],
        confidence=confidence,
        model_id=model_id,
    )


def _make_judge_with_verdict(
    model_id: str, verdict: JudgeVerdict
) -> UnifiedJudge:
    """Create a UnifiedJudge that returns a predetermined verdict."""
    backend = _make_mock_backend(model_id=model_id)
    judge = UnifiedJudge(backend=backend)
    judge.evaluate = AsyncMock(return_value=verdict)  # type: ignore[method-assign]
    return judge


def _make_failing_judge(model_id: str, error_msg: str = "API error") -> UnifiedJudge:
    """Create a UnifiedJudge that raises JudgeError on evaluate."""
    backend = _make_mock_backend(model_id=model_id)
    judge = UnifiedJudge(backend=backend)
    judge.evaluate = AsyncMock(side_effect=JudgeError(error_msg))  # type: ignore[method-assign]
    return judge


# ---------- Constructor tests ----------


class TestEnsembleJudgeInit:
    def test_requires_at_least_two_judges(self):
        backend = _make_mock_backend()
        judge = UnifiedJudge(backend=backend)
        with pytest.raises(ValueError, match="at least 2"):
            EnsembleJudge(judges=[judge])

    def test_accepts_two_judges(self):
        j1 = UnifiedJudge(backend=_make_mock_backend(model_id="a"))
        j2 = UnifiedJudge(backend=_make_mock_backend(model_id="b"))
        ensemble = EnsembleJudge(judges=[j1, j2])
        assert len(ensemble.judges) == 2

    def test_default_config(self):
        j1 = UnifiedJudge(backend=_make_mock_backend(model_id="a"))
        j2 = UnifiedJudge(backend=_make_mock_backend(model_id="b"))
        ensemble = EnsembleJudge(judges=[j1, j2])
        assert ensemble.config.consensus_strategy == "weighted_average"
        assert ensemble.config.min_successful == 2

    def test_custom_config(self):
        j1 = UnifiedJudge(backend=_make_mock_backend(model_id="a"))
        j2 = UnifiedJudge(backend=_make_mock_backend(model_id="b"))
        cfg = EnsembleConfig(
            consensus_strategy="majority_vote",
            model_weights={"a": 2.0, "b": 1.0},
            min_successful=2,
        )
        ensemble = EnsembleJudge(judges=[j1, j2], config=cfg)
        assert ensemble.config.consensus_strategy == "majority_vote"

    def test_judges_property_returns_copy(self):
        j1 = UnifiedJudge(backend=_make_mock_backend(model_id="a"))
        j2 = UnifiedJudge(backend=_make_mock_backend(model_id="b"))
        ensemble = EnsembleJudge(judges=[j1, j2])
        judges_copy = ensemble.judges
        judges_copy.append(j1)
        assert len(ensemble.judges) == 2


# ---------- Consensus strategy tests ----------


class TestMajorityVote:
    def test_unanimous_pass(self):
        verdicts = [
            _make_verdict(overall_score=0.9, model_id="a"),
            _make_verdict(overall_score=0.8, model_id="b"),
            _make_verdict(overall_score=0.85, model_id="c"),
        ]
        score, dist = _majority_vote(verdicts)
        assert score == 1.0
        assert dist["winning_category"] == "pass"
        assert dist["vote_counts"]["pass"] == 3

    def test_unanimous_fail(self):
        verdicts = [
            _make_verdict(overall_score=0.1, model_id="a"),
            _make_verdict(overall_score=0.2, model_id="b"),
            _make_verdict(overall_score=0.0, model_id="c"),
        ]
        score, dist = _majority_vote(verdicts)
        assert score == 0.0
        assert dist["winning_category"] == "fail"

    def test_majority_partial(self):
        verdicts = [
            _make_verdict(overall_score=0.5, model_id="a"),
            _make_verdict(overall_score=0.4, model_id="b"),
            _make_verdict(overall_score=0.9, model_id="c"),
        ]
        score, dist = _majority_vote(verdicts)
        assert score == 0.5
        assert dist["winning_category"] == "partial"

    def test_tie_goes_to_first_max(self):
        verdicts = [
            _make_verdict(overall_score=0.9, model_id="a"),
            _make_verdict(overall_score=0.1, model_id="b"),
        ]
        score, dist = _majority_vote(verdicts)
        assert score in (0.0, 1.0)
        assert dist["vote_counts"]["pass"] == 1
        assert dist["vote_counts"]["fail"] == 1


class TestWeightedAverage:
    def test_equal_weights(self):
        verdicts = [
            _make_verdict(overall_score=0.8, model_id="a"),
            _make_verdict(overall_score=0.6, model_id="b"),
        ]
        score, dist = _weighted_average(verdicts, {})
        assert abs(score - 0.7) < 1e-9
        assert dist["strategy"] == "weighted_average"

    def test_custom_weights(self):
        verdicts = [
            _make_verdict(overall_score=1.0, model_id="a"),
            _make_verdict(overall_score=0.0, model_id="b"),
        ]
        score, dist = _weighted_average(verdicts, {"a": 3.0, "b": 1.0})
        assert abs(score - 0.75) < 1e-9

    def test_missing_weights_default_to_one(self):
        verdicts = [
            _make_verdict(overall_score=0.8, model_id="a"),
            _make_verdict(overall_score=0.4, model_id="b"),
        ]
        score, _ = _weighted_average(verdicts, {"a": 2.0})
        # a: 0.8*2 + b: 0.4*1 = 2.0 / 3.0 = 0.6667
        assert abs(score - (2.0 / 3.0)) < 1e-9


class TestEnsembleConfidence:
    def test_perfect_agreement(self):
        verdicts = [
            _make_verdict(overall_score=0.8, model_id="a", confidence=1.0),
            _make_verdict(overall_score=0.8, model_id="b", confidence=1.0),
        ]
        conf = _compute_ensemble_confidence(verdicts, 0.8)
        assert conf == pytest.approx(1.0)

    def test_low_agreement(self):
        verdicts = [
            _make_verdict(overall_score=0.0, model_id="a", confidence=0.5),
            _make_verdict(overall_score=1.0, model_id="b", confidence=0.5),
        ]
        conf = _compute_ensemble_confidence(verdicts, 0.5)
        # variance = 0.25, spread_confidence = max(0, 1 - 1.0) = 0.0
        # avg_model_confidence = 0.5
        # result = 0.0 * 0.6 + 0.5 * 0.4 = 0.2
        assert conf == pytest.approx(0.2)

    def test_empty_verdicts(self):
        assert _compute_ensemble_confidence([], 0.5) == 0.0


# ---------- Full evaluate tests ----------


class TestEnsembleEvaluate:
    @pytest.fixture()
    def direct_input(self):
        return DirectInput(
            task_id="test-task",
            task_description="Test task",
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output="Hello world",
        )

    @pytest.mark.asyncio()
    async def test_two_models_weighted_average(self, direct_input):
        v_a = _make_verdict(overall_score=0.8, model_id="model-a")
        v_b = _make_verdict(overall_score=0.6, model_id="model-b")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_judge_with_verdict("model-b", v_b)

        ensemble = EnsembleJudge(judges=[j_a, j_b])
        result = await ensemble.evaluate(direct_input)

        assert isinstance(result, EnsembleVerdict)
        assert abs(result.consensus_score - 0.7) < 1e-9
        assert len(result.per_model_verdicts) == 2
        assert result.confidence > 0.0

    @pytest.mark.asyncio()
    async def test_three_models_majority_vote(self, direct_input):
        v_a = _make_verdict(overall_score=0.9, model_id="model-a")
        v_b = _make_verdict(overall_score=0.8, model_id="model-b")
        v_c = _make_verdict(overall_score=0.3, model_id="model-c")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_judge_with_verdict("model-b", v_b)
        j_c = _make_judge_with_verdict("model-c", v_c)

        cfg = EnsembleConfig(consensus_strategy="majority_vote")
        ensemble = EnsembleJudge(judges=[j_a, j_b, j_c], config=cfg)
        result = await ensemble.evaluate(direct_input)

        assert result.consensus_score == 1.0
        assert result.vote_distribution["winning_category"] == "pass"

    @pytest.mark.asyncio()
    async def test_model_fallback_continues(self, direct_input):
        v_a = _make_verdict(overall_score=0.7, model_id="model-a")
        v_c = _make_verdict(overall_score=0.9, model_id="model-c")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_failing_judge("model-b")
        j_c = _make_judge_with_verdict("model-c", v_c)

        ensemble = EnsembleJudge(judges=[j_a, j_b, j_c])
        result = await ensemble.evaluate(direct_input)

        assert len(result.per_model_verdicts) == 2
        assert abs(result.consensus_score - 0.8) < 1e-9

    @pytest.mark.asyncio()
    async def test_too_many_failures_raises(self, direct_input):
        v_a = _make_verdict(overall_score=0.7, model_id="model-a")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_failing_judge("model-b")
        j_c = _make_failing_judge("model-c")

        ensemble = EnsembleJudge(judges=[j_a, j_b, j_c])

        with pytest.raises(EnsembleError, match="Only 1 of 3"):
            await ensemble.evaluate(direct_input)

    @pytest.mark.asyncio()
    async def test_all_fail_raises(self, direct_input):
        j_a = _make_failing_judge("model-a")
        j_b = _make_failing_judge("model-b")

        ensemble = EnsembleJudge(judges=[j_a, j_b])

        with pytest.raises(EnsembleError, match="Only 0 of 2"):
            await ensemble.evaluate(direct_input)

    @pytest.mark.asyncio()
    async def test_parallel_execution(self, direct_input):
        """Verify all judges are called (parallel execution via asyncio.gather)."""
        v_a = _make_verdict(overall_score=0.8, model_id="model-a")
        v_b = _make_verdict(overall_score=0.6, model_id="model-b")
        v_c = _make_verdict(overall_score=0.7, model_id="model-c")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_judge_with_verdict("model-b", v_b)
        j_c = _make_judge_with_verdict("model-c", v_c)

        ensemble = EnsembleJudge(judges=[j_a, j_b, j_c])
        result = await ensemble.evaluate(direct_input)

        j_a.evaluate.assert_called_once_with(direct_input)
        j_b.evaluate.assert_called_once_with(direct_input)
        j_c.evaluate.assert_called_once_with(direct_input)
        assert len(result.per_model_verdicts) == 3

    @pytest.mark.asyncio()
    async def test_custom_model_weights(self, direct_input):
        v_a = _make_verdict(overall_score=1.0, model_id="model-a")
        v_b = _make_verdict(overall_score=0.0, model_id="model-b")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_judge_with_verdict("model-b", v_b)

        cfg = EnsembleConfig(
            model_weights={"model-a": 3.0, "model-b": 1.0}
        )
        ensemble = EnsembleJudge(judges=[j_a, j_b], config=cfg)
        result = await ensemble.evaluate(direct_input)

        assert abs(result.consensus_score - 0.75) < 1e-9

    @pytest.mark.asyncio()
    async def test_agreement_metrics_integrated(self, direct_input):
        v_a = _make_verdict(overall_score=0.8, model_id="model-a")
        v_b = _make_verdict(overall_score=0.8, model_id="model-b")

        j_a = _make_judge_with_verdict("model-a", v_a)
        j_b = _make_judge_with_verdict("model-b", v_b)

        ensemble = EnsembleJudge(judges=[j_a, j_b])
        result = await ensemble.evaluate(direct_input)

        assert isinstance(result.agreement_score, float)
        assert isinstance(result.vote_distribution, dict)
