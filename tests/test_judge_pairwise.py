"""Tests for the PairwiseEvaluator module."""

from __future__ import annotations

import json
import sys
from pathlib import Path
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

from src.judge.engine import JudgeConfig, UnifiedJudge, _compute_weighted_score
from src.judge.models import (
    DimensionScore,
    EvaluationMode,
    PairwiseInput,
    PairwiseVerdict,
)
from src.judge.modes.pairwise import PairResult, PairwiseEvaluator

_TEMPLATES_DIR = str(
    Path(__file__).resolve().parent.parent / "configs" / "judge_prompts"
)


# ---------- Helpers ----------


def _make_mock_backend(
    response: str = '{"reasoning": "ok"}', model_id: str = "test-model"
) -> MagicMock:
    backend = MagicMock()
    backend.model_id = model_id
    backend.evaluate = AsyncMock(return_value=response)
    return backend


def _make_simultaneous_response(
    rankings: list[str],
    per_output_scores: dict,
    confidence: float = 0.85,
    ties: list[str] | None = None,
) -> str:
    return json.dumps({
        "reasoning": "Analysis of outputs",
        "rankings": rankings,
        "per_output_scores": per_output_scores,
        "ties": ties or [],
        "confidence": confidence,
    })


def _make_roundrobin_response(
    winner: str,
    scores_a: dict,
    scores_b: dict,
    confidence: float = 0.8,
) -> str:
    return json.dumps({
        "reasoning": "A vs B analysis",
        "winner": winner,
        "scores": {"A": scores_a, "B": scores_b},
        "confidence": confidence,
    })


def _make_pairwise_input(
    outputs: dict[str, str] | None = None,
) -> PairwiseInput:
    return PairwiseInput(
        task_id="t1",
        task_description="Compare outputs",
        evaluation_mode=EvaluationMode.PAIRWISE,
        outputs=outputs or {"BASELINE": "output A", "MCP": "output B"},
    )


# ---------- PairResult tests ----------


class TestPairResult:
    def test_construction(self):
        pr = PairResult(
            condition_a="A",
            condition_b="B",
            winner="A",
            scores_a={},
            scores_b={},
            confidence=0.8,
            reasoning="test",
        )
        assert pr.condition_a == "A"
        assert pr.winner == "A"

    def test_frozen(self):
        pr = PairResult(
            condition_a="A",
            condition_b="B",
            winner="A",
            scores_a={},
            scores_b={},
            confidence=0.8,
            reasoning="test",
        )
        with pytest.raises(AttributeError):
            pr.winner = "B"  # type: ignore[misc]


# ---------- Simultaneous evaluation tests ----------


class TestEvaluateSimultaneous:
    @pytest.mark.asyncio
    async def test_two_way_comparison(self):
        response = _make_simultaneous_response(
            rankings=["BASELINE", "MCP"],
            per_output_scores={
                "BASELINE": {"Correctness": {"score": 0.9, "evidence": "good", "reasoning": "right"}},
                "MCP": {"Correctness": {"score": 0.6, "evidence": "ok", "reasoning": "partial"}},
            },
        )
        backend = _make_mock_backend(response)
        config = JudgeConfig()
        evaluator = PairwiseEvaluator(backend, config, _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_simultaneous(inp)

        assert isinstance(verdict, PairwiseVerdict)
        assert verdict.rankings == ["BASELINE", "MCP"]
        assert "BASELINE" in verdict.win_rates
        assert "MCP" in verdict.win_rates
        assert verdict.win_rates["BASELINE"] > verdict.win_rates["MCP"]
        assert verdict.mode == EvaluationMode.PAIRWISE
        assert verdict.model_id == "test-model"

    @pytest.mark.asyncio
    async def test_three_way_comparison(self):
        response = _make_simultaneous_response(
            rankings=["MCP_FULL", "MCP_BASE", "BASELINE"],
            per_output_scores={
                "BASELINE": {"Correctness": {"score": 0.5, "evidence": "basic", "reasoning": "ok"}},
                "MCP_BASE": {"Correctness": {"score": 0.7, "evidence": "better", "reasoning": "good"}},
                "MCP_FULL": {"Correctness": {"score": 0.9, "evidence": "best", "reasoning": "excellent"}},
            },
        )
        backend = _make_mock_backend(response)
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input({
            "BASELINE": "basic output",
            "MCP_BASE": "better output",
            "MCP_FULL": "best output",
        })

        verdict = await evaluator.evaluate_simultaneous(inp)

        assert verdict.rankings == ["MCP_FULL", "MCP_BASE", "BASELINE"]
        assert len(verdict.win_rates) == 3
        assert verdict.win_rates["MCP_FULL"] > verdict.win_rates["BASELINE"]

    @pytest.mark.asyncio
    async def test_simultaneous_with_ties(self):
        response = _make_simultaneous_response(
            rankings=["BASELINE", "MCP"],
            per_output_scores={
                "BASELINE": {"Correctness": {"score": 0.7, "evidence": "ok", "reasoning": "ok"}},
                "MCP": {"Correctness": {"score": 0.7, "evidence": "ok", "reasoning": "ok"}},
            },
            ties=["BASELINE_MCP"],
        )
        backend = _make_mock_backend(response)
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_simultaneous(inp)
        assert verdict.ties == 1

    @pytest.mark.asyncio
    async def test_simultaneous_preference_matrix(self):
        response = _make_simultaneous_response(
            rankings=["A", "B", "C"],
            per_output_scores={
                "A": {"Correctness": {"score": 0.9, "evidence": "best", "reasoning": "top"}},
                "B": {"Correctness": {"score": 0.7, "evidence": "mid", "reasoning": "ok"}},
                "C": {"Correctness": {"score": 0.5, "evidence": "low", "reasoning": "weak"}},
            },
        )
        backend = _make_mock_backend(response)
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input({"A": "a", "B": "b", "C": "c"})

        verdict = await evaluator.evaluate_simultaneous(inp)

        assert verdict.preference_matrix["A"]["B"] == 1.0
        assert verdict.preference_matrix["B"]["A"] == 0.0
        assert verdict.preference_matrix["A"]["C"] == 1.0
        assert verdict.preference_matrix["B"]["C"] == 1.0
        assert verdict.preference_matrix["C"]["B"] == 0.0

    @pytest.mark.asyncio
    async def test_simultaneous_confidence(self):
        response = _make_simultaneous_response(
            rankings=["A", "B"],
            per_output_scores={
                "A": {"Correctness": {"score": 0.8, "evidence": "ok", "reasoning": "ok"}},
                "B": {"Correctness": {"score": 0.6, "evidence": "ok", "reasoning": "ok"}},
            },
            confidence=0.92,
        )
        backend = _make_mock_backend(response)
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input({"A": "a", "B": "b"})

        verdict = await evaluator.evaluate_simultaneous(inp)
        assert verdict.confidence == 0.92


# ---------- Round-robin evaluation tests ----------


class TestEvaluateRoundRobin:
    @pytest.mark.asyncio
    async def test_two_way_roundrobin(self):
        """Two conditions = 1 pair, evaluated in both orderings (2 calls)."""
        scores = {"Correctness": {"score": 0.8, "evidence": "good", "reasoning": "right"}}
        scores_low = {"Correctness": {"score": 0.5, "evidence": "ok", "reasoning": "partial"}}

        response_ab = _make_roundrobin_response("A", scores, scores_low, 0.85)
        response_ba = _make_roundrobin_response("B", scores_low, scores, 0.80)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert isinstance(verdict, PairwiseVerdict)
        assert len(verdict.win_rates) == 2
        assert backend.evaluate.await_count == 2
        assert verdict.mode == EvaluationMode.PAIRWISE

    @pytest.mark.asyncio
    async def test_three_way_roundrobin(self):
        """Three conditions = 3 pairs, each evaluated twice = 6 backend calls."""
        scores_high = {"Correctness": {"score": 0.9, "evidence": "top", "reasoning": "best"}}
        scores_mid = {"Correctness": {"score": 0.7, "evidence": "mid", "reasoning": "ok"}}
        scores_low = {"Correctness": {"score": 0.4, "evidence": "low", "reasoning": "weak"}}

        responses = [
            _make_roundrobin_response("A", scores_high, scores_mid),
            _make_roundrobin_response("B", scores_mid, scores_high),
            _make_roundrobin_response("A", scores_high, scores_low),
            _make_roundrobin_response("B", scores_low, scores_high),
            _make_roundrobin_response("A", scores_mid, scores_low),
            _make_roundrobin_response("B", scores_low, scores_mid),
        ]

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=responses)
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input({
            "A": "best output",
            "B": "mid output",
            "C": "low output",
        })

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert len(verdict.win_rates) == 3
        assert backend.evaluate.await_count == 6
        assert len(verdict.rankings) == 3

    @pytest.mark.asyncio
    async def test_position_swap_consistency_detected(self):
        """When AB and BA give different winners, flag as inconsistent."""
        scores_a = {"Correctness": {"score": 0.7, "evidence": "ok", "reasoning": "ok"}}
        scores_b = {"Correctness": {"score": 0.6, "evidence": "ok", "reasoning": "ok"}}

        response_ab = _make_roundrobin_response("A", scores_a, scores_b)
        response_ba = _make_roundrobin_response("A", scores_a, scores_b)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert "inconsistent_pairs" in verdict.metadata
        assert len(verdict.metadata["inconsistent_pairs"]) > 0

    @pytest.mark.asyncio
    async def test_position_swap_consistent(self):
        """When AB says A wins and BA says B wins (=A wins), it's consistent."""
        scores_high = {"Correctness": {"score": 0.9, "evidence": "top", "reasoning": "best"}}
        scores_low = {"Correctness": {"score": 0.3, "evidence": "low", "reasoning": "weak"}}

        response_ab = _make_roundrobin_response("A", scores_high, scores_low, 0.9)
        response_ba = _make_roundrobin_response("B", scores_low, scores_high, 0.9)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert verdict.metadata.get("inconsistent_pairs") == []

    @pytest.mark.asyncio
    async def test_tie_handling(self):
        """When both orderings produce a tie, it stays a tie."""
        scores_eq = {"Correctness": {"score": 0.7, "evidence": "ok", "reasoning": "ok"}}

        response_ab = _make_roundrobin_response("TIE", scores_eq, scores_eq, 0.7)
        response_ba = _make_roundrobin_response("TIE", scores_eq, scores_eq, 0.7)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert verdict.ties == 1
        assert verdict.win_rates["BASELINE"] == pytest.approx(0.5)
        assert verdict.win_rates["MCP"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_roundrobin_preference_matrix(self):
        """Preference matrix should reflect pairwise outcomes."""
        scores_high = {"Correctness": {"score": 0.9, "evidence": "top", "reasoning": "best"}}
        scores_low = {"Correctness": {"score": 0.3, "evidence": "low", "reasoning": "weak"}}

        response_ab = _make_roundrobin_response("A", scores_high, scores_low, 0.9)
        response_ba = _make_roundrobin_response("B", scores_low, scores_high, 0.9)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert "BASELINE" in verdict.preference_matrix
        assert "MCP" in verdict.preference_matrix
        assert verdict.preference_matrix["BASELINE"]["MCP"] == 1.0
        assert verdict.preference_matrix["MCP"]["BASELINE"] == 0.0

    @pytest.mark.asyncio
    async def test_roundrobin_win_rate_aggregation(self):
        """Win rates should be normalized by total pair count."""
        scores_high = {"Correctness": {"score": 0.9, "evidence": "good", "reasoning": "best"}}
        scores_low = {"Correctness": {"score": 0.3, "evidence": "weak", "reasoning": "bad"}}

        response_ab = _make_roundrobin_response("A", scores_high, scores_low, 0.9)
        response_ba = _make_roundrobin_response("B", scores_low, scores_high, 0.9)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        evaluator = PairwiseEvaluator(backend, JudgeConfig(), _TEMPLATES_DIR)
        inp = _make_pairwise_input()

        verdict = await evaluator.evaluate_roundrobin(inp)

        assert verdict.win_rates["BASELINE"] == pytest.approx(1.0)
        assert verdict.win_rates["MCP"] == pytest.approx(0.0)


# ---------- UnifiedJudge integration ----------


class TestUnifiedJudgePairwiseIntegration:
    @pytest.mark.asyncio
    async def test_dispatch_simultaneous_by_default(self):
        response = _make_simultaneous_response(
            rankings=["BASELINE", "MCP"],
            per_output_scores={
                "BASELINE": {"Correctness": {"score": 0.9, "evidence": "good", "reasoning": "right"}},
                "MCP": {"Correctness": {"score": 0.6, "evidence": "ok", "reasoning": "partial"}},
            },
        )
        backend = _make_mock_backend(response)
        judge = UnifiedJudge(backend)
        inp = _make_pairwise_input()

        verdict = await judge.evaluate(inp)

        assert isinstance(verdict, PairwiseVerdict)
        assert verdict.rankings == ["BASELINE", "MCP"]
        backend.evaluate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispatch_roundrobin_via_config(self):
        scores_high = {"Correctness": {"score": 0.8, "evidence": "good", "reasoning": "ok"}}
        scores_low = {"Correctness": {"score": 0.5, "evidence": "ok", "reasoning": "weak"}}

        response_ab = _make_roundrobin_response("A", scores_high, scores_low)
        response_ba = _make_roundrobin_response("B", scores_low, scores_high)

        backend = _make_mock_backend()
        backend.evaluate = AsyncMock(side_effect=[response_ab, response_ba])
        config = JudgeConfig(pairwise_method="round_robin")
        judge = UnifiedJudge(backend, config)
        inp = _make_pairwise_input()

        verdict = await judge.evaluate(inp)

        assert isinstance(verdict, PairwiseVerdict)
        assert backend.evaluate.await_count == 2
        assert verdict.metadata.get("method") == "round_robin"


# ---------- Helper function tests ----------


class TestPairwiseHelpers:
    def test_average_dimension_scores(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        s1 = {
            "Correctness": DimensionScore(
                dimension="Correctness", score=0.8, weight=0.3,
                evidence="ev1", reasoning="r1",
            )
        }
        s2 = {
            "Correctness": DimensionScore(
                dimension="Correctness", score=0.6, weight=0.3,
                evidence="ev2", reasoning="r2",
            )
        }
        merged = evaluator._average_dimension_scores(s1, s2)
        assert merged["Correctness"].score == pytest.approx(0.7)
        assert merged["Correctness"].weight == pytest.approx(0.3)

    def test_average_dimension_scores_partial_overlap(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        s1 = {
            "Correctness": DimensionScore(
                dimension="Correctness", score=0.8, weight=0.3,
                evidence="e", reasoning="r",
            )
        }
        s2 = {
            "Completeness": DimensionScore(
                dimension="Completeness", score=0.6, weight=0.25,
                evidence="e", reasoning="r",
            )
        }
        merged = evaluator._average_dimension_scores(s1, s2)
        assert "Correctness" in merged
        assert "Completeness" in merged
        assert merged["Correctness"].score == 0.8
        assert merged["Completeness"].score == 0.6

    def test_build_preference_matrix_from_rankings(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        matrix = evaluator._build_preference_matrix_from_rankings(
            ["A", "B", "C"], ["A", "B", "C"]
        )
        assert matrix["A"]["B"] == 1.0
        assert matrix["B"]["A"] == 0.0
        assert matrix["A"]["C"] == 1.0
        assert matrix["C"]["A"] == 0.0
        assert matrix["B"]["C"] == 1.0
        assert matrix["C"]["B"] == 0.0

    def test_is_inconsistent_true(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        result_ab = PairResult(
            condition_a="X", condition_b="Y", winner="X",
            scores_a={}, scores_b={}, confidence=0.8, reasoning="AB",
        )
        result_ba = PairResult(
            condition_a="Y", condition_b="X", winner="Y",
            scores_a={}, scores_b={}, confidence=0.8, reasoning="BA",
        )
        assert evaluator._is_inconsistent(result_ab, result_ba, "X", "Y") is True

    def test_is_inconsistent_false(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        result_ab = PairResult(
            condition_a="X", condition_b="Y", winner="X",
            scores_a={}, scores_b={}, confidence=0.8, reasoning="AB",
        )
        result_ba = PairResult(
            condition_a="Y", condition_b="X", winner="X",
            scores_a={}, scores_b={}, confidence=0.8, reasoning="BA",
        )
        assert evaluator._is_inconsistent(result_ab, result_ba, "X", "Y") is False

    def test_is_inconsistent_tie_both(self):
        evaluator = PairwiseEvaluator(
            _make_mock_backend(), JudgeConfig(), _TEMPLATES_DIR
        )
        result_ab = PairResult(
            condition_a="X", condition_b="Y", winner="TIE",
            scores_a={}, scores_b={}, confidence=0.5, reasoning="AB",
        )
        result_ba = PairResult(
            condition_a="Y", condition_b="X", winner="TIE",
            scores_a={}, scores_b={}, confidence=0.5, reasoning="BA",
        )
        assert evaluator._is_inconsistent(result_ab, result_ba, "X", "Y") is False


# ---------- Export tests ----------


class TestPairwiseExports:
    def test_pairwise_evaluator_importable(self):
        from src.judge.modes.pairwise import PairwiseEvaluator
        assert PairwiseEvaluator is not None

    def test_pair_result_importable(self):
        from src.judge.modes.pairwise import PairResult
        assert PairResult is not None

    def test_modes_init_exports(self):
        from src.judge.modes import PairwiseEvaluator
        assert PairwiseEvaluator is not None

    def test_top_level_export(self):
        from src.judge import PairwiseEvaluator
        assert PairwiseEvaluator is not None
