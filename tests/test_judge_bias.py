"""Unit tests for bias detection and mitigation module."""

from __future__ import annotations

import math
import sys
from types import ModuleType
from unittest.mock import MagicMock

# --- Together SDK mock setup (required before importing src.judge) ---
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

import pytest  # noqa: E402

from src.judge.bias import (  # noqa: E402
    BiasLevel,
    BiasReport,
    compute_length_correlation,
    compute_position_consistency,
    generate_bias_report,
    inject_anti_bias_instructions,
    _extract_condition_score,
    _pearson_correlation,
)
from src.judge.models import (  # noqa: E402
    DimensionScore,
    DirectInput,
    EvaluationMode,
    JudgeInput,
    JudgeVerdict,
    PairwiseInput,
    PairwiseVerdict,
)


def _make_verdict(**overrides):
    defaults = {
        "mode": EvaluationMode.DIRECT,
        "scores": {},
        "overall_score": 0.5,
        "reasoning": "test",
        "evidence": [],
        "confidence": 0.8,
        "model_id": "test-model",
    }
    defaults.update(overrides)
    return JudgeVerdict(**defaults)


def _make_pairwise_verdict(**overrides):
    defaults = {
        "mode": EvaluationMode.PAIRWISE,
        "scores": {},
        "overall_score": 0.5,
        "reasoning": "test",
        "evidence": [],
        "confidence": 0.8,
        "model_id": "test-model",
        "rankings": [],
        "win_rates": {},
        "preference_matrix": {},
        "ties": 0,
        "metadata": {},
    }
    defaults.update(overrides)
    return PairwiseVerdict(**defaults)


class TestBiasLevel:
    def test_values(self):
        assert BiasLevel.NONE.value == "none"
        assert BiasLevel.STANDARD.value == "standard"
        assert BiasLevel.AGGRESSIVE.value == "aggressive"

    def test_all_levels_exist(self):
        levels = {bl.name for bl in BiasLevel}
        assert levels == {"NONE", "STANDARD", "AGGRESSIVE"}


class TestBiasReport:
    def test_construction(self):
        report = BiasReport(
            position_consistency_rate=0.85,
            length_score_correlation=0.12,
            flagged_pairs=["A vs B"],
            bias_level_used=BiasLevel.STANDARD,
        )
        assert report.position_consistency_rate == 0.85
        assert report.length_score_correlation == 0.12
        assert report.flagged_pairs == ["A vs B"]
        assert report.bias_level_used == BiasLevel.STANDARD

    def test_defaults(self):
        report = BiasReport(
            position_consistency_rate=1.0,
            length_score_correlation=0.0,
        )
        assert report.flagged_pairs == []
        assert report.bias_level_used == BiasLevel.NONE

    def test_immutability(self):
        report = BiasReport(
            position_consistency_rate=1.0,
            length_score_correlation=0.0,
        )
        with pytest.raises(AttributeError):
            report.position_consistency_rate = 0.5  # type: ignore[misc]


class TestComputePositionConsistency:
    def test_empty_results(self):
        assert compute_position_consistency([]) == 1.0

    def test_fully_consistent(self):
        verdict = _make_pairwise_verdict(
            metadata={"total_pairs": 3, "inconsistent_pairs": []}
        )
        assert compute_position_consistency([verdict]) == 1.0

    def test_some_inconsistency(self):
        verdict = _make_pairwise_verdict(
            metadata={
                "total_pairs": 4,
                "inconsistent_pairs": ["A vs B"],
            }
        )
        result = compute_position_consistency([verdict])
        assert result == pytest.approx(0.75)

    def test_all_inconsistent(self):
        verdict = _make_pairwise_verdict(
            metadata={
                "total_pairs": 2,
                "inconsistent_pairs": ["A vs B", "B vs C"],
            }
        )
        assert compute_position_consistency([verdict]) == pytest.approx(0.0)

    def test_multiple_verdicts_aggregated(self):
        v1 = _make_pairwise_verdict(
            metadata={"total_pairs": 3, "inconsistent_pairs": ["A vs B"]}
        )
        v2 = _make_pairwise_verdict(
            metadata={"total_pairs": 3, "inconsistent_pairs": []}
        )
        result = compute_position_consistency([v1, v2])
        assert result == pytest.approx(5.0 / 6.0)

    def test_no_metadata(self):
        verdict = _make_pairwise_verdict(metadata={})
        assert compute_position_consistency([verdict]) == 1.0


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        assert _pearson_correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)

    def test_perfect_negative(self):
        assert _pearson_correlation([1, 2, 3], [6, 4, 2]) == pytest.approx(-1.0)

    def test_no_correlation(self):
        # Symmetric data pattern that produces zero correlation
        result = _pearson_correlation([1, 2, 3, 2, 1], [1, 2, 1, 2, 1])
        assert abs(result) < 0.3

    def test_insufficient_data(self):
        assert _pearson_correlation([], []) == 0.0
        assert _pearson_correlation([1], [2]) == 0.0

    def test_zero_variance(self):
        assert _pearson_correlation([5, 5, 5], [1, 2, 3]) == 0.0

    def test_mismatched_lengths(self):
        assert _pearson_correlation([1, 2], [1, 2, 3]) == 0.0


class TestComputeLengthCorrelation:
    def test_direct_inputs(self):
        inputs = [
            DirectInput(
                task_id="t1",
                task_description="task",
                evaluation_mode=EvaluationMode.DIRECT,
                agent_output="short",
            ),
            DirectInput(
                task_id="t2",
                task_description="task",
                evaluation_mode=EvaluationMode.DIRECT,
                agent_output="a much longer output that has more text",
            ),
            DirectInput(
                task_id="t3",
                task_description="task",
                evaluation_mode=EvaluationMode.DIRECT,
                agent_output="the longest output of all with extra words padding the length",
            ),
        ]
        verdicts = [
            _make_verdict(overall_score=0.3),
            _make_verdict(overall_score=0.6),
            _make_verdict(overall_score=0.9),
        ]
        result = compute_length_correlation(inputs, verdicts)
        assert result > 0.9  # Strong positive correlation

    def test_pairwise_inputs_with_win_rates(self):
        inputs = [
            PairwiseInput(
                task_id="t1",
                task_description="compare",
                evaluation_mode=EvaluationMode.PAIRWISE,
                outputs={"A": "short", "B": "much longer output text here"},
            )
        ]
        verdicts = [
            _make_pairwise_verdict(
                win_rates={"A": 0.3, "B": 0.7},
            )
        ]
        result = compute_length_correlation(inputs, verdicts)
        # Longer output B has higher win_rate -> positive correlation
        assert result > 0.9

    def test_empty_inputs(self):
        assert compute_length_correlation([], []) == 0.0


class TestExtractConditionScore:
    def test_from_win_rates(self):
        verdict = _make_pairwise_verdict(win_rates={"A": 0.7, "B": 0.3})
        assert _extract_condition_score(verdict, "A") == 0.7
        assert _extract_condition_score(verdict, "B") == 0.3

    def test_from_dimension_scores(self):
        scores = {
            "A/correctness": DimensionScore(
                dimension="correctness",
                score=0.8,
                weight=0.5,
                evidence="ok",
                reasoning="good",
            ),
            "A/style": DimensionScore(
                dimension="style",
                score=0.6,
                weight=0.5,
                evidence="ok",
                reasoning="ok",
            ),
        }
        verdict = _make_verdict(scores=scores)
        result = _extract_condition_score(verdict, "A")
        assert result == pytest.approx(0.7)

    def test_missing_condition(self):
        verdict = _make_verdict(scores={})
        assert _extract_condition_score(verdict, "MISSING") is None


class TestGenerateBiasReport:
    def test_full_report(self):
        inputs = [
            DirectInput(
                task_id="t1",
                task_description="task",
                evaluation_mode=EvaluationMode.DIRECT,
                agent_output="output",
            ),
        ]
        verdicts = [_make_verdict(overall_score=0.7)]

        report = generate_bias_report(inputs, verdicts, BiasLevel.STANDARD)
        assert isinstance(report, BiasReport)
        assert report.position_consistency_rate == 1.0  # No pairwise data
        assert report.bias_level_used == BiasLevel.STANDARD

    def test_with_pairwise_data(self):
        inputs: list[JudgeInput] = [
            PairwiseInput(
                task_id="t1",
                task_description="compare",
                evaluation_mode=EvaluationMode.PAIRWISE,
                outputs={"A": "out a", "B": "out b"},
            ),
        ]
        verdicts: list[JudgeVerdict] = [
            _make_pairwise_verdict(
                metadata={
                    "total_pairs": 1,
                    "inconsistent_pairs": ["A vs B"],
                },
                win_rates={"A": 0.5, "B": 0.5},
            )
        ]

        report = generate_bias_report(inputs, verdicts)
        assert report.position_consistency_rate == pytest.approx(0.0)
        assert report.flagged_pairs == ["A vs B"]

    def test_default_bias_level(self):
        report = generate_bias_report([], [])
        assert report.bias_level_used == BiasLevel.NONE


class TestInjectAntiBiasInstructions:
    def test_none_level_unchanged(self):
        prompt = "Evaluate this output."
        result = inject_anti_bias_instructions(prompt, BiasLevel.NONE)
        assert result == prompt

    def test_standard_adds_position_and_length(self):
        prompt = "Evaluate this output."
        result = inject_anti_bias_instructions(prompt, BiasLevel.STANDARD)
        assert "POSITION BIAS" in result
        assert "LENGTH BIAS" in result
        assert "SELF-ENHANCEMENT" not in result

    def test_aggressive_adds_all(self):
        prompt = "Evaluate this output."
        result = inject_anti_bias_instructions(prompt, BiasLevel.AGGRESSIVE)
        assert "POSITION BIAS" in result
        assert "LENGTH BIAS" in result
        assert "LENGTH NORMALIZATION" in result
        assert "SELF-ENHANCEMENT" in result
        assert "ANCHORING" in result

    def test_preserves_original_prompt(self):
        prompt = "Original prompt text here."
        result = inject_anti_bias_instructions(prompt, BiasLevel.STANDARD)
        assert result.startswith("Original prompt text here.")

    def test_standard_is_subset_of_aggressive(self):
        prompt = "test"
        standard = inject_anti_bias_instructions(prompt, BiasLevel.STANDARD)
        aggressive = inject_anti_bias_instructions(prompt, BiasLevel.AGGRESSIVE)
        # Aggressive should contain everything standard has plus more
        assert len(aggressive) > len(standard)
