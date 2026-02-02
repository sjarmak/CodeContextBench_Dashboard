"""Unit tests for scripts/ccb_pipeline/analyze.py."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scripts.ccb_pipeline.analyze import (
    ConfigAggregateMetrics,
    EffectSizeResult,
    PairwiseTestResult,
    _cohens_d,
    _flatten_trials,
    _group_by_config,
    _interpret_cohens_d,
    _proportion_z_test,
    _safe_mean,
    _safe_median,
    _safe_se,
    _se_proportion,
    analyze,
    compute_aggregate_metrics,
    compute_effect_sizes,
    compute_pairwise_tests,
    main,
)


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _make_trial(
    *,
    agent_config: str = "BASELINE",
    reward: float | None = 1.0,
    pass_fail: str = "pass",
    duration_seconds: float | None = 300.0,
    input_tokens: int = 5000,
    output_tokens: int = 1000,
    cached_tokens: int = 200,
    task_name: str = "task-001",
    benchmark: str = "big_code_mcp",
) -> dict:
    return {
        "trial_id": "trial-001",
        "task_name": task_name,
        "benchmark": benchmark,
        "agent_config": agent_config,
        "reward": reward,
        "pass_fail": pass_fail,
        "duration_seconds": duration_seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "tool_utilization": {},
    }


def _make_categories(trials: list[dict]) -> list[dict]:
    """Wrap trials into the standard categories structure."""
    return [
        {
            "run_category": "official",
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "trials": trials,
                }
            ],
        }
    ]


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestSafeMean:
    def test_empty(self) -> None:
        assert _safe_mean([]) == 0.0

    def test_single(self) -> None:
        assert _safe_mean([5.0]) == 5.0

    def test_multiple(self) -> None:
        assert _safe_mean([2.0, 4.0, 6.0]) == 4.0


class TestSafeSe:
    def test_empty(self) -> None:
        assert _safe_se([]) == 0.0

    def test_single(self) -> None:
        assert _safe_se([5.0]) == 0.0

    def test_multiple(self) -> None:
        # SE = sqrt(var / n), var = sample variance
        values = [2.0, 4.0, 6.0]
        mean = 4.0
        var = sum((x - mean) ** 2 for x in values) / 2  # n-1
        expected = math.sqrt(var / 3)
        assert abs(_safe_se(values) - expected) < 1e-10


class TestSafeMedian:
    def test_empty(self) -> None:
        assert _safe_median([]) is None

    def test_single(self) -> None:
        assert _safe_median([5.0]) == 5.0

    def test_odd(self) -> None:
        assert _safe_median([1.0, 3.0, 2.0]) == 2.0

    def test_even(self) -> None:
        assert _safe_median([1.0, 2.0, 3.0, 4.0]) == 2.5


class TestSeProportion:
    def test_zero_n(self) -> None:
        assert _se_proportion(0.5, 0) == 0.0

    def test_zero_proportion(self) -> None:
        assert _se_proportion(0.0, 100) == 0.0

    def test_valid(self) -> None:
        se = _se_proportion(0.5, 100)
        expected = math.sqrt(0.5 * 0.5 / 100)
        assert abs(se - expected) < 1e-10


class TestCohensD:
    def test_insufficient_data(self) -> None:
        assert _cohens_d([1.0], [2.0]) == 0.0
        assert _cohens_d([], [1.0, 2.0]) == 0.0

    def test_identical_groups(self) -> None:
        assert _cohens_d([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0

    def test_different_groups(self) -> None:
        d = _cohens_d([10.0, 11.0, 12.0], [0.0, 1.0, 2.0])
        assert d > 0  # Group A has higher values


class TestInterpretCohensD:
    def test_negligible(self) -> None:
        assert _interpret_cohens_d(0.1) == "negligible"

    def test_small(self) -> None:
        assert _interpret_cohens_d(0.3) == "small"

    def test_medium(self) -> None:
        assert _interpret_cohens_d(0.6) == "medium"

    def test_large(self) -> None:
        assert _interpret_cohens_d(1.0) == "large"

    def test_negative(self) -> None:
        assert _interpret_cohens_d(-0.9) == "large"


class TestProportionZTest:
    def test_empty(self) -> None:
        z, p = _proportion_z_test(0, 0, 0, 0)
        assert z == 0.0
        assert p == 1.0

    def test_identical_rates(self) -> None:
        z, p = _proportion_z_test(50, 100, 50, 100)
        assert abs(z) < 1e-10
        assert abs(p - 1.0) < 1e-5

    def test_different_rates(self) -> None:
        z, p = _proportion_z_test(90, 100, 50, 100)
        assert abs(z) > 2.0  # Should be significant
        assert p < 0.05


# ---------------------------------------------------------------------------
# Flattening and grouping
# ---------------------------------------------------------------------------


class TestFlattenTrials:
    def test_empty(self) -> None:
        assert _flatten_trials([]) == []

    def test_single_category(self) -> None:
        t1 = _make_trial(agent_config="BASELINE")
        t2 = _make_trial(agent_config="MCP_FULL")
        cats = _make_categories([t1, t2])
        flat = _flatten_trials(cats)
        assert len(flat) == 2

    def test_multiple_categories(self) -> None:
        cats = [
            {
                "run_category": "official",
                "experiments": [{"experiment_id": "e1", "trials": [_make_trial()]}],
            },
            {
                "run_category": "experiment",
                "experiments": [{"experiment_id": "e2", "trials": [_make_trial()]}],
            },
        ]
        assert len(_flatten_trials(cats)) == 2


class TestGroupByConfig:
    def test_grouping(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE"),
            _make_trial(agent_config="MCP_FULL"),
            _make_trial(agent_config="BASELINE"),
        ]
        groups = _group_by_config(trials)
        assert len(groups["BASELINE"]) == 2
        assert len(groups["MCP_FULL"]) == 1


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


class TestComputeAggregateMetrics:
    def test_single_config(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(reward=1.0, pass_fail="pass", duration_seconds=100.0),
                _make_trial(reward=0.0, pass_fail="fail", duration_seconds=200.0),
            ]
        }
        result = compute_aggregate_metrics(groups)
        assert len(result) == 1
        agg = result[0]
        assert agg.config == "BASELINE"
        assert agg.n_trials == 2
        assert agg.mean_reward == 0.5
        assert agg.pass_rate == 0.5
        assert agg.median_duration_seconds == 150.0

    def test_multiple_configs(self) -> None:
        groups = {
            "BASELINE": [_make_trial(reward=1.0, pass_fail="pass")],
            "MCP_FULL": [_make_trial(reward=0.5, pass_fail="partial")],
        }
        result = compute_aggregate_metrics(groups)
        assert len(result) == 2
        configs = {r.config for r in result}
        assert configs == {"BASELINE", "MCP_FULL"}

    def test_none_rewards_excluded(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(reward=None, pass_fail="unknown"),
                _make_trial(reward=1.0, pass_fail="pass"),
            ]
        }
        result = compute_aggregate_metrics(groups)
        agg = result[0]
        assert agg.mean_reward == 1.0  # Only non-None included
        assert agg.n_trials == 2  # But n_trials counts all

    def test_none_durations_excluded(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(duration_seconds=None),
                _make_trial(duration_seconds=200.0),
            ]
        }
        result = compute_aggregate_metrics(groups)
        assert result[0].median_duration_seconds == 200.0


# ---------------------------------------------------------------------------
# Pairwise tests
# ---------------------------------------------------------------------------


class TestComputePairwiseTests:
    def test_single_config_no_pairs(self) -> None:
        groups = {"BASELINE": [_make_trial(), _make_trial()]}
        result = compute_pairwise_tests(groups)
        assert result == []

    def test_two_configs(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(reward=0.0, pass_fail="fail", input_tokens=1000),
                _make_trial(reward=0.0, pass_fail="fail", input_tokens=1100),
                _make_trial(reward=0.0, pass_fail="fail", input_tokens=1200),
            ],
            "MCP_FULL": [
                _make_trial(reward=1.0, pass_fail="pass", input_tokens=5000),
                _make_trial(reward=1.0, pass_fail="pass", input_tokens=5100),
                _make_trial(reward=1.0, pass_fail="pass", input_tokens=5200),
            ],
        }
        result = compute_pairwise_tests(groups)
        # Should have: reward, pass_rate, duration, input_tokens tests
        metrics = {r.metric for r in result}
        assert "reward" in metrics
        assert "pass_rate" in metrics
        assert "input_tokens" in metrics

    def test_insufficient_data_skips_ttest(self) -> None:
        groups = {
            "BASELINE": [_make_trial(reward=1.0)],
            "MCP_FULL": [_make_trial(reward=0.0)],
        }
        result = compute_pairwise_tests(groups)
        # Only pass_rate z-test should survive (t-tests need n>=2)
        assert all(r.metric == "pass_rate" for r in result)

    def test_three_configs_three_pairs(self) -> None:
        groups = {
            "BASELINE": [_make_trial(reward=0.0), _make_trial(reward=0.5)],
            "MCP_BASE": [_make_trial(reward=0.5), _make_trial(reward=0.8)],
            "MCP_FULL": [_make_trial(reward=0.8), _make_trial(reward=1.0)],
        }
        result = compute_pairwise_tests(groups)
        pairs = {(r.config_a, r.config_b) for r in result}
        assert ("BASELINE", "MCP_BASE") in pairs
        assert ("BASELINE", "MCP_FULL") in pairs
        assert ("MCP_BASE", "MCP_FULL") in pairs


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------


class TestComputeEffectSizes:
    def test_two_configs(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(reward=0.0, duration_seconds=100.0, input_tokens=1000),
                _make_trial(reward=0.0, duration_seconds=110.0, input_tokens=1100),
            ],
            "MCP_FULL": [
                _make_trial(reward=1.0, duration_seconds=200.0, input_tokens=5000),
                _make_trial(reward=1.0, duration_seconds=210.0, input_tokens=5100),
            ],
        }
        result = compute_effect_sizes(groups)
        metrics = {r.metric for r in result}
        assert "reward" in metrics
        assert "duration" in metrics
        assert "input_tokens" in metrics

        for es in result:
            assert es.interpretation in ("negligible", "small", "medium", "large")

    def test_insufficient_data_skipped(self) -> None:
        groups = {
            "BASELINE": [_make_trial(reward=0.0)],
            "MCP_FULL": [_make_trial(reward=1.0)],
        }
        result = compute_effect_sizes(groups)
        assert result == []


# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_empty_input(self) -> None:
        result = analyze([])
        assert result["aggregate_metrics"] == []
        assert result["pairwise_tests"] == []
        assert result["effect_sizes"] == []

    def test_full_pipeline(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(agent_config="BASELINE", reward=0.5, pass_fail="partial"),
            _make_trial(agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=0.8, pass_fail="partial"),
        ]
        cats = _make_categories(trials)
        result = analyze(cats)

        assert len(result["aggregate_metrics"]) == 2
        assert len(result["pairwise_tests"]) > 0
        assert len(result["effect_sizes"]) > 0

        # Verify structure
        agg = result["aggregate_metrics"][0]
        assert "config" in agg
        assert "mean_reward" in agg
        assert "se_reward" in agg
        assert "pass_rate" in agg

    def test_output_is_json_serializable(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.0),
            _make_trial(agent_config="BASELINE", reward=1.0),
            _make_trial(agent_config="MCP_FULL", reward=1.0),
            _make_trial(agent_config="MCP_FULL", reward=0.5),
        ]
        result = analyze(_make_categories(trials))
        # Should not raise
        json.dumps(result)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCli:
    def test_missing_input(self, tmp_path: Path) -> None:
        result = main(["--input", str(tmp_path / "missing.json")])
        assert result == 1

    def test_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        result = main(["--input", str(bad_file)])
        assert result == 1

    def test_non_array_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "obj.json"
        bad_file.write_text('{"key": "value"}', encoding="utf-8")
        result = main(["--input", str(bad_file)])
        assert result == 1

    def test_success(self, tmp_path: Path) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(agent_config="BASELINE", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=0.5, pass_fail="partial"),
        ]
        input_file = tmp_path / "metrics.json"
        input_file.write_text(
            json.dumps(_make_categories(trials)), encoding="utf-8"
        )
        output_file = tmp_path / "results.json"

        result = main(["--input", str(input_file), "--output", str(output_file)])
        assert result == 0
        assert output_file.is_file()

        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "aggregate_metrics" in data
        assert "pairwise_tests" in data
        assert "effect_sizes" in data

    def test_empty_trials(self, tmp_path: Path) -> None:
        input_file = tmp_path / "empty.json"
        input_file.write_text("[]", encoding="utf-8")
        output_file = tmp_path / "results.json"

        result = main(["--input", str(input_file), "--output", str(output_file)])
        assert result == 0

        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data["aggregate_metrics"] == []
