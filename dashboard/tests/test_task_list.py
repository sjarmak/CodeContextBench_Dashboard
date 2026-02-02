"""
Unit tests for dashboard/utils/task_list.py

Tests:
- Task metadata parsing (LoCoBench, SWE-Bench, unknown patterns)
- Task normalization from different experiment formats
- Multi-criteria filtering (status, language, task type, difficulty, text)
- Sorting by all supported keys
- Paired table row building
- Formatting helpers
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from dashboard.utils.task_list import (
    NormalizedTask,
    TaskFilter,
    TaskMetadata,
    _build_paired_table_rows,
    _build_table_rows,
    _compute_duration_seconds,
    _compute_token_count,
    _determine_status,
    _format_duration,
    _format_reward,
    _format_tokens,
    _shorten_task_id,
    _unique_values,
    filter_tasks,
    normalize_task,
    normalize_tasks,
    parse_task_metadata,
    sort_tasks,
)


# --- parse_task_metadata tests ---


class TestParseTaskMetadata:
    def test_locobench_full_pattern(self):
        result = parse_task_metadata(
            "python_web_medium_001_bugfix_hard_v1"
        )
        assert result.language == "Python"
        assert result.task_type == "Bugfix"
        assert result.difficulty == "Hard"

    def test_locobench_different_language(self):
        result = parse_task_metadata(
            "typescript_api_simple_042_refactor_easy_v2"
        )
        assert result.language == "TypeScript"
        assert result.task_type == "Refactor"
        assert result.difficulty == "Easy"

    def test_locobench_compound_task_category(self):
        result = parse_task_metadata(
            "rust_systems_complex_010_code_review_medium_v1"
        )
        assert result.language == "Rust"
        assert result.task_type == "Code Review"
        assert result.difficulty == "Medium"

    def test_swebench_pattern(self):
        result = parse_task_metadata(
            "instance_ansible__ansible__abc123"
        )
        assert result.language == "Python"
        assert result.task_type == "SWE-Bench"
        assert result.difficulty == "Unknown"

    def test_swebench_with_underscores_in_hash(self):
        result = parse_task_metadata(
            "instance_django__django__abcdef_123"
        )
        assert result.language == "Python"
        assert result.task_type == "SWE-Bench"

    def test_unknown_pattern(self):
        result = parse_task_metadata("some_random_task_name")
        assert result.language == "Unknown"
        assert result.task_type == "Unknown"
        assert result.difficulty == "Unknown"

    def test_empty_string(self):
        result = parse_task_metadata("")
        assert result.language == "Unknown"

    def test_returns_frozen_dataclass(self):
        result = parse_task_metadata("python_web_medium_001_bugfix_hard_v1")
        assert isinstance(result, TaskMetadata)
        with pytest.raises(AttributeError):
            result.language = "Java"


# --- _determine_status tests ---


class TestDetermineStatus:
    def test_error_status(self):
        assert _determine_status({"status": "error"}) == "error"

    def test_positive_reward_is_pass(self):
        assert _determine_status({"status": "completed", "reward": 1.0}) == "pass"

    def test_zero_reward_is_fail(self):
        assert _determine_status({"status": "completed", "reward": 0.0}) == "fail"

    def test_negative_reward_is_fail(self):
        assert _determine_status({"status": "completed", "reward": -0.5}) == "fail"

    def test_completed_without_reward_is_pass(self):
        assert _determine_status({"status": "completed"}) == "pass"

    def test_na_reward(self):
        assert _determine_status({"status": "completed", "reward": "N/A"}) == "pass"

    def test_unknown_status(self):
        assert _determine_status({"status": "running"}) == "running"

    def test_missing_status(self):
        assert _determine_status({}) == "unknown"


# --- _compute_duration_seconds tests ---


class TestComputeDurationSeconds:
    def test_from_timestamps(self):
        task = {
            "started_at": "2026-01-27T10:00:00",
            "finished_at": "2026-01-27T10:05:30",
        }
        result = _compute_duration_seconds(task)
        assert result == 330.0

    def test_from_execution_time(self):
        task = {"execution_time": 120}
        result = _compute_duration_seconds(task)
        assert result == 120.0

    def test_no_timing_data(self):
        assert _compute_duration_seconds({}) is None

    def test_invalid_timestamps(self):
        task = {"started_at": "invalid", "finished_at": "also-invalid"}
        assert _compute_duration_seconds(task) is None

    def test_timestamps_with_z_suffix(self):
        task = {
            "started_at": "2026-01-27T10:00:00Z",
            "finished_at": "2026-01-27T10:01:00Z",
        }
        result = _compute_duration_seconds(task)
        assert result == 60.0


# --- _compute_token_count tests ---


class TestComputeTokenCount:
    def test_from_total_tokens(self):
        assert _compute_token_count({"total_tokens": 5000}) == 5000

    def test_from_input_output(self):
        task = {"input_tokens": 3000, "output_tokens": 2000}
        assert _compute_token_count(task) == 5000

    def test_na_total_tokens_falls_through(self):
        task = {"total_tokens": "N/A", "input_tokens": 100, "output_tokens": 200}
        assert _compute_token_count(task) == 300

    def test_no_token_data(self):
        assert _compute_token_count({}) is None

    def test_none_values(self):
        assert _compute_token_count({"input_tokens": None, "output_tokens": None}) is None


# --- normalize_task tests ---


class TestNormalizeTask:
    def test_paired_mode_task(self):
        task = {
            "task_name": "python_web_medium_001_bugfix_hard_v1",
            "reward": 1.0,
            "status": "completed",
            "input_tokens": 3000,
            "output_tokens": 1500,
            "started_at": "2026-01-27T10:00:00",
            "finished_at": "2026-01-27T10:05:00",
            "instance_dir": Path("/tmp/task1"),
        }
        result = normalize_task(task)
        assert result.task_id == "python_web_medium_001_bugfix_hard_v1"
        assert result.status == "pass"
        assert result.language == "Python"
        assert result.task_type == "Bugfix"
        assert result.difficulty == "Hard"
        assert result.token_count == 4500
        assert result.duration_seconds == 300.0
        assert result.reward == 1.0
        assert result.instance_dir == Path("/tmp/task1")

    def test_external_task(self):
        task = {
            "task_name": "instance_django__django__abc123",
            "agent_name": "claude__code",
            "status": "completed",
            "reward": 0.0,
            "total_tokens": 10000,
            "execution_time": 45,
        }
        result = normalize_task(task)
        assert result.task_id == "instance_django__django__abc123"
        assert result.status == "fail"
        assert result.language == "Python"
        assert result.task_type == "SWE-Bench"
        assert result.token_count == 10000
        assert result.duration_seconds == 45.0

    def test_error_task(self):
        task = {
            "task_name": "failed_task",
            "status": "error",
            "reward": None,
        }
        result = normalize_task(task)
        assert result.status == "error"
        assert result.reward is None

    def test_normalize_tasks_list(self):
        tasks = [
            {"task_name": "task_a", "status": "completed", "reward": 1.0},
            {"task_name": "task_b", "status": "error"},
        ]
        results = normalize_tasks(tasks)
        assert len(results) == 2
        assert results[0].task_id == "task_a"
        assert results[1].task_id == "task_b"

    def test_instance_dir_string_to_path(self):
        task = {"task_name": "test", "instance_dir": "/tmp/test"}
        result = normalize_task(task)
        assert isinstance(result.instance_dir, Path)


# --- filter_tasks tests ---


def _make_task(
    task_id: str = "test",
    status: str = "pass",
    language: str = "Python",
    task_type: str = "Bugfix",
    difficulty: str = "Hard",
) -> NormalizedTask:
    return NormalizedTask(
        task_id=task_id,
        status=status,
        language=language,
        task_type=task_type,
        difficulty=difficulty,
        duration_seconds=None,
        token_count=None,
        reward=None,
        instance_dir=None,
        raw={},
    )


class TestFilterTasks:
    def test_no_filters(self):
        tasks = [_make_task(task_id="a"), _make_task(task_id="b")]
        result = filter_tasks(tasks, TaskFilter())
        assert len(result) == 2

    def test_filter_by_status(self):
        tasks = [
            _make_task(task_id="a", status="pass"),
            _make_task(task_id="b", status="fail"),
            _make_task(task_id="c", status="error"),
        ]
        result = filter_tasks(tasks, TaskFilter(statuses=("pass", "error")))
        assert len(result) == 2
        assert {t.task_id for t in result} == {"a", "c"}

    def test_filter_by_language(self):
        tasks = [
            _make_task(task_id="a", language="Python"),
            _make_task(task_id="b", language="Typescript"),
        ]
        result = filter_tasks(tasks, TaskFilter(languages=("Python",)))
        assert len(result) == 1
        assert result[0].task_id == "a"

    def test_filter_by_task_type(self):
        tasks = [
            _make_task(task_id="a", task_type="Bugfix"),
            _make_task(task_id="b", task_type="Refactor"),
        ]
        result = filter_tasks(tasks, TaskFilter(task_types=("Refactor",)))
        assert len(result) == 1
        assert result[0].task_id == "b"

    def test_filter_by_difficulty(self):
        tasks = [
            _make_task(task_id="a", difficulty="Hard"),
            _make_task(task_id="b", difficulty="Easy"),
        ]
        result = filter_tasks(tasks, TaskFilter(difficulty="Easy"))
        assert len(result) == 1
        assert result[0].task_id == "b"

    def test_filter_by_search_text(self):
        tasks = [
            _make_task(task_id="python_bugfix_001"),
            _make_task(task_id="rust_refactor_002"),
        ]
        result = filter_tasks(tasks, TaskFilter(search_text="bugfix"))
        assert len(result) == 1
        assert result[0].task_id == "python_bugfix_001"

    def test_search_case_insensitive(self):
        tasks = [_make_task(task_id="Python_BugFix_001")]
        result = filter_tasks(tasks, TaskFilter(search_text="BUGFIX"))
        assert len(result) == 1

    def test_combined_filters_and_logic(self):
        tasks = [
            _make_task(task_id="a", status="pass", language="Python"),
            _make_task(task_id="b", status="pass", language="Rust"),
            _make_task(task_id="c", status="fail", language="Python"),
        ]
        result = filter_tasks(
            tasks,
            TaskFilter(statuses=("pass",), languages=("Python",)),
        )
        assert len(result) == 1
        assert result[0].task_id == "a"

    def test_empty_filter_values(self):
        tasks = [_make_task()]
        result = filter_tasks(
            tasks,
            TaskFilter(statuses=(), languages=(), search_text=""),
        )
        assert len(result) == 1


# --- sort_tasks tests ---


class TestSortTasks:
    def test_sort_by_name(self):
        tasks = [
            _make_task(task_id="charlie"),
            _make_task(task_id="alpha"),
            _make_task(task_id="bravo"),
        ]
        result = sort_tasks(tasks, "Name")
        assert [t.task_id for t in result] == ["alpha", "bravo", "charlie"]

    def test_sort_by_name_descending(self):
        tasks = [
            _make_task(task_id="alpha"),
            _make_task(task_id="bravo"),
        ]
        result = sort_tasks(tasks, "Name", descending=True)
        assert [t.task_id for t in result] == ["bravo", "alpha"]

    def test_sort_by_reward(self):
        tasks = [
            NormalizedTask("a", "pass", "Python", "Bugfix", "Hard", None, None, 0.5, None, {}),
            NormalizedTask("b", "pass", "Python", "Bugfix", "Hard", None, None, 0.9, None, {}),
            NormalizedTask("c", "pass", "Python", "Bugfix", "Hard", None, None, 0.1, None, {}),
        ]
        result = sort_tasks(tasks, "Reward")
        assert [t.reward for t in result] == [pytest.approx(0.1), pytest.approx(0.5), pytest.approx(0.9)]

    def test_sort_by_reward_descending(self):
        tasks = [
            NormalizedTask("a", "pass", "Python", "Bugfix", "Hard", None, None, 0.5, None, {}),
            NormalizedTask("b", "pass", "Python", "Bugfix", "Hard", None, None, 0.9, None, {}),
        ]
        result = sort_tasks(tasks, "Reward", descending=True)
        assert result[0].reward == pytest.approx(0.9)

    def test_sort_by_duration(self):
        tasks = [
            NormalizedTask("a", "pass", "Py", "B", "H", 300.0, None, None, None, {}),
            NormalizedTask("b", "pass", "Py", "B", "H", 60.0, None, None, None, {}),
        ]
        result = sort_tasks(tasks, "Duration")
        assert result[0].duration_seconds == 60.0

    def test_sort_none_values_last(self):
        tasks = [
            NormalizedTask("a", "pass", "Py", "B", "H", None, None, None, None, {}),
            NormalizedTask("b", "pass", "Py", "B", "H", None, None, 0.5, None, {}),
        ]
        result = sort_tasks(tasks, "Reward")
        # None reward (-1.0) sorts before 0.5
        assert result[0].task_id == "a"
        assert result[1].task_id == "b"

    def test_sort_by_status(self):
        tasks = [
            _make_task(task_id="a", status="pass"),
            _make_task(task_id="b", status="error"),
            _make_task(task_id="c", status="fail"),
        ]
        result = sort_tasks(tasks, "Status")
        assert [t.status for t in result] == ["error", "fail", "pass"]

    def test_sort_unknown_key_defaults_to_name(self):
        tasks = [_make_task(task_id="b"), _make_task(task_id="a")]
        result = sort_tasks(tasks, "NonExistent")
        assert [t.task_id for t in result] == ["a", "b"]


# --- _build_table_rows tests ---


class TestBuildTableRows:
    def test_basic_row(self):
        tasks = [
            NormalizedTask(
                "test_task", "pass", "Python", "Bugfix", "Hard",
                120.0, 5000, 0.85, None, {},
            )
        ]
        rows = _build_table_rows(tasks)
        assert len(rows) == 1
        row = rows[0]
        assert row["Task"] == "test_task"
        assert "Pass" in row["Status"]
        assert row["Lang"] == "Python"
        assert row["Duration"] == "2m 0s"
        assert row["Tokens"] == "5.0k"
        assert row["Reward"] == "0.8500"

    def test_truncated_task_id(self):
        long_id = "a" * 100
        rows = _build_table_rows(
            [normalize_task({"task_name": long_id, "status": "completed", "reward": 1.0})]
        )
        assert len(rows[0]["Task"]) == 40


# --- _shorten_task_id tests ---


class TestShortenTaskId:
    def test_swebench_id(self):
        task_id = "instance_ansible__ansible-4c5ce5a1a9e79a845aff4978cfeb72a0d4ecf7d6"
        assert _shorten_task_id(task_id) == "ansible/ansible"

    def test_swebench_with_double_underscore(self):
        task_id = "instance_protonmail__webclients-abc123def456"
        assert _shorten_task_id(task_id) == "protonmail/webclients"

    def test_short_id_unchanged(self):
        assert _shorten_task_id("my_task") == "my_task"

    def test_long_non_swebench_id_truncated(self):
        long_id = "a" * 50
        assert len(_shorten_task_id(long_id)) == 40

    def test_empty_string(self):
        assert _shorten_task_id("") == ""


# --- _build_paired_table_rows tests ---


class TestBuildPairedTableRows:
    def test_matching_tasks(self):
        baseline = [
            NormalizedTask("task_1", "pass", "Python", "Bugfix", "Hard", None, None, 1.0, None, {}),
        ]
        variant = [
            NormalizedTask("task_1", "fail", "Python", "Bugfix", "Hard", None, None, 0.0, None, {}),
        ]
        rows = _build_paired_table_rows(baseline, variant)
        assert len(rows) == 1
        assert "Pass" in rows[0]["Base"]
        assert "Fail" in rows[0]["Var"]

    def test_disjoint_tasks(self):
        baseline = [
            NormalizedTask("task_a", "pass", "Python", "B", "H", None, None, None, None, {}),
        ]
        variant = [
            NormalizedTask("task_b", "fail", "Rust", "R", "E", None, None, None, None, {}),
        ]
        rows = _build_paired_table_rows(baseline, variant)
        assert len(rows) == 2
        # task_a only in baseline
        row_a = next(r for r in rows if r["Task"] == "task_a")
        assert "Pass" in row_a["Base"]
        assert row_a["Var"] == "N/A"

        # task_b only in variant
        row_b = next(r for r in rows if r["Task"] == "task_b")
        assert row_b["Base"] == "N/A"
        assert "Fail" in row_b["Var"]

    def test_empty_inputs(self):
        rows = _build_paired_table_rows([], [])
        assert rows == []


# --- Formatting tests ---


class TestFormatHelpers:
    def test_format_duration_seconds(self):
        assert _format_duration(30.0) == "30s"

    def test_format_duration_minutes(self):
        assert _format_duration(150.0) == "2m 30s"

    def test_format_duration_none(self):
        assert _format_duration(None) == "N/A"

    def test_format_tokens_small(self):
        assert _format_tokens(500) == "500"

    def test_format_tokens_thousands(self):
        assert _format_tokens(5000) == "5.0k"

    def test_format_tokens_millions(self):
        assert _format_tokens(1_500_000) == "1.5M"

    def test_format_tokens_none(self):
        assert _format_tokens(None) == "N/A"

    def test_format_reward(self):
        assert _format_reward(0.85) == "0.8500"

    def test_format_reward_none(self):
        assert _format_reward(None) == "N/A"


# --- _unique_values tests ---


class TestUniqueValues:
    def test_basic(self):
        tasks = [
            _make_task(language="Python"),
            _make_task(language="Rust"),
            _make_task(language="Python"),
        ]
        result = _unique_values(tasks, "language")
        assert result == ["Python", "Rust"]

    def test_single_value(self):
        tasks = [_make_task(status="pass"), _make_task(status="pass")]
        assert _unique_values(tasks, "status") == ["pass"]

    def test_empty_list(self):
        assert _unique_values([], "status") == []
