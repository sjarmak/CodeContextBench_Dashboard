"""Tests for dashboard/views/judge_annotation.py - human annotation collection."""

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

from dashboard.views.judge_annotation import (  # noqa: E402
    Annotation,
    AnnotationTask,
    _extract_agent_output,
    _load_annotations,
    _merge_tasks_by_id,
    _save_annotation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_annotations_dir(tmp_path: Path) -> Path:
    """Create a temporary annotations directory."""
    ann_dir = tmp_path / "human_annotations"
    ann_dir.mkdir()
    return ann_dir


@pytest.fixture()
def sample_annotation() -> Annotation:
    return Annotation(
        annotator_id="tester",
        timestamp="2026-02-03T12:00:00+00:00",
        task_id="task_001",
        mode="pairwise",
        preference="BASELINE",
        reasoning="Better structured",
        scores={"conditions": ["BASELINE", "MCP"]},
    )


@pytest.fixture()
def sample_tasks() -> list[AnnotationTask]:
    return [
        AnnotationTask(
            task_id="task_001",
            task_description="Fix the auth bug",
            agent_outputs={"BASELINE": "output A"},
            source="exp_001",
        ),
        AnnotationTask(
            task_id="task_001",
            task_description="Fix the auth bug",
            agent_outputs={"MCP": "output B"},
            reference_answer="expected fix",
            source="runs/run_001",
        ),
        AnnotationTask(
            task_id="task_002",
            task_description="Add logging",
            agent_outputs={"BASELINE": "output C"},
            source="exp_001",
        ),
    ]


# ---------------------------------------------------------------------------
# AnnotationTask dataclass tests
# ---------------------------------------------------------------------------


class TestAnnotationTask:
    def test_frozen(self) -> None:
        task = AnnotationTask(
            task_id="t1", task_description="desc", agent_outputs={}
        )
        with pytest.raises(AttributeError):
            task.task_id = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        task = AnnotationTask(
            task_id="t1", task_description="desc", agent_outputs={}
        )
        assert task.reference_answer == ""
        assert task.evaluation_criteria == ""
        assert task.source == ""


# ---------------------------------------------------------------------------
# Annotation dataclass tests
# ---------------------------------------------------------------------------


class TestAnnotation:
    def test_frozen(self) -> None:
        ann = Annotation(
            annotator_id="a",
            timestamp="t",
            task_id="task",
            mode="direct",
        )
        with pytest.raises(AttributeError):
            ann.mode = "pairwise"  # type: ignore[misc]

    def test_defaults(self) -> None:
        ann = Annotation(
            annotator_id="a",
            timestamp="t",
            task_id="task",
            mode="direct",
        )
        assert ann.scores == {}
        assert ann.preference == ""
        assert ann.reasoning == ""


# ---------------------------------------------------------------------------
# Annotation save/load tests
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_and_load(self, tmp_path: Path, sample_annotation: Annotation) -> None:
        ann_file = tmp_path / "annotations.jsonl"

        with patch(
            "dashboard.views.judge_annotation._ANNOTATIONS_FILE", ann_file
        ), patch(
            "dashboard.views.judge_annotation._ANNOTATIONS_DIR", tmp_path
        ):
            _save_annotation(sample_annotation)
            _save_annotation(sample_annotation)

            loaded = _load_annotations()

        assert len(loaded) == 2
        assert loaded[0]["annotator_id"] == "tester"
        assert loaded[0]["task_id"] == "task_001"
        assert loaded[0]["mode"] == "pairwise"
        assert loaded[0]["preference"] == "BASELINE"

    def test_load_empty(self, tmp_path: Path) -> None:
        ann_file = tmp_path / "annotations.jsonl"
        with patch("dashboard.views.judge_annotation._ANNOTATIONS_FILE", ann_file):
            loaded = _load_annotations()
        assert loaded == []

    def test_load_with_corrupt_lines(self, tmp_path: Path) -> None:
        ann_file = tmp_path / "annotations.jsonl"
        ann_file.write_text(
            '{"annotator_id": "a", "task_id": "t", "mode": "direct"}\n'
            "not json\n"
            '{"annotator_id": "b", "task_id": "t2", "mode": "reference"}\n'
        )
        with patch("dashboard.views.judge_annotation._ANNOTATIONS_FILE", ann_file):
            loaded = _load_annotations()
        assert len(loaded) == 2


# ---------------------------------------------------------------------------
# Task merging tests
# ---------------------------------------------------------------------------


class TestMergeTasks:
    def test_merge_combines_outputs(self, sample_tasks: list[AnnotationTask]) -> None:
        merged = _merge_tasks_by_id(sample_tasks[:2], [sample_tasks[2]])
        assert len(merged) == 2

        task_001 = next(t for t in merged if t.task_id == "task_001")
        assert "BASELINE" in task_001.agent_outputs
        assert "MCP" in task_001.agent_outputs
        assert task_001.reference_answer == "expected fix"

    def test_merge_preserves_unique(self, sample_tasks: list[AnnotationTask]) -> None:
        merged = _merge_tasks_by_id([], sample_tasks)
        ids = [t.task_id for t in merged]
        assert "task_001" in ids
        assert "task_002" in ids

    def test_merge_empty(self) -> None:
        merged = _merge_tasks_by_id([], [])
        assert merged == []


# ---------------------------------------------------------------------------
# Agent output extraction tests
# ---------------------------------------------------------------------------


class TestExtractAgentOutput:
    def test_solution_md(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("# Solution\nFixed the bug.")
        result = _extract_agent_output(tmp_path)
        assert "Fixed the bug" in result

    def test_fallback_md(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "output.md").write_text("Some analysis")
        result = _extract_agent_output(tmp_path)
        assert "Some analysis" in result

    def test_fallback_submission(self, tmp_path: Path) -> None:
        (tmp_path / "submission.txt").write_text("patch content")
        result = _extract_agent_output(tmp_path)
        assert "patch content" in result

    def test_no_output(self, tmp_path: Path) -> None:
        result = _extract_agent_output(tmp_path)
        assert result == ""

    def test_truncation(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("x" * 25000)
        result = _extract_agent_output(tmp_path)
        assert len(result) == 20000


# ---------------------------------------------------------------------------
# Load tasks from experiments tests
# ---------------------------------------------------------------------------


class TestLoadFromExperiments:
    def test_load_experiment_results(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_test001"
        exp_dir.mkdir()
        results = {
            "results": [
                {
                    "task_id": "task_a",
                    "task_description": "Test task",
                    "agent_output": "some output",
                    "reference_answer": "ref answer",
                },
                {
                    "task_id": "task_b",
                    "task_description": "Another task",
                    "agent_output": "other output",
                },
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))

        with patch(
            "dashboard.views.judge_annotation._EXPERIMENTS_DIR", tmp_path
        ):
            from dashboard.views.judge_annotation import _load_tasks_from_experiments

            tasks = _load_tasks_from_experiments()

        assert len(tasks) == 2
        assert tasks[0].task_id == "task_a"
        assert tasks[0].agent_outputs == {"default": "some output"}
        assert tasks[0].reference_answer == "ref answer"

    def test_skips_missing_task_id(self, tmp_path: Path) -> None:
        exp_dir = tmp_path / "exp_bad"
        exp_dir.mkdir()
        results = {"results": [{"agent_output": "orphan"}]}
        (exp_dir / "results.json").write_text(json.dumps(results))

        with patch(
            "dashboard.views.judge_annotation._EXPERIMENTS_DIR", tmp_path
        ):
            from dashboard.views.judge_annotation import _load_tasks_from_experiments

            tasks = _load_tasks_from_experiments()

        assert len(tasks) == 0


# ---------------------------------------------------------------------------
# Load tasks from runs tests
# ---------------------------------------------------------------------------


class TestLoadFromRuns:
    def test_load_run_results(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run_001"
        run_dir.mkdir()
        (run_dir / "result.json").write_text(json.dumps({"task_name": "my_task"}))
        agent_dir = run_dir / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("solution content")

        with patch(
            "dashboard.views.judge_annotation._EXTERNAL_RUNS_DIR", tmp_path
        ):
            from dashboard.views.judge_annotation import _load_tasks_from_runs

            tasks = _load_tasks_from_runs()

        assert len(tasks) == 1
        assert tasks[0].task_id == "my_task"
        assert "solution content" in tasks[0].agent_outputs.get("run_001", "")

    def test_task_id_dict_fallback(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run_002"
        run_dir.mkdir()
        (run_dir / "result.json").write_text(
            json.dumps({"task_id": {"path": "fallback_task"}})
        )
        agent_dir = run_dir / "logs" / "agent"
        agent_dir.mkdir(parents=True)
        (agent_dir / "solution.md").write_text("output")

        with patch(
            "dashboard.views.judge_annotation._EXTERNAL_RUNS_DIR", tmp_path
        ):
            from dashboard.views.judge_annotation import _load_tasks_from_runs

            tasks = _load_tasks_from_runs()

        assert len(tasks) == 1
        assert tasks[0].task_id == "fallback_task"

    def test_skips_no_output(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run_003"
        run_dir.mkdir()
        (run_dir / "result.json").write_text(json.dumps({"task_name": "empty_task"}))

        with patch(
            "dashboard.views.judge_annotation._EXTERNAL_RUNS_DIR", tmp_path
        ):
            from dashboard.views.judge_annotation import _load_tasks_from_runs

            tasks = _load_tasks_from_runs()

        assert len(tasks) == 0
