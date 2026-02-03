"""Tests for src/judge/experiment.py - experiment tracking for judge evaluations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

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

from src.judge.experiment import (  # noqa: E402
    ExperimentDiff,
    JudgeExperiment,
    _compute_data_hash,
    _deserialize_experiment,
    _extract_task_scores,
    _serialize_experiment,
    compare_experiments,
    create_experiment,
    list_experiments,
    load_experiment,
    save_experiment,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_experiment() -> JudgeExperiment:
    return JudgeExperiment(
        experiment_id="abc12345",
        timestamp="2026-02-03T12:00:00+00:00",
        judge_config={"temperature": 0.0, "max_tokens": 2000},
        prompt_template_versions={"direct_review": "v1.0"},
        model_ids=["claude-sonnet-4-20250514"],
        evaluation_mode="direct",
        input_data_hash="deadbeef01234567",
        results_path="eval_runs_v2/judge_experiments/exp_abc12345",
    )


@pytest.fixture()
def sample_results() -> dict:
    return {
        "mode": "direct",
        "total_tasks": 3,
        "successful": 3,
        "failed": 0,
        "results": [
            {"task_id": "task_a", "overall_score": 0.8, "confidence": 0.9},
            {"task_id": "task_b", "overall_score": 0.6, "confidence": 0.85},
            {"task_id": "task_c", "overall_score": 0.9, "confidence": 0.95},
        ],
        "errors": [],
    }


@pytest.fixture()
def sample_bias_report() -> dict:
    return {
        "position_consistency_rate": 0.95,
        "length_score_correlation": 0.12,
        "flagged_pairs": [],
        "bias_level_used": "standard",
    }


# ---------------------------------------------------------------------------
# JudgeExperiment dataclass
# ---------------------------------------------------------------------------

class TestJudgeExperiment:
    def test_frozen(self, sample_experiment: JudgeExperiment) -> None:
        with pytest.raises(AttributeError):
            sample_experiment.experiment_id = "new_id"  # type: ignore[misc]

    def test_fields(self, sample_experiment: JudgeExperiment) -> None:
        assert sample_experiment.experiment_id == "abc12345"
        assert sample_experiment.evaluation_mode == "direct"
        assert sample_experiment.model_ids == ["claude-sonnet-4-20250514"]
        assert sample_experiment.judge_config["temperature"] == 0.0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_round_trip(self, sample_experiment: JudgeExperiment) -> None:
        serialized = _serialize_experiment(sample_experiment)
        deserialized = _deserialize_experiment(serialized)
        assert deserialized.experiment_id == sample_experiment.experiment_id
        assert deserialized.timestamp == sample_experiment.timestamp
        assert deserialized.judge_config == sample_experiment.judge_config
        assert deserialized.model_ids == sample_experiment.model_ids
        assert deserialized.evaluation_mode == sample_experiment.evaluation_mode

    def test_deserialize_with_missing_fields(self) -> None:
        minimal = {
            "experiment_id": "test123",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        exp = _deserialize_experiment(minimal)
        assert exp.experiment_id == "test123"
        assert exp.judge_config == {}
        assert exp.model_ids == []
        assert exp.evaluation_mode == "unknown"


# ---------------------------------------------------------------------------
# create_experiment
# ---------------------------------------------------------------------------

class TestCreateExperiment:
    def test_creates_valid_experiment(self) -> None:
        exp = create_experiment(
            judge_config={"temperature": 0.5},
            prompt_template_versions={"direct": "v2"},
            model_ids=["model-a", "model-b"],
            evaluation_mode="reference",
            input_data={"tasks": ["t1", "t2"]},
        )
        assert len(exp.experiment_id) == 8
        assert exp.evaluation_mode == "reference"
        assert exp.model_ids == ["model-a", "model-b"]
        assert exp.input_data_hash != ""

    def test_no_input_data_hash(self) -> None:
        exp = create_experiment(
            judge_config={},
            prompt_template_versions={},
            model_ids=["m1"],
            evaluation_mode="direct",
        )
        assert exp.input_data_hash == ""


# ---------------------------------------------------------------------------
# Data hash
# ---------------------------------------------------------------------------

class TestDataHash:
    def test_deterministic(self) -> None:
        data = {"key": "value", "num": 42}
        h1 = _compute_data_hash(data)
        h2 = _compute_data_hash(data)
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        h1 = _compute_data_hash({"a": 1})
        h2 = _compute_data_hash({"a": 2})
        assert h1 != h2

    def test_hash_length(self) -> None:
        h = _compute_data_hash({"test": True})
        assert len(h) == 16


# ---------------------------------------------------------------------------
# save_experiment / load_experiment
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_creates_files(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        exp_dir = save_experiment(sample_experiment, sample_results, tmp_path)
        assert exp_dir.is_dir()
        assert (exp_dir / "config.json").exists()
        assert (exp_dir / "results.json").exists()
        assert (exp_dir / "summary.md").exists()

    def test_save_with_bias_report(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
        sample_bias_report: dict,
    ) -> None:
        exp_dir = save_experiment(
            sample_experiment, sample_results, tmp_path, bias_report=sample_bias_report
        )
        assert (exp_dir / "bias_report.json").exists()
        with open(exp_dir / "bias_report.json") as f:
            loaded_bias = json.load(f)
        assert loaded_bias["position_consistency_rate"] == 0.95

    def test_save_without_bias_report(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        exp_dir = save_experiment(sample_experiment, sample_results, tmp_path)
        assert not (exp_dir / "bias_report.json").exists()

    def test_load_round_trip(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        save_experiment(sample_experiment, sample_results, tmp_path)
        loaded_exp, loaded_results = load_experiment(
            sample_experiment.experiment_id, tmp_path
        )
        assert loaded_exp.experiment_id == sample_experiment.experiment_id
        assert loaded_exp.timestamp == sample_experiment.timestamp
        assert loaded_results["successful"] == 3

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_experiment("nonexistent", tmp_path)

    def test_load_missing_config_raises(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_noconfig"
        exp_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            load_experiment("noconfig", tmp_path)

    def test_load_missing_results(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        save_experiment(sample_experiment, sample_results, tmp_path)
        # Remove results.json
        (tmp_path / f"exp_{sample_experiment.experiment_id}" / "results.json").unlink()
        loaded_exp, loaded_results = load_experiment(
            sample_experiment.experiment_id, tmp_path
        )
        assert loaded_exp.experiment_id == sample_experiment.experiment_id
        assert loaded_results == {}

    def test_summary_contains_scores(
        self,
        tmp_path: Path,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        exp_dir = save_experiment(sample_experiment, sample_results, tmp_path)
        summary = (exp_dir / "summary.md").read_text()
        assert "Experiment abc12345" in summary
        assert "Mean score" in summary
        assert "direct" in summary.lower()


# ---------------------------------------------------------------------------
# list_experiments
# ---------------------------------------------------------------------------

class TestListExperiments:
    def test_empty_dir(self, tmp_path: Path) -> None:
        result = list_experiments(tmp_path)
        assert result == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        result = list_experiments(tmp_path / "nonexistent")
        assert result == []

    def test_lists_sorted_by_timestamp(self, tmp_path: Path) -> None:
        for i, ts in enumerate(["2026-01-01", "2026-03-01", "2026-02-01"]):
            exp = JudgeExperiment(
                experiment_id=f"exp{i:03d}",
                timestamp=f"{ts}T00:00:00+00:00",
                judge_config={},
                prompt_template_versions={},
                model_ids=["model"],
                evaluation_mode="direct",
                input_data_hash="",
                results_path="",
            )
            save_experiment(exp, {"results": []}, tmp_path)

        experiments = list_experiments(tmp_path)
        assert len(experiments) == 3
        # Newest first
        assert experiments[0].experiment_id == "exp001"  # 2026-03-01
        assert experiments[1].experiment_id == "exp002"  # 2026-02-01
        assert experiments[2].experiment_id == "exp000"  # 2026-01-01

    def test_skips_non_experiment_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "random_dir").mkdir()
        (tmp_path / "exp_valid").mkdir()
        config = {
            "experiment_id": "valid",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "judge_config": {},
            "prompt_template_versions": {},
            "model_ids": [],
            "evaluation_mode": "direct",
            "input_data_hash": "",
            "results_path": "",
        }
        with open(tmp_path / "exp_valid" / "config.json", "w") as f:
            json.dump(config, f)

        experiments = list_experiments(tmp_path)
        assert len(experiments) == 1
        assert experiments[0].experiment_id == "valid"

    def test_skips_corrupt_configs(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_corrupt"
        exp_dir.mkdir()
        with open(exp_dir / "config.json", "w") as f:
            f.write("not valid json")

        experiments = list_experiments(tmp_path)
        assert len(experiments) == 0


# ---------------------------------------------------------------------------
# compare_experiments
# ---------------------------------------------------------------------------

class TestCompareExperiments:
    def test_identical_experiments(
        self,
        sample_experiment: JudgeExperiment,
        sample_results: dict,
    ) -> None:
        diff = compare_experiments(
            sample_experiment, sample_results,
            sample_experiment, sample_results,
        )
        assert diff.config_changes == {}
        assert diff.prompt_changes == {}
        assert diff.result_deltas["mean_delta"] == 0.0
        assert diff.result_deltas["common_task_count"] == 3.0

    def test_config_differences(self) -> None:
        exp_a = JudgeExperiment(
            experiment_id="a",
            timestamp="2026-01-01T00:00:00+00:00",
            judge_config={"temperature": 0.0, "max_tokens": 2000},
            prompt_template_versions={"direct": "v1"},
            model_ids=["model-a"],
            evaluation_mode="direct",
            input_data_hash="",
            results_path="",
        )
        exp_b = JudgeExperiment(
            experiment_id="b",
            timestamp="2026-01-02T00:00:00+00:00",
            judge_config={"temperature": 0.5, "max_tokens": 4000},
            prompt_template_versions={"direct": "v2"},
            model_ids=["model-b"],
            evaluation_mode="direct",
            input_data_hash="",
            results_path="",
        )
        diff = compare_experiments(exp_a, {"results": []}, exp_b, {"results": []})
        assert "temperature" in diff.config_changes
        assert diff.config_changes["temperature"] == (0.0, 0.5)
        assert diff.config_changes["max_tokens"] == (2000, 4000)
        assert diff.prompt_changes["direct"] == ("v1", "v2")
        assert diff.model_changes == (["model-a"], ["model-b"])

    def test_result_deltas_common_tasks(self) -> None:
        exp_a = create_experiment({}, {}, ["m1"], "direct")
        exp_b = create_experiment({}, {}, ["m2"], "direct")
        results_a = {
            "results": [
                {"task_id": "t1", "overall_score": 0.5},
                {"task_id": "t2", "overall_score": 0.6},
                {"task_id": "t3", "overall_score": 0.7},
            ]
        }
        results_b = {
            "results": [
                {"task_id": "t1", "overall_score": 0.8},
                {"task_id": "t2", "overall_score": 0.7},
            ]
        }
        diff = compare_experiments(exp_a, results_a, exp_b, results_b)
        assert diff.result_deltas["common_task_count"] == 2.0
        # t1: 0.8-0.5=0.3, t2: 0.7-0.6=0.1 => mean = 0.2
        assert abs(diff.result_deltas["common_mean_delta"] - 0.2) < 1e-6

    def test_no_results(self) -> None:
        exp_a = create_experiment({}, {}, ["m1"], "direct")
        exp_b = create_experiment({}, {}, ["m2"], "direct")
        diff = compare_experiments(exp_a, {"results": []}, exp_b, {"results": []})
        assert "mean_delta" not in diff.result_deltas
        assert "common_task_count" not in diff.result_deltas

    def test_experiment_diff_frozen(self) -> None:
        diff = ExperimentDiff(
            config_changes={},
            prompt_changes={},
            model_changes=([], []),
            result_deltas={},
        )
        with pytest.raises(AttributeError):
            diff.config_changes = {"new": ("a", "b")}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _extract_task_scores
# ---------------------------------------------------------------------------

class TestExtractTaskScores:
    def test_extracts_overall_score(self) -> None:
        results = {
            "results": [
                {"task_id": "t1", "overall_score": 0.8},
                {"task_id": "t2", "overall_score": 0.6},
            ]
        }
        scores = _extract_task_scores(results)
        assert scores == {"t1": 0.8, "t2": 0.6}

    def test_extracts_consensus_score(self) -> None:
        results = {
            "results": [
                {"task_id": "t1", "consensus_score": 0.75},
            ]
        }
        scores = _extract_task_scores(results)
        assert scores == {"t1": 0.75}

    def test_skips_missing_score(self) -> None:
        results = {
            "results": [
                {"task_id": "t1"},
                {"task_id": "t2", "overall_score": 0.5},
            ]
        }
        scores = _extract_task_scores(results)
        assert scores == {"t2": 0.5}

    def test_empty_results(self) -> None:
        assert _extract_task_scores({}) == {}
        assert _extract_task_scores({"results": []}) == {}


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCLIExperiment:
    def test_experiment_list_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from scripts.judge.__main__ import main

        result = main(["experiment", "list", "--base-dir", str(tmp_path)])
        assert result == 0

    def test_experiment_list_with_data(
        self, tmp_path: Path, sample_experiment: JudgeExperiment, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts.judge.__main__ import main

        save_experiment(sample_experiment, {"results": []}, tmp_path)
        result = main(["experiment", "list", "--base-dir", str(tmp_path)])
        assert result == 0
        captured = capsys.readouterr()
        assert "abc12345" in captured.out
        assert "direct" in captured.out

    def test_experiment_compare_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts.judge.__main__ import main

        exp_a = create_experiment(
            {"temperature": 0.0}, {"direct": "v1"}, ["m1"], "direct"
        )
        exp_b = create_experiment(
            {"temperature": 0.5}, {"direct": "v2"}, ["m2"], "direct"
        )
        results_a = {"results": [{"task_id": "t1", "overall_score": 0.5}]}
        results_b = {"results": [{"task_id": "t1", "overall_score": 0.8}]}

        save_experiment(exp_a, results_a, tmp_path)
        save_experiment(exp_b, results_b, tmp_path)

        result = main([
            "experiment", "compare",
            exp_a.experiment_id, exp_b.experiment_id,
            "--base-dir", str(tmp_path),
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "temperature" in captured.out
        assert "Config Changes" in captured.out

    def test_experiment_compare_missing_exp(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from scripts.judge.__main__ import main

        result = main([
            "experiment", "compare", "nonexist1", "nonexist2",
            "--base-dir", str(tmp_path),
        ])
        assert result == 1
