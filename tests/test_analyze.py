"""Unit tests for scripts/ccb_pipeline/analyze.py."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scripts.ccb_pipeline.analyze import (
    BenchmarkConfigMetrics,
    BenchmarkSignificanceResult,
    ConfigAggregateMetrics,
    EffectSizeResult,
    EfficiencyMetrics,
    PairwiseTestResult,
    SDLCPhaseMetrics,
    _cohens_d,
    _flatten_trials,
    _get_trial_benchmark,
    _group_by_benchmark,
    _group_by_config,
    _interpret_cohens_d,
    _is_mcp_improvement,
    _proportion_z_test,
    _safe_mean,
    _safe_median,
    _safe_se,
    _se_proportion,
    analyze,
    compute_aggregate_metrics,
    compute_effect_sizes,
    compute_efficiency_metrics,
    compute_pairwise_tests,
    compute_per_benchmark_metrics,
    compute_per_benchmark_significance,
    compute_per_sdlc_phase_metrics,
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


# ---------------------------------------------------------------------------
# Per-benchmark breakdown tests (US-006)
# ---------------------------------------------------------------------------


class TestGetTrialBenchmark:
    def test_uses_benchmark_field(self) -> None:
        trial = _make_trial(benchmark="locobench")
        assert _get_trial_benchmark(trial) == "locobench"

    def test_falls_back_to_task_name(self) -> None:
        trial = _make_trial(benchmark="")
        trial["task_name"] = "benchmarks/swe-bench-pro/task-001"
        assert _get_trial_benchmark(trial) == "swe-bench-pro"

    def test_unknown_when_no_info(self) -> None:
        trial = _make_trial(benchmark="")
        trial["task_name"] = ""
        assert _get_trial_benchmark(trial) == "unknown"


class TestGroupByBenchmark:
    def test_groups_correctly(self) -> None:
        trials = [
            _make_trial(benchmark="locobench"),
            _make_trial(benchmark="swe-bench-pro"),
            _make_trial(benchmark="locobench"),
        ]
        groups = _group_by_benchmark(trials)
        assert len(groups["locobench"]) == 2
        assert len(groups["swe-bench-pro"]) == 1


class TestIsMcpImprovement:
    def test_mcp_full_improves_over_baseline(self) -> None:
        assert _is_mcp_improvement("BASELINE", "MCP_FULL", 0.5, 0.8) is True

    def test_baseline_better_than_mcp(self) -> None:
        assert _is_mcp_improvement("BASELINE", "MCP_FULL", 0.8, 0.5) is False

    def test_mcp_full_over_mcp_base(self) -> None:
        assert _is_mcp_improvement("MCP_BASE", "MCP_FULL", 0.5, 0.8) is True

    def test_unknown_configs(self) -> None:
        # Unknown configs default to rank 0; equal rank means config_a is "higher"
        assert _is_mcp_improvement("UNKNOWN_A", "UNKNOWN_B", 0.7, 0.3) is True


class TestComputePerBenchmarkMetrics:
    def test_single_benchmark_two_configs(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.3, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=0.8, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
        ]
        result = compute_per_benchmark_metrics(trials)
        assert len(result) == 2  # 1 benchmark x 2 configs

        baseline = [r for r in result if r.config == "BASELINE"][0]
        assert baseline.benchmark == "locobench"
        assert baseline.n_trials == 2
        assert baseline.pass_rate == 0.5
        assert abs(baseline.mean_reward - 0.4) < 1e-10

        mcp = [r for r in result if r.config == "MCP_FULL"][0]
        assert mcp.pass_rate == 1.0
        assert abs(mcp.mean_reward - 0.9) < 1e-10

    def test_multiple_benchmarks(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=1.0),
            _make_trial(benchmark="swe-bench-pro", agent_config="BASELINE", reward=0.5),
        ]
        result = compute_per_benchmark_metrics(trials)
        benchmarks = {r.benchmark for r in result}
        assert benchmarks == {"locobench", "swe-bench-pro"}

    def test_empty_trials(self) -> None:
        result = compute_per_benchmark_metrics([])
        assert result == []


class TestComputePerBenchmarkSignificance:
    def test_significant_difference(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
        ]
        result = compute_per_benchmark_significance(trials)
        # Should have pass_rate and reward tests
        metrics = {r.metric for r in result}
        assert "pass_rate" in metrics
        assert "reward" in metrics

        # MCP_FULL should show improvement
        for r in result:
            if r.significant:
                assert r.mcp_improves is True

    def test_no_significance_when_similar(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=0.5, pass_fail="pass"),
        ]
        result = compute_per_benchmark_significance(trials)
        for r in result:
            assert r.mcp_improves is False

    def test_multiple_benchmarks_separate(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(benchmark="swe-bench-pro", agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(benchmark="swe-bench-pro", agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
        ]
        result = compute_per_benchmark_significance(trials)
        benchmarks = {r.benchmark for r in result}
        assert "locobench" in benchmarks
        assert "swe-bench-pro" in benchmarks

    def test_single_config_no_tests(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5),
        ]
        result = compute_per_benchmark_significance(trials)
        assert result == []

    def test_empty_trials(self) -> None:
        result = compute_per_benchmark_significance([])
        assert result == []


# ---------------------------------------------------------------------------
# Per-SDLC-phase breakdown tests (US-006)
# ---------------------------------------------------------------------------


class TestComputePerSdlcPhaseMetrics:
    def test_single_phase(self) -> None:
        # locobench maps to Implementation + Code Review
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=0.8, pass_fail="pass"),
        ]
        result = compute_per_sdlc_phase_metrics(trials)
        phases = {r.sdlc_phase for r in result}
        assert "Implementation" in phases
        assert "Code Review" in phases

    def test_delta_computation(self) -> None:
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.4, pass_fail="fail"),
            _make_trial(benchmark="locobench", agent_config="MCP_FULL", reward=0.8, pass_fail="pass"),
        ]
        result = compute_per_sdlc_phase_metrics(trials)

        baseline_entries = [r for r in result if r.config == "BASELINE"]
        mcp_entries = [r for r in result if r.config == "MCP_FULL"]

        for bl in baseline_entries:
            assert bl.mean_reward_delta is None  # No delta for baseline

        for mcp in mcp_entries:
            assert mcp.mean_reward_delta is not None
            assert abs(mcp.mean_reward_delta - 0.4) < 1e-10  # 0.8 - 0.4

    def test_trial_in_multiple_phases(self) -> None:
        # swe-bench-pro maps to Implementation + Testing
        trials = [
            _make_trial(benchmark="swe-bench-pro", agent_config="BASELINE", reward=1.0, pass_fail="pass"),
        ]
        result = compute_per_sdlc_phase_metrics(trials)
        phases = {r.sdlc_phase for r in result}
        assert "Implementation" in phases
        assert "Testing" in phases
        # Same trial counted in both phases
        for r in result:
            assert r.n_trials == 1

    def test_aggregation_across_benchmarks(self) -> None:
        # Both locobench and big_code_mcp map to Implementation
        trials = [
            _make_trial(benchmark="locobench", agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(benchmark="big_code_mcp", agent_config="BASELINE", reward=0.3, pass_fail="fail"),
        ]
        result = compute_per_sdlc_phase_metrics(trials)
        impl_baseline = [
            r for r in result if r.sdlc_phase == "Implementation" and r.config == "BASELINE"
        ]
        assert len(impl_baseline) == 1
        assert impl_baseline[0].n_trials == 2
        assert abs(impl_baseline[0].mean_reward - 0.4) < 1e-10

    def test_empty_trials(self) -> None:
        result = compute_per_sdlc_phase_metrics([])
        assert result == []


# ---------------------------------------------------------------------------
# Full analysis with per-benchmark/SDLC (US-006)
# ---------------------------------------------------------------------------


class TestAnalyzeWithBreakdowns:
    def test_includes_per_benchmark_sections(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", benchmark="locobench", reward=0.0, pass_fail="fail"),
            _make_trial(agent_config="BASELINE", benchmark="locobench", reward=0.5, pass_fail="partial"),
            _make_trial(agent_config="MCP_FULL", benchmark="locobench", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", benchmark="locobench", reward=0.8, pass_fail="partial"),
        ]
        cats = _make_categories(trials)
        result = analyze(cats)

        assert "per_benchmark" in result
        assert "per_benchmark_significance" in result
        assert "per_sdlc_phase" in result

        assert len(result["per_benchmark"]) > 0
        assert len(result["per_sdlc_phase"]) > 0

        # Verify per_benchmark structure
        pb = result["per_benchmark"][0]
        assert "benchmark" in pb
        assert "config" in pb
        assert "pass_rate" in pb
        assert "mean_reward" in pb
        assert "se_reward" in pb

    def test_empty_returns_all_sections(self) -> None:
        result = analyze([])
        assert result["per_benchmark"] == []
        assert result["per_benchmark_significance"] == []
        assert result["per_sdlc_phase"] == []

    def test_cli_output_includes_new_sections(self, tmp_path: Path) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", benchmark="locobench", reward=0.0, pass_fail="fail"),
            _make_trial(agent_config="BASELINE", benchmark="locobench", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", benchmark="locobench", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", benchmark="locobench", reward=0.5, pass_fail="partial"),
        ]
        input_file = tmp_path / "metrics.json"
        input_file.write_text(json.dumps(_make_categories(trials)), encoding="utf-8")
        output_file = tmp_path / "results.json"

        result = main(["--input", str(input_file), "--output", str(output_file)])
        assert result == 0

        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "per_benchmark" in data
        assert "per_benchmark_significance" in data
        assert "per_sdlc_phase" in data

    def test_json_serializable_with_new_sections(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", benchmark="swe-bench-pro", reward=0.0),
            _make_trial(agent_config="BASELINE", benchmark="swe-bench-pro", reward=1.0),
            _make_trial(agent_config="MCP_FULL", benchmark="swe-bench-pro", reward=1.0),
            _make_trial(agent_config="MCP_FULL", benchmark="swe-bench-pro", reward=0.5),
        ]
        result = analyze(_make_categories(trials))
        json.dumps(result)  # Should not raise


# ---------------------------------------------------------------------------
# Efficiency analysis tests (US-007)
# ---------------------------------------------------------------------------


class TestComputeEfficiencyMetrics:
    def test_single_config_totals(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200, cached_tokens=50, pass_fail="pass", duration_seconds=100.0),
                _make_trial(input_tokens=3000, output_tokens=400, cached_tokens=150, pass_fail="fail", duration_seconds=200.0),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert len(result) == 1
        eff = result[0]
        assert eff.config == "BASELINE"
        assert eff.n_trials == 2
        assert eff.total_input_tokens == 4000
        assert eff.total_output_tokens == 600
        assert eff.total_cached_tokens == 200
        assert eff.mean_input_tokens == 2000.0
        assert eff.mean_output_tokens == 300.0
        assert eff.n_passing == 1
        assert eff.mcp_token_overhead is None  # Baseline has no overhead

    def test_input_to_output_ratio(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=500),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].input_to_output_ratio is not None
        assert abs(result[0].input_to_output_ratio - 2.0) < 1e-10

    def test_input_to_output_ratio_zero_output(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=0),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].input_to_output_ratio is None

    def test_median_wall_clock(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(duration_seconds=100.0),
                _make_trial(duration_seconds=200.0),
                _make_trial(duration_seconds=300.0),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].median_wall_clock_seconds == 200.0

    def test_median_wall_clock_none_durations(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(duration_seconds=None),
                _make_trial(duration_seconds=None),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].median_wall_clock_seconds is None

    def test_tokens_per_success(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200, pass_fail="pass"),
                _make_trial(input_tokens=3000, output_tokens=400, pass_fail="fail"),
            ]
        }
        result = compute_efficiency_metrics(groups)
        # total tokens = 4000 + 600 = 4600, n_passing = 1
        assert result[0].tokens_per_success == 4600.0

    def test_tokens_per_success_no_passing(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200, pass_fail="fail"),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].tokens_per_success is None

    def test_mcp_token_overhead(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200),
                _make_trial(input_tokens=1000, output_tokens=200),
            ],
            "MCP_FULL": [
                _make_trial(input_tokens=5000, output_tokens=800),
                _make_trial(input_tokens=5000, output_tokens=800),
            ],
        }
        result = compute_efficiency_metrics(groups)
        baseline = [r for r in result if r.config == "BASELINE"][0]
        mcp = [r for r in result if r.config == "MCP_FULL"][0]

        assert baseline.mcp_token_overhead is None
        # baseline mean total = 1200, mcp mean total = 5800
        assert mcp.mcp_token_overhead is not None
        assert abs(mcp.mcp_token_overhead - 4600.0) < 1e-10

    def test_standard_errors_included(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200),
                _make_trial(input_tokens=3000, output_tokens=400),
            ]
        }
        result = compute_efficiency_metrics(groups)
        eff = result[0]
        assert eff.se_input_tokens > 0
        assert eff.se_output_tokens > 0

    def test_standard_errors_single_trial(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200),
            ]
        }
        result = compute_efficiency_metrics(groups)
        assert result[0].se_input_tokens == 0.0
        assert result[0].se_output_tokens == 0.0

    def test_multiple_configs_sorted(self) -> None:
        groups = {
            "MCP_FULL": [_make_trial()],
            "BASELINE": [_make_trial()],
            "MCP_BASE": [_make_trial()],
        }
        result = compute_efficiency_metrics(groups)
        assert [r.config for r in result] == ["BASELINE", "MCP_BASE", "MCP_FULL"]

    def test_mcp_base_overhead_vs_baseline(self) -> None:
        groups = {
            "BASELINE": [
                _make_trial(input_tokens=1000, output_tokens=200),
            ],
            "MCP_BASE": [
                _make_trial(input_tokens=2000, output_tokens=300),
            ],
        }
        result = compute_efficiency_metrics(groups)
        mcp_base = [r for r in result if r.config == "MCP_BASE"][0]
        # baseline mean total = 1200, mcp_base mean total = 2300
        assert mcp_base.mcp_token_overhead is not None
        assert abs(mcp_base.mcp_token_overhead - 1100.0) < 1e-10

    def test_none_token_values_treated_as_zero(self) -> None:
        trial = _make_trial(input_tokens=0, output_tokens=0, cached_tokens=0)
        trial["input_tokens"] = None
        trial["output_tokens"] = None
        trial["cached_tokens"] = None
        groups = {"BASELINE": [trial]}
        result = compute_efficiency_metrics(groups)
        assert result[0].total_input_tokens == 0
        assert result[0].total_output_tokens == 0
        assert result[0].total_cached_tokens == 0


class TestAnalyzeWithEfficiency:
    def test_efficiency_section_present(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.5, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=0.8, pass_fail="pass"),
        ]
        result = analyze(_make_categories(trials))
        assert "efficiency" in result
        assert len(result["efficiency"]) == 2

    def test_efficiency_structure(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=1.0, pass_fail="pass",
                        input_tokens=1000, output_tokens=200),
            _make_trial(agent_config="MCP_FULL", reward=1.0, pass_fail="pass",
                        input_tokens=5000, output_tokens=800),
        ]
        result = analyze(_make_categories(trials))
        eff = result["efficiency"][0]
        assert "config" in eff
        assert "total_input_tokens" in eff
        assert "total_output_tokens" in eff
        assert "mean_input_tokens" in eff
        assert "se_input_tokens" in eff
        assert "input_to_output_ratio" in eff
        assert "median_wall_clock_seconds" in eff
        assert "tokens_per_success" in eff
        assert "mcp_token_overhead" in eff

    def test_empty_returns_efficiency_section(self) -> None:
        result = analyze([])
        assert result["efficiency"] == []

    def test_cli_output_includes_efficiency(self, tmp_path: Path) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.0, pass_fail="fail"),
            _make_trial(agent_config="BASELINE", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=1.0, pass_fail="pass"),
            _make_trial(agent_config="MCP_FULL", reward=0.5, pass_fail="partial"),
        ]
        input_file = tmp_path / "metrics.json"
        input_file.write_text(json.dumps(_make_categories(trials)), encoding="utf-8")
        output_file = tmp_path / "results.json"

        result = main(["--input", str(input_file), "--output", str(output_file)])
        assert result == 0

        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "efficiency" in data
        assert len(data["efficiency"]) == 2

    def test_json_serializable_with_efficiency(self) -> None:
        trials = [
            _make_trial(agent_config="BASELINE", reward=0.0, input_tokens=1000, output_tokens=200),
            _make_trial(agent_config="BASELINE", reward=1.0, input_tokens=2000, output_tokens=400),
            _make_trial(agent_config="MCP_FULL", reward=1.0, input_tokens=5000, output_tokens=800),
            _make_trial(agent_config="MCP_FULL", reward=0.5, input_tokens=6000, output_tokens=900),
        ]
        result = analyze(_make_categories(trials))
        json.dumps(result)  # Should not raise
