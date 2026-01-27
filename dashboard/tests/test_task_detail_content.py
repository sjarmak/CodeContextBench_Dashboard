"""
Tests for CLAUDE.md and task prompt extraction in the task detail panel.

Verifies extraction from various file locations and graceful fallbacks
when content is not available.
"""

import json
import pytest
from pathlib import Path
import tempfile

from dashboard.utils.task_detail import (
    _extract_claude_md_content,
    _extract_task_prompt,
    _parse_system_prompt_from_jsonl,
    _extract_prompt_from_config,
)


@pytest.fixture
def temp_instance_dir():
    """Create a temporary instance directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _write_json(path: Path, data: dict) -> None:
    """Helper to write JSON to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _write_text(path: Path, content: str) -> None:
    """Helper to write text to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# ── _extract_claude_md_content ──────────────────────────────


class TestExtractClaudeMdContent:
    """Tests for CLAUDE.md content extraction."""

    def test_returns_none_when_no_instance_dir(self) -> None:
        assert _extract_claude_md_content(None) is None

    def test_returns_none_when_dir_does_not_exist(self) -> None:
        assert _extract_claude_md_content(Path("/nonexistent/path")) is None

    def test_extracts_from_agent_claude_json(
        self, temp_instance_dir: Path
    ) -> None:
        claude_json = temp_instance_dir / "agent" / ".claude.json"
        _write_json(claude_json, {"claudeMd": "# Agent Config\nSome rules."})
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "# Agent Config\nSome rules."

    def test_extracts_from_sessions_claude_json(
        self, temp_instance_dir: Path
    ) -> None:
        sessions_json = temp_instance_dir / "sessions" / ".claude.json"
        _write_json(sessions_json, {"claudeMd": "# Session Config"})
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "# Session Config"

    def test_agent_claude_json_takes_priority(
        self, temp_instance_dir: Path
    ) -> None:
        agent_json = temp_instance_dir / "agent" / ".claude.json"
        _write_json(agent_json, {"claudeMd": "Agent version"})
        sessions_json = temp_instance_dir / "sessions" / ".claude.json"
        _write_json(sessions_json, {"claudeMd": "Session version"})
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "Agent version"

    def test_skips_empty_claude_md_in_json(
        self, temp_instance_dir: Path
    ) -> None:
        agent_json = temp_instance_dir / "agent" / ".claude.json"
        _write_json(agent_json, {"claudeMd": ""})
        # Should fall through to next location
        _write_text(
            temp_instance_dir / "CLAUDE.md", "# Fallback"
        )
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "# Fallback"

    def test_extracts_from_instance_dir_claude_md(
        self, temp_instance_dir: Path
    ) -> None:
        _write_text(temp_instance_dir / "CLAUDE.md", "# Project CLAUDE.md")
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "# Project CLAUDE.md"

    def test_extracts_from_agent_claude_md(
        self, temp_instance_dir: Path
    ) -> None:
        _write_text(
            temp_instance_dir / "agent" / "CLAUDE.md",
            "# Agent CLAUDE.md",
        )
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "# Agent CLAUDE.md"

    def test_instance_dir_claude_md_before_agent(
        self, temp_instance_dir: Path
    ) -> None:
        _write_text(
            temp_instance_dir / "CLAUDE.md", "Instance version"
        )
        _write_text(
            temp_instance_dir / "agent" / "CLAUDE.md",
            "Agent version",
        )
        result = _extract_claude_md_content(temp_instance_dir)
        assert result == "Instance version"

    def test_extracts_from_parent_directory(
        self, temp_instance_dir: Path
    ) -> None:
        # Create a subdirectory to use as instance_dir
        sub_dir = temp_instance_dir / "tasks" / "task_001"
        sub_dir.mkdir(parents=True)
        _write_text(
            temp_instance_dir / "CLAUDE.md", "# Parent CLAUDE.md"
        )
        result = _extract_claude_md_content(sub_dir)
        assert result == "# Parent CLAUDE.md"

    def test_returns_none_when_no_claude_md_found(
        self, temp_instance_dir: Path
    ) -> None:
        # Empty directory with no CLAUDE.md anywhere
        result = _extract_claude_md_content(temp_instance_dir)
        assert result is None

    def test_handles_malformed_claude_json(
        self, temp_instance_dir: Path
    ) -> None:
        agent_dir = temp_instance_dir / "agent"
        agent_dir.mkdir(parents=True)
        # Write invalid JSON
        with open(agent_dir / ".claude.json", "w") as f:
            f.write("not valid json{{{")
        result = _extract_claude_md_content(temp_instance_dir)
        assert result is None

    def test_claude_json_without_claudemd_key(
        self, temp_instance_dir: Path
    ) -> None:
        agent_json = temp_instance_dir / "agent" / ".claude.json"
        _write_json(agent_json, {"someOtherKey": "value"})
        result = _extract_claude_md_content(temp_instance_dir)
        assert result is None


# ── _parse_system_prompt_from_jsonl ─────────────────────────


class TestParseSystemPromptFromJsonl:
    """Tests for system prompt extraction from JSONL trace files."""

    def test_extracts_system_message_string_content(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": "You are a coding assistant."},
            }),
            json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result == "You are a coding assistant."

    def test_extracts_system_message_list_content(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        content_list = [
            {"type": "text", "text": "System instructions."},
            {"type": "text", "text": "Additional context."},
        ]
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": content_list},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result == "System instructions.\nAdditional context."

    def test_extracts_system_message_with_string_items(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": ["Part 1", "Part 2"]},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result == "Part 1\nPart 2"

    def test_returns_none_when_no_system_message(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result is None

    def test_returns_none_for_empty_file(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        _write_text(trace_file, "")
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result is None

    def test_skips_malformed_lines(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            "not valid json",
            json.dumps({
                "type": "system",
                "message": {"content": "Found after malformed line."},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result == "Found after malformed line."

    def test_returns_none_for_nonexistent_file(self) -> None:
        result = _parse_system_prompt_from_jsonl(
            Path("/nonexistent/trace.jsonl")
        )
        assert result is None

    def test_returns_none_for_empty_system_content(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": ""},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result is None

    def test_returns_none_for_empty_list_content(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "trace.jsonl"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": []},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _parse_system_prompt_from_jsonl(trace_file)
        assert result is None


# ── _extract_prompt_from_config ─────────────────────────────


class TestExtractPromptFromConfig:
    """Tests for prompt extraction from config dicts."""

    def test_extracts_problem_statement(self) -> None:
        config = {"problem_statement": "Fix the login bug."}
        assert _extract_prompt_from_config(config) == "Fix the login bug."

    def test_extracts_task_instruction(self) -> None:
        config = {"task": {"instruction": "Refactor the auth module."}}
        result = _extract_prompt_from_config(config)
        assert result == "Refactor the auth module."

    def test_extracts_task_prompt(self) -> None:
        config = {"task": {"prompt": "Add dark mode support."}}
        result = _extract_prompt_from_config(config)
        assert result == "Add dark mode support."

    def test_extracts_direct_instruction(self) -> None:
        config = {"instruction": "Run the test suite."}
        assert _extract_prompt_from_config(config) == "Run the test suite."

    def test_extracts_direct_prompt(self) -> None:
        config = {"prompt": "Fix the typo in README."}
        assert _extract_prompt_from_config(config) == "Fix the typo in README."

    def test_problem_statement_takes_priority(self) -> None:
        config = {
            "problem_statement": "Priority",
            "task": {"instruction": "Lower priority"},
            "prompt": "Lowest priority",
        }
        assert _extract_prompt_from_config(config) == "Priority"

    def test_returns_none_for_empty_config(self) -> None:
        assert _extract_prompt_from_config({}) is None

    def test_returns_none_for_non_dict(self) -> None:
        assert _extract_prompt_from_config("not a dict") is None

    def test_ignores_non_string_problem_statement(self) -> None:
        config = {"problem_statement": 42}
        assert _extract_prompt_from_config(config) is None

    def test_ignores_empty_string_fields(self) -> None:
        config = {"problem_statement": "", "instruction": ""}
        assert _extract_prompt_from_config(config) is None


# ── _extract_task_prompt (integration) ──────────────────────


class TestExtractTaskPrompt:
    """Integration tests for full task prompt extraction."""

    def test_extracts_from_claude_code_txt(
        self, temp_instance_dir: Path
    ) -> None:
        trace_file = temp_instance_dir / "agent" / "claude-code.txt"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": "System prompt from trace."},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        result = _extract_task_prompt(temp_instance_dir, {})
        assert result == "System prompt from trace."

    def test_falls_back_to_config_json(
        self, temp_instance_dir: Path
    ) -> None:
        config_path = temp_instance_dir / "config.json"
        _write_json(config_path, {
            "problem_statement": "Config problem statement."
        })
        result = _extract_task_prompt(temp_instance_dir, {})
        assert result == "Config problem statement."

    def test_falls_back_to_tests_config_json(
        self, temp_instance_dir: Path
    ) -> None:
        tests_config = temp_instance_dir / "tests" / "config.json"
        _write_json(tests_config, {
            "problem_statement": "Tests config problem."
        })
        result = _extract_task_prompt(temp_instance_dir, {})
        assert result == "Tests config problem."

    def test_falls_back_to_result_data(
        self, temp_instance_dir: Path
    ) -> None:
        result_data = {"problem_statement": "From result data."}
        result = _extract_task_prompt(temp_instance_dir, result_data)
        assert result == "From result data."

    def test_claude_code_txt_takes_priority(
        self, temp_instance_dir: Path
    ) -> None:
        # Write both trace and config
        trace_file = temp_instance_dir / "agent" / "claude-code.txt"
        lines = [
            json.dumps({
                "type": "system",
                "message": {"content": "Trace prompt."},
            }),
        ]
        _write_text(trace_file, "\n".join(lines))
        config_path = temp_instance_dir / "config.json"
        _write_json(config_path, {
            "problem_statement": "Config prompt."
        })
        result = _extract_task_prompt(temp_instance_dir, {})
        assert result == "Trace prompt."

    def test_returns_none_when_nothing_available(
        self, temp_instance_dir: Path
    ) -> None:
        result = _extract_task_prompt(temp_instance_dir, {})
        assert result is None

    def test_returns_from_result_data_when_no_instance_dir(self) -> None:
        result_data = {"problem_statement": "Fallback."}
        result = _extract_task_prompt(None, result_data)
        assert result == "Fallback."

    def test_returns_none_for_nonexistent_instance_dir(self) -> None:
        result = _extract_task_prompt(Path("/nonexistent"), {})
        assert result is None
