"""Unit tests for inter-judge agreement metrics module."""

from __future__ import annotations

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

from src.judge.metrics import (  # noqa: E402
    AgreementReport,
    compute_cohens_kappa,
    compute_fleiss_kappa,
    compute_krippendorff_alpha,
    compute_spearman_correlation,
    generate_agreement_report,
    _categorize_score,
    _compute_ranks,
)
from src.judge.models import (  # noqa: E402
    EvaluationMode,
    JudgeVerdict,
)


def _make_verdict(overall_score: float, model_id: str = "test") -> JudgeVerdict:
    return JudgeVerdict(
        mode=EvaluationMode.DIRECT,
        scores={},
        overall_score=overall_score,
        reasoning="test",
        evidence=[],
        confidence=0.8,
        model_id=model_id,
    )


class TestAgreementReport:
    def test_construction(self):
        report = AgreementReport(
            cohens_kappa={"A vs B": 0.8},
            fleiss_kappa=0.75,
            krippendorff_alpha=0.7,
            spearman_correlations={"A vs B": 0.9},
            low_agreement_flag=False,
        )
        assert report.cohens_kappa == {"A vs B": 0.8}
        assert report.fleiss_kappa == 0.75
        assert report.krippendorff_alpha == 0.7
        assert report.spearman_correlations == {"A vs B": 0.9}
        assert report.low_agreement_flag is False

    def test_defaults(self):
        report = AgreementReport()
        assert report.cohens_kappa == {}
        assert report.fleiss_kappa == 0.0
        assert report.krippendorff_alpha == 0.0
        assert report.spearman_correlations == {}
        assert report.low_agreement_flag is False

    def test_immutability(self):
        report = AgreementReport()
        with pytest.raises(AttributeError):
            report.fleiss_kappa = 0.5  # type: ignore[misc]


class TestCohensKappa:
    def test_perfect_agreement(self):
        ratings = ["pass", "fail", "partial", "pass", "fail"]
        kappa = compute_cohens_kappa(ratings, ratings)
        assert kappa == pytest.approx(1.0)

    def test_no_agreement_beyond_chance(self):
        # Rater A always says "pass", rater B always says "fail"
        # p_observed=0, p_expected=0 -> kappa=0 (degenerate case)
        a = ["pass"] * 10
        b = ["fail"] * 10
        kappa = compute_cohens_kappa(a, b)
        assert kappa <= 0.0

    def test_known_example(self):
        # Classic 2x2 example: 20 items, 2 raters, 2 categories
        # Both agree "yes" on 10, both agree "no" on 5,
        # A=yes/B=no on 3, A=no/B=yes on 2
        a = ["yes"] * 13 + ["no"] * 7
        b = ["yes"] * 10 + ["no"] * 3 + ["yes"] * 2 + ["no"] * 5
        kappa = compute_cohens_kappa(a, b)
        # p_o = 15/20 = 0.75
        # p_e = (13*12 + 7*8) / 400 = (156+56)/400 = 0.53
        # kappa = (0.75 - 0.53) / (1 - 0.53) = 0.22/0.47 ≈ 0.468
        assert kappa == pytest.approx(0.468, abs=0.01)

    def test_empty_ratings(self):
        assert compute_cohens_kappa([], []) == 0.0

    def test_mismatched_lengths(self):
        assert compute_cohens_kappa(["a", "b"], ["a"]) == 0.0

    def test_single_category(self):
        # Both raters always agree on same category
        a = ["pass"] * 5
        b = ["pass"] * 5
        kappa = compute_cohens_kappa(a, b)
        assert kappa == 1.0


class TestFleissKappa:
    def test_perfect_agreement(self):
        # 3 raters, 5 subjects, 3 categories; all agree
        matrix = [
            [3, 0, 0],
            [0, 3, 0],
            [0, 0, 3],
            [3, 0, 0],
            [0, 3, 0],
        ]
        kappa = compute_fleiss_kappa(matrix)
        assert kappa == pytest.approx(1.0)

    def test_no_agreement(self):
        # Each rater picks a different category for every subject
        # With 3 raters and 3 categories, maximum disagreement yields -0.5
        matrix = [
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
        ]
        kappa = compute_fleiss_kappa(matrix)
        assert kappa < 0.0  # Worse than chance

    def test_known_example(self):
        # Fleiss (1971) Table 1 example (simplified, 3 raters, 2 categories)
        # 10 subjects rated by 3 raters into 2 categories
        matrix = [
            [3, 0],
            [3, 0],
            [3, 0],
            [2, 1],
            [2, 1],
            [1, 2],
            [1, 2],
            [0, 3],
            [0, 3],
            [0, 3],
        ]
        kappa = compute_fleiss_kappa(matrix)
        # P_bar = avg of P_i where P_i = (sum(n_ij^2) - n) / (n*(n-1))
        # This is a moderate agreement scenario
        assert 0.3 < kappa < 0.8

    def test_empty_matrix(self):
        assert compute_fleiss_kappa([]) == 0.0
        assert compute_fleiss_kappa([[]]) == 0.0

    def test_inconsistent_rater_counts(self):
        matrix = [
            [2, 1],
            [1, 1],  # Only 2 raters instead of 3
        ]
        assert compute_fleiss_kappa(matrix) == 0.0

    def test_single_rater(self):
        matrix = [[1, 0], [0, 1]]
        assert compute_fleiss_kappa(matrix) == 0.0


class TestKrippendorffAlpha:
    def test_perfect_agreement_nominal(self):
        ratings = [
            ["a", "b", "c", "a"],
            ["a", "b", "c", "a"],
            ["a", "b", "c", "a"],
        ]
        alpha = compute_krippendorff_alpha(ratings, level="nominal")
        assert alpha == pytest.approx(1.0)

    def test_no_agreement_nominal(self):
        ratings = [
            ["a", "b", "a"],
            ["b", "a", "b"],
        ]
        alpha = compute_krippendorff_alpha(ratings, level="nominal")
        assert alpha < 0.0

    def test_interval_level(self):
        # Perfect agreement on interval data
        ratings = [
            [1.0, 2.0, 3.0, 4.0],
            [1.0, 2.0, 3.0, 4.0],
        ]
        alpha = compute_krippendorff_alpha(ratings, level="interval")
        assert alpha == pytest.approx(1.0)

    def test_interval_with_noise(self):
        # Close agreement
        ratings = [
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [1.1, 2.1, 2.9, 4.1, 4.9],
        ]
        alpha = compute_krippendorff_alpha(ratings, level="interval")
        assert alpha > 0.9

    def test_with_missing_values(self):
        ratings = [
            ["a", "b", None, "a"],
            ["a", "b", "c", "a"],
            ["a", None, "c", "a"],
        ]
        alpha = compute_krippendorff_alpha(ratings, level="nominal")
        # Should handle None values gracefully
        assert alpha > 0.5

    def test_empty_matrix(self):
        assert compute_krippendorff_alpha([]) == 0.0
        assert compute_krippendorff_alpha([[]]) == 0.0

    def test_single_rater(self):
        assert compute_krippendorff_alpha([[1, 2, 3]]) == 0.0

    def test_mismatched_row_lengths(self):
        ratings = [
            [1, 2, 3],
            [1, 2],
        ]
        assert compute_krippendorff_alpha(ratings) == 0.0

    def test_invalid_level(self):
        with pytest.raises(ValueError, match="Unsupported measurement level"):
            compute_krippendorff_alpha([[1, 2], [1, 2]], level="ratio")


class TestSpearmanCorrelation:
    def test_perfect_positive(self):
        rho, p = compute_spearman_correlation([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert rho == pytest.approx(1.0)
        assert p < 0.05

    def test_perfect_negative(self):
        rho, p = compute_spearman_correlation([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert rho == pytest.approx(-1.0)
        assert p < 0.05

    def test_no_correlation(self):
        # Designed to have near-zero rank correlation
        rho, _ = compute_spearman_correlation(
            [1, 2, 3, 4, 5], [3, 1, 5, 2, 4]
        )
        assert abs(rho) < 0.5

    def test_tied_values(self):
        rho, _ = compute_spearman_correlation(
            [1, 1, 2, 3, 3], [1, 2, 2, 3, 3]
        )
        assert rho > 0.5  # Should still show positive correlation

    def test_empty(self):
        rho, p = compute_spearman_correlation([], [])
        assert rho == 0.0
        assert p == 1.0

    def test_single_value(self):
        rho, p = compute_spearman_correlation([1.0], [2.0])
        assert rho == 0.0
        assert p == 1.0

    def test_mismatched_lengths(self):
        rho, p = compute_spearman_correlation([1, 2], [1, 2, 3])
        assert rho == 0.0
        assert p == 1.0

    def test_two_values(self):
        rho, _ = compute_spearman_correlation([1.0, 2.0], [3.0, 4.0])
        assert rho == pytest.approx(1.0)


class TestComputeRanks:
    def test_no_ties(self):
        ranks = _compute_ranks([30, 10, 20])
        assert ranks == pytest.approx([3.0, 1.0, 2.0])

    def test_with_ties(self):
        ranks = _compute_ranks([1, 2, 2, 4])
        assert ranks == pytest.approx([1.0, 2.5, 2.5, 4.0])

    def test_all_tied(self):
        ranks = _compute_ranks([5, 5, 5])
        assert ranks == pytest.approx([2.0, 2.0, 2.0])


class TestCategorizeScore:
    def test_pass(self):
        assert _categorize_score(1.0) == "pass"
        assert _categorize_score(0.75) == "pass"

    def test_partial(self):
        assert _categorize_score(0.5) == "partial"
        assert _categorize_score(0.25) == "partial"

    def test_fail(self):
        assert _categorize_score(0.0) == "fail"
        assert _categorize_score(0.24) == "fail"


class TestGenerateAgreementReport:
    def test_perfect_agreement(self):
        verdicts = {
            "model_a": [
                _make_verdict(0.9, "model_a"),
                _make_verdict(0.1, "model_a"),
                _make_verdict(0.5, "model_a"),
            ],
            "model_b": [
                _make_verdict(0.9, "model_b"),
                _make_verdict(0.1, "model_b"),
                _make_verdict(0.5, "model_b"),
            ],
        }
        report = generate_agreement_report(verdicts)
        assert report.cohens_kappa["model_a vs model_b"] == pytest.approx(1.0)
        assert report.spearman_correlations["model_a vs model_b"] == pytest.approx(1.0)
        assert report.fleiss_kappa == pytest.approx(1.0)
        assert report.low_agreement_flag is False

    def test_low_agreement_flagged(self):
        verdicts = {
            "model_a": [
                _make_verdict(0.9, "model_a"),
                _make_verdict(0.1, "model_a"),
                _make_verdict(0.5, "model_a"),
            ],
            "model_b": [
                _make_verdict(0.1, "model_b"),
                _make_verdict(0.9, "model_b"),
                _make_verdict(0.5, "model_b"),
            ],
        }
        report = generate_agreement_report(verdicts, threshold=0.8)
        assert report.low_agreement_flag is True

    def test_single_model_flags_low_agreement(self):
        verdicts = {
            "model_a": [_make_verdict(0.5, "model_a")],
        }
        report = generate_agreement_report(verdicts)
        assert report.low_agreement_flag is True

    def test_empty_verdicts(self):
        verdicts = {
            "model_a": [],
            "model_b": [],
        }
        report = generate_agreement_report(verdicts)
        assert report.low_agreement_flag is True

    def test_mismatched_verdict_counts(self):
        verdicts = {
            "model_a": [_make_verdict(0.5)],
            "model_b": [_make_verdict(0.5), _make_verdict(0.8)],
        }
        report = generate_agreement_report(verdicts)
        assert report.low_agreement_flag is True

    def test_three_models(self):
        verdicts = {
            "model_a": [
                _make_verdict(0.9, "model_a"),
                _make_verdict(0.1, "model_a"),
                _make_verdict(0.5, "model_a"),
            ],
            "model_b": [
                _make_verdict(0.85, "model_b"),
                _make_verdict(0.15, "model_b"),
                _make_verdict(0.55, "model_b"),
            ],
            "model_c": [
                _make_verdict(0.95, "model_c"),
                _make_verdict(0.05, "model_c"),
                _make_verdict(0.45, "model_c"),
            ],
        }
        report = generate_agreement_report(verdicts)
        # All models roughly agree
        assert len(report.cohens_kappa) == 3  # 3 pairs
        assert len(report.spearman_correlations) == 3
        assert report.fleiss_kappa > 0.0
