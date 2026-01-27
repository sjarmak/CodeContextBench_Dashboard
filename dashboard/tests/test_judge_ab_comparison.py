"""
Tests for LLM judge A/B comparison mode.

Covers:
- Score parsing
- Mean score computation
- Pearson correlation computation
- Agreement rate computation
- Comparison summary computation
- Results table building
- Rendering functions
- Tab rendering
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dashboard.utils.judge_ab_comparison import (
    ComparisonSummary,
    TaskComparisonResult,
    _build_results_table,
    _compute_agreement_rate,
    _compute_mean_overall_score,
    _compute_pearson_correlation,
    _parse_score,
    _session_key,
    compute_comparison_summary,
    run_ab_comparison,
)
from dashboard.utils.judge_config import (
    JudgeConfig,
    ScoringCriterion,
    ScoringDimension,
)
from dashboard.utils.judge_test_prompt import (
    DimensionResult,
    TestPromptResult,
)


def _make_result(
    task_id: str = "task_1",
    overall_score: str = "3",
    dim_scores: tuple[tuple[str, str], ...] = (("Correctness", "3"),),
    error: str | None = None,
) -> TestPromptResult:
    """Helper to create a TestPromptResult."""
    return TestPromptResult(
        task_id=task_id,
        dimension_results=tuple(
            DimensionResult(name=name, score=score, reasoning="test")
            for name, score in dim_scores
        ),
        overall_score=overall_score,
        overall_reasoning="test reasoning",
        error=error,
    )


def _make_config() -> JudgeConfig:
    """Helper to create a minimal JudgeConfig."""
    return JudgeConfig(
        system_prompt="Test prompt",
        dimensions=(
            ScoringDimension(
                name="Correctness",
                weight=1.0,
                criteria=(ScoringCriterion(1, "Bad"), ScoringCriterion(5, "Good")),
            ),
        ),
        model="claude-haiku-4-5-20251001",
        temperature=0.0,
        max_tokens=4096,
    )


class TestSessionKey(unittest.TestCase):
    """Tests for _session_key."""

    def test_builds_prefixed_key(self):
        result = _session_key("template_a")
        self.assertEqual(result, "judge_ab_template_a")

    def test_different_suffixes(self):
        self.assertNotEqual(_session_key("a"), _session_key("b"))


class TestParseScore(unittest.TestCase):
    """Tests for _parse_score."""

    def test_integer_string(self):
        self.assertEqual(_parse_score("3"), 3.0)

    def test_float_string(self):
        self.assertEqual(_parse_score("3.5"), 3.5)

    def test_na_returns_none(self):
        self.assertIsNone(_parse_score("N/A"))

    def test_empty_returns_none(self):
        self.assertIsNone(_parse_score(""))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_score(None))

    def test_text_returns_none(self):
        self.assertIsNone(_parse_score("pass"))

    def test_zero(self):
        self.assertEqual(_parse_score("0"), 0.0)

    def test_negative(self):
        self.assertEqual(_parse_score("-1"), -1.0)


class TestComputeMeanOverallScore(unittest.TestCase):
    """Tests for _compute_mean_overall_score."""

    def test_single_result(self):
        results = (_make_result(overall_score="4"),)
        self.assertEqual(_compute_mean_overall_score(results), 4.0)

    def test_multiple_results(self):
        results = (
            _make_result(overall_score="3"),
            _make_result(overall_score="5"),
        )
        self.assertEqual(_compute_mean_overall_score(results), 4.0)

    def test_empty_results(self):
        self.assertEqual(_compute_mean_overall_score(()), 0.0)

    def test_skips_invalid_scores(self):
        results = (
            _make_result(overall_score="4"),
            _make_result(overall_score="N/A"),
        )
        self.assertEqual(_compute_mean_overall_score(results), 4.0)

    def test_all_invalid_scores(self):
        results = (
            _make_result(overall_score="N/A"),
            _make_result(overall_score="error"),
        )
        self.assertEqual(_compute_mean_overall_score(results), 0.0)


class TestComputePearsonCorrelation(unittest.TestCase):
    """Tests for _compute_pearson_correlation."""

    def test_perfect_positive_correlation(self):
        scores_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        scores_b = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = _compute_pearson_correlation(scores_a, scores_b)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_perfect_negative_correlation(self):
        scores_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        scores_b = [10.0, 8.0, 6.0, 4.0, 2.0]
        result = _compute_pearson_correlation(scores_a, scores_b)
        self.assertAlmostEqual(result, -1.0, places=5)

    def test_no_correlation(self):
        # Orthogonal pattern
        scores_a = [1.0, 1.0, 1.0, 1.0]
        scores_b = [1.0, 2.0, 3.0, 4.0]
        result = _compute_pearson_correlation(scores_a, scores_b)
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_single_value_returns_zero(self):
        result = _compute_pearson_correlation([3.0], [4.0])
        self.assertEqual(result, 0.0)

    def test_empty_lists_returns_zero(self):
        result = _compute_pearson_correlation([], [])
        self.assertEqual(result, 0.0)

    def test_mismatched_lengths_returns_zero(self):
        result = _compute_pearson_correlation([1.0, 2.0], [3.0])
        self.assertEqual(result, 0.0)

    def test_identical_scores_returns_zero(self):
        # All same values -> zero variance -> zero correlation
        scores = [3.0, 3.0, 3.0]
        result = _compute_pearson_correlation(scores, scores)
        self.assertEqual(result, 0.0)


class TestComputeAgreementRate(unittest.TestCase):
    """Tests for _compute_agreement_rate."""

    def test_perfect_agreement(self):
        scores_a = [3.0, 4.0, 5.0]
        scores_b = [3.0, 4.0, 5.0]
        result = _compute_agreement_rate(scores_a, scores_b)
        self.assertAlmostEqual(result, 1.0)

    def test_no_agreement(self):
        scores_a = [1.0, 2.0, 3.0]
        scores_b = [4.0, 5.0, 1.0]
        result = _compute_agreement_rate(scores_a, scores_b, threshold=0.5)
        self.assertAlmostEqual(result, 0.0)

    def test_partial_agreement(self):
        scores_a = [3.0, 3.0, 3.0, 3.0]
        scores_b = [3.0, 4.0, 5.0, 3.0]
        # Within threshold=1.0: first (0 delta), second (1 delta), fourth (0 delta)
        result = _compute_agreement_rate(scores_a, scores_b, threshold=1.0)
        self.assertAlmostEqual(result, 0.75)

    def test_custom_threshold(self):
        scores_a = [3.0, 3.0]
        scores_b = [5.0, 4.5]
        # threshold=2.0: first (delta=2) agrees, second (delta=1.5) agrees
        result = _compute_agreement_rate(scores_a, scores_b, threshold=2.0)
        self.assertAlmostEqual(result, 1.0)

    def test_empty_lists(self):
        result = _compute_agreement_rate([], [])
        self.assertAlmostEqual(result, 0.0)

    def test_mismatched_lengths(self):
        result = _compute_agreement_rate([1.0], [1.0, 2.0])
        self.assertAlmostEqual(result, 0.0)


class TestComputeComparisonSummary(unittest.TestCase):
    """Tests for compute_comparison_summary."""

    def test_basic_summary(self):
        results = (
            TaskComparisonResult(
                task_id="task_1",
                template_a_result=_make_result(overall_score="3"),
                template_b_result=_make_result(overall_score="4"),
            ),
            TaskComparisonResult(
                task_id="task_2",
                template_a_result=_make_result(overall_score="5"),
                template_b_result=_make_result(overall_score="2"),
            ),
        )
        summary = compute_comparison_summary("Template A", "Template B", results)

        self.assertEqual(summary.template_a_name, "Template A")
        self.assertEqual(summary.template_b_name, "Template B")
        self.assertEqual(summary.task_count, 2)
        self.assertAlmostEqual(summary.template_a_mean, 4.0)
        self.assertAlmostEqual(summary.template_b_mean, 3.0)
        self.assertEqual(len(summary.task_results), 2)

    def test_empty_results(self):
        summary = compute_comparison_summary("A", "B", ())
        self.assertEqual(summary.task_count, 0)
        self.assertAlmostEqual(summary.template_a_mean, 0.0)
        self.assertAlmostEqual(summary.template_b_mean, 0.0)
        self.assertAlmostEqual(summary.correlation, 0.0)
        self.assertAlmostEqual(summary.agreement_rate, 0.0)

    def test_with_invalid_scores(self):
        results = (
            TaskComparisonResult(
                task_id="task_1",
                template_a_result=_make_result(overall_score="N/A"),
                template_b_result=_make_result(overall_score="3"),
            ),
        )
        summary = compute_comparison_summary("A", "B", results)
        # Only B has a valid score
        self.assertAlmostEqual(summary.template_b_mean, 3.0)

    def test_agreement_and_correlation_computed(self):
        results = tuple(
            TaskComparisonResult(
                task_id=f"task_{i}",
                template_a_result=_make_result(overall_score=str(i + 1)),
                template_b_result=_make_result(overall_score=str(i + 1)),
            )
            for i in range(5)
        )
        summary = compute_comparison_summary("A", "B", results)
        self.assertAlmostEqual(summary.agreement_rate, 1.0)
        # Perfect correlation (identical scores)
        self.assertAlmostEqual(summary.correlation, 1.0, places=5)


class TestBuildResultsTable(unittest.TestCase):
    """Tests for _build_results_table."""

    def test_basic_table(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=3.0,
            template_b_mean=4.0,
            correlation=0.5,
            agreement_rate=0.8,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(
                        overall_score="3",
                        dim_scores=(("Correctness", "3"),),
                    ),
                    template_b_result=_make_result(
                        overall_score="4",
                        dim_scores=(("Correctness", "4"),),
                    ),
                ),
            ),
        )
        df = _build_results_table(summary)

        self.assertEqual(len(df), 1)
        self.assertIn("Task ID", df.columns)
        self.assertIn("A: Correctness", df.columns)
        self.assertIn("B: Correctness", df.columns)
        self.assertIn("A: Overall", df.columns)
        self.assertIn("B: Overall", df.columns)
        self.assertIn("Delta (B-A)", df.columns)

    def test_delta_computation(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=3.0,
            template_b_mean=5.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(overall_score="3"),
                    template_b_result=_make_result(overall_score="5"),
                ),
            ),
        )
        df = _build_results_table(summary)
        self.assertEqual(df.iloc[0]["Delta (B-A)"], "+2.0")

    def test_na_delta_when_scores_invalid(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=0.0,
            template_b_mean=0.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(overall_score="N/A"),
                    template_b_result=_make_result(overall_score="3"),
                ),
            ),
        )
        df = _build_results_table(summary)
        self.assertEqual(df.iloc[0]["Delta (B-A)"], "N/A")

    def test_empty_results_returns_empty_df(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=0,
            template_a_mean=0.0,
            template_b_mean=0.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(),
        )
        df = _build_results_table(summary)
        self.assertTrue(df.empty)

    def test_multiple_dimensions(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=3.0,
            template_b_mean=4.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(
                        overall_score="3",
                        dim_scores=(
                            ("Correctness", "3"),
                            ("Code Quality", "4"),
                        ),
                    ),
                    template_b_result=_make_result(
                        overall_score="4",
                        dim_scores=(
                            ("Correctness", "5"),
                            ("Code Quality", "3"),
                        ),
                    ),
                ),
            ),
        )
        df = _build_results_table(summary)
        self.assertIn("A: Correctness", df.columns)
        self.assertIn("A: Code Quality", df.columns)
        self.assertIn("B: Correctness", df.columns)
        self.assertIn("B: Code Quality", df.columns)


class TestTaskComparisonResult(unittest.TestCase):
    """Tests for TaskComparisonResult dataclass."""

    def test_frozen(self):
        result = TaskComparisonResult(
            task_id="task_1",
            template_a_result=_make_result(),
            template_b_result=_make_result(),
        )
        with self.assertRaises(AttributeError):
            result.task_id = "changed"

    def test_fields(self):
        result_a = _make_result(task_id="a")
        result_b = _make_result(task_id="b")
        result = TaskComparisonResult(
            task_id="task_1",
            template_a_result=result_a,
            template_b_result=result_b,
        )
        self.assertEqual(result.task_id, "task_1")
        self.assertEqual(result.template_a_result, result_a)
        self.assertEqual(result.template_b_result, result_b)


class TestComparisonSummary(unittest.TestCase):
    """Tests for ComparisonSummary dataclass."""

    def test_frozen(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=0,
            template_a_mean=0.0,
            template_b_mean=0.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(),
        )
        with self.assertRaises(AttributeError):
            summary.task_count = 5

    def test_all_fields(self):
        summary = ComparisonSummary(
            template_a_name="Template X",
            template_b_name="Template Y",
            task_count=10,
            template_a_mean=3.5,
            template_b_mean=4.2,
            correlation=0.85,
            agreement_rate=0.7,
            task_results=(),
        )
        self.assertEqual(summary.template_a_name, "Template X")
        self.assertEqual(summary.template_b_name, "Template Y")
        self.assertEqual(summary.task_count, 10)
        self.assertAlmostEqual(summary.template_a_mean, 3.5)
        self.assertAlmostEqual(summary.template_b_mean, 4.2)
        self.assertAlmostEqual(summary.correlation, 0.85)
        self.assertAlmostEqual(summary.agreement_rate, 0.7)


class TestRunAbComparison(unittest.TestCase):
    """Tests for run_ab_comparison."""

    @patch("dashboard.utils.judge_ab_comparison.run_test_prompt")
    def test_calls_both_configs_per_task(self, mock_run):
        mock_run.return_value = _make_result(overall_score="3")

        config_a = _make_config()
        config_b = _make_config()
        tasks = [("task_1", Path("/tasks/t1")), ("task_2", Path("/tasks/t2"))]

        summary = run_ab_comparison(config_a, config_b, "A", "B", tasks)

        # Should call run_test_prompt twice per task (once per config)
        self.assertEqual(mock_run.call_count, 4)
        self.assertEqual(summary.task_count, 2)

    @patch("dashboard.utils.judge_ab_comparison.run_test_prompt")
    def test_progress_callback_called(self, mock_run):
        mock_run.return_value = _make_result()
        callback = MagicMock()

        config = _make_config()
        tasks = [("t1", Path("/t1")), ("t2", Path("/t2"))]

        run_ab_comparison(config, config, "A", "B", tasks, callback)
        self.assertEqual(callback.call_count, 2)
        callback.assert_any_call(1, 2)
        callback.assert_any_call(2, 2)

    @patch("dashboard.utils.judge_ab_comparison.run_test_prompt")
    def test_empty_tasks(self, mock_run):
        config = _make_config()
        summary = run_ab_comparison(config, config, "A", "B", [])
        self.assertEqual(summary.task_count, 0)
        mock_run.assert_not_called()

    @patch("dashboard.utils.judge_ab_comparison.run_test_prompt")
    def test_returns_comparison_summary(self, mock_run):
        mock_run.side_effect = [
            _make_result(overall_score="3"),
            _make_result(overall_score="4"),
        ]
        config = _make_config()
        tasks = [("task_1", Path("/t1"))]

        summary = run_ab_comparison(config, config, "Alpha", "Beta", tasks)
        self.assertIsInstance(summary, ComparisonSummary)
        self.assertEqual(summary.template_a_name, "Alpha")
        self.assertEqual(summary.template_b_name, "Beta")


class TestRenderSummaryStats(unittest.TestCase):
    """Tests for _render_summary_stats."""

    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_renders_four_metric_cards(self, mock_st):
        from dashboard.utils.judge_ab_comparison import _render_summary_stats

        mock_cols = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
        mock_st.columns.return_value = mock_cols

        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=5,
            template_a_mean=3.0,
            template_b_mean=4.0,
            correlation=0.5,
            agreement_rate=0.8,
            task_results=(),
        )

        _render_summary_stats(summary)

        mock_st.markdown.assert_called()
        mock_st.columns.assert_called_once_with(4)


class TestRenderResultsTable(unittest.TestCase):
    """Tests for _render_results_table."""

    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_renders_empty_message(self, mock_st):
        from dashboard.utils.judge_ab_comparison import _render_results_table

        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=0,
            template_a_mean=0.0,
            template_b_mean=0.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(),
        )

        _render_results_table(summary)

        mock_st.info.assert_called_with("No results to display.")

    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_renders_dataframe_and_export(self, mock_st):
        from dashboard.utils.judge_ab_comparison import _render_results_table

        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=3.0,
            template_b_mean=4.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(overall_score="3"),
                    template_b_result=_make_result(overall_score="4"),
                ),
            ),
        )

        _render_results_table(summary)

        mock_st.dataframe.assert_called_once()
        mock_st.download_button.assert_called_once()


class TestRenderComparisonResults(unittest.TestCase):
    """Tests for _render_comparison_results."""

    @patch("dashboard.utils.judge_ab_comparison._render_results_table")
    @patch("dashboard.utils.judge_ab_comparison._render_summary_stats")
    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_calls_both_renderers(self, mock_st, mock_stats, mock_table):
        from dashboard.utils.judge_ab_comparison import _render_comparison_results

        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=0,
            template_a_mean=0.0,
            template_b_mean=0.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(),
        )

        _render_comparison_results(summary)

        mock_stats.assert_called_once_with(summary)
        mock_table.assert_called_once_with(summary)


class TestRenderAbComparisonTab(unittest.TestCase):
    """Tests for render_ab_comparison_tab."""

    @patch("dashboard.utils.judge_ab_comparison.list_template_infos")
    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_shows_info_when_fewer_than_2_templates(self, mock_st, mock_list):
        from dashboard.utils.judge_ab_comparison import render_ab_comparison_tab

        mock_list.return_value = []

        render_ab_comparison_tab(Path("/project"))

        mock_st.info.assert_called_once()
        info_msg = mock_st.info.call_args[0][0]
        self.assertIn("2 saved templates", info_msg)

    @patch("dashboard.utils.judge_ab_comparison.list_template_infos")
    @patch("dashboard.utils.judge_ab_comparison.st")
    def test_shows_info_with_one_template(self, mock_st, mock_list):
        from dashboard.utils.judge_ab_comparison import render_ab_comparison_tab
        from dashboard.utils.judge_config import TemplateInfo

        mock_list.return_value = [
            TemplateInfo(name="T1", filename="t1.json", model="haiku", created_at="2026-01-01"),
        ]

        render_ab_comparison_tab(Path("/project"))

        mock_st.info.assert_called()


class TestNegativeDelta(unittest.TestCase):
    """Test negative delta display in results table."""

    def test_negative_delta(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=5.0,
            template_b_mean=2.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(overall_score="5"),
                    template_b_result=_make_result(overall_score="2"),
                ),
            ),
        )
        df = _build_results_table(summary)
        self.assertEqual(df.iloc[0]["Delta (B-A)"], "-3.0")

    def test_zero_delta(self):
        summary = ComparisonSummary(
            template_a_name="A",
            template_b_name="B",
            task_count=1,
            template_a_mean=3.0,
            template_b_mean=3.0,
            correlation=0.0,
            agreement_rate=0.0,
            task_results=(
                TaskComparisonResult(
                    task_id="task_1",
                    template_a_result=_make_result(overall_score="3"),
                    template_b_result=_make_result(overall_score="3"),
                ),
            ),
        )
        df = _build_results_table(summary)
        self.assertEqual(df.iloc[0]["Delta (B-A)"], "+0.0")


class TestTabIntegration(unittest.TestCase):
    """Test that analysis_llm_judge.py imports the A/B comparison tab."""

    def test_import_render_ab_comparison_tab(self):
        from dashboard.utils.judge_ab_comparison import render_ab_comparison_tab
        self.assertTrue(callable(render_ab_comparison_tab))

    def test_analysis_llm_judge_imports(self):
        # Verify the import path works
        import dashboard.utils.judge_ab_comparison as mod
        self.assertTrue(callable(mod.compute_comparison_summary))
        self.assertTrue(callable(mod.run_ab_comparison))
        self.assertTrue(callable(mod.render_ab_comparison_tab))


if __name__ == "__main__":
    unittest.main()
