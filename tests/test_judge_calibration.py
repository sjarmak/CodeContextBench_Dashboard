"""Tests for dashboard/views/judge_calibration.py - judge calibration view."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# --- Together SDK mock setup (required before importing src.judge) ---
_together_mock_needed = "together" not in sys.modules

if _together_mock_needed:
    _together_module = ModuleType("together")
    _together_error = ModuleType("together.error")

    class _MockTogetherRateLimitError(Exception):
        pass

    _together_error.RateLimitError = _MockTogetherRateLimitError  # type: ignore[attr-defined]
    _together_module.error = _together_error  # type: ignore[attr-defined]
    _together_module.AsyncTogether = MagicMock  # type: ignore[attr-defined]
    sys.modules["together"] = _together_module
    sys.modules["together.error"] = _together_error

from dashboard.views.judge_calibration import (  # noqa: E402
    CalibrationData,
    _build_calibration_data,
    _build_confusion_matrix,
    _categorize_score,
    _compute_per_dimension_accuracy,
    _compute_per_model_metrics,
    _extract_human_scores,
    _find_disagreements,
    _load_annotations,
    _load_experiment_results,
)


# ---------------------------------------------------------------------------
# CalibrationData dataclass tests
# ---------------------------------------------------------------------------


class TestCalibrationData:
    """Tests for CalibrationData frozen dataclass."""

    def test_construction(self) -> None:
        cd = CalibrationData(
            task_id="task_1",
            human_score=0.8,
            model_score=0.7,
            model_id="test-model",
        )
        assert cd.task_id == "task_1"
        assert cd.human_score == 0.8
        assert cd.model_score == 0.7
        assert cd.model_id == "test-model"

    def test_immutability(self) -> None:
        cd = CalibrationData(
            task_id="task_1",
            human_score=0.8,
            model_score=0.7,
            model_id="test-model",
        )
        with pytest.raises(AttributeError):
            cd.task_id = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        cd = CalibrationData(
            task_id="t",
            human_score=0.5,
            model_score=0.5,
            model_id="m",
        )
        assert cd.human_category == ""
        assert cd.model_category == ""
        assert cd.dimension_scores == {}
        assert cd.human_dimension_scores == {}


# ---------------------------------------------------------------------------
# _categorize_score tests
# ---------------------------------------------------------------------------


class TestCategorizeScore:
    def test_pass(self) -> None:
        assert _categorize_score(0.75) == "pass"
        assert _categorize_score(1.0) == "pass"

    def test_partial(self) -> None:
        assert _categorize_score(0.25) == "partial"
        assert _categorize_score(0.5) == "partial"
        assert _categorize_score(0.74) == "partial"

    def test_fail(self) -> None:
        assert _categorize_score(0.0) == "fail"
        assert _categorize_score(0.24) == "fail"


# ---------------------------------------------------------------------------
# _load_annotations tests
# ---------------------------------------------------------------------------


class TestLoadAnnotations:
    def test_missing_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_calibration._ANNOTATIONS_FILE",
            Path("/nonexistent/annotations.jsonl"),
        )
        result = _load_annotations()
        assert result == []

    def test_valid_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ann_file = tmp_path / "annotations.jsonl"
        records = [
            {"task_id": "t1", "mode": "direct", "scores": {"Correctness": 4}},
            {"task_id": "t2", "mode": "reference", "scores": {"Oracle Correctness": "pass"}},
        ]
        ann_file.write_text("\n".join(json.dumps(r) for r in records))
        monkeypatch.setattr("dashboard.views.judge_calibration._ANNOTATIONS_FILE", ann_file)

        result = _load_annotations()
        assert len(result) == 2

    def test_corrupt_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ann_file = tmp_path / "annotations.jsonl"
        ann_file.write_text('{"valid": true}\n{INVALID\n{"also_valid": true}\n')
        monkeypatch.setattr("dashboard.views.judge_calibration._ANNOTATIONS_FILE", ann_file)

        result = _load_annotations()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _extract_human_scores tests
# ---------------------------------------------------------------------------


class TestExtractHumanScores:
    def test_direct_mode(self) -> None:
        annotations = [
            {
                "task_id": "t1",
                "mode": "direct",
                "scores": {"Correctness": 4, "Completeness": 3},
            }
        ]
        result = _extract_human_scores(annotations)
        assert "t1" in result
        assert abs(result["t1"]["score"] - (4 / 5.0 + 3 / 5.0) / 2) < 0.001
        assert "Correctness" in result["t1"]["dimension_scores"]
        assert abs(result["t1"]["dimension_scores"]["Correctness"] - 0.8) < 0.001

    def test_reference_mode(self) -> None:
        annotations = [
            {
                "task_id": "t1",
                "mode": "reference",
                "scores": {
                    "Oracle Correctness": "pass",
                    "Oracle Completeness": "partial",
                },
            }
        ]
        result = _extract_human_scores(annotations)
        assert "t1" in result
        assert abs(result["t1"]["score"] - (1.0 + 0.5) / 2) < 0.001

    def test_pairwise_mode(self) -> None:
        annotations = [
            {"task_id": "t1", "mode": "pairwise", "scores": {"conditions": ["A", "B"]}},
        ]
        result = _extract_human_scores(annotations)
        assert "t1" in result
        assert result["t1"]["score"] == 1.0

    def test_empty_annotations(self) -> None:
        assert _extract_human_scores([]) == {}

    def test_missing_task_id(self) -> None:
        annotations = [{"mode": "direct", "scores": {"Correctness": 5}}]
        assert _extract_human_scores(annotations) == {}

    def test_multiple_annotations_averaged(self) -> None:
        annotations = [
            {"task_id": "t1", "mode": "direct", "scores": {"Correctness": 5}},
            {"task_id": "t1", "mode": "direct", "scores": {"Correctness": 3}},
        ]
        result = _extract_human_scores(annotations)
        # Each annotation: score = 5/5=1.0 and 3/5=0.6. Average = 0.8
        assert abs(result["t1"]["score"] - 0.8) < 0.001


# ---------------------------------------------------------------------------
# _load_experiment_results tests
# ---------------------------------------------------------------------------


class TestLoadExperimentResults:
    def test_missing_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "dashboard.views.judge_calibration._EXPERIMENTS_DIR",
            Path("/nonexistent/experiments"),
        )
        assert _load_experiment_results() == []

    def test_valid_experiment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp_dir = tmp_path / "exp_001"
        exp_dir.mkdir()
        config = {"model_id": "claude-test"}
        results = {
            "results": [
                {
                    "task_id": "task_a",
                    "overall_score": 0.85,
                    "scores": {"Correctness": {"score": 0.9, "weight": 0.3}},
                }
            ]
        }
        (exp_dir / "config.json").write_text(json.dumps(config))
        (exp_dir / "results.json").write_text(json.dumps(results))

        monkeypatch.setattr("dashboard.views.judge_calibration._EXPERIMENTS_DIR", tmp_path)

        exps = _load_experiment_results()
        assert len(exps) == 1
        assert exps[0]["model_id"] == "claude-test"
        assert "task_a" in exps[0]["task_scores"]
        assert abs(exps[0]["task_scores"]["task_a"]["score"] - 0.85) < 0.001

    def test_corrupt_results(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp_dir = tmp_path / "exp_bad"
        exp_dir.mkdir()
        (exp_dir / "results.json").write_text("{INVALID")
        monkeypatch.setattr("dashboard.views.judge_calibration._EXPERIMENTS_DIR", tmp_path)

        assert _load_experiment_results() == []

    def test_consensus_score_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp_dir = tmp_path / "exp_002"
        exp_dir.mkdir()
        results = {
            "results": [
                {"task_id": "t1", "consensus_score": 0.6}
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))
        monkeypatch.setattr("dashboard.views.judge_calibration._EXPERIMENTS_DIR", tmp_path)

        exps = _load_experiment_results()
        assert len(exps) == 1
        assert abs(exps[0]["task_scores"]["t1"]["score"] - 0.6) < 0.001

    def test_model_id_from_dir_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp_dir = tmp_path / "exp_fallback"
        exp_dir.mkdir()
        results = {"results": [{"task_id": "t1", "overall_score": 0.5}]}
        (exp_dir / "results.json").write_text(json.dumps(results))
        # No config.json -- model_id falls back to dir name
        monkeypatch.setattr("dashboard.views.judge_calibration._EXPERIMENTS_DIR", tmp_path)

        exps = _load_experiment_results()
        assert exps[0]["model_id"] == "exp_fallback"


# ---------------------------------------------------------------------------
# _build_calibration_data tests
# ---------------------------------------------------------------------------


class TestBuildCalibrationData:
    def test_matching_tasks(self) -> None:
        human = {"t1": {"score": 0.8, "category": "pass", "dimension_scores": {}}}
        experiments = [
            {
                "model_id": "model_a",
                "task_scores": {
                    "t1": {"score": 0.7, "category": "partial", "dimension_scores": {}},
                    "t2": {"score": 0.5, "category": "partial", "dimension_scores": {}},
                },
            }
        ]
        result = _build_calibration_data(human, experiments)
        assert len(result) == 1
        assert result[0].task_id == "t1"
        assert result[0].human_score == 0.8
        assert result[0].model_score == 0.7

    def test_no_overlap(self) -> None:
        human = {"t1": {"score": 0.8, "category": "pass", "dimension_scores": {}}}
        experiments = [
            {"model_id": "m", "task_scores": {"t2": {"score": 0.5, "category": "partial", "dimension_scores": {}}}}
        ]
        assert _build_calibration_data(human, experiments) == []

    def test_empty_inputs(self) -> None:
        assert _build_calibration_data({}, []) == []


# ---------------------------------------------------------------------------
# _compute_per_model_metrics tests
# ---------------------------------------------------------------------------


class TestComputePerModelMetrics:
    def test_single_model(self) -> None:
        data = [
            CalibrationData("t1", 0.9, 0.85, "model_a", "pass", "pass"),
            CalibrationData("t2", 0.3, 0.2, "model_a", "partial", "fail"),
            CalibrationData("t3", 0.1, 0.15, "model_a", "fail", "fail"),
        ]
        result = _compute_per_model_metrics(data)
        assert len(result) == 1
        assert result[0]["model_id"] == "model_a"
        assert result[0]["n_tasks"] == 3
        assert result[0]["spearman_rho"] > 0

    def test_multiple_models(self) -> None:
        data = [
            CalibrationData("t1", 0.9, 0.8, "model_a", "pass", "pass"),
            CalibrationData("t1", 0.9, 0.5, "model_b", "pass", "partial"),
        ]
        result = _compute_per_model_metrics(data)
        assert len(result) == 2

    def test_empty_data(self) -> None:
        assert _compute_per_model_metrics([]) == []


# ---------------------------------------------------------------------------
# _compute_per_dimension_accuracy tests
# ---------------------------------------------------------------------------


class TestComputePerDimensionAccuracy:
    def test_matching_dimensions(self) -> None:
        data = [
            CalibrationData(
                "t1", 0.8, 0.8, "m",
                dimension_scores={"Correctness": 0.9},
                human_dimension_scores={"Correctness": 0.8},
            ),
            CalibrationData(
                "t2", 0.3, 0.3, "m",
                dimension_scores={"Correctness": 0.2},
                human_dimension_scores={"Correctness": 0.1},
            ),
        ]
        result = _compute_per_dimension_accuracy(data)
        assert len(result) == 1
        assert result[0]["dimension"] == "Correctness"
        # Both are pass/fail so accuracy depends on categorization
        assert result[0]["n_samples"] == 2

    def test_no_overlapping_dimensions(self) -> None:
        data = [
            CalibrationData(
                "t1", 0.5, 0.5, "m",
                dimension_scores={"A": 0.5},
                human_dimension_scores={"B": 0.5},
            ),
        ]
        assert _compute_per_dimension_accuracy(data) == []

    def test_empty_data(self) -> None:
        assert _compute_per_dimension_accuracy([]) == []


# ---------------------------------------------------------------------------
# _build_confusion_matrix tests
# ---------------------------------------------------------------------------


class TestBuildConfusionMatrix:
    def test_all_categories(self) -> None:
        data = [
            CalibrationData("t1", 0.9, 0.9, "m", "pass", "pass"),
            CalibrationData("t2", 0.5, 0.3, "m", "partial", "partial"),
            CalibrationData("t3", 0.1, 0.8, "m", "fail", "pass"),
        ]
        result = _build_confusion_matrix(data)
        assert result["categories"] == ["pass", "partial", "fail"]
        matrix = result["matrix"]
        assert matrix[0][0] == 1  # pass-pass
        assert matrix[1][1] == 1  # partial-partial
        assert matrix[2][0] == 1  # fail predicted as pass

    def test_empty_data(self) -> None:
        result = _build_confusion_matrix([])
        assert result["matrix"] == [[0, 0, 0], [0, 0, 0], [0, 0, 0]]


# ---------------------------------------------------------------------------
# _find_disagreements tests
# ---------------------------------------------------------------------------


class TestFindDisagreements:
    def test_finds_large_differences(self) -> None:
        data = [
            CalibrationData("t1", 0.9, 0.2, "m", "pass", "fail"),
            CalibrationData("t2", 0.5, 0.45, "m", "partial", "partial"),
        ]
        result = _find_disagreements(data)
        # threshold=1.0 -> normalized 0.2; t1 diff=0.7 > 0.2, t2 diff=0.05 < 0.2
        assert len(result) == 1
        assert result[0]["task_id"] == "t1"

    def test_no_disagreements(self) -> None:
        data = [
            CalibrationData("t1", 0.5, 0.55, "m", "partial", "partial"),
        ]
        result = _find_disagreements(data)
        assert result == []

    def test_sorted_by_difference(self) -> None:
        data = [
            CalibrationData("t1", 0.9, 0.3, "m", "pass", "partial"),
            CalibrationData("t2", 0.9, 0.1, "m", "pass", "fail"),
        ]
        result = _find_disagreements(data)
        assert len(result) == 2
        assert result[0]["task_id"] == "t2"  # larger diff first

    def test_empty_data(self) -> None:
        assert _find_disagreements([]) == []
