"""
Tests for dashboard.utils.judge_alignment_metrics.

Covers:
- Score pair building from human/LLM dicts
- LLM score parsing
- Pearson correlation computation
- Mean absolute error computation
- Cohen's kappa computation
- Disagreement detection
- Export DataFrame building
- Composite alignment metrics computation
- Metrics panel rendering
- Extract LLM scores dict helper
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from dashboard.utils.judge_alignment_metrics import (
    AlignmentMetrics,
    ScorePair,
    _parse_llm_score,
    build_export_dataframe,
    build_score_pairs,
    compute_alignment_metrics,
    compute_cohens_kappa,
    compute_mean_absolute_error,
    compute_pearson_correlation,
    find_disagreements,
    render_alignment_metrics_panel,
)
from dashboard.utils.judge_human_alignment import (
    _extract_llm_scores_dict,
)
from dashboard.utils.judge_test_prompt import (
    DimensionResult,
    TestPromptResult,
)


class TestParseLlmScore(TestCase):
    """Tests for _parse_llm_score."""

    def test_parses_integer_string(self):
        self.assertEqual(_parse_llm_score("3"), 3.0)

    def test_parses_float_string(self):
        self.assertEqual(_parse_llm_score("4.5"), 4.5)

    def test_returns_none_for_na(self):
        self.assertIsNone(_parse_llm_score("N/A"))

    def test_returns_none_for_empty(self):
        self.assertIsNone(_parse_llm_score(""))

    def test_returns_none_for_none(self):
        self.assertIsNone(_parse_llm_score(None))

    def test_returns_none_for_text(self):
        self.assertIsNone(_parse_llm_score("good"))


class TestBuildScorePairs(TestCase):
    """Tests for build_score_pairs."""

    def test_builds_pairs_from_matching_scores(self):
        human = {"t1": {"Dim1": 4, "Dim2": 3}}
        llm = {"t1": {"Dim1": "3", "Dim2": "5"}}
        dims = ["Dim1", "Dim2"]

        pairs = build_score_pairs(human, llm, dims)

        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].task_id, "t1")
        self.assertEqual(pairs[0].dimension, "Dim1")
        self.assertEqual(pairs[0].human_score, 4)
        self.assertEqual(pairs[0].llm_score, 3.0)

    def test_skips_missing_human_scores(self):
        human = {"t1": {"Dim1": 4}}
        llm = {"t1": {"Dim1": "3", "Dim2": "5"}}
        dims = ["Dim1", "Dim2"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 1)

    def test_skips_missing_llm_scores(self):
        human = {"t1": {"Dim1": 4, "Dim2": 3}}
        llm = {"t1": {"Dim1": "3"}}
        dims = ["Dim1", "Dim2"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 1)

    def test_skips_unparseable_llm_scores(self):
        human = {"t1": {"Dim1": 4}}
        llm = {"t1": {"Dim1": "N/A"}}
        dims = ["Dim1"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 0)

    def test_skips_tasks_not_in_llm(self):
        human = {"t1": {"Dim1": 4}}
        llm = {"t2": {"Dim1": "3"}}
        dims = ["Dim1"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 0)

    def test_empty_inputs_return_empty(self):
        pairs = build_score_pairs({}, {}, ["Dim1"])
        self.assertEqual(len(pairs), 0)

    def test_multiple_tasks(self):
        human = {"t1": {"Dim1": 4}, "t2": {"Dim1": 2}}
        llm = {"t1": {"Dim1": "3"}, "t2": {"Dim1": "4"}}
        dims = ["Dim1"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 2)

    def test_filters_by_dimension_list(self):
        human = {"t1": {"Dim1": 4, "Dim2": 3, "Dim3": 5}}
        llm = {"t1": {"Dim1": "3", "Dim2": "4", "Dim3": "2"}}
        dims = ["Dim1", "Dim3"]

        pairs = build_score_pairs(human, llm, dims)
        self.assertEqual(len(pairs), 2)
        dim_names = {p.dimension for p in pairs}
        self.assertEqual(dim_names, {"Dim1", "Dim3"})

    def test_returns_frozen_dataclass(self):
        human = {"t1": {"Dim1": 4}}
        llm = {"t1": {"Dim1": "3"}}

        pairs = build_score_pairs(human, llm, ["Dim1"])
        with self.assertRaises(AttributeError):
            pairs[0].human_score = 5  # type: ignore


class TestComputePearsonCorrelation(TestCase):
    """Tests for compute_pearson_correlation."""

    def _make_pairs(self, values):
        """Create ScorePairs from (human, llm) tuples."""
        return tuple(
            ScorePair(
                task_id=f"t{i}",
                dimension="Dim1",
                human_score=h,
                llm_score=lv,
            )
            for i, (h, lv) in enumerate(values)
        )

    def test_perfect_positive_correlation(self):
        pairs = self._make_pairs([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
        result = compute_pearson_correlation(pairs)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_perfect_negative_correlation(self):
        pairs = self._make_pairs([(1, 5), (2, 4), (3, 3), (4, 2), (5, 1)])
        result = compute_pearson_correlation(pairs)
        self.assertAlmostEqual(result, -1.0, places=5)

    def test_zero_correlation_for_constant_scores(self):
        pairs = self._make_pairs([(3, 3), (3, 3), (3, 3)])
        result = compute_pearson_correlation(pairs)
        self.assertEqual(result, 0.0)

    def test_returns_zero_for_single_pair(self):
        pairs = self._make_pairs([(3, 4)])
        result = compute_pearson_correlation(pairs)
        self.assertEqual(result, 0.0)

    def test_returns_zero_for_empty(self):
        result = compute_pearson_correlation(())
        self.assertEqual(result, 0.0)

    def test_moderate_positive_correlation(self):
        pairs = self._make_pairs([(1, 2), (2, 2), (3, 4), (4, 3), (5, 5)])
        result = compute_pearson_correlation(pairs)
        self.assertGreater(result, 0.5)
        self.assertLess(result, 1.0)


class TestComputeMeanAbsoluteError(TestCase):
    """Tests for compute_mean_absolute_error."""

    def _make_pairs(self, values):
        return tuple(
            ScorePair(
                task_id=f"t{i}",
                dimension="Dim1",
                human_score=h,
                llm_score=lv,
            )
            for i, (h, lv) in enumerate(values)
        )

    def test_zero_error_for_identical_scores(self):
        pairs = self._make_pairs([(3, 3.0), (4, 4.0), (5, 5.0)])
        result = compute_mean_absolute_error(pairs)
        self.assertAlmostEqual(result, 0.0)

    def test_computes_correct_mae(self):
        pairs = self._make_pairs([(3, 1.0), (4, 5.0), (2, 4.0)])
        # |3-1| + |4-5| + |2-4| = 2 + 1 + 2 = 5, MAE = 5/3
        result = compute_mean_absolute_error(pairs)
        self.assertAlmostEqual(result, 5.0 / 3.0, places=5)

    def test_returns_zero_for_empty(self):
        result = compute_mean_absolute_error(())
        self.assertEqual(result, 0.0)

    def test_single_pair(self):
        pairs = self._make_pairs([(3, 5.0)])
        result = compute_mean_absolute_error(pairs)
        self.assertAlmostEqual(result, 2.0)


class TestComputeCohensKappa(TestCase):
    """Tests for compute_cohens_kappa."""

    def _make_pairs(self, values):
        return tuple(
            ScorePair(
                task_id=f"t{i}",
                dimension="Dim1",
                human_score=h,
                llm_score=lv,
            )
            for i, (h, lv) in enumerate(values)
        )

    def test_perfect_agreement(self):
        pairs = self._make_pairs([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
        result = compute_cohens_kappa(pairs)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_returns_zero_for_empty(self):
        result = compute_cohens_kappa(())
        self.assertEqual(result, 0.0)

    def test_returns_one_for_all_same_category(self):
        # All agree on the same score
        pairs = self._make_pairs([(3, 3), (3, 3), (3, 3)])
        result = compute_cohens_kappa(pairs)
        self.assertEqual(result, 1.0)

    def test_partial_agreement(self):
        # Some agree, some don't
        pairs = self._make_pairs([
            (1, 1), (2, 2), (3, 3),  # agree
            (4, 1), (5, 2),  # disagree
        ])
        result = compute_cohens_kappa(pairs)
        # Should be between 0 and 1
        self.assertGreater(result, 0.0)
        self.assertLess(result, 1.0)

    def test_rounds_llm_scores(self):
        # LLM score 3.4 should round to 3
        pairs = self._make_pairs([(3, 3.4), (4, 3.6)])
        # (3, 3) and (4, 4) -> perfect agreement
        result = compute_cohens_kappa(pairs)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_no_agreement(self):
        # Complete disagreement
        pairs = self._make_pairs([
            (1, 5), (2, 4), (3, 1), (4, 2), (5, 3),
        ])
        result = compute_cohens_kappa(pairs)
        # Should be negative or near zero
        self.assertLess(result, 0.5)


class TestComputeAlignmentMetrics(TestCase):
    """Tests for compute_alignment_metrics."""

    def test_computes_all_metrics(self):
        human = {
            "t1": {"Dim1": 4, "Dim2": 3},
            "t2": {"Dim1": 2, "Dim2": 5},
        }
        llm = {
            "t1": {"Dim1": "3", "Dim2": "4"},
            "t2": {"Dim1": "3", "Dim2": "4"},
        }
        dims = ["Dim1", "Dim2"]

        metrics = compute_alignment_metrics(human, llm, dims)

        self.assertIsInstance(metrics, AlignmentMetrics)
        self.assertEqual(metrics.total_pairs, 4)
        self.assertIsInstance(metrics.cohens_kappa, float)
        self.assertIsInstance(metrics.pearson_correlation, float)
        self.assertIsInstance(metrics.mean_absolute_error, float)
        self.assertEqual(len(metrics.score_pairs), 4)

    def test_empty_scores_return_zeros(self):
        metrics = compute_alignment_metrics({}, {}, ["Dim1"])

        self.assertEqual(metrics.total_pairs, 0)
        self.assertEqual(metrics.cohens_kappa, 0.0)
        self.assertEqual(metrics.pearson_correlation, 0.0)
        self.assertEqual(metrics.mean_absolute_error, 0.0)

    def test_frozen_dataclass(self):
        metrics = compute_alignment_metrics({}, {}, ["Dim1"])
        with self.assertRaises(AttributeError):
            metrics.total_pairs = 10  # type: ignore


class TestFindDisagreements(TestCase):
    """Tests for find_disagreements."""

    def _make_pairs(self, values):
        return tuple(
            ScorePair(
                task_id=f"t{i}",
                dimension="Dim1",
                human_score=h,
                llm_score=lv,
            )
            for i, (h, lv) in enumerate(values)
        )

    def test_finds_disagreements_above_threshold(self):
        pairs = self._make_pairs([(1, 1), (2, 5), (3, 3)])
        # Only (2, 5) has diff 3 > threshold 2
        result = find_disagreements(pairs, threshold=2.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].human_score, 2)

    def test_empty_when_all_agree(self):
        pairs = self._make_pairs([(3, 3), (4, 4), (5, 5)])
        result = find_disagreements(pairs, threshold=2.0)
        self.assertEqual(len(result), 0)

    def test_threshold_is_exclusive(self):
        # Exactly at threshold (diff = 2.0) should NOT be flagged
        pairs = self._make_pairs([(1, 3)])
        result = find_disagreements(pairs, threshold=2.0)
        self.assertEqual(len(result), 0)

    def test_threshold_just_above(self):
        # Diff = 2.1 > threshold 2.0 should be flagged
        pairs = (
            ScorePair(task_id="t0", dimension="Dim1", human_score=1, llm_score=3.1),
        )
        result = find_disagreements(pairs, threshold=2.0)
        self.assertEqual(len(result), 1)

    def test_empty_input(self):
        result = find_disagreements((), threshold=2.0)
        self.assertEqual(len(result), 0)

    def test_custom_threshold(self):
        pairs = self._make_pairs([(1, 2), (3, 5)])
        # With threshold=0.5: both disagree (diffs: 1, 2)
        result = find_disagreements(pairs, threshold=0.5)
        self.assertEqual(len(result), 2)

    def test_default_threshold_is_2(self):
        pairs = self._make_pairs([(1, 4)])  # diff = 3 > 2
        result = find_disagreements(pairs)
        self.assertEqual(len(result), 1)


class TestBuildExportDataframe(TestCase):
    """Tests for build_export_dataframe."""

    def test_builds_correct_columns(self):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=3.0),
        )
        df = build_export_dataframe(pairs)

        expected_cols = {
            "Task ID", "Dimension", "Human Score",
            "LLM Score", "Absolute Difference",
        }
        self.assertEqual(set(df.columns), expected_cols)

    def test_computes_absolute_difference(self):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=1.0),
        )
        df = build_export_dataframe(pairs)
        self.assertEqual(df.iloc[0]["Absolute Difference"], 3.0)

    def test_empty_pairs_return_empty_df(self):
        df = build_export_dataframe(())
        self.assertEqual(len(df), 0)
        self.assertIn("Task ID", df.columns)

    def test_multiple_pairs(self):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=3.0),
            ScorePair(task_id="t2", dimension="Dim2", human_score=2, llm_score=5.0),
        )
        df = build_export_dataframe(pairs)
        self.assertEqual(len(df), 2)

    def test_data_values_match(self):
        pairs = (
            ScorePair(task_id="t1", dimension="Quality", human_score=5, llm_score=4.0),
        )
        df = build_export_dataframe(pairs)
        row = df.iloc[0]
        self.assertEqual(row["Task ID"], "t1")
        self.assertEqual(row["Dimension"], "Quality")
        self.assertEqual(row["Human Score"], 5)
        self.assertEqual(row["LLM Score"], 4.0)
        self.assertEqual(row["Absolute Difference"], 1.0)


class TestRenderAlignmentMetricsPanel(TestCase):
    """Tests for render_alignment_metrics_panel."""

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_shows_info_when_no_pairs(self, mock_st):
        metrics = AlignmentMetrics(
            cohens_kappa=0.0,
            pearson_correlation=0.0,
            mean_absolute_error=0.0,
            score_pairs=(),
            total_pairs=0,
        )
        render_alignment_metrics_panel(metrics)
        mock_st.info.assert_called()

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_renders_metric_cards(self, mock_st):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=3.0),
            ScorePair(task_id="t2", dimension="Dim1", human_score=3, llm_score=3.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=0.5,
            pearson_correlation=0.8,
            mean_absolute_error=0.5,
            score_pairs=pairs,
            total_pairs=2,
        )

        mock_st.columns.return_value = (
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        mock_st.slider.return_value = 2.0

        render_alignment_metrics_panel(metrics)

        # Should call st.metric at least 4 times for the metric cards
        self.assertGreaterEqual(mock_st.metric.call_count, 4)

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_renders_export_button(self, mock_st):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=3.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=0.5,
            pearson_correlation=0.8,
            mean_absolute_error=0.5,
            score_pairs=pairs,
            total_pairs=1,
        )

        mock_st.columns.return_value = (
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        mock_st.slider.return_value = 2.0

        render_alignment_metrics_panel(metrics)

        mock_st.download_button.assert_called_once()
        # Verify it's a CSV download
        call_kwargs = mock_st.download_button.call_args
        self.assertEqual(call_kwargs[1].get("mime") or call_kwargs.kwargs.get("mime"), "text/csv")

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_renders_slider_for_threshold(self, mock_st):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=4, llm_score=3.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=0.5,
            pearson_correlation=0.8,
            mean_absolute_error=0.5,
            score_pairs=pairs,
            total_pairs=1,
        )

        mock_st.columns.return_value = (
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        mock_st.slider.return_value = 2.0

        render_alignment_metrics_panel(metrics)

        mock_st.slider.assert_called_once()

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_shows_warning_for_disagreements(self, mock_st):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=1, llm_score=5.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=-0.5,
            pearson_correlation=-0.5,
            mean_absolute_error=4.0,
            score_pairs=pairs,
            total_pairs=1,
        )

        mock_st.columns.return_value = (
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        mock_st.slider.return_value = 2.0

        render_alignment_metrics_panel(metrics)

        mock_st.warning.assert_called()

    @patch("dashboard.utils.judge_alignment_metrics.st")
    def test_shows_success_when_all_agree(self, mock_st):
        pairs = (
            ScorePair(task_id="t1", dimension="Dim1", human_score=3, llm_score=3.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=1.0,
            pearson_correlation=1.0,
            mean_absolute_error=0.0,
            score_pairs=pairs,
            total_pairs=1,
        )

        mock_st.columns.return_value = (
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        mock_st.slider.return_value = 2.0

        render_alignment_metrics_panel(metrics)

        mock_st.success.assert_called()


class TestExtractLlmScoresDict(TestCase):
    """Tests for _extract_llm_scores_dict in judge_human_alignment."""

    def _make_result(self, task_id, dim_scores):
        dim_results = tuple(
            DimensionResult(name=name, score=score, reasoning="")
            for name, score in dim_scores
        )
        return TestPromptResult(
            task_id=task_id,
            dimension_results=dim_results,
            overall_score="3",
            overall_reasoning="",
        )

    def test_extracts_scores_for_dimensions(self):
        llm_results = {
            "t1": self._make_result("t1", [("Dim1", "4"), ("Dim2", "3")]),
        }
        dims = ["Dim1", "Dim2"]

        result = _extract_llm_scores_dict(llm_results, dims)

        self.assertEqual(result["t1"]["Dim1"], "4")
        self.assertEqual(result["t1"]["Dim2"], "3")

    def test_filters_by_dimension_list(self):
        llm_results = {
            "t1": self._make_result("t1", [("Dim1", "4"), ("Dim2", "3"), ("Dim3", "5")]),
        }
        dims = ["Dim1", "Dim3"]

        result = _extract_llm_scores_dict(llm_results, dims)

        self.assertIn("Dim1", result["t1"])
        self.assertIn("Dim3", result["t1"])
        self.assertNotIn("Dim2", result["t1"])

    def test_empty_results_return_empty(self):
        result = _extract_llm_scores_dict({}, ["Dim1"])
        self.assertEqual(result, {})

    def test_handles_no_dimension_results(self):
        llm_results = {
            "t1": TestPromptResult(
                task_id="t1",
                dimension_results=(),
                overall_score="3",
                overall_reasoning="",
            ),
        }
        result = _extract_llm_scores_dict(llm_results, ["Dim1"])
        self.assertEqual(result["t1"], {})

    def test_multiple_tasks(self):
        llm_results = {
            "t1": self._make_result("t1", [("Dim1", "4")]),
            "t2": self._make_result("t2", [("Dim1", "2")]),
        }
        result = _extract_llm_scores_dict(llm_results, ["Dim1"])

        self.assertEqual(result["t1"]["Dim1"], "4")
        self.assertEqual(result["t2"]["Dim1"], "2")


class TestScorePairDataclass(TestCase):
    """Tests for the ScorePair frozen dataclass."""

    def test_is_frozen(self):
        pair = ScorePair(
            task_id="t1",
            dimension="Dim1",
            human_score=4,
            llm_score=3.0,
        )
        with self.assertRaises(AttributeError):
            pair.human_score = 5  # type: ignore

    def test_equality(self):
        pair1 = ScorePair("t1", "Dim1", 4, 3.0)
        pair2 = ScorePair("t1", "Dim1", 4, 3.0)
        self.assertEqual(pair1, pair2)


class TestAlignmentMetricsDataclass(TestCase):
    """Tests for the AlignmentMetrics frozen dataclass."""

    def test_is_frozen(self):
        metrics = AlignmentMetrics(
            cohens_kappa=0.5,
            pearson_correlation=0.8,
            mean_absolute_error=0.5,
            score_pairs=(),
            total_pairs=0,
        )
        with self.assertRaises(AttributeError):
            metrics.total_pairs = 10  # type: ignore

    def test_stores_all_fields(self):
        pairs = (
            ScorePair("t1", "Dim1", 4, 3.0),
        )
        metrics = AlignmentMetrics(
            cohens_kappa=0.5,
            pearson_correlation=0.8,
            mean_absolute_error=0.5,
            score_pairs=pairs,
            total_pairs=1,
        )
        self.assertEqual(metrics.cohens_kappa, 0.5)
        self.assertEqual(metrics.pearson_correlation, 0.8)
        self.assertEqual(metrics.mean_absolute_error, 0.5)
        self.assertEqual(metrics.total_pairs, 1)
        self.assertEqual(len(metrics.score_pairs), 1)


class TestCohensKappaEdgeCases(TestCase):
    """Edge case tests for Cohen's kappa."""

    def _make_pairs(self, values):
        return tuple(
            ScorePair(
                task_id=f"t{i}",
                dimension="Dim1",
                human_score=h,
                llm_score=float(lv),
            )
            for i, (h, lv) in enumerate(values)
        )

    def test_two_categories_perfect_agreement(self):
        pairs = self._make_pairs([(1, 1), (2, 2), (1, 1), (2, 2)])
        result = compute_cohens_kappa(pairs)
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_two_categories_no_better_than_chance(self):
        # When agreement is exactly at chance level
        # 50/50 split in both raters, all off-diagonal
        pairs = self._make_pairs([(1, 2), (2, 1), (1, 2), (2, 1)])
        result = compute_cohens_kappa(pairs)
        self.assertLessEqual(result, 0.0)

    def test_fractional_llm_scores_rounded(self):
        # 3.2 rounds to 3, 4.7 rounds to 5
        pairs = self._make_pairs([(3, 3.2), (5, 4.7)])
        result = compute_cohens_kappa(pairs)
        self.assertAlmostEqual(result, 1.0, places=5)


class TestIntegrationMetricsWithHumanAlignment(TestCase):
    """Integration tests verifying metrics work with human alignment data."""

    def test_end_to_end_metrics_computation(self):
        """Test full flow from score dicts to metrics."""
        human = {
            "t1": {"Correctness": 4, "Quality": 3},
            "t2": {"Correctness": 2, "Quality": 5},
            "t3": {"Correctness": 5, "Quality": 4},
        }
        llm = {
            "t1": {"Correctness": "4", "Quality": "4"},
            "t2": {"Correctness": "3", "Quality": "4"},
            "t3": {"Correctness": "5", "Quality": "3"},
        }
        dims = ["Correctness", "Quality"]

        metrics = compute_alignment_metrics(human, llm, dims)

        self.assertEqual(metrics.total_pairs, 6)
        self.assertGreater(metrics.pearson_correlation, -1.0)
        self.assertLess(metrics.pearson_correlation, 1.0)
        self.assertGreater(metrics.mean_absolute_error, 0.0)
        self.assertIsInstance(metrics.cohens_kappa, float)

    def test_disagreements_from_metrics(self):
        """Test finding disagreements from computed metrics."""
        human = {
            "t1": {"Dim1": 1},
            "t2": {"Dim1": 5},
        }
        llm = {
            "t1": {"Dim1": "5"},  # big disagreement
            "t2": {"Dim1": "5"},  # perfect agreement
        }

        metrics = compute_alignment_metrics(human, llm, ["Dim1"])
        disagreements = find_disagreements(metrics.score_pairs, threshold=2.0)

        self.assertEqual(len(disagreements), 1)
        self.assertEqual(disagreements[0].task_id, "t1")

    def test_export_from_metrics(self):
        """Test building export DataFrame from metrics."""
        human = {"t1": {"Dim1": 4}}
        llm = {"t1": {"Dim1": "3"}}

        metrics = compute_alignment_metrics(human, llm, ["Dim1"])
        df = build_export_dataframe(metrics.score_pairs)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Task ID"], "t1")
        self.assertEqual(df.iloc[0]["Human Score"], 4)
        self.assertEqual(df.iloc[0]["LLM Score"], 3.0)
        self.assertEqual(df.iloc[0]["Absolute Difference"], 1.0)
