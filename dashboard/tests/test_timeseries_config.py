"""
Tests for dashboard.utils.timeseries_config.

Covers:
- TimeSeriesConfig frozen dataclass
- Constants and labels
- Session key generation
- Experiment selector rendering
- Metric selector rendering
- Aggregation selector rendering
- Full config rendering
- Timeseries DataFrame building
- Anomaly DataFrame building
- Trend line chart building
- Anomaly markers chart building
- Run and display orchestration
- Results rendering
- View integration
"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.utils.timeseries_config import (
    AGGREGATION_LEVELS,
    SESSION_KEY_PREFIX,
    TIMESERIES_METRIC_LABELS,
    TIMESERIES_METRICS,
    TimeSeriesConfig,
    _build_anomaly_dataframe,
    _build_anomaly_markers_chart,
    _build_timeseries_dataframe,
    _build_trend_line_chart,
    _render_aggregation_selector,
    _render_experiment_selector,
    _render_metric_selector,
    _session_key,
    render_timeseries_config,
    run_and_display_timeseries,
    _render_timeseries_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trend(
    metric_name: str = "pass_rate",
    agent_name: str = "agent_a",
    direction_value: str = "improving",
    slope: float = 0.05,
    confidence: float = 0.85,
    first_value: float = 0.6,
    last_value: float = 0.8,
    percent_change: float = 33.33,
    data_points: int = 3,
    has_anomalies: bool = False,
    anomaly_indices: list | None = None,
    anomaly_descriptions: list | None = None,
):
    """Create a mock TimeSeriesTrend object."""
    direction = SimpleNamespace(value=direction_value)
    return SimpleNamespace(
        metric_name=metric_name,
        agent_name=agent_name,
        direction=direction,
        slope=slope,
        confidence=confidence,
        first_value=first_value,
        last_value=last_value,
        percent_change=percent_change,
        data_points=data_points,
        total_change=last_value - first_value,
        has_anomalies=has_anomalies,
        anomaly_indices=anomaly_indices or [],
        anomaly_descriptions=anomaly_descriptions or [],
        interpretation=f"{metric_name} {direction_value}",
    )


def _make_analysis_result(trends: dict | None = None):
    """Create a mock TimeSeriesAnalysisResult."""
    return SimpleNamespace(
        experiment_ids=["exp001", "exp002", "exp003"],
        agent_names=["agent_a"],
        trends=trends or {},
        best_improving_metric=None,
        worst_degrading_metric=None,
        most_stable_metric=None,
        total_anomalies=0,
        agents_with_anomalies=[],
    )


# ---------------------------------------------------------------------------
# Session key
# ---------------------------------------------------------------------------

class TestSessionKey(TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("foo")
        self.assertEqual(result, f"{SESSION_KEY_PREFIX}_foo")

    def test_different_suffixes(self):
        self.assertNotEqual(_session_key("a"), _session_key("b"))


# ---------------------------------------------------------------------------
# TimeSeriesConfig dataclass
# ---------------------------------------------------------------------------

class TestTimeSeriesConfig(TestCase):
    """Tests for TimeSeriesConfig frozen dataclass."""

    def test_default_values(self):
        config = TimeSeriesConfig()
        self.assertEqual(config.experiment_ids, ())
        self.assertEqual(config.selected_metrics, ("pass_rate",))
        self.assertEqual(config.aggregation_level, "per-run")

    def test_custom_values(self):
        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002"),
            selected_metrics=("pass_rate", "avg_duration_seconds"),
            aggregation_level="per-day",
        )
        self.assertEqual(config.experiment_ids, ("exp001", "exp002"))
        self.assertEqual(config.selected_metrics, ("pass_rate", "avg_duration_seconds"))
        self.assertEqual(config.aggregation_level, "per-day")

    def test_frozen(self):
        config = TimeSeriesConfig()
        with self.assertRaises(AttributeError):
            config.experiment_ids = ("changed",)  # type: ignore

    def test_to_dict(self):
        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002"),
            selected_metrics=("pass_rate",),
            aggregation_level="per-week",
        )
        d = config.to_dict()
        self.assertEqual(d["experiment_ids"], ["exp001", "exp002"])
        self.assertEqual(d["selected_metrics"], ["pass_rate"])
        self.assertEqual(d["aggregation_level"], "per-week")

    def test_to_dict_converts_tuples_to_lists(self):
        config = TimeSeriesConfig(
            experiment_ids=("a", "b"),
            selected_metrics=("pass_rate",),
        )
        d = config.to_dict()
        self.assertIsInstance(d["experiment_ids"], list)
        self.assertIsInstance(d["selected_metrics"], list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants(TestCase):
    """Tests for module-level constants."""

    def test_metrics_tuple_has_entries(self):
        self.assertGreater(len(TIMESERIES_METRICS), 0)

    def test_labels_cover_all_metrics(self):
        for metric in TIMESERIES_METRICS:
            self.assertIn(metric, TIMESERIES_METRIC_LABELS)

    def test_aggregation_levels_has_entries(self):
        self.assertGreater(len(AGGREGATION_LEVELS), 0)

    def test_aggregation_levels_format(self):
        for level in AGGREGATION_LEVELS:
            self.assertEqual(len(level), 2)
            self.assertIsInstance(level[0], str)
            self.assertIsInstance(level[1], str)


# ---------------------------------------------------------------------------
# Experiment selector
# ---------------------------------------------------------------------------

class TestExperimentSelector(TestCase):
    """Tests for _render_experiment_selector."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_empty_when_no_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = []

        result = _render_experiment_selector(loader)
        self.assertEqual(result, ())
        mock_st.warning.assert_called_once()

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_selected_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002", "exp003"]
        mock_st.multiselect.return_value = ["exp001", "exp002"]

        result = _render_experiment_selector(loader)
        self.assertEqual(result, ("exp001", "exp002"))

    @patch("dashboard.utils.timeseries_config.st")
    def test_default_selects_last_three(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002", "exp003", "exp004"]
        mock_st.multiselect.return_value = ["exp002", "exp003", "exp004"]

        _render_experiment_selector(loader)
        call_args = mock_st.multiselect.call_args
        self.assertEqual(call_args[1]["default"], ["exp002", "exp003", "exp004"])


# ---------------------------------------------------------------------------
# Metric selector
# ---------------------------------------------------------------------------

class TestMetricSelector(TestCase):
    """Tests for _render_metric_selector."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_selected_metrics(self, mock_st):
        mock_st.multiselect.return_value = ["pass_rate", "avg_duration_seconds"]

        result = _render_metric_selector()
        self.assertEqual(result, ("pass_rate", "avg_duration_seconds"))

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_default_when_none_selected(self, mock_st):
        mock_st.multiselect.return_value = []

        result = _render_metric_selector()
        self.assertEqual(result, ("pass_rate",))

    @patch("dashboard.utils.timeseries_config.st")
    def test_uses_format_func(self, mock_st):
        mock_st.multiselect.return_value = ["pass_rate"]
        _render_metric_selector()

        call_args = mock_st.multiselect.call_args
        fmt = call_args[1]["format_func"]
        self.assertEqual(fmt("pass_rate"), "Pass Rate")
        self.assertEqual(fmt("avg_duration_seconds"), "Avg Duration (seconds)")


# ---------------------------------------------------------------------------
# Aggregation selector
# ---------------------------------------------------------------------------

class TestAggregationSelector(TestCase):
    """Tests for _render_aggregation_selector."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_selected_level(self, mock_st):
        mock_st.selectbox.return_value = "per-week"

        result = _render_aggregation_selector()
        self.assertEqual(result, "per-week")

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_default_when_none(self, mock_st):
        mock_st.selectbox.return_value = None

        result = _render_aggregation_selector()
        self.assertEqual(result, "per-run")

    @patch("dashboard.utils.timeseries_config.st")
    def test_uses_format_func(self, mock_st):
        mock_st.selectbox.return_value = "per-run"
        _render_aggregation_selector()

        call_args = mock_st.selectbox.call_args
        fmt = call_args[1]["format_func"]
        self.assertEqual(fmt("per-run"), "Per Run (each experiment as a data point)")
        self.assertEqual(fmt("per-day"), "Per Day (group experiments by date)")


# ---------------------------------------------------------------------------
# Full config rendering
# ---------------------------------------------------------------------------

class TestRenderTimeseriesConfig(TestCase):
    """Tests for render_timeseries_config."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_none_when_no_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = []

        result = render_timeseries_config(loader)
        self.assertIsNone(result)

    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_none_when_fewer_than_two(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        mock_st.multiselect.return_value = ["exp001"]

        result = render_timeseries_config(loader)
        self.assertIsNone(result)
        mock_st.warning.assert_called()

    @patch("dashboard.utils.timeseries_config._render_aggregation_selector")
    @patch("dashboard.utils.timeseries_config._render_metric_selector")
    @patch("dashboard.utils.timeseries_config._render_experiment_selector")
    @patch("dashboard.utils.timeseries_config.st")
    def test_returns_config_when_valid(self, mock_st, mock_exp, mock_met, mock_agg):
        loader = MagicMock()
        mock_exp.return_value = ("exp001", "exp002")
        mock_met.return_value = ("pass_rate",)
        mock_agg.return_value = "per-run"

        result = render_timeseries_config(loader)
        self.assertIsNotNone(result)
        self.assertEqual(result.experiment_ids, ("exp001", "exp002"))
        self.assertEqual(result.selected_metrics, ("pass_rate",))
        self.assertEqual(result.aggregation_level, "per-run")


# ---------------------------------------------------------------------------
# Timeseries DataFrame building
# ---------------------------------------------------------------------------

class TestBuildTimeseriesDataframe(TestCase):
    """Tests for _build_timeseries_dataframe."""

    def test_empty_when_no_trends(self):
        result = _make_analysis_result(trends={})
        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertTrue(df.empty)

    def test_builds_rows_for_matching_metrics(self):
        trend = _make_trend(metric_name="pass_rate", agent_name="agent_a")
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Metric"], "pass_rate")
        self.assertEqual(df.iloc[0]["Agent"], "agent_a")
        self.assertEqual(df.iloc[0]["Direction"], "IMPROVING")

    def test_filters_unselected_metrics(self):
        trend = _make_trend(metric_name="pass_rate")
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_timeseries_dataframe(result, ("avg_duration_seconds",))
        self.assertTrue(df.empty)

    def test_multiple_agents(self):
        trend_a = _make_trend(agent_name="agent_a")
        trend_b = _make_trend(agent_name="agent_b", direction_value="degrading")
        result = _make_analysis_result(trends={
            "pass_rate": {"agent_a": trend_a, "agent_b": trend_b}
        })

        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertEqual(len(df), 2)
        agents = set(df["Agent"])
        self.assertEqual(agents, {"agent_a", "agent_b"})

    def test_includes_anomaly_count(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[1, 2],
            anomaly_descriptions=["Point 1: 0.9", "Point 2: 0.1"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertEqual(df.iloc[0]["Anomalies"], 2)

    def test_rounds_values(self):
        trend = _make_trend(
            first_value=0.123456789,
            last_value=0.987654321,
            percent_change=12.345678,
            slope=0.0012345678,
            confidence=0.87654321,
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertEqual(df.iloc[0]["First Value"], 0.1235)
        self.assertEqual(df.iloc[0]["Last Value"], 0.9877)
        self.assertEqual(df.iloc[0]["Change (%)"], 12.35)
        self.assertEqual(df.iloc[0]["Slope"], 0.001235)
        self.assertEqual(df.iloc[0]["Confidence"], 0.8765)


# ---------------------------------------------------------------------------
# Anomaly DataFrame building
# ---------------------------------------------------------------------------

class TestBuildAnomalyDataframe(TestCase):
    """Tests for _build_anomaly_dataframe."""

    def test_empty_when_no_anomalies(self):
        trend = _make_trend(has_anomalies=False)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_anomaly_dataframe(result, ("pass_rate",))
        self.assertTrue(df.empty)

    def test_builds_rows_for_anomalies(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[1, 2],
            anomaly_descriptions=["Point 1: 0.900", "Point 2: 0.100"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_anomaly_dataframe(result, ("pass_rate",))
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["Data Point Index"], 1)
        self.assertIn("0.900", df.iloc[0]["Description"])

    def test_filters_unselected_metrics(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[0],
            anomaly_descriptions=["Point 0: 0.500"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_anomaly_dataframe(result, ("avg_duration_seconds",))
        self.assertTrue(df.empty)

    def test_empty_when_no_trends(self):
        result = _make_analysis_result(trends={})
        df = _build_anomaly_dataframe(result, ("pass_rate",))
        self.assertTrue(df.empty)


# ---------------------------------------------------------------------------
# Trend line chart building
# ---------------------------------------------------------------------------

class TestBuildTrendLineChart(TestCase):
    """Tests for _build_trend_line_chart."""

    def test_returns_none_when_no_trends(self):
        result = _make_analysis_result(trends={})
        fig = _build_trend_line_chart(result, ("pass_rate",), ("exp001", "exp002"))
        self.assertIsNone(fig)

    def test_returns_figure_with_data(self):
        trend = _make_trend(data_points=3, first_value=0.6, last_value=0.8)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_trend_line_chart(
            result, ("pass_rate",), ("exp001", "exp002", "exp003")
        )
        self.assertIsNotNone(fig)

    def test_filters_unselected_metrics(self):
        trend = _make_trend(metric_name="pass_rate")
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_trend_line_chart(
            result, ("avg_duration_seconds",), ("exp001", "exp002", "exp003")
        )
        self.assertIsNone(fig)

    def test_chart_has_correct_title(self):
        trend = _make_trend(data_points=2)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_trend_line_chart(result, ("pass_rate",), ("exp001", "exp002"))
        self.assertIn("Metric Trends", fig.layout.title.text)


# ---------------------------------------------------------------------------
# Anomaly markers chart building
# ---------------------------------------------------------------------------

class TestBuildAnomalyMarkersChart(TestCase):
    """Tests for _build_anomaly_markers_chart."""

    def test_returns_none_when_no_anomalies(self):
        trend = _make_trend(has_anomalies=False)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_anomaly_markers_chart(
            result, ("pass_rate",), ("exp001", "exp002", "exp003")
        )
        self.assertIsNone(fig)

    def test_returns_figure_with_anomalies(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[1],
            anomaly_descriptions=["Point 1: 0.900"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_anomaly_markers_chart(
            result, ("pass_rate",), ("exp001", "exp002", "exp003")
        )
        self.assertIsNotNone(fig)

    def test_returns_none_when_no_trends(self):
        result = _make_analysis_result(trends={})
        fig = _build_anomaly_markers_chart(
            result, ("pass_rate",), ("exp001", "exp002")
        )
        self.assertIsNone(fig)

    def test_chart_has_correct_title(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[0],
            anomaly_descriptions=["Point 0: 0.500"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_anomaly_markers_chart(
            result, ("pass_rate",), ("exp001", "exp002", "exp003")
        )
        self.assertIn("Anomaly", fig.layout.title.text)


# ---------------------------------------------------------------------------
# Run and display orchestration
# ---------------------------------------------------------------------------

class TestRunAndDisplayTimeseries(TestCase):
    """Tests for run_and_display_timeseries."""

    @patch("dashboard.utils.timeseries_config._render_timeseries_results")
    @patch("dashboard.utils.timeseries_config.st")
    def test_calls_loader_and_renders(self, mock_st, mock_render):
        mock_st.session_state = {}
        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=None)
        mock_spinner.__exit__ = MagicMock(return_value=False)
        mock_st.spinner.return_value = mock_spinner

        loader = MagicMock()
        trend = _make_trend()
        analysis_result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})
        loader.load_timeseries.return_value = analysis_result

        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002"),
            selected_metrics=("pass_rate",),
        )

        run_and_display_timeseries(loader, config)
        loader.load_timeseries.assert_called_once_with(
            experiment_ids=["exp001", "exp002"],
            agent_names=None,
        )
        mock_render.assert_called_once()

    @patch("dashboard.utils.timeseries_config.display_error_message")
    @patch("dashboard.utils.timeseries_config.st")
    def test_handles_loader_exception(self, mock_st, mock_error):
        mock_st.session_state = {}
        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=None)
        mock_spinner.__exit__ = MagicMock(return_value=False)
        mock_st.spinner.return_value = mock_spinner

        loader = MagicMock()
        loader.load_timeseries.side_effect = Exception("DB error")

        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002"),
            selected_metrics=("pass_rate",),
        )

        run_and_display_timeseries(loader, config)
        mock_error.assert_called_once()

    @patch("dashboard.utils.timeseries_config.display_no_data_message")
    @patch("dashboard.utils.timeseries_config.st")
    def test_handles_none_result(self, mock_st, mock_no_data):
        mock_st.session_state = {}
        mock_spinner = MagicMock()
        mock_spinner.__enter__ = MagicMock(return_value=None)
        mock_spinner.__exit__ = MagicMock(return_value=False)
        mock_st.spinner.return_value = mock_spinner

        loader = MagicMock()
        loader.load_timeseries.return_value = None

        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002"),
            selected_metrics=("pass_rate",),
        )

        run_and_display_timeseries(loader, config)
        mock_no_data.assert_called_once()


# ---------------------------------------------------------------------------
# Results rendering
# ---------------------------------------------------------------------------

class TestRenderTimeseriesResults(TestCase):
    """Tests for _render_timeseries_results."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_renders_summary_cards(self, mock_st):
        mock_st.session_state = {}
        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=col_mock)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock] * 4

        trend = _make_trend()
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})
        ts_df = _build_timeseries_dataframe(result, ("pass_rate",))
        anomaly_df = pd.DataFrame()
        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002", "exp003"),
            selected_metrics=("pass_rate",),
        )

        _render_timeseries_results(ts_df, anomaly_df, result, config)
        mock_st.subheader.assert_any_call("Trend Summary")

    @patch("dashboard.utils.timeseries_config.st")
    def test_renders_data_table(self, mock_st):
        mock_st.session_state = {}
        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=col_mock)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock] * 4

        trend = _make_trend()
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})
        ts_df = _build_timeseries_dataframe(result, ("pass_rate",))
        anomaly_df = pd.DataFrame()
        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002", "exp003"),
            selected_metrics=("pass_rate",),
        )

        _render_timeseries_results(ts_df, anomaly_df, result, config)
        mock_st.dataframe.assert_called()

    @patch("dashboard.utils.timeseries_config.st")
    def test_shows_export_button(self, mock_st):
        mock_st.session_state = {}
        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=col_mock)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock] * 4

        trend = _make_trend()
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})
        ts_df = _build_timeseries_dataframe(result, ("pass_rate",))
        anomaly_df = pd.DataFrame()
        config = TimeSeriesConfig(
            experiment_ids=("exp001", "exp002", "exp003"),
            selected_metrics=("pass_rate",),
        )

        _render_timeseries_results(ts_df, anomaly_df, result, config)
        mock_st.download_button.assert_called_once()
        call_args = mock_st.download_button.call_args
        self.assertEqual(call_args[1]["file_name"], "timeseries_analysis_results.csv")


# ---------------------------------------------------------------------------
# View integration
# ---------------------------------------------------------------------------

class TestViewIntegration(TestCase):
    """Tests for integration with analysis_timeseries.py view."""

    @patch("dashboard.utils.timeseries_config.st")
    def test_config_returns_none_for_single_experiment(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        mock_st.multiselect.return_value = ["exp001"]

        result = render_timeseries_config(loader)
        self.assertIsNone(result)

    @patch("dashboard.utils.timeseries_config._render_aggregation_selector")
    @patch("dashboard.utils.timeseries_config._render_metric_selector")
    @patch("dashboard.utils.timeseries_config._render_experiment_selector")
    @patch("dashboard.utils.timeseries_config.st")
    def test_full_config_round_trip(self, mock_st, mock_exp, mock_met, mock_agg):
        loader = MagicMock()
        mock_exp.return_value = ("exp001", "exp002", "exp003")
        mock_met.return_value = ("pass_rate", "avg_duration_seconds")
        mock_agg.return_value = "per-week"

        config = render_timeseries_config(loader)
        self.assertIsNotNone(config)

        d = config.to_dict()
        self.assertEqual(d["experiment_ids"], ["exp001", "exp002", "exp003"])
        self.assertEqual(d["selected_metrics"], ["pass_rate", "avg_duration_seconds"])
        self.assertEqual(d["aggregation_level"], "per-week")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_empty_analysis_result_trends(self):
        result = _make_analysis_result(trends={})
        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertTrue(df.empty)

    def test_trend_with_zero_values(self):
        trend = _make_trend(first_value=0.0, last_value=0.0, percent_change=0.0, slope=0.0)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        df = _build_timeseries_dataframe(result, ("pass_rate",))
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["First Value"], 0.0)

    def test_single_data_point_trend(self):
        trend = _make_trend(data_points=1, first_value=0.5, last_value=0.5)
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        fig = _build_trend_line_chart(result, ("pass_rate",), ("exp001",))
        self.assertIsNotNone(fig)

    def test_anomaly_description_parsing_fallback(self):
        trend = _make_trend(
            has_anomalies=True,
            anomaly_indices=[0],
            anomaly_descriptions=["malformed description"],
        )
        result = _make_analysis_result(trends={"pass_rate": {"agent_a": trend}})

        # Should not raise - fallback to 0.0
        fig = _build_anomaly_markers_chart(result, ("pass_rate",), ("exp001",))
        self.assertIsNotNone(fig)

    def test_multiple_metrics_and_agents(self):
        trend_a_pr = _make_trend(metric_name="pass_rate", agent_name="agent_a")
        trend_b_pr = _make_trend(metric_name="pass_rate", agent_name="agent_b")
        trend_a_dur = _make_trend(
            metric_name="avg_duration_seconds",
            agent_name="agent_a",
            direction_value="degrading",
        )
        result = _make_analysis_result(trends={
            "pass_rate": {"agent_a": trend_a_pr, "agent_b": trend_b_pr},
            "avg_duration_seconds": {"agent_a": trend_a_dur},
        })

        df = _build_timeseries_dataframe(
            result, ("pass_rate", "avg_duration_seconds"),
        )
        self.assertEqual(len(df), 3)

    def test_config_to_dict_and_back(self):
        config = TimeSeriesConfig(
            experiment_ids=("a", "b", "c"),
            selected_metrics=("pass_rate", "avg_mcp_calls"),
            aggregation_level="per-day",
        )
        d = config.to_dict()
        reconstructed = TimeSeriesConfig(
            experiment_ids=tuple(d["experiment_ids"]),
            selected_metrics=tuple(d["selected_metrics"]),
            aggregation_level=d["aggregation_level"],
        )
        self.assertEqual(config, reconstructed)
