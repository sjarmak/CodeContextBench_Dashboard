"""Tests for the LLM Judge Viewer dashboard view."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


def _sample_categories() -> list[dict]:
    """Build a minimal experiment_metrics.json structure with judge scores."""
    return [
        {
            "run_category": "official",
            "experiments": [
                {
                    "experiment_id": "exp-001",
                    "trials": [
                        {
                            "trial_id": "trial-001",
                            "task_name": "task-alpha",
                            "benchmark": "locobench",
                            "agent_config": "BASELINE",
                            "reward": 0.5,
                            "pass_fail": "partial",
                            "duration_seconds": 120.0,
                            "input_tokens": 50000,
                            "output_tokens": 5000,
                            "judge_scores": {
                                "mean_score": 0.75,
                                "overall_quality": "pass",
                                "dimensions": [
                                    {
                                        "dimension": "correctness",
                                        "score": 1.0,
                                        "score_label": "pass",
                                        "reasoning": "Correct solution",
                                        "vote_distribution": [("1.0", 3)],
                                        "confidence": 1.0,
                                        "num_rounds": 3,
                                    },
                                    {
                                        "dimension": "completeness",
                                        "score": 0.5,
                                        "score_label": "partial",
                                        "reasoning": "Partially complete",
                                        "vote_distribution": [("0.5", 2), ("1.0", 1)],
                                        "confidence": 0.67,
                                        "num_rounds": 3,
                                    },
                                ],
                                "error": None,
                            },
                        },
                        {
                            "trial_id": "trial-002",
                            "task_name": "task-alpha",
                            "benchmark": "locobench",
                            "agent_config": "MCP_FULL",
                            "reward": 0.8,
                            "pass_fail": "pass",
                            "duration_seconds": 150.0,
                            "input_tokens": 80000,
                            "output_tokens": 8000,
                            "judge_scores": {
                                "mean_score": 0.9,
                                "overall_quality": "pass",
                                "dimensions": [
                                    {
                                        "dimension": "correctness",
                                        "score": 1.0,
                                        "score_label": "pass",
                                        "reasoning": "Fully correct",
                                        "vote_distribution": [("1.0", 3)],
                                        "confidence": 1.0,
                                        "num_rounds": 3,
                                    },
                                    {
                                        "dimension": "completeness",
                                        "score": 0.8,
                                        "score_label": "pass",
                                        "reasoning": "Nearly complete",
                                        "vote_distribution": [("1.0", 2), ("0.5", 1)],
                                        "confidence": 0.67,
                                        "num_rounds": 3,
                                    },
                                ],
                                "error": None,
                            },
                        },
                        {
                            "trial_id": "trial-003",
                            "task_name": "task-beta",
                            "benchmark": "swe-bench",
                            "agent_config": "BASELINE",
                            "reward": 0.0,
                            "pass_fail": "fail",
                            "duration_seconds": 60.0,
                            "input_tokens": 20000,
                            "output_tokens": 2000,
                        },
                    ],
                },
            ],
        },
    ]


def _sample_categories_no_judge() -> list[dict]:
    """Categories with no judge scores."""
    return [
        {
            "run_category": "experiment",
            "experiments": [
                {
                    "experiment_id": "exp-002",
                    "trials": [
                        {
                            "trial_id": "trial-010",
                            "task_name": "task-gamma",
                            "benchmark": "locobench",
                            "agent_config": "BASELINE",
                            "reward": 0.3,
                        },
                    ],
                },
            ],
        },
    ]


def _sample_categories_with_error() -> list[dict]:
    """Categories with judge scores containing an error."""
    return [
        {
            "run_category": "official",
            "experiments": [
                {
                    "experiment_id": "exp-003",
                    "trials": [
                        {
                            "trial_id": "trial-020",
                            "task_name": "task-delta",
                            "benchmark": "locobench",
                            "agent_config": "BASELINE",
                            "reward": 0.0,
                            "judge_scores": {
                                "mean_score": 0.0,
                                "overall_quality": "fail",
                                "dimensions": [],
                                "error": "No solution text found for trial",
                            },
                        },
                    ],
                },
            ],
        },
    ]


def _write_experiment_metrics(tmp_path: Path, categories: list[dict]) -> Path:
    """Write experiment_metrics.json and return the output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    metrics_path = output_dir / "experiment_metrics.json"
    metrics_path.write_text(json.dumps(categories), encoding="utf-8")
    return output_dir


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestExtractJudgeData:
    """Test _extract_judge_data helper."""

    def test_none_when_no_scores(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        assert _extract_judge_data({}) is None
        assert _extract_judge_data({"judge_scores": None}) is None

    def test_numeric_score(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        result = _extract_judge_data({"judge_scores": 0.8})
        assert result is not None
        assert result["mean_score"] == 0.8
        assert result["overall_quality"] == "pass"

    def test_numeric_score_partial(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        result = _extract_judge_data({"judge_scores": 0.5})
        assert result is not None
        assert result["overall_quality"] == "partial"

    def test_numeric_score_fail(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        result = _extract_judge_data({"judge_scores": 0.1})
        assert result is not None
        assert result["overall_quality"] == "fail"

    def test_dict_with_dimensions(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        trial = _sample_categories()[0]["experiments"][0]["trials"][0]
        result = _extract_judge_data(trial)
        assert result is not None
        assert result["mean_score"] == 0.75
        assert result["overall_quality"] == "pass"
        assert len(result["dimensions"]) == 2
        # Average confidence: (1.0 + 0.67) / 2
        assert abs(result["confidence"] - 0.835) < 0.01

    def test_dict_with_error(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        trial = _sample_categories_with_error()[0]["experiments"][0]["trials"][0]
        result = _extract_judge_data(trial)
        assert result is not None
        assert result["error"] == "No solution text found for trial"
        assert result["mean_score"] == 0.0

    def test_dict_no_dimensions(self):
        from dashboard.views.judge_viewer import _extract_judge_data

        result = _extract_judge_data({
            "judge_scores": {"mean_score": 0.5, "overall_quality": "partial"}
        })
        assert result is not None
        assert result["dimensions"] == []
        assert result["confidence"] == 0.0


class TestFlattenTrials:
    """Test _flatten_trials helper."""

    def test_flatten(self):
        from dashboard.views.judge_viewer import _flatten_trials

        categories = _sample_categories()
        flat = _flatten_trials(categories)
        assert len(flat) == 3
        assert flat[0]["run_category"] == "official"
        assert flat[0]["experiment_id"] == "exp-001"

    def test_flatten_empty(self):
        from dashboard.views.judge_viewer import _flatten_trials

        assert _flatten_trials([]) == []

    def test_flatten_no_trials(self):
        from dashboard.views.judge_viewer import _flatten_trials

        result = _flatten_trials([{"run_category": "x", "experiments": [{"experiment_id": "e", "trials": []}]}])
        assert result == []


class TestLoadExperimentMetrics:
    """Test _load_experiment_metrics."""

    def test_load_valid(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_experiment_metrics

        output_dir = _write_experiment_metrics(tmp_path, _sample_categories())
        data = _load_experiment_metrics(output_dir)
        assert len(data) == 1
        assert data[0]["run_category"] == "official"

    def test_load_missing(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_experiment_metrics

        data = _load_experiment_metrics(tmp_path / "nonexistent")
        assert data == []

    def test_load_invalid_json(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_experiment_metrics

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "experiment_metrics.json").write_text("{bad", encoding="utf-8")
        data = _load_experiment_metrics(output_dir)
        assert data == []

    def test_load_non_list(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_experiment_metrics

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "experiment_metrics.json").write_text('{"key": "value"}', encoding="utf-8")
        data = _load_experiment_metrics(output_dir)
        assert data == []


class TestLoadJudgeTemplates:
    """Test _load_judge_templates."""

    def test_no_dir(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_judge_templates

        assert _load_judge_templates(tmp_path / "nonexistent") == []

    def test_empty_dir(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_judge_templates

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        assert _load_judge_templates(templates_dir) == []

    def test_finds_json_files(self, tmp_path: Path):
        from dashboard.views.judge_viewer import _load_judge_templates

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "rubric_a.json").write_text('{"dimensions": ["correctness"]}')
        (templates_dir / "rubric_b.json").write_text('{"dimensions": ["completeness"]}')
        (templates_dir / "readme.md").write_text("# Not a template")

        result = _load_judge_templates(templates_dir)
        assert len(result) == 2
        assert all(p.suffix == ".json" for p in result)


class TestDisplayConfig:
    """Test _display_config."""

    def test_known_configs(self):
        from dashboard.views.judge_viewer import _display_config

        assert _display_config("BASELINE") == "Baseline"
        assert _display_config("MCP_BASE") == "MCP-Base"
        assert _display_config("MCP_FULL") == "MCP-Full"

    def test_unknown_config(self):
        from dashboard.views.judge_viewer import _display_config

        assert _display_config("CUSTOM") == "CUSTOM"


class TestDfToCsv:
    """Test _df_to_csv."""

    def test_basic(self):
        import pandas as pd

        from dashboard.views.judge_viewer import _df_to_csv

        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        csv = _df_to_csv(df)
        assert "a,b" in csv
        assert "1,3" in csv


# ---------------------------------------------------------------------------
# Rendering tests (mock streamlit)
# ---------------------------------------------------------------------------


class TestRenderAggregatedScores:
    """Test _render_aggregated_scores."""

    @patch("dashboard.views.judge_viewer.st")
    def test_renders_with_judge_data(self, mock_st):
        from dashboard.views.judge_viewer import _flatten_trials, _render_aggregated_scores

        flat = _flatten_trials(_sample_categories())
        _render_aggregated_scores(flat)

        mock_st.dataframe.assert_called_once()
        mock_st.download_button.assert_called_once()

    @patch("dashboard.views.judge_viewer.st")
    def test_no_judge_data(self, mock_st):
        from dashboard.views.judge_viewer import _flatten_trials, _render_aggregated_scores

        flat = _flatten_trials(_sample_categories_no_judge())
        _render_aggregated_scores(flat)

        mock_st.info.assert_called()

    @patch("dashboard.views.judge_viewer.st")
    def test_empty_trials(self, mock_st):
        from dashboard.views.judge_viewer import _render_aggregated_scores

        _render_aggregated_scores([])
        mock_st.info.assert_called()


class TestRenderPerTaskBreakdown:
    """Test _render_per_task_breakdown."""

    @patch("dashboard.views.judge_viewer.st")
    def test_renders_with_data(self, mock_st):
        from dashboard.views.judge_viewer import _flatten_trials, _render_per_task_breakdown

        # Mock expander context manager
        expander_mock = MagicMock()
        expander_mock.__enter__ = MagicMock(return_value=expander_mock)
        expander_mock.__exit__ = MagicMock(return_value=False)
        mock_st.expander.return_value = expander_mock
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

        flat = _flatten_trials(_sample_categories())
        _render_per_task_breakdown(flat)

        mock_st.dataframe.assert_called()
        # Should create expanders for judged trials
        assert mock_st.expander.called

    @patch("dashboard.views.judge_viewer.st")
    def test_no_judge_data(self, mock_st):
        from dashboard.views.judge_viewer import _flatten_trials, _render_per_task_breakdown

        flat = _flatten_trials(_sample_categories_no_judge())
        _render_per_task_breakdown(flat)

        mock_st.info.assert_called()


class TestRenderScoreComparison:
    """Test _render_score_comparison."""

    @patch("dashboard.views.judge_viewer.st")
    def test_renders_multi_config(self, mock_st):
        from dashboard.views.judge_viewer import _flatten_trials, _render_score_comparison

        flat = _flatten_trials(_sample_categories())
        _render_score_comparison(flat)

        # Should show comparison table for task-alpha (has BASELINE + MCP_FULL)
        mock_st.dataframe.assert_called()
        mock_st.download_button.assert_called()

    @patch("dashboard.views.judge_viewer.st")
    def test_single_trial(self, mock_st):
        from dashboard.views.judge_viewer import _render_score_comparison

        _render_score_comparison([{
            "trial_id": "t1",
            "task_name": "task1",
            "benchmark": "b1",
            "agent_config": "BASELINE",
            "judge_scores": {"mean_score": 0.5, "overall_quality": "partial", "dimensions": []},
        }])

        mock_st.caption.assert_called()

    @patch("dashboard.views.judge_viewer.st")
    def test_empty(self, mock_st):
        from dashboard.views.judge_viewer import _render_score_comparison

        _render_score_comparison([])
        mock_st.caption.assert_called()


class TestRenderRerunSection:
    """Test _render_rerun_section."""

    @patch("dashboard.views.judge_viewer.st")
    def test_renders_controls(self, mock_st):
        from dashboard.views.judge_viewer import _render_rerun_section

        mock_st.selectbox.return_value = "Default (auto by benchmark)"
        mock_st.multiselect.return_value = []
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.button.return_value = False

        _render_rerun_section([{"task_name": "task1"}])

        mock_st.selectbox.assert_called_once()
        mock_st.multiselect.assert_called_once()

    @patch("dashboard.views.judge_viewer._run_judge_subprocess")
    @patch("dashboard.views.judge_viewer.st")
    def test_rerun_button_triggers_subprocess(self, mock_st, mock_subprocess):
        from dashboard.views.judge_viewer import _render_rerun_section

        mock_st.selectbox.return_value = "Default (auto by benchmark)"
        mock_st.multiselect.return_value = []
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.button.return_value = True

        _render_rerun_section([{"task_name": "task1"}])

        mock_subprocess.assert_called_once_with(
            template_path=None,
            selected_tasks=[],
        )


class TestRunJudgeSubprocess:
    """Test _run_judge_subprocess."""

    @patch("dashboard.views.judge_viewer.subprocess.run")
    @patch("dashboard.views.judge_viewer.st")
    def test_success(self, mock_st, mock_run, tmp_path: Path):
        from dashboard.views.judge_viewer import _run_judge_subprocess

        # Mock spinner context manager
        spinner_mock = MagicMock()
        spinner_mock.__enter__ = MagicMock(return_value=spinner_mock)
        spinner_mock.__exit__ = MagicMock(return_value=False)
        mock_st.spinner.return_value = spinner_mock

        mock_run.return_value = MagicMock(returncode=0, stderr="Done", stdout="")

        with patch("dashboard.views.judge_viewer._DEFAULT_OUTPUT_DIR", tmp_path):
            metrics_path = tmp_path / "experiment_metrics.json"
            metrics_path.write_text("[]")
            _run_judge_subprocess(template_path=None, selected_tasks=[])

        mock_st.success.assert_called()

    @patch("dashboard.views.judge_viewer.st")
    def test_no_metrics_file(self, mock_st, tmp_path: Path):
        from dashboard.views.judge_viewer import _run_judge_subprocess

        with patch("dashboard.views.judge_viewer._DEFAULT_OUTPUT_DIR", tmp_path):
            _run_judge_subprocess(template_path=None, selected_tasks=[])

        mock_st.error.assert_called()


# ---------------------------------------------------------------------------
# Main entry point test
# ---------------------------------------------------------------------------


class TestShowJudgeViewer:
    """Test the main entry point."""

    @patch("dashboard.views.judge_viewer.st")
    def test_no_data(self, mock_st):
        from dashboard.views.judge_viewer import show_judge_viewer

        mock_st.selectbox.return_value = "Default (auto by benchmark)"
        mock_st.multiselect.return_value = []
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.button.return_value = False

        with patch(
            "dashboard.views.judge_viewer._load_experiment_metrics",
            return_value=[],
        ):
            show_judge_viewer()

        mock_st.info.assert_called()

    @patch("dashboard.views.judge_viewer.st")
    def test_with_judge_data(self, mock_st):
        from dashboard.views.judge_viewer import show_judge_viewer

        mock_st.selectbox.return_value = "Default (auto by benchmark)"
        mock_st.multiselect.return_value = []
        # Different calls to st.columns need different return lengths
        mock_st.columns.side_effect = lambda *args, **kwargs: [MagicMock() for _ in range(args[0] if isinstance(args[0], int) else len(args[0]))]
        mock_st.button.return_value = False

        expander_mock = MagicMock()
        expander_mock.__enter__ = MagicMock(return_value=expander_mock)
        expander_mock.__exit__ = MagicMock(return_value=False)
        mock_st.expander.return_value = expander_mock

        with patch(
            "dashboard.views.judge_viewer._load_experiment_metrics",
            return_value=_sample_categories(),
        ):
            show_judge_viewer()

        # Should render aggregated scores and per-task breakdown
        assert mock_st.dataframe.called

    @patch("dashboard.views.judge_viewer.st")
    def test_with_no_judge_scores(self, mock_st):
        from dashboard.views.judge_viewer import show_judge_viewer

        mock_st.selectbox.return_value = "Default (auto by benchmark)"
        mock_st.multiselect.return_value = []
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.button.return_value = False

        with patch(
            "dashboard.views.judge_viewer._load_experiment_metrics",
            return_value=_sample_categories_no_judge(),
        ):
            show_judge_viewer()

        # Should show info about no judge scores
        mock_st.info.assert_called()
