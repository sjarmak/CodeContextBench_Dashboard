"""Tests for the Comparison Analysis dashboard view."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


def _sample_analysis_results() -> dict:
    """Build a minimal analysis_results.json structure for testing."""
    return {
        "aggregate_metrics": [
            {
                "config": "BASELINE",
                "n_trials": 10,
                "mean_reward": 0.45,
                "se_reward": 0.05,
                "pass_rate": 0.60,
                "se_pass_rate": 0.15,
                "median_duration_seconds": 120.0,
                "mean_input_tokens": 50000.0,
                "mean_output_tokens": 5000.0,
            },
            {
                "config": "MCP_FULL",
                "n_trials": 10,
                "mean_reward": 0.50,
                "se_reward": 0.04,
                "pass_rate": 0.70,
                "se_pass_rate": 0.14,
                "median_duration_seconds": 150.0,
                "mean_input_tokens": 80000.0,
                "mean_output_tokens": 8000.0,
            },
        ],
        "pairwise_tests": [
            {
                "config_a": "BASELINE",
                "config_b": "MCP_FULL",
                "metric": "reward",
                "test_name": "welch_t_test",
                "statistic": -1.5,
                "p_value": 0.15,
                "significant": False,
            },
            {
                "config_a": "BASELINE",
                "config_b": "MCP_FULL",
                "metric": "pass_rate",
                "test_name": "proportion_z_test",
                "statistic": -0.8,
                "p_value": 0.42,
                "significant": False,
            },
        ],
        "effect_sizes": [
            {
                "config_a": "BASELINE",
                "config_b": "MCP_FULL",
                "metric": "reward",
                "cohens_d": -0.35,
                "interpretation": "small",
            },
        ],
        "per_benchmark": [
            {
                "benchmark": "locobench",
                "config": "BASELINE",
                "n_trials": 5,
                "pass_rate": 0.60,
                "mean_reward": 0.45,
                "se_reward": 0.07,
            },
            {
                "benchmark": "locobench",
                "config": "MCP_FULL",
                "n_trials": 5,
                "pass_rate": 0.80,
                "mean_reward": 0.55,
                "se_reward": 0.05,
            },
        ],
        "per_benchmark_significance": [
            {
                "benchmark": "locobench",
                "config_a": "BASELINE",
                "config_b": "MCP_FULL",
                "metric": "pass_rate",
                "test_name": "proportion_z_test",
                "statistic": -1.0,
                "p_value": 0.03,
                "significant": True,
                "mcp_improves": True,
            },
        ],
        "per_sdlc_phase": [],
        "efficiency": [
            {
                "config": "BASELINE",
                "n_trials": 10,
                "total_input_tokens": 500000,
                "total_output_tokens": 50000,
                "total_cached_tokens": 10000,
                "mean_input_tokens": 50000.0,
                "se_input_tokens": 5000.0,
                "mean_output_tokens": 5000.0,
                "se_output_tokens": 500.0,
                "input_to_output_ratio": 10.0,
                "median_wall_clock_seconds": 120.0,
                "n_passing": 6,
                "tokens_per_success": 91666.67,
                "mcp_token_overhead": None,
            },
            {
                "config": "MCP_FULL",
                "n_trials": 10,
                "total_input_tokens": 800000,
                "total_output_tokens": 80000,
                "total_cached_tokens": 20000,
                "mean_input_tokens": 80000.0,
                "se_input_tokens": 8000.0,
                "mean_output_tokens": 8000.0,
                "se_output_tokens": 800.0,
                "input_to_output_ratio": 10.0,
                "median_wall_clock_seconds": 150.0,
                "n_passing": 7,
                "tokens_per_success": 125714.29,
                "mcp_token_overhead": 33000.0,
            },
        ],
        "tool_utilization": [
            {
                "config": "BASELINE",
                "n_trials": 10,
                "mean_mcp_calls": 0.0,
                "se_mcp_calls": 0.0,
                "mean_deep_search_calls": 0.0,
                "se_deep_search_calls": 0.0,
                "mean_deep_search_vs_keyword_ratio": 0.0,
                "mean_context_fill_rate": 0.25,
                "se_context_fill_rate": 0.05,
            },
            {
                "config": "MCP_FULL",
                "n_trials": 10,
                "mean_mcp_calls": 12.5,
                "se_mcp_calls": 2.0,
                "mean_deep_search_calls": 5.0,
                "se_deep_search_calls": 1.0,
                "mean_deep_search_vs_keyword_ratio": 0.67,
                "mean_context_fill_rate": 0.55,
                "se_context_fill_rate": 0.08,
            },
        ],
        "tool_reward_correlation": [
            {
                "metric": "mcp_calls_vs_reward",
                "pearson_r": 0.35,
                "p_value": 0.12,
                "n_observations": 20,
                "significant": False,
            },
        ],
        "benchmark_tool_usage": [
            {
                "benchmark": "locobench",
                "config": "BASELINE",
                "n_trials": 5,
                "mean_mcp_calls": 0.0,
                "mean_deep_search_calls": 0.0,
                "mean_total_tool_calls": 15.0,
            },
            {
                "benchmark": "locobench",
                "config": "MCP_FULL",
                "n_trials": 5,
                "mean_mcp_calls": 12.5,
                "mean_deep_search_calls": 5.0,
                "mean_total_tool_calls": 32.0,
            },
        ],
    }


def _write_analysis_results(tmp_path: Path) -> Path:
    """Write sample analysis_results.json to tmp_path and return the dir."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    results_path = output_dir / "analysis_results.json"
    results_path.write_text(json.dumps(_sample_analysis_results()), encoding="utf-8")
    return output_dir


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_display_config_known(self):
        from dashboard.views.comparison_analysis import _display_config

        assert _display_config("BASELINE") == "Baseline"
        assert _display_config("MCP_BASE") == "MCP-Base"
        assert _display_config("MCP_FULL") == "MCP-Full"

    def test_display_config_unknown(self):
        from dashboard.views.comparison_analysis import _display_config

        assert _display_config("UNKNOWN") == "UNKNOWN"

    def test_sort_configs(self):
        from dashboard.views.comparison_analysis import _sort_configs

        result = _sort_configs(["MCP_FULL", "BASELINE", "MCP_BASE"])
        assert result == ["BASELINE", "MCP_BASE", "MCP_FULL"]

    def test_sort_configs_unknown(self):
        from dashboard.views.comparison_analysis import _sort_configs

        result = _sort_configs(["CUSTOM", "BASELINE"])
        assert result == ["BASELINE", "CUSTOM"]

    def test_significance_marker(self):
        from dashboard.views.comparison_analysis import _significance_marker

        assert _significance_marker(0.0001) == "***"
        assert _significance_marker(0.005) == "**"
        assert _significance_marker(0.03) == "*"
        assert _significance_marker(0.10) == ""

    def test_fmt_pvalue(self):
        from dashboard.views.comparison_analysis import _fmt_pvalue

        assert _fmt_pvalue(0.0001) == "< 0.001"
        assert _fmt_pvalue(0.05) == "0.0500"

    def test_df_to_csv(self):
        import pandas as pd

        from dashboard.views.comparison_analysis import _df_to_csv

        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        csv = _df_to_csv(df)
        assert "a,b" in csv
        assert "1,3" in csv


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------


class TestLoadAnalysisResults:
    """Test loading of analysis_results.json."""

    def test_load_valid(self, tmp_path: Path):
        from dashboard.views.comparison_analysis import _load_analysis_results

        output_dir = _write_analysis_results(tmp_path)
        data = _load_analysis_results(output_dir)
        assert "aggregate_metrics" in data
        assert len(data["aggregate_metrics"]) == 2

    def test_load_missing(self, tmp_path: Path):
        from dashboard.views.comparison_analysis import _load_analysis_results

        data = _load_analysis_results(tmp_path / "nonexistent")
        assert data == {}

    def test_load_invalid_json(self, tmp_path: Path):
        from dashboard.views.comparison_analysis import _load_analysis_results

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "analysis_results.json").write_text("{bad json", encoding="utf-8")
        data = _load_analysis_results(output_dir)
        assert data == {}

    def test_load_non_dict(self, tmp_path: Path):
        from dashboard.views.comparison_analysis import _load_analysis_results

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "analysis_results.json").write_text("[1, 2, 3]", encoding="utf-8")
        data = _load_analysis_results(output_dir)
        assert data == {}


# ---------------------------------------------------------------------------
# Rendering tests (mock streamlit)
# ---------------------------------------------------------------------------


class TestRenderAggregate:
    """Test aggregate tab rendering."""

    @patch("plotly.graph_objects.Figure.to_image", return_value=b"fake-png")
    @patch("dashboard.views.comparison_analysis.st")
    def test_renders_with_data(self, mock_st, _mock_img):
        from dashboard.views.comparison_analysis import _render_aggregate_tab

        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        data = _sample_analysis_results()
        _render_aggregate_tab(data)

        mock_st.dataframe.assert_called_once()
        mock_st.plotly_chart.assert_called_once()

    @patch("dashboard.views.comparison_analysis.st")
    def test_empty_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_aggregate_tab

        _render_aggregate_tab({})
        mock_st.info.assert_called_once()


class TestRenderPerBenchmark:
    """Test per-benchmark tab rendering."""

    @patch("plotly.graph_objects.Figure.to_image", return_value=b"fake-png")
    @patch("dashboard.views.comparison_analysis.st")
    def test_renders_with_data(self, mock_st, _mock_img):
        from dashboard.views.comparison_analysis import _render_per_benchmark_tab

        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        data = _sample_analysis_results()
        _render_per_benchmark_tab(data)

        # Should render table + heatmap
        assert mock_st.dataframe.called
        assert mock_st.plotly_chart.called

    @patch("dashboard.views.comparison_analysis.st")
    def test_empty_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_per_benchmark_tab

        _render_per_benchmark_tab({})
        mock_st.info.assert_called_once()


class TestRenderConfigSensitivity:
    """Test config sensitivity tab rendering."""

    @patch("dashboard.views.comparison_analysis.st")
    def test_renders_with_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_config_sensitivity_tab

        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        data = _sample_analysis_results()
        _render_config_sensitivity_tab(data)

        # Should render pairwise tests table + effect sizes
        assert mock_st.dataframe.call_count >= 1
        assert mock_st.plotly_chart.called

    @patch("dashboard.views.comparison_analysis.st")
    def test_empty_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_config_sensitivity_tab

        _render_config_sensitivity_tab({})
        mock_st.info.assert_called_once()


class TestRenderEfficiency:
    """Test efficiency tab rendering."""

    @patch("plotly.graph_objects.Figure.to_image", return_value=b"fake-png")
    @patch("dashboard.views.comparison_analysis.st")
    def test_renders_with_data(self, mock_st, _mock_img):
        from dashboard.views.comparison_analysis import _render_efficiency_tab

        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        data = _sample_analysis_results()
        _render_efficiency_tab(data)

        assert mock_st.dataframe.called
        # Token dist chart + tokens per success chart
        assert mock_st.plotly_chart.call_count >= 1

    @patch("dashboard.views.comparison_analysis.st")
    def test_empty_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_efficiency_tab

        _render_efficiency_tab({})
        mock_st.info.assert_called_once()


class TestRenderToolUtilization:
    """Test tool utilization tab rendering."""

    @patch("plotly.graph_objects.Figure.to_image", return_value=b"fake-png")
    @patch("dashboard.views.comparison_analysis.st")
    def test_renders_with_data(self, mock_st, _mock_img):
        from dashboard.views.comparison_analysis import _render_tool_utilization_tab

        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        data = _sample_analysis_results()
        _render_tool_utilization_tab(data)

        # Distribution chart + metrics table + benchmark tool usage table
        assert mock_st.plotly_chart.called
        assert mock_st.dataframe.call_count >= 1

    @patch("dashboard.views.comparison_analysis.st")
    def test_empty_data(self, mock_st):
        from dashboard.views.comparison_analysis import _render_tool_utilization_tab

        _render_tool_utilization_tab({})
        mock_st.info.assert_called_once()


# ---------------------------------------------------------------------------
# Main entry point test
# ---------------------------------------------------------------------------


class TestShowComparisonAnalysis:
    """Test the main entry point."""

    @patch("dashboard.views.comparison_analysis.st")
    def test_no_data(self, mock_st):
        from dashboard.views.comparison_analysis import show_comparison_analysis

        with patch(
            "dashboard.views.comparison_analysis._load_analysis_results",
            return_value={},
        ):
            show_comparison_analysis()

        mock_st.info.assert_called()

    @patch("plotly.graph_objects.Figure.to_image", return_value=b"fake-png")
    @patch("dashboard.views.comparison_analysis.st")
    def test_with_data(self, mock_st, _mock_img):
        from dashboard.views.comparison_analysis import show_comparison_analysis

        mock_tabs = [MagicMock() for _ in range(5)]
        for tab in mock_tabs:
            tab.__enter__ = MagicMock(return_value=tab)
            tab.__exit__ = MagicMock(return_value=False)
        mock_st.tabs.return_value = mock_tabs
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.download_button = MagicMock()

        with patch(
            "dashboard.views.comparison_analysis._load_analysis_results",
            return_value=_sample_analysis_results(),
        ):
            show_comparison_analysis()

        mock_st.tabs.assert_called_once()
