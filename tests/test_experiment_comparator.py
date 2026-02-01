"""Tests for the experiment comparator task alignment module."""

import json
import pytest
from pathlib import Path

from src.analysis.experiment_comparator import TaskAligner, AlignmentResult


@pytest.fixture
def aligner():
    """Create a TaskAligner instance."""
    return TaskAligner()


def _make_task_dir(parent: Path, dir_name: str, task_path: str | None = None) -> Path:
    """Helper: create a task directory with optional config.json.

    Args:
        parent: Parent experiment directory.
        dir_name: Directory name for the task.
        task_path: If set, write config.json with this task.path value.

    Returns:
        The created task directory path.
    """
    task_dir = parent / dir_name
    task_dir.mkdir(parents=True, exist_ok=True)

    if task_path is not None:
        config = {"task": {"path": task_path}}
        (task_dir / "config.json").write_text(json.dumps(config))

    return task_dir


def _make_result(task_dir: Path, reward: float | None = None, **extra) -> None:
    """Helper: write a result.json to a task directory."""
    data = {
        "task_name": task_dir.name,
        "started_at": "2025-12-17T21:03:06.052742",
        "finished_at": "2025-12-17T21:06:18.968956",
        "agent_info": {"name": "claude-code"},
        "agent_result": {"n_input_tokens": 100},
        "verifier_result": {
            "rewards": {"reward": reward},
        } if reward is not None else None,
        "exception_info": None,
        **extra,
    }
    (task_dir / "result.json").write_text(json.dumps(data))


class TestTaskAlignerIdenticalSets:
    """Test alignment when both directories have the same tasks."""

    def test_identical_tasks_all_common(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        for name in ["task-a", "task-b", "task-c"]:
            _make_task_dir(baseline, f"{name}__abc", task_path=f"benchmarks/test/{name}")
            _make_task_dir(treatment, f"{name}__xyz", task_path=f"benchmarks/test/{name}")

        result = aligner.align(baseline, treatment)

        assert sorted(result.common_tasks) == ["task-a", "task-b", "task-c"]
        assert result.baseline_only == []
        assert result.treatment_only == []
        assert result.total_baseline == 3
        assert result.total_treatment == 3


class TestTaskAlignerDisjointSets:
    """Test alignment when directories have no tasks in common."""

    def test_disjoint_tasks_no_overlap(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, "alpha__abc", task_path="benchmarks/test/alpha")
        _make_task_dir(baseline, "beta__def", task_path="benchmarks/test/beta")
        _make_task_dir(treatment, "gamma__ghi", task_path="benchmarks/test/gamma")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert sorted(result.baseline_only) == ["alpha", "beta"]
        assert result.treatment_only == ["gamma"]
        assert result.total_baseline == 2
        assert result.total_treatment == 1


class TestTaskAlignerPartialOverlap:
    """Test alignment with partial task overlap."""

    def test_partial_overlap(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, "shared__abc", task_path="benchmarks/test/shared")
        _make_task_dir(baseline, "base-only__def", task_path="benchmarks/test/base-only")
        _make_task_dir(treatment, "shared__xyz", task_path="benchmarks/test/shared")
        _make_task_dir(treatment, "treat-only__ghi", task_path="benchmarks/test/treat-only")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["shared"]
        assert result.baseline_only == ["base-only"]
        assert result.treatment_only == ["treat-only"]
        assert result.total_baseline == 2
        assert result.total_treatment == 2


class TestTaskAlignerMissingConfig:
    """Test alignment when config.json is missing."""

    def test_falls_back_to_directory_name(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        # No config.json — should strip hash suffix and use dir name
        task_b = baseline / "mytask__abc123"
        task_b.mkdir(parents=True)
        task_t = treatment / "mytask__xyz789"
        task_t.mkdir(parents=True)

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["mytask"]

    def test_no_hash_suffix_uses_full_name(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        (baseline / "plain-task").mkdir(parents=True)
        (treatment / "plain-task").mkdir(parents=True)

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["plain-task"]


class TestTaskAlignerNullFields:
    """Test handling of null fields in result.json."""

    def test_load_result_with_null_fields(self, tmp_path, aligner):
        task_dir = tmp_path / "task-x__abc"
        task_dir.mkdir(parents=True)

        data = {
            "task_name": None,
            "started_at": None,
            "finished_at": None,
            "agent_info": None,
            "agent_result": None,
            "verifier_result": None,
            "exception_info": None,
        }
        (task_dir / "result.json").write_text(json.dumps(data))

        result = aligner.load_result(task_dir)

        assert result["task_name"] == ""
        assert result["started_at"] == ""
        assert result["finished_at"] == ""
        assert result["agent_info"] == {}
        assert result["agent_result"] == {}
        assert result["verifier_result"] == {}
        assert result["exception_info"] is None

    def test_load_result_missing_file(self, tmp_path, aligner):
        task_dir = tmp_path / "no-result"
        task_dir.mkdir(parents=True)

        result = aligner.load_result(task_dir)
        assert result == {}

    def test_load_result_invalid_json(self, tmp_path, aligner):
        task_dir = tmp_path / "bad-json"
        task_dir.mkdir(parents=True)
        (task_dir / "result.json").write_text("not valid json {{{")

        result = aligner.load_result(task_dir)
        assert result == {}

    def test_load_reward_with_valid_data(self, tmp_path, aligner):
        task_dir = tmp_path / "reward-task"
        task_dir.mkdir(parents=True)
        _make_result(task_dir, reward=0.75)

        reward = aligner.load_reward(task_dir)
        assert reward == pytest.approx(0.75)

    def test_load_reward_with_null_verifier(self, tmp_path, aligner):
        task_dir = tmp_path / "null-verifier"
        task_dir.mkdir(parents=True)

        data = {"verifier_result": None}
        (task_dir / "result.json").write_text(json.dumps(data))

        reward = aligner.load_reward(task_dir)
        assert reward is None

    def test_load_reward_missing_result(self, tmp_path, aligner):
        task_dir = tmp_path / "no-result"
        task_dir.mkdir(parents=True)

        reward = aligner.load_reward(task_dir)
        assert reward is None


class TestTaskAlignerEdgeCases:
    """Edge cases for task alignment."""

    def test_empty_directories(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"
        baseline.mkdir()
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert result.baseline_only == []
        assert result.treatment_only == []
        assert result.total_baseline == 0
        assert result.total_treatment == 0

    def test_nonexistent_directory(self, tmp_path, aligner):
        baseline = tmp_path / "does-not-exist"
        treatment = tmp_path / "also-missing"

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == []
        assert result.total_baseline == 0
        assert result.total_treatment == 0

    def test_skips_hidden_directories(self, tmp_path, aligner):
        baseline = tmp_path / "baseline"
        treatment = tmp_path / "treatment"

        _make_task_dir(baseline, ".hidden", task_path="benchmarks/test/.hidden")
        _make_task_dir(baseline, "visible__abc", task_path="benchmarks/test/visible")
        _make_task_dir(treatment, "visible__xyz", task_path="benchmarks/test/visible")

        result = aligner.align(baseline, treatment)

        assert result.common_tasks == ["visible"]
        assert result.baseline_only == []

    def test_config_with_empty_task_path(self, tmp_path, aligner):
        """Config exists but task.path is empty string."""
        baseline = tmp_path / "baseline"
        task_dir = baseline / "fallback-name__abc"
        task_dir.mkdir(parents=True)

        config = {"task": {"path": ""}}
        (task_dir / "config.json").write_text(json.dumps(config))

        treatment = tmp_path / "treatment"
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        # Should fall back to directory name stripping
        assert result.baseline_only == ["fallback-name"]

    def test_alignment_result_is_frozen(self, aligner, tmp_path):
        """AlignmentResult should be immutable."""
        baseline = tmp_path / "b"
        baseline.mkdir()
        treatment = tmp_path / "t"
        treatment.mkdir()

        result = aligner.align(baseline, treatment)

        with pytest.raises(AttributeError):
            result.total_baseline = 999
