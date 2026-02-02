"""Tests for scripts.ccb_pipeline.publish - LaTeX table generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ccb_pipeline.publish import (
    generate_table_aggregate,
    generate_table_efficiency,
    generate_table_per_benchmark,
    generate_table_significance,
    main,
    publish_tables,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_aggregate_metrics() -> list[dict]:
    return [
        {
            "config": "BASELINE",
            "n_trials": 50,
            "mean_reward": 0.448,
            "se_reward": 0.035,
            "pass_rate": 0.420,
            "se_pass_rate": 0.070,
            "median_duration_seconds": 120.5,
            "mean_input_tokens": 15000.0,
            "mean_output_tokens": 3000.0,
        },
        {
            "config": "MCP_FULL",
            "n_trials": 50,
            "mean_reward": 0.452,
            "se_reward": 0.034,
            "pass_rate": 0.440,
            "se_pass_rate": 0.068,
            "median_duration_seconds": 180.2,
            "mean_input_tokens": 51000.0,
            "mean_output_tokens": 5000.0,
        },
    ]


def _make_per_benchmark() -> list[dict]:
    return [
        {
            "benchmark": "locobench",
            "config": "BASELINE",
            "n_trials": 25,
            "pass_rate": 0.400,
            "mean_reward": 0.420,
            "se_reward": 0.040,
        },
        {
            "benchmark": "locobench",
            "config": "MCP_FULL",
            "n_trials": 25,
            "pass_rate": 0.480,
            "mean_reward": 0.500,
            "se_reward": 0.038,
        },
        {
            "benchmark": "swe-bench-pro",
            "config": "BASELINE",
            "n_trials": 25,
            "pass_rate": 0.620,
            "mean_reward": 0.620,
            "se_reward": 0.050,
        },
    ]


def _make_per_benchmark_significance() -> list[dict]:
    return [
        {
            "benchmark": "locobench",
            "config_a": "BASELINE",
            "config_b": "MCP_FULL",
            "metric": "reward",
            "test_name": "welch_t_test",
            "statistic": 1.45,
            "p_value": 0.008,
            "significant": True,
            "mcp_improves": True,
        },
        {
            "benchmark": "locobench",
            "config_a": "BASELINE",
            "config_b": "MCP_FULL",
            "metric": "pass_rate",
            "test_name": "proportion_z_test",
            "statistic": 0.57,
            "p_value": 0.57,
            "significant": False,
            "mcp_improves": False,
        },
    ]


def _make_pairwise_tests() -> list[dict]:
    return [
        {
            "config_a": "BASELINE",
            "config_b": "MCP_FULL",
            "metric": "reward",
            "test_name": "welch_t_test",
            "statistic": 0.08,
            "p_value": 0.94,
            "significant": False,
        },
        {
            "config_a": "BASELINE",
            "config_b": "MCP_FULL",
            "metric": "pass_rate",
            "test_name": "proportion_z_test",
            "statistic": 0.20,
            "p_value": 0.84,
            "significant": False,
        },
    ]


def _make_effect_sizes() -> list[dict]:
    return [
        {
            "config_a": "BASELINE",
            "config_b": "MCP_FULL",
            "metric": "reward",
            "cohens_d": 0.012,
            "interpretation": "negligible",
        },
    ]


def _make_efficiency() -> list[dict]:
    return [
        {
            "config": "BASELINE",
            "n_trials": 50,
            "total_input_tokens": 750000,
            "total_output_tokens": 150000,
            "total_cached_tokens": 100000,
            "mean_input_tokens": 15000.0,
            "se_input_tokens": 500.0,
            "mean_output_tokens": 3000.0,
            "se_output_tokens": 200.0,
            "input_to_output_ratio": 5.0,
            "median_wall_clock_seconds": 120.5,
            "n_passing": 21,
            "tokens_per_success": 42857.0,
            "mcp_token_overhead": None,
        },
        {
            "config": "MCP_FULL",
            "n_trials": 50,
            "total_input_tokens": 2550000,
            "total_output_tokens": 250000,
            "total_cached_tokens": 200000,
            "mean_input_tokens": 51000.0,
            "se_input_tokens": 2000.0,
            "mean_output_tokens": 5000.0,
            "se_output_tokens": 400.0,
            "input_to_output_ratio": 10.2,
            "median_wall_clock_seconds": 180.2,
            "n_passing": 22,
            "tokens_per_success": 127273.0,
            "mcp_token_overhead": 38000.0,
        },
    ]


def _make_analysis_results() -> dict:
    return {
        "aggregate_metrics": _make_aggregate_metrics(),
        "pairwise_tests": _make_pairwise_tests(),
        "effect_sizes": _make_effect_sizes(),
        "per_benchmark": _make_per_benchmark(),
        "per_benchmark_significance": _make_per_benchmark_significance(),
        "per_sdlc_phase": [],
        "efficiency": _make_efficiency(),
        "tool_utilization": [],
        "tool_reward_correlation": [],
        "benchmark_tool_usage": [],
    }


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestTableAggregate:
    def test_contains_booktabs(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert r"\toprule" in result
        assert r"\midrule" in result
        assert r"\bottomrule" in result

    def test_contains_table_environment(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert r"\begin{table}" in result
        assert r"\end{table}" in result

    def test_contains_config_names(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert "Baseline" in result
        assert "MCP-Full" in result

    def test_contains_se_values(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert r"$\pm$" in result

    def test_contains_label(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert r"\label{tab:aggregate}" in result

    def test_contains_caption(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert r"\caption{" in result

    def test_duration_formatted(self) -> None:
        result = generate_table_aggregate(_make_aggregate_metrics())
        assert "120.5" in result

    def test_empty_input(self) -> None:
        result = generate_table_aggregate([])
        assert r"\toprule" in result
        assert r"\bottomrule" in result

    def test_none_duration(self) -> None:
        metrics = [
            {
                "config": "BASELINE",
                "n_trials": 5,
                "mean_reward": 0.5,
                "se_reward": 0.1,
                "pass_rate": 0.4,
                "se_pass_rate": 0.1,
                "median_duration_seconds": None,
                "mean_input_tokens": 1000.0,
                "mean_output_tokens": 200.0,
            },
        ]
        result = generate_table_aggregate(metrics)
        assert "--" in result


class TestTablePerBenchmark:
    def test_contains_benchmarks(self) -> None:
        result = generate_table_per_benchmark(
            _make_per_benchmark(), _make_per_benchmark_significance()
        )
        assert "locobench" in result
        assert "swe-bench-pro" in result

    def test_significance_markers(self) -> None:
        result = generate_table_per_benchmark(
            _make_per_benchmark(), _make_per_benchmark_significance()
        )
        # locobench reward p=0.008 should get ** marker
        assert "**" in result

    def test_booktabs_formatting(self) -> None:
        result = generate_table_per_benchmark(
            _make_per_benchmark(), _make_per_benchmark_significance()
        )
        assert r"\toprule" in result
        assert r"\bottomrule" in result

    def test_config_display_names(self) -> None:
        result = generate_table_per_benchmark(
            _make_per_benchmark(), _make_per_benchmark_significance()
        )
        assert "Baseline" in result
        assert "MCP-Full" in result

    def test_empty_input(self) -> None:
        result = generate_table_per_benchmark([], [])
        assert r"\toprule" in result

    def test_no_significance_data(self) -> None:
        result = generate_table_per_benchmark(_make_per_benchmark(), [])
        assert "locobench" in result


class TestTableSignificance:
    def test_contains_pairs(self) -> None:
        result = generate_table_significance(
            _make_pairwise_tests(), _make_effect_sizes()
        )
        assert "Baseline vs MCP-Full" in result

    def test_contains_cohens_d(self) -> None:
        result = generate_table_significance(
            _make_pairwise_tests(), _make_effect_sizes()
        )
        assert "0.012" in result
        assert "negligible" in result

    def test_missing_effect_size(self) -> None:
        result = generate_table_significance(_make_pairwise_tests(), [])
        assert "--" in result

    def test_booktabs(self) -> None:
        result = generate_table_significance(
            _make_pairwise_tests(), _make_effect_sizes()
        )
        assert r"\toprule" in result
        assert r"\bottomrule" in result

    def test_empty_input(self) -> None:
        result = generate_table_significance([], [])
        assert r"\toprule" in result

    def test_very_small_pvalue(self) -> None:
        tests = [
            {
                "config_a": "BASELINE",
                "config_b": "MCP_FULL",
                "metric": "reward",
                "test_name": "welch_t_test",
                "statistic": 5.0,
                "p_value": 0.0001,
                "significant": True,
            },
        ]
        result = generate_table_significance(tests, [])
        assert "$< 0.001$" in result
        assert "***" in result


class TestTableEfficiency:
    def test_contains_configs(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        assert "Baseline" in result
        assert "MCP-Full" in result

    def test_contains_token_values(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        assert "15,000" in result
        assert "51,000" in result

    def test_contains_tokens_per_success(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        assert "42,857" in result

    def test_none_overhead_for_baseline(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        # Baseline should have -- for overhead
        lines = result.split("\n")
        baseline_line = [l for l in lines if "Baseline" in l][0]
        assert "--" in baseline_line

    def test_mcp_overhead_shown(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        assert "38,000" in result

    def test_booktabs(self) -> None:
        result = generate_table_efficiency(_make_efficiency())
        assert r"\toprule" in result
        assert r"\bottomrule" in result

    def test_empty_input(self) -> None:
        result = generate_table_efficiency([])
        assert r"\toprule" in result

    def test_none_tokens_per_success(self) -> None:
        eff = [
            {
                "config": "BASELINE",
                "n_trials": 5,
                "total_input_tokens": 1000,
                "total_output_tokens": 200,
                "total_cached_tokens": 0,
                "mean_input_tokens": 200.0,
                "se_input_tokens": 50.0,
                "mean_output_tokens": 40.0,
                "se_output_tokens": 10.0,
                "input_to_output_ratio": 5.0,
                "median_wall_clock_seconds": 60.0,
                "n_passing": 0,
                "tokens_per_success": None,
                "mcp_token_overhead": None,
            },
        ]
        result = generate_table_efficiency(eff)
        assert "--" in result


# ---------------------------------------------------------------------------
# publish_tables integration
# ---------------------------------------------------------------------------


class TestPublishTables:
    def test_creates_tables_directory(self, tmp_path: Path) -> None:
        results = _make_analysis_results()
        publish_tables(results, tmp_path)
        assert (tmp_path / "tables").is_dir()

    def test_writes_all_four_tables(self, tmp_path: Path) -> None:
        results = _make_analysis_results()
        files = publish_tables(results, tmp_path)
        assert len(files) == 4

        expected_names = {
            "table_aggregate.tex",
            "table_per_benchmark.tex",
            "table_significance.tex",
            "table_efficiency.tex",
        }
        actual_names = {Path(f).name for f in files}
        assert actual_names == expected_names

    def test_files_are_valid_latex(self, tmp_path: Path) -> None:
        results = _make_analysis_results()
        files = publish_tables(results, tmp_path)
        for f in files:
            content = Path(f).read_text(encoding="utf-8")
            assert r"\begin{table}" in content
            assert r"\end{table}" in content

    def test_empty_analysis_results(self, tmp_path: Path) -> None:
        empty_results: dict = {
            "aggregate_metrics": [],
            "pairwise_tests": [],
            "effect_sizes": [],
            "per_benchmark": [],
            "per_benchmark_significance": [],
            "per_sdlc_phase": [],
            "efficiency": [],
            "tool_utilization": [],
            "tool_reward_correlation": [],
            "benchmark_tool_usage": [],
        }
        files = publish_tables(empty_results, tmp_path)
        assert len(files) == 0

    def test_partial_results(self, tmp_path: Path) -> None:
        results: dict = {
            "aggregate_metrics": _make_aggregate_metrics(),
            "pairwise_tests": [],
            "effect_sizes": [],
            "per_benchmark": [],
            "per_benchmark_significance": [],
            "efficiency": [],
        }
        files = publish_tables(results, tmp_path)
        assert len(files) == 1
        assert "table_aggregate.tex" in files[0]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_missing_input_file(self, tmp_path: Path) -> None:
        result = main(["--input", str(tmp_path / "nonexistent.json"), "--output-dir", str(tmp_path)])
        assert result == 1

    def test_invalid_json(self, tmp_path: Path) -> None:
        input_file = tmp_path / "bad.json"
        input_file.write_text("not json", encoding="utf-8")
        result = main(["--input", str(input_file), "--output-dir", str(tmp_path)])
        assert result == 1

    def test_non_dict_json(self, tmp_path: Path) -> None:
        input_file = tmp_path / "array.json"
        input_file.write_text("[]", encoding="utf-8")
        result = main(["--input", str(input_file), "--output-dir", str(tmp_path)])
        assert result == 1

    def test_successful_run(self, tmp_path: Path) -> None:
        input_file = tmp_path / "analysis_results.json"
        input_file.write_text(
            json.dumps(_make_analysis_results()), encoding="utf-8"
        )
        output_dir = tmp_path / "out"
        result = main(["--input", str(input_file), "--output-dir", str(output_dir)])
        assert result == 0
        assert (output_dir / "tables").is_dir()
        assert (output_dir / "tables" / "table_aggregate.tex").is_file()

    def test_default_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Just verify args parse without error for defaults
        # Can't easily test real defaults since files won't exist
        result = main(["--input", str(tmp_path / "missing.json")])
        assert result == 1
