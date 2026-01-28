"""
Tests for dashboard.utils.comparison_config.

Covers:
- ComparisonConfig frozen dataclass
- Constants and labels
- Run selector rendering
- Metric selector rendering
- Task filter rendering
- Full config rendering
- Comparison DataFrame building
- Metric value formatting
- Pass rate bar chart building
- Per-task scatter plot building
- Per-task metric extraction
- Run and display results orchestration
- Results rendering
- View integration
"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.utils.comparison_config import (
    COMPARISON_METRICS,
    METRIC_LABELS,
    SESSION_KEY_PREFIX,
    ComparisonConfig,
    _build_comparison_dataframe,
    _build_pass_rate_bar_chart,
    _build_per_task_scatter,
    _extract_per_task_metrics,
    _format_metric_value,
    _render_metric_selector,
    _render_task_filter,
    _session_key,
)


class TestSessionKey(TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("foo")
        self.assertEqual(result, f"{SESSION_KEY_PREFIX}_foo")

    def test_different_suffixes(self):
        self.assertNotEqual(_session_key("a"), _session_key("b"))


class TestComparisonConfig(TestCase):
    """Tests for ComparisonConfig frozen dataclass."""

    def test_default_values(self):
        config = ComparisonConfig()
        self.assertEqual(config.baseline_experiment, "")
        self.assertEqual(config.baseline_agent, "")
        self.assertEqual(config.variant_experiment, "")
        self.assertEqual(config.variant_agent, "")
        self.assertEqual(config.selected_metrics, COMPARISON_METRICS)
        self.assertEqual(config.task_filter, "")

    def test_custom_values(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("pass_rate",),
            task_filter="swe-bench",
        )
        self.assertEqual(config.baseline_experiment, "exp001")
        self.assertEqual(config.baseline_agent, "agent_a")
        self.assertEqual(config.variant_experiment, "exp002")
        self.assertEqual(config.variant_agent, "agent_b")
        self.assertEqual(config.selected_metrics, ("pass_rate",))
        self.assertEqual(config.task_filter, "swe-bench")

    def test_frozen(self):
        config = ComparisonConfig()
        with self.assertRaises(AttributeError):
            config.baseline_experiment = "changed"  # type: ignore

    def test_to_dict(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("pass_rate", "reward"),
            task_filter="filter",
        )
        d = config.to_dict()
        self.assertEqual(d["baseline_experiment"], "exp001")
        self.assertEqual(d["baseline_agent"], "agent_a")
        self.assertEqual(d["variant_experiment"], "exp002")
        self.assertEqual(d["variant_agent"], "agent_b")
        self.assertIsInstance(d["selected_metrics"], list)
        self.assertEqual(d["selected_metrics"], ["pass_rate", "reward"])
        self.assertEqual(d["task_filter"], "filter")


class TestConstants(TestCase):
    """Tests for module constants."""

    def test_comparison_metrics_has_four(self):
        self.assertEqual(len(COMPARISON_METRICS), 4)

    def test_comparison_metrics_content(self):
        self.assertIn("pass_rate", COMPARISON_METRICS)
        self.assertIn("reward", COMPARISON_METRICS)
        self.assertIn("avg_duration_seconds", COMPARISON_METRICS)
        self.assertIn("total_tokens", COMPARISON_METRICS)

    def test_metric_labels_covers_all_metrics(self):
        for metric in COMPARISON_METRICS:
            self.assertIn(metric, METRIC_LABELS)

    def test_metric_labels_are_strings(self):
        for label in METRIC_LABELS.values():
            self.assertIsInstance(label, str)
            self.assertTrue(len(label) > 0)


class TestRenderMetricSelector(TestCase):
    """Tests for _render_metric_selector."""

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_selected_metrics(self, mock_st):
        mock_st.multiselect.return_value = ["pass_rate", "reward"]
        result = _render_metric_selector("test_key")
        self.assertEqual(result, ("pass_rate", "reward"))

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_all_when_empty(self, mock_st):
        mock_st.multiselect.return_value = []
        result = _render_metric_selector("test_key")
        self.assertEqual(result, COMPARISON_METRICS)


class TestRenderTaskFilter(TestCase):
    """Tests for _render_task_filter."""

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_text_input_value(self, mock_st):
        mock_st.text_input.return_value = "swe-bench"
        result = _render_task_filter("test_key")
        self.assertEqual(result, "swe-bench")

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_empty_by_default(self, mock_st):
        mock_st.text_input.return_value = ""
        result = _render_task_filter("test_key")
        self.assertEqual(result, "")


class TestRenderRunSelector(TestCase):
    """Tests for _render_run_selector."""

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_experiment_and_agent(self, mock_st):
        from dashboard.utils.comparison_config import _render_run_selector

        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002"]
        loader.list_agents.return_value = ["agent_a", "agent_b"]

        mock_st.selectbox.side_effect = ["exp001", "agent_a"]

        result = _render_run_selector(loader, "Baseline", "test_key")
        self.assertEqual(result, ("exp001", "agent_a"))

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_empty_when_no_experiments(self, mock_st):
        from dashboard.utils.comparison_config import _render_run_selector

        loader = MagicMock()
        loader.list_experiments.return_value = []

        result = _render_run_selector(loader, "Baseline", "test_key")
        self.assertEqual(result, ("", ""))

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_empty_agent_when_no_agents(self, mock_st):
        from dashboard.utils.comparison_config import _render_run_selector

        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        loader.list_agents.return_value = []

        mock_st.selectbox.return_value = "exp001"

        result = _render_run_selector(loader, "Baseline", "test_key")
        self.assertEqual(result, ("exp001", ""))


class TestRenderComparisonConfig(TestCase):
    """Tests for render_comparison_config."""

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_none_when_no_experiments(self, mock_st):
        from dashboard.utils.comparison_config import render_comparison_config

        loader = MagicMock()
        loader.list_experiments.return_value = []

        result = render_comparison_config(loader)
        self.assertIsNone(result)

    @patch("dashboard.utils.comparison_config.st")
    def test_returns_config_when_valid(self, mock_st):
        from dashboard.utils.comparison_config import render_comparison_config

        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002"]
        loader.list_agents.side_effect = [
            ["agent_a"],
            ["agent_b"],
        ]

        # selectbox calls: baseline_exp, baseline_agent, variant_exp, variant_agent
        mock_st.selectbox.side_effect = ["exp001", "agent_a", "exp002", "agent_b"]
        mock_st.multiselect.return_value = ["pass_rate"]
        mock_st.text_input.return_value = ""

        result = render_comparison_config(loader)
        self.assertIsNotNone(result)
        self.assertEqual(result.baseline_experiment, "exp001")
        self.assertEqual(result.baseline_agent, "agent_a")
        self.assertEqual(result.variant_experiment, "exp002")
        self.assertEqual(result.variant_agent, "agent_b")


class TestFormatMetricValue(TestCase):
    """Tests for _format_metric_value."""

    def test_formats_pass_rate(self):
        self.assertEqual(_format_metric_value("pass_rate", 0.75), "75.0%")

    def test_formats_duration(self):
        self.assertEqual(_format_metric_value("avg_duration_seconds", 123.456), "123.46")

    def test_formats_tokens(self):
        self.assertEqual(_format_metric_value("total_tokens", 12345.0), "12,345")

    def test_formats_reward(self):
        self.assertEqual(_format_metric_value("reward", 0.85), "0.85")

    def test_returns_na_for_none(self):
        self.assertEqual(_format_metric_value("pass_rate", None), "N/A")

    def test_returns_string_for_unconvertible(self):
        self.assertEqual(_format_metric_value("pass_rate", "invalid"), "invalid")


class TestBuildComparisonDataframe(TestCase):
    """Tests for _build_comparison_dataframe."""

    def _make_result(self, agent_name, metrics):
        """Create a mock ComparisonResult."""
        return SimpleNamespace(
            agent_results={agent_name: metrics},
            total_tasks=10,
        )

    def test_builds_dataframe_with_deltas(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("pass_rate", "avg_duration_seconds"),
        )
        baseline = self._make_result("agent_a", {"pass_rate": 0.6, "avg_duration_seconds": 100.0})
        variant = self._make_result("agent_b", {"pass_rate": 0.8, "avg_duration_seconds": 80.0})

        df = _build_comparison_dataframe(baseline, variant, config)

        self.assertEqual(len(df), 2)
        self.assertIn("Metric", df.columns)
        self.assertIn("Baseline", df.columns)
        self.assertIn("Variant", df.columns)
        self.assertIn("Delta", df.columns)

    def test_handles_missing_metrics(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("pass_rate",),
        )
        baseline = self._make_result("agent_a", {})
        variant = self._make_result("agent_b", {"pass_rate": 0.8})

        df = _build_comparison_dataframe(baseline, variant, config)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Baseline"], "N/A")

    def test_empty_when_no_metrics_selected(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=(),
        )
        baseline = self._make_result("agent_a", {"pass_rate": 0.6})
        variant = self._make_result("agent_b", {"pass_rate": 0.8})

        df = _build_comparison_dataframe(baseline, variant, config)
        self.assertTrue(df.empty)

    def test_delta_computation_pass_rate(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("pass_rate",),
        )
        baseline = self._make_result("agent_a", {"pass_rate": 0.5})
        variant = self._make_result("agent_b", {"pass_rate": 0.7})

        df = _build_comparison_dataframe(baseline, variant, config)
        self.assertIn("+", df.iloc[0]["Delta"])

    def test_delta_computation_numeric(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=("avg_duration_seconds",),
        )
        baseline = self._make_result("agent_a", {"avg_duration_seconds": 100.0})
        variant = self._make_result("agent_b", {"avg_duration_seconds": 80.0})

        df = _build_comparison_dataframe(baseline, variant, config)
        delta = df.iloc[0]["Delta"]
        self.assertTrue(delta.startswith("-"))


class TestBuildPassRateBarChart(TestCase):
    """Tests for _build_pass_rate_bar_chart."""

    def _make_result(self, agent_name, pass_rate):
        return SimpleNamespace(
            agent_results={agent_name: {"pass_rate": pass_rate}},
            total_tasks=10,
        )

    def test_returns_figure_for_valid_data(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = self._make_result("agent_a", 0.6)
        variant = self._make_result("agent_b", 0.8)

        fig = _build_pass_rate_bar_chart(baseline, variant, config)
        self.assertIsNotNone(fig)

    def test_returns_none_when_no_pass_rate(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = SimpleNamespace(agent_results={"agent_a": {}}, total_tasks=10)
        variant = SimpleNamespace(agent_results={"agent_b": {}}, total_tasks=10)

        fig = _build_pass_rate_bar_chart(baseline, variant, config)
        self.assertIsNone(fig)

    def test_chart_has_title(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = self._make_result("agent_a", 0.6)
        variant = self._make_result("agent_b", 0.8)

        fig = _build_pass_rate_bar_chart(baseline, variant, config)
        self.assertIn("Pass Rate", fig.layout.title.text)


class TestBuildPerTaskScatter(TestCase):
    """Tests for _build_per_task_scatter."""

    def _make_result_with_tasks(self, agent_name, task_metrics):
        per_task = {}
        for task_id, value in task_metrics.items():
            per_task[task_id] = {agent_name: {"pass_rate": value}}
        return SimpleNamespace(
            agent_results={agent_name: {"pass_rate": 0.5}},
            per_task_results=per_task,
            total_tasks=len(task_metrics),
        )

    def test_returns_figure_for_paired_data(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = self._make_result_with_tasks("agent_a", {"t1": 0.5, "t2": 0.8})
        variant = self._make_result_with_tasks("agent_b", {"t1": 0.6, "t2": 0.9})

        fig = _build_per_task_scatter(baseline, variant, config)
        self.assertIsNotNone(fig)

    def test_returns_none_when_no_per_task_results(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = SimpleNamespace(
            agent_results={"agent_a": {}},
            total_tasks=0,
        )
        variant = SimpleNamespace(
            agent_results={"agent_b": {}},
            total_tasks=0,
        )

        fig = _build_per_task_scatter(baseline, variant, config)
        self.assertIsNone(fig)

    def test_returns_none_when_no_common_tasks(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )
        baseline = self._make_result_with_tasks("agent_a", {"t1": 0.5})
        variant = self._make_result_with_tasks("agent_b", {"t3": 0.6})

        fig = _build_per_task_scatter(baseline, variant, config)
        self.assertIsNone(fig)


class TestExtractPerTaskMetrics(TestCase):
    """Tests for _extract_per_task_metrics."""

    def test_extracts_metrics_from_per_task_results(self):
        result = SimpleNamespace(
            per_task_results={
                "t1": {"agent_a": {"pass_rate": 0.5, "reward": 1.0}},
                "t2": {"agent_a": {"pass_rate": 0.8}},
            }
        )

        metrics = _extract_per_task_metrics(result, "agent_a", "pass_rate")
        self.assertEqual(metrics, {"t1": 0.5, "t2": 0.8})

    def test_returns_empty_when_no_per_task(self):
        result = SimpleNamespace()
        metrics = _extract_per_task_metrics(result, "agent_a", "pass_rate")
        self.assertEqual(metrics, {})

    def test_skips_tasks_without_agent(self):
        result = SimpleNamespace(
            per_task_results={
                "t1": {"agent_b": {"pass_rate": 0.5}},
            }
        )

        metrics = _extract_per_task_metrics(result, "agent_a", "pass_rate")
        self.assertEqual(metrics, {})

    def test_skips_tasks_without_metric(self):
        result = SimpleNamespace(
            per_task_results={
                "t1": {"agent_a": {"reward": 1.0}},
            }
        )

        metrics = _extract_per_task_metrics(result, "agent_a", "pass_rate")
        self.assertEqual(metrics, {})


class TestRunAndDisplayComparison(TestCase):
    """Tests for run_and_display_comparison."""

    @patch("dashboard.utils.comparison_config.st")
    @patch("dashboard.utils.comparison_config._render_comparison_results")
    def test_runs_and_renders(self, mock_render, mock_st):
        from dashboard.utils.comparison_config import run_and_display_comparison

        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        loader = MagicMock()
        baseline_result = SimpleNamespace(
            agent_results={"agent_a": {"pass_rate": 0.6}},
            total_tasks=10,
        )
        variant_result = SimpleNamespace(
            agent_results={"agent_b": {"pass_rate": 0.8}},
            total_tasks=10,
        )
        loader.load_comparison.side_effect = [baseline_result, variant_result]

        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )

        run_and_display_comparison(loader, config)

        mock_render.assert_called_once()

    @patch("dashboard.utils.comparison_config.st")
    def test_handles_baseline_error(self, mock_st):
        from dashboard.utils.comparison_config import run_and_display_comparison
        from contextlib import contextmanager

        mock_st.session_state = {}

        # Create a real context manager that doesn't suppress exceptions
        @contextmanager
        def real_spinner(text):
            yield

        mock_st.spinner = real_spinner

        loader = MagicMock()
        loader.load_comparison.side_effect = Exception("DB error")

        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )

        # Should not raise; error is handled internally
        run_and_display_comparison(loader, config)

        # Should only call load_comparison for baseline (fails, then returns)
        loader.load_comparison.assert_called_once_with(
            "exp001",
            baseline_agent="agent_a",
        )


class TestRenderComparisonResults(TestCase):
    """Tests for _render_comparison_results."""

    @patch("dashboard.utils.comparison_config.st")
    @patch("dashboard.utils.comparison_config.display_summary_card")
    def test_renders_summary_cards(self, mock_card, mock_st):
        from dashboard.utils.comparison_config import _render_comparison_results

        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

        baseline = SimpleNamespace(
            agent_results={"agent_a": {"pass_rate": 0.6}},
            total_tasks=10,
        )
        variant = SimpleNamespace(
            agent_results={"agent_b": {"pass_rate": 0.8}},
            total_tasks=10,
        )
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )

        _render_comparison_results(baseline, variant, config)

        # Should render 4 summary cards
        self.assertEqual(mock_card.call_count, 4)

    @patch("dashboard.utils.comparison_config.st")
    @patch("dashboard.utils.comparison_config.display_summary_card")
    def test_renders_export_button(self, mock_card, mock_st):
        from dashboard.utils.comparison_config import _render_comparison_results

        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

        baseline = SimpleNamespace(
            agent_results={"agent_a": {"pass_rate": 0.6}},
            total_tasks=10,
        )
        variant = SimpleNamespace(
            agent_results={"agent_b": {"pass_rate": 0.8}},
            total_tasks=10,
        )
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
        )

        _render_comparison_results(baseline, variant, config)

        # Should have a download_button call for CSV export
        mock_st.download_button.assert_called()


class TestComparisonViewIntegration(TestCase):
    """Tests for view integration."""

    def test_import_render_functions(self):
        from dashboard.utils.comparison_config import (
            render_comparison_config,
            run_and_display_comparison,
        )

        self.assertTrue(callable(render_comparison_config))
        self.assertTrue(callable(run_and_display_comparison))

    def test_view_imports_config(self):
        import importlib

        mod = importlib.import_module("dashboard.views.analysis_comparison")
        self.assertTrue(hasattr(mod, "show_comparison_analysis"))


class TestEdgeCases(TestCase):
    """Edge case tests."""

    def test_format_metric_none(self):
        self.assertEqual(_format_metric_value("pass_rate", None), "N/A")

    def test_format_metric_zero(self):
        self.assertEqual(_format_metric_value("pass_rate", 0.0), "0.0%")

    def test_format_metric_negative(self):
        result = _format_metric_value("reward", -0.5)
        self.assertEqual(result, "-0.50")

    def test_config_equality(self):
        c1 = ComparisonConfig(baseline_experiment="a")
        c2 = ComparisonConfig(baseline_experiment="a")
        self.assertEqual(c1, c2)

    def test_config_inequality(self):
        c1 = ComparisonConfig(baseline_experiment="a")
        c2 = ComparisonConfig(baseline_experiment="b")
        self.assertNotEqual(c1, c2)

    def test_build_df_with_all_metrics(self):
        config = ComparisonConfig(
            baseline_experiment="exp001",
            baseline_agent="agent_a",
            variant_experiment="exp002",
            variant_agent="agent_b",
            selected_metrics=COMPARISON_METRICS,
        )
        baseline = SimpleNamespace(
            agent_results={"agent_a": {
                "pass_rate": 0.6,
                "reward": 0.5,
                "avg_duration_seconds": 100.0,
                "total_tokens": 5000.0,
            }},
            total_tasks=10,
        )
        variant = SimpleNamespace(
            agent_results={"agent_b": {
                "pass_rate": 0.8,
                "reward": 0.7,
                "avg_duration_seconds": 80.0,
                "total_tokens": 4000.0,
            }},
            total_tasks=10,
        )

        df = _build_comparison_dataframe(baseline, variant, config)
        self.assertEqual(len(df), 4)
        metrics = list(df["Metric"])
        self.assertIn("Pass Rate", metrics)
        self.assertIn("Reward", metrics)
        self.assertIn("Avg Duration (s)", metrics)
        self.assertIn("Total Tokens", metrics)
