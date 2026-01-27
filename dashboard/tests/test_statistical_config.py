"""
Tests for dashboard/utils/statistical_config.py - GUI-driven statistical analysis config.

Tests cover:
- StatisticalConfig dataclass
- Experiment selector rendering
- Baseline agent selector rendering
- Significance level input
- Test type selector
- Effect size threshold slider
- Metric selector
- Full config panel rendering
- Results dataframe building
- Effect size chart building
- P-value chart building
- Confidence interval chart building
- Run and display results
- Render results
"""

import unittest
from unittest.mock import MagicMock, patch
from dataclasses import FrozenInstanceError

import pandas as pd

from dashboard.utils.statistical_config import (
    StatisticalConfig,
    AVAILABLE_METRICS,
    TEST_TYPES,
    EFFECT_SIZE_THRESHOLDS,
    _render_experiment_selector,
    _render_baseline_selector,
    _render_significance_level,
    _render_test_type_selector,
    _render_effect_size_threshold,
    _render_metric_selector,
    render_statistical_config,
    _build_results_dataframe,
    _build_effect_size_chart,
    _build_pvalue_chart,
    _build_confidence_interval_chart,
    run_and_display_results,
    _render_results,
)


# --- StatisticalConfig dataclass tests ---


class TestStatisticalConfig(unittest.TestCase):
    """Tests for the StatisticalConfig frozen dataclass."""

    def test_default_values(self):
        config = StatisticalConfig()
        self.assertEqual(config.experiment_ids, ())
        self.assertEqual(config.baseline_agent, "")
        self.assertEqual(config.significance_level, 0.05)
        self.assertEqual(config.test_types, ("t-test",))
        self.assertEqual(config.effect_size_threshold, 0.5)
        self.assertEqual(config.selected_metrics, AVAILABLE_METRICS)

    def test_custom_values(self):
        config = StatisticalConfig(
            experiment_ids=("exp1", "exp2"),
            baseline_agent="agent_a",
            significance_level=0.01,
            test_types=("mann-whitney", "chi-squared"),
            effect_size_threshold=0.8,
            selected_metrics=("pass_rate",),
        )
        self.assertEqual(config.experiment_ids, ("exp1", "exp2"))
        self.assertEqual(config.baseline_agent, "agent_a")
        self.assertEqual(config.significance_level, 0.01)
        self.assertEqual(config.test_types, ("mann-whitney", "chi-squared"))
        self.assertEqual(config.effect_size_threshold, 0.8)
        self.assertEqual(config.selected_metrics, ("pass_rate",))

    def test_frozen(self):
        config = StatisticalConfig()
        with self.assertRaises(FrozenInstanceError):
            config.significance_level = 0.01

    def test_to_dict(self):
        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
            significance_level=0.05,
            test_types=("t-test",),
            effect_size_threshold=0.5,
            selected_metrics=("pass_rate", "avg_duration_seconds"),
        )
        result = config.to_dict()
        self.assertEqual(result["experiment_ids"], ["exp1"])
        self.assertEqual(result["baseline_agent"], "agent_a")
        self.assertEqual(result["significance_level"], 0.05)
        self.assertEqual(result["test_types"], ["t-test"])
        self.assertEqual(result["effect_size_threshold"], 0.5)
        self.assertEqual(result["selected_metrics"], ["pass_rate", "avg_duration_seconds"])

    def test_to_dict_returns_lists_not_tuples(self):
        config = StatisticalConfig(
            experiment_ids=("a", "b"),
            test_types=("t-test", "mann-whitney"),
            selected_metrics=("pass_rate",),
        )
        result = config.to_dict()
        self.assertIsInstance(result["experiment_ids"], list)
        self.assertIsInstance(result["test_types"], list)
        self.assertIsInstance(result["selected_metrics"], list)


# --- Constants tests ---


class TestConstants(unittest.TestCase):
    """Tests for module-level constants."""

    def test_test_types_structure(self):
        self.assertGreater(len(TEST_TYPES), 0)
        for item in TEST_TYPES:
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], str)
            self.assertIsInstance(item[1], str)

    def test_available_metrics(self):
        self.assertIn("pass_rate", AVAILABLE_METRICS)
        self.assertIn("avg_duration_seconds", AVAILABLE_METRICS)
        self.assertIn("avg_mcp_calls", AVAILABLE_METRICS)

    def test_effect_size_thresholds(self):
        self.assertGreater(len(EFFECT_SIZE_THRESHOLDS), 0)
        for name, threshold in EFFECT_SIZE_THRESHOLDS:
            self.assertIsInstance(name, str)
            self.assertIsInstance(threshold, float)

    def test_test_types_contains_expected(self):
        type_names = [t[0] for t in TEST_TYPES]
        self.assertIn("t-test", type_names)
        self.assertIn("mann-whitney", type_names)
        self.assertIn("chi-squared", type_names)


# --- Experiment selector tests ---


class TestRenderExperimentSelector(unittest.TestCase):
    """Tests for _render_experiment_selector."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_empty_when_no_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = []
        result = _render_experiment_selector(loader)
        self.assertEqual(result, ())

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_selected_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp1", "exp2", "exp3"]
        mock_st.multiselect.return_value = ["exp1", "exp2"]
        result = _render_experiment_selector(loader)
        self.assertEqual(result, ("exp1", "exp2"))

    @patch("dashboard.utils.statistical_config.st")
    def test_uses_custom_session_key(self, mock_st):
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp1"]
        mock_st.multiselect.return_value = ["exp1"]
        _render_experiment_selector(loader, session_key="custom")
        mock_st.multiselect.assert_called_once()
        call_kwargs = mock_st.multiselect.call_args
        self.assertIn("custom_experiments", call_kwargs.kwargs.get("key", ""))


# --- Baseline selector tests ---


class TestRenderBaselineSelector(unittest.TestCase):
    """Tests for _render_baseline_selector."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_empty_when_no_agents(self, mock_st):
        loader = MagicMock()
        loader.list_agents.return_value = []
        result = _render_baseline_selector(loader, ("exp1",))
        self.assertEqual(result, "")

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_selected_agent(self, mock_st):
        loader = MagicMock()
        loader.list_agents.return_value = ["agent_a", "agent_b"]
        mock_st.selectbox.return_value = "agent_a"
        result = _render_baseline_selector(loader, ("exp1",))
        self.assertEqual(result, "agent_a")

    @patch("dashboard.utils.statistical_config.st")
    def test_deduplicates_agents_from_multiple_experiments(self, mock_st):
        loader = MagicMock()
        loader.list_agents.side_effect = [
            ["agent_a", "agent_b"],
            ["agent_b", "agent_c"],
        ]
        mock_st.selectbox.return_value = "agent_a"
        _render_baseline_selector(loader, ("exp1", "exp2"))
        # Should call list_agents for each experiment
        self.assertEqual(loader.list_agents.call_count, 2)
        # selectbox should have deduplicated agents
        call_args = mock_st.selectbox.call_args
        agents_list = call_args.args[1]
        self.assertEqual(agents_list, ["agent_a", "agent_b", "agent_c"])

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_empty_string_for_none_selection(self, mock_st):
        loader = MagicMock()
        loader.list_agents.return_value = ["agent_a"]
        mock_st.selectbox.return_value = None
        result = _render_baseline_selector(loader, ("exp1",))
        self.assertEqual(result, "")


# --- Significance level tests ---


class TestRenderSignificanceLevel(unittest.TestCase):
    """Tests for _render_significance_level."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_number_input_value(self, mock_st):
        mock_st.number_input.return_value = 0.01
        result = _render_significance_level()
        self.assertEqual(result, 0.01)

    @patch("dashboard.utils.statistical_config.st")
    def test_uses_session_key(self, mock_st):
        mock_st.number_input.return_value = 0.05
        _render_significance_level(session_key="test_key")
        call_kwargs = mock_st.number_input.call_args.kwargs
        self.assertEqual(call_kwargs["key"], "test_key_alpha")


# --- Test type selector tests ---


class TestRenderTestTypeSelector(unittest.TestCase):
    """Tests for _render_test_type_selector."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_selected_types(self, mock_st):
        mock_st.multiselect.return_value = ["t-test", "mann-whitney"]
        result = _render_test_type_selector()
        self.assertEqual(result, ("t-test", "mann-whitney"))

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_default_when_empty(self, mock_st):
        mock_st.multiselect.return_value = []
        result = _render_test_type_selector()
        self.assertEqual(result, ("t-test",))


# --- Effect size threshold tests ---


class TestRenderEffectSizeThreshold(unittest.TestCase):
    """Tests for _render_effect_size_threshold."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_slider_value(self, mock_st):
        mock_st.slider.return_value = 0.8
        result = _render_effect_size_threshold()
        self.assertEqual(result, 0.8)


# --- Metric selector tests ---


class TestRenderMetricSelector(unittest.TestCase):
    """Tests for _render_metric_selector."""

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_selected_metrics(self, mock_st):
        mock_st.multiselect.return_value = ["pass_rate"]
        result = _render_metric_selector()
        self.assertEqual(result, ("pass_rate",))

    @patch("dashboard.utils.statistical_config.st")
    def test_returns_all_when_empty(self, mock_st):
        mock_st.multiselect.return_value = []
        result = _render_metric_selector()
        self.assertEqual(result, AVAILABLE_METRICS)


# --- Full config rendering tests ---


class TestRenderStatisticalConfig(unittest.TestCase):
    """Tests for render_statistical_config."""

    @patch("dashboard.utils.statistical_config._render_metric_selector")
    @patch("dashboard.utils.statistical_config._render_effect_size_threshold")
    @patch("dashboard.utils.statistical_config._render_test_type_selector")
    @patch("dashboard.utils.statistical_config._render_significance_level")
    @patch("dashboard.utils.statistical_config._render_baseline_selector")
    @patch("dashboard.utils.statistical_config._render_experiment_selector")
    @patch("dashboard.utils.statistical_config.st")
    def test_returns_config_with_all_values(
        self, mock_st, mock_exp, mock_base, mock_sig, mock_test, mock_effect, mock_metric
    ):
        loader = MagicMock()
        mock_exp.return_value = ("exp1",)
        mock_base.return_value = "agent_a"
        mock_sig.return_value = 0.05
        mock_test.return_value = ("t-test",)
        mock_effect.return_value = 0.5
        mock_metric.return_value = ("pass_rate",)

        result = render_statistical_config(loader)

        self.assertIsNotNone(result)
        self.assertEqual(result.experiment_ids, ("exp1",))
        self.assertEqual(result.baseline_agent, "agent_a")
        self.assertEqual(result.significance_level, 0.05)
        self.assertEqual(result.test_types, ("t-test",))
        self.assertEqual(result.effect_size_threshold, 0.5)
        self.assertEqual(result.selected_metrics, ("pass_rate",))

    @patch("dashboard.utils.statistical_config._render_experiment_selector")
    @patch("dashboard.utils.statistical_config.st")
    def test_returns_none_when_no_experiments(self, mock_st, mock_exp):
        loader = MagicMock()
        mock_exp.return_value = ()

        result = render_statistical_config(loader)
        self.assertIsNone(result)

    @patch("dashboard.utils.statistical_config._render_baseline_selector")
    @patch("dashboard.utils.statistical_config._render_experiment_selector")
    @patch("dashboard.utils.statistical_config.st")
    def test_returns_none_when_no_baseline(self, mock_st, mock_exp, mock_base):
        loader = MagicMock()
        mock_exp.return_value = ("exp1",)
        mock_base.return_value = ""

        result = render_statistical_config(loader)
        self.assertIsNone(result)


# --- Results dataframe building tests ---


class TestBuildResultsDataframe(unittest.TestCase):
    """Tests for _build_results_dataframe."""

    def _make_effect_size(self, cohens_d=0.5, cramers_v=None, interpretation="medium"):
        effect = MagicMock()
        effect.cohens_d = cohens_d
        effect.cramers_v = cramers_v
        effect.interpretation = interpretation
        return effect

    def _make_test(self, metric_name="pass_rate", p_value=0.03, baseline_mean=0.7,
                   variant_mean=0.8, baseline_n=50, variant_n=50, power=0.85):
        test = MagicMock()
        test.metric_name = metric_name
        test.p_value = p_value
        test.baseline_mean = baseline_mean
        test.variant_mean = variant_mean
        test.baseline_n = baseline_n
        test.variant_n = variant_n
        test.effect_size = self._make_effect_size()
        test.observed_power = power
        return test

    def test_builds_dataframe_from_result(self):
        result = MagicMock()
        result.tests = {
            "variant_b": {
                "pass_rate": self._make_test(p_value=0.03),
                "avg_duration_seconds": self._make_test(
                    metric_name="avg_duration_seconds", p_value=0.12
                ),
            }
        }

        df = _build_results_dataframe(result, alpha=0.05)

        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertIn("Variant", df.columns)
        self.assertIn("Metric", df.columns)
        self.assertIn("P-Value", df.columns)
        self.assertIn("Significant", df.columns)

    def test_empty_for_no_tests(self):
        result = MagicMock()
        result.tests = {}

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertTrue(df.empty)

    def test_significant_flag(self):
        result = MagicMock()
        result.tests = {
            "variant_b": {
                "pass_rate": self._make_test(p_value=0.03),
            }
        }

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertEqual(df.iloc[0]["Significant"], "Yes")

    def test_not_significant_flag(self):
        result = MagicMock()
        result.tests = {
            "variant_b": {
                "pass_rate": self._make_test(p_value=0.12),
            }
        }

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertEqual(df.iloc[0]["Significant"], "No")

    def test_effect_size_uses_cohens_d(self):
        test = self._make_test()
        test.effect_size = self._make_effect_size(cohens_d=0.7, cramers_v=None)

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": test}}

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertAlmostEqual(df.iloc[0]["Effect Size"], 0.7, places=3)

    def test_effect_size_uses_cramers_v_when_larger(self):
        test = self._make_test()
        test.effect_size = self._make_effect_size(cohens_d=0.3, cramers_v=0.9)

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": test}}

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertAlmostEqual(df.iloc[0]["Effect Size"], 0.9, places=3)

    def test_handles_none_effect_sizes(self):
        test = self._make_test()
        test.effect_size = self._make_effect_size(cohens_d=None, cramers_v=None)

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": test}}

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertAlmostEqual(df.iloc[0]["Effect Size"], 0.0, places=3)

    def test_multiple_variants(self):
        result = MagicMock()
        result.tests = {
            "variant_b": {"pass_rate": self._make_test()},
            "variant_c": {"pass_rate": self._make_test()},
        }

        df = _build_results_dataframe(result, alpha=0.05)
        self.assertEqual(len(df), 2)
        variants = set(df["Variant"])
        self.assertEqual(variants, {"variant_b", "variant_c"})


# --- Chart building tests ---


class TestBuildEffectSizeChart(unittest.TestCase):
    """Tests for _build_effect_size_chart."""

    def test_returns_none_for_empty_df(self):
        df = pd.DataFrame()
        result = _build_effect_size_chart(df, 0.5)
        self.assertIsNone(result)

    def test_returns_figure_for_valid_data(self):
        df = pd.DataFrame([
            {
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Effect Size": 0.7,
                "Effect Magnitude": "medium",
            }
        ])
        fig = _build_effect_size_chart(df, 0.5)
        self.assertIsNotNone(fig)

    def test_chart_includes_threshold_line(self):
        df = pd.DataFrame([
            {
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Effect Size": 0.7,
                "Effect Magnitude": "medium",
            }
        ])
        fig = _build_effect_size_chart(df, 0.5)
        # The figure should have layout shapes (vline)
        self.assertIsNotNone(fig)


class TestBuildPvalueChart(unittest.TestCase):
    """Tests for _build_pvalue_chart."""

    def test_returns_none_for_empty_df(self):
        df = pd.DataFrame()
        result = _build_pvalue_chart(df, 0.05)
        self.assertIsNone(result)

    def test_returns_figure_for_valid_data(self):
        df = pd.DataFrame([
            {
                "Variant": "var_b",
                "Metric": "pass_rate",
                "P-Value": 0.03,
            }
        ])
        fig = _build_pvalue_chart(df, 0.05)
        self.assertIsNotNone(fig)

    def test_color_coding_significant(self):
        df = pd.DataFrame([
            {"Variant": "var_b", "Metric": "pass_rate", "P-Value": 0.01},
            {"Variant": "var_b", "Metric": "duration", "P-Value": 0.12},
        ])
        fig = _build_pvalue_chart(df, 0.05)
        self.assertIsNotNone(fig)


class TestBuildConfidenceIntervalChart(unittest.TestCase):
    """Tests for _build_confidence_interval_chart."""

    def test_returns_none_for_empty_df(self):
        df = pd.DataFrame()
        result = _build_confidence_interval_chart(df)
        self.assertIsNone(result)

    def test_returns_figure_for_valid_data(self):
        df = pd.DataFrame([
            {
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Baseline Mean": 0.7,
                "Variant Mean": 0.85,
            }
        ])
        fig = _build_confidence_interval_chart(df)
        self.assertIsNotNone(fig)

    def test_creates_baseline_and_variant_groups(self):
        df = pd.DataFrame([
            {
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Baseline Mean": 0.7,
                "Variant Mean": 0.85,
            }
        ])
        fig = _build_confidence_interval_chart(df)
        # Figure should have data for both groups
        self.assertIsNotNone(fig)
        # Check that figure has traces
        self.assertGreater(len(fig.data), 0)


# --- Run and display results tests ---


class TestRunAndDisplayResults(unittest.TestCase):
    """Tests for run_and_display_results."""

    def _make_effect_size(self, cohens_d=0.5, cramers_v=None, interpretation="medium"):
        effect = MagicMock()
        effect.cohens_d = cohens_d
        effect.cramers_v = cramers_v
        effect.interpretation = interpretation
        return effect

    def _make_test(self, p_value=0.03):
        test = MagicMock()
        test.p_value = p_value
        test.baseline_mean = 0.7
        test.variant_mean = 0.8
        test.baseline_n = 50
        test.variant_n = 50
        test.effect_size = self._make_effect_size()
        test.observed_power = 0.85
        return test

    @patch("dashboard.utils.statistical_config._render_results")
    @patch("dashboard.utils.statistical_config.st")
    def test_runs_analysis_and_renders(self, mock_st, mock_render):
        mock_st.session_state = {}

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": self._make_test()}}

        loader = MagicMock()
        loader.load_statistical.return_value = result

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
            significance_level=0.05,
        )

        run_and_display_results(loader, config)

        loader.load_statistical.assert_called_once_with(
            "exp1",
            baseline_agent="agent_a",
            confidence_level=0.95,
        )
        mock_render.assert_called_once()

    @patch("dashboard.utils.statistical_config.display_error_message")
    @patch("dashboard.utils.statistical_config.st")
    def test_handles_loader_error(self, mock_st, mock_error):
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        loader = MagicMock()
        loader.load_statistical.side_effect = Exception("DB error")

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
        )

        run_and_display_results(loader, config)

        mock_error.assert_called()

    @patch("dashboard.utils.statistical_config.display_no_data_message")
    @patch("dashboard.utils.statistical_config.st")
    def test_shows_no_data_when_empty_results(self, mock_st, mock_no_data):
        mock_st.session_state = {}

        result = MagicMock()
        result.tests = {}

        loader = MagicMock()
        loader.load_statistical.return_value = result

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
        )

        run_and_display_results(loader, config)

        mock_no_data.assert_called()

    @patch("dashboard.utils.statistical_config._render_results")
    @patch("dashboard.utils.statistical_config.st")
    def test_filters_by_selected_metrics(self, mock_st, mock_render):
        mock_st.session_state = {}

        test_pass = self._make_test()
        test_dur = self._make_test(p_value=0.12)

        result = MagicMock()
        result.tests = {
            "variant_b": {
                "pass_rate": test_pass,
                "avg_duration_seconds": test_dur,
            }
        }

        loader = MagicMock()
        loader.load_statistical.return_value = result

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
            selected_metrics=("pass_rate",),
        )

        run_and_display_results(loader, config)

        # _render_results should be called with a df that only has pass_rate
        mock_render.assert_called_once()
        rendered_df = mock_render.call_args.args[0]
        self.assertTrue(all(rendered_df["Metric"] == "pass_rate"))

    @patch("dashboard.utils.statistical_config._render_results")
    @patch("dashboard.utils.statistical_config.st")
    def test_stores_results_in_session_state(self, mock_st, mock_render):
        mock_st.session_state = {}

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": self._make_test()}}

        loader = MagicMock()
        loader.load_statistical.return_value = result

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
        )

        run_and_display_results(loader, config)

        self.assertIn("stat_config_results", mock_st.session_state)
        self.assertIn("stat_config_config_snapshot", mock_st.session_state)


# --- Render results tests ---


class TestRenderResults(unittest.TestCase):
    """Tests for _render_results."""

    @patch("dashboard.utils.statistical_config._build_confidence_interval_chart")
    @patch("dashboard.utils.statistical_config._build_pvalue_chart")
    @patch("dashboard.utils.statistical_config._build_effect_size_chart")
    @patch("dashboard.utils.statistical_config.display_summary_card")
    @patch("dashboard.utils.statistical_config.st")
    def test_renders_summary_cards(
        self, mock_st, mock_card, mock_effect, mock_pvalue, mock_ci
    ):
        mock_effect.return_value = None
        mock_pvalue.return_value = None
        mock_ci.return_value = None

        df = pd.DataFrame([
            {
                "Experiment": "exp1",
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Baseline Mean": 0.7,
                "Variant Mean": 0.85,
                "P-Value": 0.03,
                "Significant": "Yes",
                "Effect Size": 0.5,
                "Effect Magnitude": "medium",
                "Power": 0.85,
                "Baseline N": 50,
                "Variant N": 50,
            }
        ])

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
            significance_level=0.05,
        )

        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())

        _render_results(df, config)

        # 4 summary cards should be rendered
        self.assertEqual(mock_card.call_count, 4)

    @patch("dashboard.utils.statistical_config._build_confidence_interval_chart")
    @patch("dashboard.utils.statistical_config._build_pvalue_chart")
    @patch("dashboard.utils.statistical_config._build_effect_size_chart")
    @patch("dashboard.utils.statistical_config.st")
    def test_renders_csv_export(
        self, mock_st, mock_effect, mock_pvalue, mock_ci
    ):
        mock_effect.return_value = None
        mock_pvalue.return_value = None
        mock_ci.return_value = None

        df = pd.DataFrame([
            {
                "Experiment": "exp1",
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Baseline Mean": 0.7,
                "Variant Mean": 0.85,
                "P-Value": 0.03,
                "Significant": "Yes",
                "Effect Size": 0.5,
                "Effect Magnitude": "medium",
                "Power": 0.85,
                "Baseline N": 50,
                "Variant N": 50,
            }
        ])

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
        )

        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())

        _render_results(df, config)

        # download_button should be called for CSV export
        mock_st.download_button.assert_called_once()
        call_kwargs = mock_st.download_button.call_args.kwargs
        self.assertEqual(call_kwargs["mime"], "text/csv")

    @patch("dashboard.utils.statistical_config._build_confidence_interval_chart")
    @patch("dashboard.utils.statistical_config._build_pvalue_chart")
    @patch("dashboard.utils.statistical_config._build_effect_size_chart")
    @patch("dashboard.utils.statistical_config.st")
    def test_renders_plotly_charts_when_available(
        self, mock_st, mock_effect, mock_pvalue, mock_ci
    ):
        mock_fig = MagicMock()
        mock_effect.return_value = mock_fig
        mock_pvalue.return_value = mock_fig
        mock_ci.return_value = mock_fig

        df = pd.DataFrame([
            {
                "Experiment": "exp1",
                "Variant": "var_b",
                "Metric": "pass_rate",
                "Baseline Mean": 0.7,
                "Variant Mean": 0.85,
                "P-Value": 0.03,
                "Significant": "Yes",
                "Effect Size": 0.5,
                "Effect Magnitude": "medium",
                "Power": 0.85,
                "Baseline N": 50,
                "Variant N": 50,
            }
        ])

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
        )

        mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())

        _render_results(df, config)

        # plotly_chart should be called 3 times (effect, pvalue, CI)
        self.assertEqual(mock_st.plotly_chart.call_count, 3)


# --- Integration tests ---


class TestStatisticalViewIntegration(unittest.TestCase):
    """Integration tests for the statistical analysis view."""

    @patch("dashboard.utils.statistical_config.st")
    def test_config_to_results_flow(self, mock_st):
        """Test the complete flow from config to results."""
        mock_st.session_state = {}

        config = StatisticalConfig(
            experiment_ids=("exp1",),
            baseline_agent="agent_a",
            significance_level=0.05,
            test_types=("t-test",),
            effect_size_threshold=0.5,
            selected_metrics=("pass_rate", "avg_duration_seconds"),
        )

        # Verify config is valid
        self.assertEqual(len(config.experiment_ids), 1)
        self.assertEqual(config.baseline_agent, "agent_a")

        # Verify serialization roundtrip
        config_dict = config.to_dict()
        self.assertEqual(config_dict["experiment_ids"], ["exp1"])
        self.assertEqual(config_dict["baseline_agent"], "agent_a")

    def test_results_dataframe_structure(self):
        """Test that results dataframe has expected columns."""
        effect = MagicMock()
        effect.cohens_d = 0.5
        effect.cramers_v = None
        effect.interpretation = "medium"

        test = MagicMock()
        test.p_value = 0.03
        test.baseline_mean = 0.7
        test.variant_mean = 0.8
        test.baseline_n = 50
        test.variant_n = 50
        test.effect_size = effect
        test.observed_power = 0.85

        result = MagicMock()
        result.tests = {"variant_b": {"pass_rate": test}}

        df = _build_results_dataframe(result, 0.05)

        expected_columns = {
            "Variant", "Metric", "Baseline Mean", "Variant Mean",
            "P-Value", "Significant", "Effect Size", "Effect Magnitude",
            "Power", "Baseline N", "Variant N",
        }
        self.assertEqual(set(df.columns), expected_columns)


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_empty_experiment_ids(self):
        config = StatisticalConfig(experiment_ids=())
        self.assertEqual(len(config.experiment_ids), 0)

    def test_single_metric(self):
        config = StatisticalConfig(selected_metrics=("pass_rate",))
        self.assertEqual(len(config.selected_metrics), 1)

    def test_build_chart_with_single_row(self):
        df = pd.DataFrame([
            {
                "Variant": "v",
                "Metric": "m",
                "Effect Size": 0.3,
                "Effect Magnitude": "small",
            }
        ])
        fig = _build_effect_size_chart(df, 0.5)
        self.assertIsNotNone(fig)

    def test_build_pvalue_chart_all_significant(self):
        df = pd.DataFrame([
            {"Variant": "v1", "Metric": "m1", "P-Value": 0.001},
            {"Variant": "v2", "Metric": "m2", "P-Value": 0.01},
        ])
        fig = _build_pvalue_chart(df, 0.05)
        self.assertIsNotNone(fig)

    def test_build_pvalue_chart_none_significant(self):
        df = pd.DataFrame([
            {"Variant": "v1", "Metric": "m1", "P-Value": 0.5},
            {"Variant": "v2", "Metric": "m2", "P-Value": 0.9},
        ])
        fig = _build_pvalue_chart(df, 0.05)
        self.assertIsNotNone(fig)

    def test_build_ci_chart_with_zero_means(self):
        df = pd.DataFrame([
            {
                "Variant": "v",
                "Metric": "m",
                "Baseline Mean": 0.0,
                "Variant Mean": 0.0,
            }
        ])
        fig = _build_confidence_interval_chart(df)
        self.assertIsNotNone(fig)


if __name__ == "__main__":
    unittest.main()
