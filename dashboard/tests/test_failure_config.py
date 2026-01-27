"""
Tests for dashboard.utils.failure_config.

Covers:
- FailureConfig frozen dataclass
- Session key generation
- Experiment selector rendering
- Agent selector rendering
- Full config rendering
- Pattern DataFrame building
- Category DataFrame building
- Difficulty DataFrame building
- Category pie chart building
- Pattern bar chart building
- Run and display failures orchestration
- Results rendering
- View integration
"""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pandas as pd

from dashboard.utils.failure_config import (
    SESSION_KEY_PREFIX,
    FailureConfig,
    _build_category_dataframe,
    _build_category_pie_chart,
    _build_difficulty_dataframe,
    _build_pattern_bar_chart,
    _build_pattern_dataframe,
    _session_key,
)


class TestSessionKey(TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("foo")
        self.assertEqual(result, f"{SESSION_KEY_PREFIX}_foo")

    def test_different_suffixes(self):
        self.assertNotEqual(_session_key("a"), _session_key("b"))


class TestFailureConfig(TestCase):
    """Tests for FailureConfig frozen dataclass."""

    def test_default_values(self):
        config = FailureConfig()
        self.assertEqual(config.experiment_id, "")
        self.assertEqual(config.agent_name, "")
        self.assertTrue(config.include_all_agents)

    def test_custom_values(self):
        config = FailureConfig(
            experiment_id="exp001",
            agent_name="agent_a",
            include_all_agents=False,
        )
        self.assertEqual(config.experiment_id, "exp001")
        self.assertEqual(config.agent_name, "agent_a")
        self.assertFalse(config.include_all_agents)

    def test_frozen(self):
        config = FailureConfig()
        with self.assertRaises(AttributeError):
            config.experiment_id = "changed"  # type: ignore

    def test_to_dict(self):
        config = FailureConfig(
            experiment_id="exp001",
            agent_name="agent_a",
            include_all_agents=False,
        )
        d = config.to_dict()
        self.assertEqual(d["experiment_id"], "exp001")
        self.assertEqual(d["agent_name"], "agent_a")
        self.assertFalse(d["include_all_agents"])

    def test_to_dict_all_agents(self):
        config = FailureConfig(experiment_id="exp001")
        d = config.to_dict()
        self.assertEqual(d["agent_name"], "")
        self.assertTrue(d["include_all_agents"])


class TestBuildPatternDataframe(TestCase):
    """Tests for _build_pattern_dataframe."""

    def _make_pattern(self, **kwargs):
        defaults = {
            "pattern_name": "High-Difficulty Task Failures",
            "description": "Agent struggles with harder tasks",
            "affected_tasks": ["task_1", "task_2"],
            "frequency": 5,
            "avg_duration_seconds": 120.5,
            "suggested_fix": "Improve reasoning",
            "confidence": 0.75,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_empty_result(self):
        result = SimpleNamespace(patterns=[])
        df = _build_pattern_dataframe(result)
        self.assertTrue(df.empty)

    def test_single_pattern(self):
        pattern = self._make_pattern()
        result = SimpleNamespace(patterns=[pattern])
        df = _build_pattern_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Pattern"], "High-Difficulty Task Failures")
        self.assertEqual(df.iloc[0]["Frequency"], 5)
        self.assertEqual(df.iloc[0]["Affected Tasks"], 2)

    def test_multiple_patterns_sorted(self):
        p1 = self._make_pattern(pattern_name="A", frequency=3)
        p2 = self._make_pattern(pattern_name="B", frequency=10)
        result = SimpleNamespace(patterns=[p1, p2])
        df = _build_pattern_dataframe(result)
        self.assertEqual(len(df), 2)
        # Sorted descending by frequency
        self.assertEqual(df.iloc[0]["Pattern"], "B")
        self.assertEqual(df.iloc[1]["Pattern"], "A")

    def test_no_patterns_attr(self):
        result = SimpleNamespace()
        df = _build_pattern_dataframe(result)
        self.assertTrue(df.empty)

    def test_includes_all_columns(self):
        pattern = self._make_pattern()
        result = SimpleNamespace(patterns=[pattern])
        df = _build_pattern_dataframe(result)
        expected_cols = ["Pattern", "Description", "Frequency", "Affected Tasks",
                         "Avg Duration (s)", "Suggested Fix", "Confidence"]
        for col in expected_cols:
            self.assertIn(col, df.columns)

    def test_zero_duration(self):
        pattern = self._make_pattern(avg_duration_seconds=0.0)
        result = SimpleNamespace(patterns=[pattern])
        df = _build_pattern_dataframe(result)
        self.assertAlmostEqual(df.iloc[0]["Avg Duration (s)"], 0.0)


class TestBuildCategoryDataframe(TestCase):
    """Tests for _build_category_dataframe."""

    def test_empty_categories(self):
        result = SimpleNamespace(top_failing_categories=[], total_failures=0)
        df = _build_category_dataframe(result)
        self.assertTrue(df.empty)

    def test_single_category(self):
        result = SimpleNamespace(
            top_failing_categories=[("architecture", 5)],
            total_failures=10,
        )
        df = _build_category_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Category"], "architecture")
        self.assertEqual(df.iloc[0]["Failures"], 5)
        self.assertAlmostEqual(df.iloc[0]["Percentage"], 50.0)

    def test_multiple_categories(self):
        result = SimpleNamespace(
            top_failing_categories=[("arch", 5), ("tool", 3), ("prompt", 2)],
            total_failures=10,
        )
        df = _build_category_dataframe(result)
        self.assertEqual(len(df), 3)

    def test_zero_failures(self):
        result = SimpleNamespace(
            top_failing_categories=[("arch", 0)],
            total_failures=0,
        )
        df = _build_category_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertAlmostEqual(df.iloc[0]["Percentage"], 0.0)

    def test_no_categories_attr(self):
        result = SimpleNamespace()
        df = _build_category_dataframe(result)
        self.assertTrue(df.empty)


class TestBuildDifficultyDataframe(TestCase):
    """Tests for _build_difficulty_dataframe."""

    def test_empty_difficulties(self):
        result = SimpleNamespace(top_failing_difficulties=[], total_failures=0)
        df = _build_difficulty_dataframe(result)
        self.assertTrue(df.empty)

    def test_single_difficulty(self):
        result = SimpleNamespace(
            top_failing_difficulties=[("hard", 8)],
            total_failures=10,
        )
        df = _build_difficulty_dataframe(result)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Difficulty"], "hard")
        self.assertAlmostEqual(df.iloc[0]["Percentage"], 80.0)

    def test_multiple_difficulties(self):
        result = SimpleNamespace(
            top_failing_difficulties=[("hard", 5), ("expert", 3), ("easy", 2)],
            total_failures=10,
        )
        df = _build_difficulty_dataframe(result)
        self.assertEqual(len(df), 3)

    def test_no_difficulties_attr(self):
        result = SimpleNamespace()
        df = _build_difficulty_dataframe(result)
        self.assertTrue(df.empty)


class TestBuildCategoryPieChart(TestCase):
    """Tests for _build_category_pie_chart."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _build_category_pie_chart(df)
        self.assertIsNone(result)

    def test_valid_dataframe(self):
        df = pd.DataFrame([
            {"Category": "architecture", "Failures": 5, "Percentage": 50.0},
            {"Category": "tooling", "Failures": 5, "Percentage": 50.0},
        ])
        fig = _build_category_pie_chart(df)
        self.assertIsNotNone(fig)

    def test_single_category(self):
        df = pd.DataFrame([
            {"Category": "architecture", "Failures": 10, "Percentage": 100.0},
        ])
        fig = _build_category_pie_chart(df)
        self.assertIsNotNone(fig)


class TestBuildPatternBarChart(TestCase):
    """Tests for _build_pattern_bar_chart."""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = _build_pattern_bar_chart(df)
        self.assertIsNone(result)

    def test_valid_dataframe(self):
        df = pd.DataFrame([
            {"Pattern": "High-Difficulty", "Frequency": 5, "Confidence": 0.8,
             "Description": "desc", "Suggested Fix": "fix"},
        ])
        fig = _build_pattern_bar_chart(df)
        self.assertIsNotNone(fig)

    def test_multiple_patterns(self):
        df = pd.DataFrame([
            {"Pattern": "P1", "Frequency": 5, "Confidence": 0.8,
             "Description": "d1", "Suggested Fix": "f1"},
            {"Pattern": "P2", "Frequency": 3, "Confidence": 0.6,
             "Description": "d2", "Suggested Fix": "f2"},
        ])
        fig = _build_pattern_bar_chart(df)
        self.assertIsNotNone(fig)


class TestRenderExperimentSelector(TestCase):
    """Tests for _render_experiment_selector."""

    @patch("dashboard.utils.failure_config.st")
    def test_no_experiments(self, mock_st):
        from dashboard.utils.failure_config import _render_experiment_selector
        loader = MagicMock()
        loader.list_experiments.return_value = []
        result = _render_experiment_selector(loader, "test")
        self.assertEqual(result, "")
        mock_st.warning.assert_called_once()

    @patch("dashboard.utils.failure_config.st")
    def test_selects_experiment(self, mock_st):
        from dashboard.utils.failure_config import _render_experiment_selector
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001", "exp002"]
        mock_st.selectbox.return_value = "exp001"
        result = _render_experiment_selector(loader, "test")
        self.assertEqual(result, "exp001")


class TestRenderAgentSelector(TestCase):
    """Tests for _render_agent_selector."""

    @patch("dashboard.utils.failure_config.st")
    def test_no_agents(self, mock_st):
        from dashboard.utils.failure_config import _render_agent_selector
        loader = MagicMock()
        loader.list_agents.return_value = []
        result = _render_agent_selector(loader, "exp001", "test")
        self.assertEqual(result, ("", True))
        mock_st.warning.assert_called_once()

    @patch("dashboard.utils.failure_config.st")
    def test_all_agents_selected(self, mock_st):
        from dashboard.utils.failure_config import _render_agent_selector
        loader = MagicMock()
        loader.list_agents.return_value = ["agent_a", "agent_b"]
        mock_st.selectbox.return_value = "All Agents"
        result = _render_agent_selector(loader, "exp001", "test")
        self.assertEqual(result, ("", True))

    @patch("dashboard.utils.failure_config.st")
    def test_specific_agent_selected(self, mock_st):
        from dashboard.utils.failure_config import _render_agent_selector
        loader = MagicMock()
        loader.list_agents.return_value = ["agent_a", "agent_b"]
        mock_st.selectbox.return_value = "agent_a"
        result = _render_agent_selector(loader, "exp001", "test")
        self.assertEqual(result, ("agent_a", False))


class TestRenderFailureConfig(TestCase):
    """Tests for render_failure_config."""

    @patch("dashboard.utils.failure_config.st")
    def test_returns_none_when_no_experiments(self, mock_st):
        from dashboard.utils.failure_config import render_failure_config
        loader = MagicMock()
        loader.list_experiments.return_value = []
        result = render_failure_config(loader, "test")
        self.assertIsNone(result)

    @patch("dashboard.utils.failure_config.st")
    def test_returns_config_all_agents(self, mock_st):
        from dashboard.utils.failure_config import render_failure_config
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        loader.list_agents.return_value = ["agent_a"]
        mock_st.selectbox.side_effect = ["exp001", "All Agents"]
        result = render_failure_config(loader, "test")
        self.assertIsNotNone(result)
        self.assertEqual(result.experiment_id, "exp001")
        self.assertTrue(result.include_all_agents)

    @patch("dashboard.utils.failure_config.st")
    def test_returns_config_specific_agent(self, mock_st):
        from dashboard.utils.failure_config import render_failure_config
        loader = MagicMock()
        loader.list_experiments.return_value = ["exp001"]
        loader.list_agents.return_value = ["agent_a"]
        mock_st.selectbox.side_effect = ["exp001", "agent_a"]
        result = render_failure_config(loader, "test")
        self.assertIsNotNone(result)
        self.assertEqual(result.experiment_id, "exp001")
        self.assertEqual(result.agent_name, "agent_a")
        self.assertFalse(result.include_all_agents)


class TestRunAndDisplayFailures(TestCase):
    """Tests for run_and_display_failures."""

    @patch("dashboard.utils.failure_config._render_failure_results")
    @patch("dashboard.utils.failure_config._build_difficulty_dataframe")
    @patch("dashboard.utils.failure_config._build_category_dataframe")
    @patch("dashboard.utils.failure_config._build_pattern_dataframe")
    @patch("dashboard.utils.failure_config.st")
    def test_stores_results_in_session_state(self, mock_st, mock_pattern, mock_cat, mock_diff, mock_render):
        from dashboard.utils.failure_config import run_and_display_failures
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        loader = MagicMock()
        failure_result = SimpleNamespace(
            patterns=[], top_failing_categories=[], top_failing_difficulties=[],
            total_failures=5, total_tasks=10, failure_rate=0.5,
        )
        loader.load_failures.return_value = failure_result

        mock_pattern.return_value = pd.DataFrame()
        mock_cat.return_value = pd.DataFrame()
        mock_diff.return_value = pd.DataFrame()

        config = FailureConfig(experiment_id="exp001")
        run_and_display_failures(loader, config)

        self.assertIn("failure_config_pattern_results", mock_st.session_state)
        self.assertIn("failure_config_config_snapshot", mock_st.session_state)

    @patch("dashboard.utils.failure_config._render_failure_results")
    @patch("dashboard.utils.failure_config._build_difficulty_dataframe")
    @patch("dashboard.utils.failure_config._build_category_dataframe")
    @patch("dashboard.utils.failure_config._build_pattern_dataframe")
    @patch("dashboard.utils.failure_config.st")
    def test_passes_none_agent_when_all_agents(self, mock_st, mock_pattern, mock_cat, mock_diff, mock_render):
        from dashboard.utils.failure_config import run_and_display_failures
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        mock_pattern.return_value = pd.DataFrame()
        mock_cat.return_value = pd.DataFrame()
        mock_diff.return_value = pd.DataFrame()

        loader = MagicMock()
        failure_result = SimpleNamespace(
            patterns=[], top_failing_categories=[], top_failing_difficulties=[],
            total_failures=0, total_tasks=10, failure_rate=0.0,
        )
        loader.load_failures.return_value = failure_result

        config = FailureConfig(experiment_id="exp001", include_all_agents=True)
        run_and_display_failures(loader, config)

        loader.load_failures.assert_called_once_with("exp001", agent_name=None)

    @patch("dashboard.utils.failure_config._render_failure_results")
    @patch("dashboard.utils.failure_config._build_difficulty_dataframe")
    @patch("dashboard.utils.failure_config._build_category_dataframe")
    @patch("dashboard.utils.failure_config._build_pattern_dataframe")
    @patch("dashboard.utils.failure_config.st")
    def test_passes_specific_agent(self, mock_st, mock_pattern, mock_cat, mock_diff, mock_render):
        from dashboard.utils.failure_config import run_and_display_failures
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        mock_pattern.return_value = pd.DataFrame()
        mock_cat.return_value = pd.DataFrame()
        mock_diff.return_value = pd.DataFrame()

        loader = MagicMock()
        failure_result = SimpleNamespace(
            patterns=[], top_failing_categories=[], top_failing_difficulties=[],
            total_failures=0, total_tasks=10, failure_rate=0.0,
        )
        loader.load_failures.return_value = failure_result

        config = FailureConfig(experiment_id="exp001", agent_name="agent_a", include_all_agents=False)
        run_and_display_failures(loader, config)

        loader.load_failures.assert_called_once_with("exp001", agent_name="agent_a")

    @patch("dashboard.utils.failure_config.display_error_message")
    @patch("dashboard.utils.failure_config.st")
    def test_handles_load_error(self, mock_st, mock_error):
        from dashboard.utils.failure_config import run_and_display_failures
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        loader = MagicMock()
        loader.load_failures.side_effect = Exception("DB error")

        config = FailureConfig(experiment_id="exp001")
        run_and_display_failures(loader, config)
        mock_error.assert_called_once()

    @patch("dashboard.utils.failure_config.display_no_data_message")
    @patch("dashboard.utils.failure_config.st")
    def test_handles_none_result(self, mock_st, mock_no_data):
        from dashboard.utils.failure_config import run_and_display_failures
        mock_st.session_state = {}
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock()

        loader = MagicMock()
        loader.load_failures.return_value = None

        config = FailureConfig(experiment_id="exp001")
        run_and_display_failures(loader, config)
        mock_no_data.assert_called_once()


class TestRenderFailureResults(TestCase):
    """Tests for _render_failure_results."""

    @patch("dashboard.utils.failure_config.st")
    def test_renders_summary_cards(self, mock_st):
        from dashboard.utils.failure_config import _render_failure_results

        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=None)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock, col_mock, col_mock, col_mock]

        failure_result = SimpleNamespace(
            total_failures=5, total_tasks=10, failure_rate=0.5,
        )
        pattern_df = pd.DataFrame()
        category_df = pd.DataFrame()
        difficulty_df = pd.DataFrame()
        config = FailureConfig(experiment_id="exp001")

        _render_failure_results(pattern_df, category_df, difficulty_df, failure_result, config)
        mock_st.subheader.assert_any_call("Failure Summary")

    @patch("dashboard.utils.failure_config.st")
    def test_renders_pattern_section(self, mock_st):
        from dashboard.utils.failure_config import _render_failure_results

        col_mock = MagicMock()
        col_mock.__enter__ = MagicMock(return_value=None)
        col_mock.__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value = [col_mock, col_mock, col_mock, col_mock]

        failure_result = SimpleNamespace(
            total_failures=5, total_tasks=10, failure_rate=0.5,
        )
        pattern_df = pd.DataFrame([{
            "Pattern": "P1", "Description": "d", "Frequency": 3,
            "Affected Tasks": 2, "Avg Duration (s)": 100.0,
            "Suggested Fix": "fix", "Confidence": 0.8,
        }])
        category_df = pd.DataFrame()
        difficulty_df = pd.DataFrame()
        config = FailureConfig(experiment_id="exp001")

        _render_failure_results(pattern_df, category_df, difficulty_df, failure_result, config)
        mock_st.subheader.assert_any_call("Failure Patterns")


class TestViewIntegration(TestCase):
    """Tests for view integration."""

    @patch("dashboard.views.analysis_failure.render_breadcrumb_navigation")
    @patch("dashboard.views.analysis_failure.st")
    def test_show_failure_analysis_no_loader(self, mock_st, mock_breadcrumb):
        from dashboard.views.analysis_failure import show_failure_analysis
        session = MagicMock()
        session.get.return_value = None
        session.__contains__ = MagicMock(return_value=False)
        mock_st.session_state = session
        show_failure_analysis()
        mock_st.error.assert_called_once()

    @patch("dashboard.views.analysis_failure.render_failure_config")
    @patch("dashboard.views.analysis_failure.render_breadcrumb_navigation")
    @patch("dashboard.views.analysis_failure.st")
    def test_show_failure_analysis_no_config(self, mock_st, mock_breadcrumb, mock_render_config):
        from dashboard.views.analysis_failure import show_failure_analysis
        session = MagicMock()
        session.get.side_effect = lambda k, d=None: MagicMock() if k == "analysis_loader" else d
        session.__contains__ = MagicMock(return_value=False)
        mock_st.session_state = session
        mock_render_config.return_value = None
        mock_st.sidebar.__enter__ = MagicMock(return_value=None)
        mock_st.sidebar.__exit__ = MagicMock(return_value=False)
        show_failure_analysis()
        mock_st.info.assert_called()
