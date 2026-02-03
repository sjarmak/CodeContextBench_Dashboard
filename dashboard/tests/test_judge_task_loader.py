"""Tests for judge_task_loader utility."""

import json
from pathlib import Path

import pytest

from dashboard.utils.judge_task_loader import (
    TaskInstanceData,
    extract_code_changes_from_trace,
    extract_tool_counts_from_trace,
    load_task_instance,
)


@pytest.fixture()
def task_dir(tmp_path):
    """Create a minimal task directory structure for testing."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()

    # config.json
    config = {"task": {"path": "benchmarks/locobench/tasks/python_web_3_arch_hard_v1"}}
    (tmp_path / "config.json").write_text(json.dumps(config))

    # result.json -- reward at top level (None falls through to verifier_result)
    result = {
        "task_name": "python_web_3_arch_hard_v1",
        "verifier_result": {"rewards": {"reward": 0.75}},
        "agent_result": {"n_input_tokens": 5000, "n_output_tokens": 1200, "n_cache_tokens": 300},
        "started_at": "2026-01-15T10:00:00Z",
        "finished_at": "2026-01-15T10:05:30Z",
    }
    (tmp_path / "result.json").write_text(json.dumps(result))

    # command.txt
    cmd_dir = agent_dir / "command-1"
    cmd_dir.mkdir()
    (cmd_dir / "command.txt").write_text("# Task\nAnalyze the architecture of the web app.\n---\nEnd")

    # solution.md
    (agent_dir / "solution.md").write_text("The architecture uses MVC pattern...")

    # claude-code.txt (JSONL trace)
    trace_records = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/app/main.py"}},
                    {"type": "tool_use", "name": "mcp__sourcegraph__search", "input": {"query": "controller"}},
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Found the architecture"},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/app/fix.py", "old_string": "old", "new_string": "new"}},
                ]
            },
        },
    ]
    trace_lines = [json.dumps(r) for r in trace_records]
    (agent_dir / "claude-code.txt").write_text("\n".join(trace_lines))

    return tmp_path


class TestLoadTaskInstance:
    def test_loads_basic_fields(self, task_dir):
        data = load_task_instance(task_dir)

        assert isinstance(data, TaskInstanceData)
        assert data.real_task_name == "python_web_3_arch_hard_v1"
        assert data.reward == 0.75
        assert data.input_tokens == 5000
        assert data.output_tokens == 1200
        assert "architecture" in data.task_description.lower() or "Task" in data.task_description

    def test_solution_type(self, task_dir):
        data = load_task_instance(task_dir)
        # Without oracle task_category, code changes from trace are preferred
        # when they exist (non-analysis path)
        assert data.solution_type in ("solution.md", "code changes (trace)")
        # The effective_solution should contain content from one source
        assert len(data.effective_solution) > 0

    def test_duration_computed(self, task_dir):
        data = load_task_instance(task_dir)
        assert data.duration is not None
        assert data.duration == pytest.approx(330.0, abs=1.0)

    def test_missing_config(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        data = load_task_instance(tmp_path)
        assert "config.json" in data.missing_files
        assert data.real_task_name == tmp_path.name

    def test_missing_result(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (tmp_path / "config.json").write_text('{"task": {"path": "x/y"}}')
        data = load_task_instance(tmp_path)
        assert "result.json" in data.missing_files
        assert data.reward == 0.0

    def test_missing_solution_and_trace(self, tmp_path):
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        data = load_task_instance(tmp_path)
        assert "solution.md" in data.missing_files
        assert "claude-code.txt" in data.missing_files
        assert data.solution_type == "none"

    def test_frozen_dataclass(self, task_dir):
        data = load_task_instance(task_dir)
        with pytest.raises(AttributeError):
            data.reward = 0.0  # type: ignore[misc]

    def test_reward_from_top_level(self, tmp_path):
        """Test reward extraction when reward is at top level (not in verifier_result)."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        result = {"reward": 1.0, "started_at": "", "finished_at": ""}
        (tmp_path / "result.json").write_text(json.dumps(result))
        data = load_task_instance(tmp_path)
        assert data.reward == 1.0

    def test_task_metrics_override(self, task_dir):
        """task_metrics.json should override agent_result token counts."""
        metrics = {"input_tokens": 9999, "output_tokens": 8888, "cache_creation_tokens": 100, "cache_read_tokens": 50}
        (task_dir / "task_metrics.json").write_text(json.dumps(metrics))
        data = load_task_instance(task_dir)
        assert data.input_tokens == 9999
        assert data.output_tokens == 8888
        assert data.cache_read_tokens == 50


class TestExtractCodeChanges:
    def test_extracts_edit_pattern(self, tmp_path):
        content = (
            '{"name":"Edit","input":{"file_path":"/app/main.py",'
            '"old_string":"foo","new_string":"bar"}}'
        )
        trace_file = tmp_path / "trace.txt"
        trace_file.write_text(content)

        result = extract_code_changes_from_trace(trace_file, max_chars=5000)
        assert "/app/main.py" in result
        assert "foo" in result
        assert "bar" in result

    def test_nonexistent_file(self, tmp_path):
        result = extract_code_changes_from_trace(tmp_path / "missing.txt")
        assert result == ""

    def test_no_edits_returns_raw(self, tmp_path):
        trace_file = tmp_path / "trace.txt"
        trace_file.write_text("just some text content")
        result = extract_code_changes_from_trace(trace_file)
        assert "just some text content" in result


class TestExtractToolCounts:
    def test_counts_tool_use_patterns(self):
        content = (
            '{"name":"Read","type":"tool_use"} '
            '{"name":"Read","type":"tool_use"} '
            '{"name":"Edit","type":"tool_use"} '
            '{"type":"tool_use","name":"mcp__sg__search"}'
        )
        counts = extract_tool_counts_from_trace(content)
        assert counts.get("Read", 0) >= 2
        assert counts.get("Edit", 0) >= 1
        assert counts.get("mcp__sg__search", 0) >= 1

    def test_empty_content(self):
        counts = extract_tool_counts_from_trace("")
        assert counts == {}
