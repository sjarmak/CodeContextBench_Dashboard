"""
Tests for dashboard.utils.cost_config.

Covers:
- CostConfig frozen dataclass
- Constants and labels
- Session key generation
- Experiment selector rendering
- Baseline agent selector rendering
- Metric selector rendering
- Full config rendering
- Cost DataFrame building
- Regression DataFrame building
- Value formatting
- Token distribution chart building
- Cost breakdown chart building
- Run and display cost orchestration
- Results rendering
- View integration
"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

import pandas as pd

from dashboard.utils.cost_config import (
    COST_METRICS,
    COST_METRIC_LABELS,
    SESSION_KEY_PREFIX,
    CostConfig,
    _build_cost_breakdown_chart,
    _build_cost_dataframe,
    _build_regression_dataframe,
    _build_token_distribution_chart,
    _format_cost_value,
    _format_token_value,
    _render_metric_selector,
    _session_key,
)


class TestSessionKey(TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("foo")
        self.assertEqual(result, f"{SESSION_KEY_PREFIX}_foo")

    def test_different_suffixes(self):
        self.assertNotEqual(_session_key("a"), _session_key("b"))


class TestCostConfig(TestCase):
    """Tests for CostConfig frozen dataclass."""

    def test_default_values(self):
        config = CostConfig()
        self.assertEqual(config.experiment_id, "")
        self.assertEqual(config.baseline_agent, "")
        self.assertEqual(config.selected_metrics, COST_METRICS)

    def test_custom_values(self):
        config = CostConfig(
            experiment_id="exp001",
            baseline_agent="agent_a",
            selected_metrics=("total_cost_usd",),
        )
        self.assertEqual(config.experiment_id, "exp001")
        self.assertEqual(config.baseline_agent, "agent_a")
        self.assertEqual(config.selected_metrics, ("total_cost_usd",))

    def test_frozen(self):
        config = CostConfig()
        with self.assertRaises(AttributeError):
            config.experiment_id = "changed"  # type: ignore

    def test_to_dict(self):
        config = CostConfig(
            experiment_id="exp001",
            baseline_agent="agent_a",
            selected_metrics=("total_cost_usd", "input_cost_usd"),
        )
        d = config.to_dict()
        self.assertEqual(d["experiment_id"], "exp001")
        self.assertEqual(d["baseline_agent"], "agent_a")
        self.assertEqual(d["selected_metrics"], ["total_cost_usd", "input_cost_usd"])

    def test_to_dict_converts_tuples_to_lists(self):
        config = CostConfig(selected_metrics=("a", "b"))
        d = config.to_dict()
        self.assertIsInstance(d["selected_metrics"], list)


class TestConstants(TestCase):
    """Tests for module constants."""

    def test_cost_metrics_is_tuple(self):
        self.assertIsInstance(COST_METRICS, tuple)

    def test_cost_metrics_has_items(self):
        self.assertGreater(len(COST_METRICS), 0)

    def test_all_metrics_have_labels(self):
        for metric in COST_METRICS:
            self.assertIn(metric, COST_METRIC_LABELS)

    def test_session_key_prefix(self):
        self.assertEqual(SESSION_KEY_PREFIX, "cost_config")


class TestFormatCostValue(TestCase):
    """Tests for _format_cost_value."""

    def test_none_returns_na(self):
        self.assertEqual(_format_cost_value(None), "N/A")

    def test_normal_value(self):
        self.assertEqual(_format_cost_value(12.50), "$12.50")

    def test_zero(self):
        self.assertEqual(_format_cost_value(0), "$0.00")

    def test_small_value(self):
        result = _format_cost_value(0.005)
        self.assertEqual(result, "$0.0050")

    def test_invalid_type(self):
        self.assertEqual(_format_cost_value("not_a_number"), "not_a_number")

    def test_large_value(self):
        self.assertEqual(_format_cost_value(1000.00), "$1000.00")


class TestFormatTokenValue(TestCase):
    """Tests for _format_token_value."""

    def test_none_returns_na(self):
        self.assertEqual(_format_token_value(None), "N/A")

    def test_normal_value(self):
        self.assertEqual(_format_token_value(12345), "12,345")

    def test_zero(self):
        self.assertEqual(_format_token_value(0), "0")

    def test_invalid_type(self):
        self.assertEqual(_format_token_value("not_a_number"), "not_a_number")

    def test_large_value(self):
        self.assertEqual(_format_token_value(1000000), "1,000,000")


class TestBuildCostDataframe(TestCase):
    """Tests for _build_cost_dataframe."""

    def _make_agent_metrics(self, **kwargs):
        defaults = {
            "agent_name": "agent_a",
            "model_name": "claude-3-5-haiku",
            "total_tasks": 10,
            "passed_tasks": 7,
            "pass_rate": 0.7,
            "total_input_tokens": 50000.0,
            "total_output_tokens": 10000.0,
            "total_cost_usd": 1.50,
            "input_cost_usd": 0.80,
            "output_cost_usd": 0.70,
            "cost_per_success": 0.21,
            "cost_rank": 1,
            "efficiency_rank": 1,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_empty_result(self):
        result = SimpleNamespace(agent_metrics={})
        df = _build_cost_dataframe(result)
        self.assertTrue(df.empty)

    def test_single_agent(self):
        metrics = self._make_agent_metrics()
        result = SimpleNamespace(agent_metrics={"agent_a": metrics})
        df = _build_cost_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Agent"], "agent_a")
        self.assertAlmostEqual(df.iloc[0]["Total Cost (USD)"], 1.50)

    def test_multiple_agents(self):
        metrics_a = self._make_agent_metrics(agent_name="agent_a")
        metrics_b = self._make_agent_metrics(agent_name="agent_b", total_cost_usd=2.50)
        result = SimpleNamespace(agent_metrics={"agent_a": metrics_a, "agent_b": metrics_b})
        df = _build_cost_dataframe(result)
        self.assertEqual(len(df), 2)

    def test_includes_all_columns(self):
        metrics = self._make_agent_metrics()
        result = SimpleNamespace(agent_metrics={"agent_a": metrics})
        df = _build_cost_dataframe(result)
        expected_cols = [
            "Agent", "Total Cost (USD)", "Input Cost (USD)", "Output Cost (USD)",
            "Cost per Success (USD)", "Total Input Tokens", "Total Output Tokens",
            "Total Tasks", "Passed Tasks", "Pass Rate", "Cost Rank", "Efficiency Rank",
        ]
        for col in expected_cols:
            self.assertIn(col, df.columns)

    def test_no_agent_metrics_attr(self):
        result = SimpleNamespace()
        df = _build_cost_dataframe(result)
        self.assertTrue(df.empty)


class TestBuildRegressionDataframe(TestCase):
    """Tests for _build_regression_dataframe."""

    def test_empty_regressions(self):
        result = SimpleNamespace(regressions=[])
        df = _build_regression_dataframe(result)
        self.assertTrue(df.empty)

    def test_single_regression(self):
        reg = SimpleNamespace(
            agent_name="agent_b",
            metric_name="total_cost_usd",
            baseline_value=1.00,
            regression_value=1.50,
            delta_percent=50.0,
            severity="high",
        )
        result = SimpleNamespace(regressions=[reg])
        df = _build_regression_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Agent"], "agent_b")
        self.assertEqual(df.iloc[0]["Severity"], "HIGH")

    def test_multiple_regressions(self):
        regs = [
            SimpleNamespace(
                agent_name="a", metric_name="cost", baseline_value=1.0,
                regression_value=2.0, delta_percent=100.0, severity="critical",
            ),
            SimpleNamespace(
                agent_name="b", metric_name="tokens", baseline_value=1000,
                regression_value=2000, delta_percent=100.0, severity="medium",
            ),
        ]
        result = SimpleNamespace(regressions=regs)
        df = _build_regression_dataframe(result)
        self.assertEqual(len(df), 2)

    def test_no_regressions_attr(self):
        result = SimpleNamespace()
        df = _build_regression_dataframe(result)
        self.assertTrue(df.empty)


class TestBuildTokenDistributionChart(TestCase):
    """Tests for _build_token_distribution_chart."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _build_token_distribution_chart(df)
        self.assertIsNone(result)

    def test_valid_dataframe(self):
        df = pd.DataFrame([{
            "Agent": "agent_a",
            "Total Input Tokens": 50000,
            "Total Output Tokens": 10000,
        }])
        fig = _build_token_distribution_chart(df)
        self.assertIsNotNone(fig)

    def test_multiple_agents(self):
        df = pd.DataFrame([
            {"Agent": "agent_a", "Total Input Tokens": 50000, "Total Output Tokens": 10000},
            {"Agent": "agent_b", "Total Input Tokens": 30000, "Total Output Tokens": 20000},
        ])
        fig = _build_token_distribution_chart(df)
        self.assertIsNotNone(fig)


class TestBuildCostBreakdownChart(TestCase):
    """Tests for _build_cost_breakdown_chart."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _build_cost_breakdown_chart(df)
        self.assertIsNone(result)

    def test_valid_dataframe(self):
        df = pd.DataFrame([{
            "Agent": "agent_a",
            "Input Cost (USD)": 0.80,
            "Output Cost (USD)": 0.70,
        }])
        fig = _build_cost_breakdown_chart(df)
        self.assertIsNotNone(fig)

    def test_multiple_agents(self):
        df = pd.DataFrame([
            {"Agent": "agent_a", "Input Cost (USD)": 0.80, "Output Cost (USD)": 0.70},
            {"Agent": "agent_b", "Input Cost (USD)": 1.20, "Output Cost (USD)": 1.50},
        ])
        fig = _build_cost_breakdown_chart(df)
        self.assertIsNotNone(fig)


class TestRenderMetricSelector(TestCase):
    """Tests for _render_metric_selector."""

    @patch("dashboard.utils.cost_config.st")
    def test_returns_tuple(self, mock_st):
        mock_st.multiselect.return_value = ["total_cost_usd"]
        result = _render_metric_selector("test")
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, ("total_cost_usd",))

    @patch("dashboard.utils.cost_config.st")
    def test_empty_selection_returns_defaults(self, mock_st):
        mock_st.multiselect.return_value = []
        result = _render_metric_selector("test")
        self.assertEqual(result, COST_METRICS[:4])


class TestRenderExperimentSelector(TestCase):
    """Tests for _render_experiment_selector."""

    @patch("dashboard.utils.cost_config.st")
    def test_no_experiments(self, mock_st):
        from dashboard.utils.cost_config import _render_experiment_selector
        loader = MagicMock()
        loader.list_experiments.return_value = []
        result = _render_experiment_selector(loader, "test")
        self.assertEqual(result, "")
        mock_st.warning.assert_called_once()

    @patch("dashboard.utils.cost_config.st")
    def test_selects_experiment(self, mock_st):
        from dashboard.utils.cost_config import _render_experiment_selector
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002"]
        mock_st.selectbox.return_value = "exp001"
        result = _render_experiment_selector(loader, "test")
        self.assertEqual(result, "exp001")


class TestRenderBaselineSelector(TestCase):
    """Tests for _render_baseline_selector."""

    @patch("dashboard.utils.cost_config.st")
    def test_no_agents(self, mock_st):
        from dashboard.utils.cost_config import _render_baseline_selector
        loader = MagicMock()
        loader.list_agents.return_value = []
        result = _render_baseline_selector(loader, "exp001", "test")
        self.assertEqual(result, "")
        mock_st.warning.assert_called_once()

    @patch("dashboard.utils.cost_config.st")
    def test_selects_agent(self, mock_st):
        from dashboard.utils.cost_config import _render_baseline_selector
        loader = MagicMock()
        loader.list_agents.return_value = ["agent_a", "agent_b"]
        mock_st.selectbox.return_value = "agent_a"
        result = _render_baseline_selector(loader, "exp001", "test")
        self.assertEqual(result, "agent_a")


class TestRenderCostConfig(TestCase):
    """Tests for render_cost_config."""

    @patch("dashboard.utils.cost_config.st")
    def test_returns_none_when_no_experiments(self, mock_st):
        from dashboard.utils.cost_config import render_cost_config
        loader = MagicMock()
        loader.list_experiments.return_value = []
        result = render_cost_config(loader, "test")
        self.assertIsNone(result)

    @patch("dashboard.utils.cost_config.st")
    def test_returns_config_when_valid(self, mock_st):
        from dashboard.utils.cost_config import render_cost_config
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        loader.list_agents.return_value = ["agent_a"]
        mock_st.selectbox.side_effect = ["exp001", "agent_a"]
        mock_st.multiselect.return_value = ["total_cost_usd"]
        result = render_cost_config(loader, "test")
        self.assertIsNotNone(result)
        self.assertEqual(result.experiment_id, "exp001")
        self.assertEqual(result.baseline_agent, "agent_a")

    @patch("dashboard.utils.cost_config.st")
    def test_returns_none_when_no_agents(self, mock_st):
        from dashboard.utils.cost_config import render_cost_config
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        loader.list_agents.return_value = []
        mock_st.selectbox.return_value = "exp001"
        result = render_cost_config(loader, "test")
        self.assertIsNone(result)


class TestRunAndDisplayCost(TestCase):
    """Tests for run_and_display_cost."""

    @patch("dashboard.utils.cost_config._render_cost_results")
    @patch("dashboard.utils.cost_config._build_regression_dataframe")
    @patch("dashboard.utils.cost_config._build_cost_dataframe")
    @patch("dashboard.utils.cost_config.st")
    def test_stores_results_in_session_state(self, mock_st, mock_build_cost, mock_build_reg, mock_render):
        from dashboard.utils.cost_config import run_and_display_cost
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        loader = MagicMock()
        cost_result = SimpleNamespace(agent_metrics={}, regressions=[])
        loader.load_cost.return_value = cost_result

        mock_build_cost.return_value = pd.DataFrame([{"Agent": "a"}])
        mock_build_reg.return_value = pd.DataFrame()

        config = CostConfig(experiment_id="exp001", baseline_agent="agent_a")
        run_and_display_cost(loader, config)

        self.assertIn("cost_config_results", mock_st.session_state)
        self.assertIn("cost_config_config_snapshot", mock_st.session_state)

    @patch("dashboard.utils.cost_config.display_error_message")
    @patch("dashboard.utils.cost_config.st")
    def test_handles_load_error(self, mock_st, mock_error):
        from dashboard.utils.cost_config import run_and_display_cost
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        loader = MagicMock()
        loader.load_cost.side_effect = Exception("DB error")

        config = CostConfig(experiment_id="exp001", baseline_agent="agent_a")
        run_and_display_cost(loader, config)
        mock_error.assert_called_once()

    @patch("dashboard.utils.cost_config.display_no_data_message")
    @patch("dashboard.utils.cost_config.st")
    def test_handles_none_result(self, mock_st, mock_no_data):
        from dashboard.utils.cost_config import run_and_display_cost
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        loader = MagicMock()
        loader.load_cost.return_value = None

        config = CostConfig(experiment_id="exp001", baseline_agent="agent_a")
        run_and_display_cost(loader, config)
        mock_no_data.assert_called_once()


class TestRenderCostResults(TestCase):
    """Tests for _render_cost_results."""

    def _make_full_cost_df(self):
        return pd.DataFrame([{
            "Agent": "agent_a",
            "Total Cost (USD)": 5.50,
            "Input Cost (USD)": 3.00,
            "Output Cost (USD)": 2.50,
            "Cost per Success (USD)": 0.79,
            "Total Input Tokens": 50000,
            "Total Output Tokens": 10000,
            "Total Tasks": 10,
            "Passed Tasks": 7,
            "Pass Rate": 0.7,
            "Cost Rank": 1,
            "Efficiency Rank": 1,
        }])

    @patch("dashboard.utils.cost_config.st")
    def test_renders_summary_cards(self, mock_st):
        from dashboard.utils.cost_config import _render_cost_results

        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=None)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock, col_mock, col_mock, col_mock]

        cost_result = SimpleNamespace(
            total_experiment_cost=5.50,
            cheapest_agent="agent_a",
            most_efficient_agent="agent_a",
        )
        cost_df = self._make_full_cost_df()
        regression_df = pd.DataFrame()
        config = CostConfig(experiment_id="exp001", baseline_agent="agent_a")

        _render_cost_results(cost_df, regression_df, cost_result, config)
        mock_st.subheader.assert_any_call("Cost Summary")

    @patch("dashboard.utils.cost_config.st")
    def test_renders_regression_section(self, mock_st):
        from dashboard.utils.cost_config import _render_cost_results

        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=None)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock, col_mock, col_mock, col_mock]

        cost_result = SimpleNamespace(
            total_experiment_cost=5.50,
            cheapest_agent="agent_a",
            most_efficient_agent="agent_a",
        )
        cost_df = self._make_full_cost_df()
        regression_df = pd.DataFrame([{"Agent": "b", "Severity": "HIGH"}])
        config = CostConfig(experiment_id="exp001", baseline_agent="agent_a")

        _render_cost_results(cost_df, regression_df, cost_result, config)
        mock_st.subheader.assert_any_call("Cost Regressions")


class TestViewIntegration(TestCase):
    """Tests for view integration."""

    @patch("dashboard.views.analysis_cost.render_breadcrumb_navigation")
    @patch("dashboard.views.analysis_cost.st")
    def test_show_cost_analysis_no_loader(self, mock_st, mock_breadcrumb):
        from dashboard.views.analysis_cost import show_cost_analysis
        session = MagicMock()
        session.get.return_value = None
        session.__contains__ = MagicMock(return_value=False)
        mock_st.session_state = session
        show_cost_analysis()
        mock_st.error.assert_called_once()

    @patch("dashboard.views.analysis_cost.render_cost_config")
    @patch("dashboard.views.analysis_cost.render_breadcrumb_navigation")
    @patch("dashboard.views.analysis_cost.st")
    def test_show_cost_analysis_no_config(self, mock_st, mock_breadcrumb, mock_render_config):
        from dashboard.views.analysis_cost import show_cost_analysis
        session = MagicMock()
        session.get.side_effect = lambda k, d=None: MagicMock() if k == "analysis_loader" else d
        session.__contains__ = MagicMock(return_value=False)
        mock_st.session_state = session
        mock_render_config.return_value = None
        mock_st.sidebar.__enter__ = MagicMock(return_value=None)
        mock_st.sidebar.__exit__ = MagicMock(return_value=False)
        show_cost_analysis()
        mock_st.info.assert_called()
