"""
Tests for the JSONL trace viewer parser.

Verifies parsing of claude-code.txt JSONL files and
summary metrics computation.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.ingest.trace_viewer_parser import (
    TraceMessage,
    TraceSummary,
    TokenUsage,
    compute_summary,
    parse_trace,
)


# --- Sample JSONL data ---


def _system_init_line(
    session_id: str = "sess-001",
    model: str = "claude-opus-4-1",
    tools: list[str] | None = None,
) -> dict:
    return {
        "type": "system",
        "subtype": "init",
        "session_id": session_id,
        "model": model,
        "tools": tools or ["Bash", "Read", "Edit", "Write", "Grep", "Glob"],
        "uuid": "uuid-sys-001",
    }


def _assistant_text_line(
    text: str = "I'll help you with that.",
    uuid: str = "uuid-a-001",
    parent_uuid: str = "uuid-u-001",
    session_id: str = "sess-001",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> dict:
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        },
    }


def _assistant_tool_use_line(
    tool_name: str = "Bash",
    tool_input: dict | None = None,
    tool_id: str = "toolu_001",
    uuid: str = "uuid-a-002",
    parent_uuid: str = "uuid-u-001",
    session_id: str = "sess-001",
    input_tokens: int = 200,
    output_tokens: int = 10,
) -> dict:
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": tool_input or {"command": "ls -la"},
                }
            ],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }


def _user_tool_result_line(
    content: str = "file1.py\nfile2.py",
    uuid: str = "uuid-u-002",
    parent_uuid: str = "uuid-a-002",
    session_id: str = "sess-001",
) -> dict:
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "toolUseResult": {"content": content},
        "message": {"role": "user", "content": ""},
    }


def _user_text_line(
    text: str = "Please help me fix this bug.",
    uuid: str = "uuid-u-001",
    session_id: str = "sess-001",
) -> dict:
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": None,
        "message": {"role": "user", "content": text},
    }


def _queue_operation_line() -> dict:
    return {
        "type": "queue-operation",
        "operation": "dequeue",
        "timestamp": "2025-12-18T01:50:53.508Z",
        "sessionId": "sess-001",
    }


def _write_jsonl(tmp_dir: Path, lines: list[dict]) -> Path:
    """Write JSONL data to a temp file and return its path."""
    file_path = tmp_dir / "claude-code.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        for line_data in lines:
            f.write(json.dumps(line_data) + "\n")
    return file_path


# --- Parse Tests ---


class TestParseTrace:
    """Tests for the parse_trace function."""

    def test_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "claude-code.txt"
            path.write_text("")
            result = parse_trace(path)
            assert result == []

    def test_nonexistent_file(self) -> None:
        result = parse_trace("/nonexistent/path/claude-code.txt")
        assert result == []

    def test_system_init_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(Path(tmpdir), [_system_init_line()])
            result = parse_trace(path)

            assert len(result) == 1
            msg = result[0]
            assert msg.type == "system"
            assert msg.subtype == "init"
            assert "claude-opus-4-1" in msg.content
            assert msg.sequence_number == 0

    def test_assistant_text_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [_assistant_text_line(text="Hello world")],
            )
            result = parse_trace(path)

            assert len(result) == 1
            msg = result[0]
            assert msg.type == "assistant"
            assert msg.subtype == "text"
            assert msg.content == "Hello world"
            assert msg.token_usage is not None
            assert msg.token_usage.input_tokens == 100
            assert msg.token_usage.output_tokens == 50

    def test_assistant_tool_use_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _assistant_tool_use_line(
                        tool_name="Read",
                        tool_input={"file_path": "/workspace/main.py"},
                    )
                ],
            )
            result = parse_trace(path)

            assert len(result) == 1
            msg = result[0]
            assert msg.type == "assistant"
            assert msg.subtype == "tool_use"
            assert msg.tool_name == "Read"
            assert msg.tool_input == {"file_path": "/workspace/main.py"}
            assert msg.token_usage is not None

    def test_user_tool_result_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [_user_tool_result_line(content="result data")],
            )
            result = parse_trace(path)

            assert len(result) == 1
            msg = result[0]
            assert msg.type == "user"
            assert msg.subtype == "tool_result"
            assert msg.tool_result == "result data"

    def test_user_text_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [_user_text_line(text="Fix the bug")],
            )
            result = parse_trace(path)

            assert len(result) == 1
            msg = result[0]
            assert msg.type == "user"
            assert msg.subtype == "text"
            assert msg.content == "Fix the bug"

    def test_queue_operation_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(Path(tmpdir), [_queue_operation_line()])
            result = parse_trace(path)
            assert result == []

    def test_malformed_line_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "claude-code.txt"
            with open(file_path, "w") as f:
                f.write("not valid json{{{" + "\n")
                f.write(json.dumps(_assistant_text_line()) + "\n")
            result = parse_trace(file_path)
            assert len(result) == 1
            assert result[0].type == "assistant"

    def test_sequence_numbers_increment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _system_init_line(),
                    _user_text_line(),
                    _assistant_text_line(),
                    _assistant_tool_use_line(),
                    _user_tool_result_line(),
                ],
            )
            result = parse_trace(path)

            assert len(result) == 5
            for i, msg in enumerate(result):
                assert msg.sequence_number == i

    def test_mixed_content_blocks(self) -> None:
        """Assistant message with both text and tool_use blocks produces multiple messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "type": "assistant",
                "sessionId": "sess-001",
                "uuid": "uuid-mixed",
                "parentUuid": "uuid-parent",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check that file."},
                        {
                            "type": "tool_use",
                            "id": "toolu_mix",
                            "name": "Read",
                            "input": {"file_path": "/workspace/app.py"},
                        },
                    ],
                    "usage": {
                        "input_tokens": 500,
                        "output_tokens": 20,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                },
            }
            path = _write_jsonl(Path(tmpdir), [data])
            result = parse_trace(path)

            assert len(result) == 2
            assert result[0].subtype == "text"
            assert result[0].content == "Let me check that file."
            assert result[1].subtype == "tool_use"
            assert result[1].tool_name == "Read"

    def test_token_usage_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _assistant_text_line(
                        input_tokens=2349,
                        output_tokens=1,
                        cache_creation=18053,
                        cache_read=500,
                    )
                ],
            )
            result = parse_trace(path)

            assert len(result) == 1
            usage = result[0].token_usage
            assert usage is not None
            assert usage.input_tokens == 2349
            assert usage.output_tokens == 1
            assert usage.cache_creation_input_tokens == 18053
            assert usage.cache_read_input_tokens == 500

    def test_string_path_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(Path(tmpdir), [_system_init_line()])
            result = parse_trace(str(path))
            assert len(result) == 1

    def test_session_id_from_both_fields(self) -> None:
        """session_id can come from 'sessionId' or 'session_id' field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # System uses session_id
            sys_line = _system_init_line(session_id="sess-sys")
            # Assistant uses sessionId
            asst_line = _assistant_text_line(session_id="sess-asst")

            path = _write_jsonl(Path(tmpdir), [sys_line, asst_line])
            result = parse_trace(path)

            assert result[0].session_id == "sess-sys"
            assert result[1].session_id == "sess-asst"


# --- Summary Tests ---


class TestComputeSummary:
    """Tests for the compute_summary function."""

    def test_empty_messages(self) -> None:
        summary = compute_summary([])
        assert summary.total_messages == 0
        assert summary.total_tool_calls == 0
        assert summary.unique_tools == 0
        assert summary.total_tokens == 0
        assert summary.tools_by_name == {}
        assert summary.files_accessed == {}

    def test_counts_tool_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _assistant_tool_use_line(tool_name="Bash", uuid="u1"),
                    _user_tool_result_line(uuid="u2"),
                    _assistant_tool_use_line(tool_name="Read", uuid="u3",
                                            tool_input={"file_path": "/a.py"}),
                    _user_tool_result_line(uuid="u4"),
                    _assistant_tool_use_line(tool_name="Bash", uuid="u5"),
                    _user_tool_result_line(uuid="u6"),
                ],
            )
            messages = parse_trace(path)
            summary = compute_summary(messages)

            assert summary.total_tool_calls == 3
            assert summary.unique_tools == 2
            assert summary.tools_by_name["Bash"] == 2
            assert summary.tools_by_name["Read"] == 1

    def test_total_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _assistant_text_line(
                        uuid="u1",
                        input_tokens=100,
                        output_tokens=50,
                    ),
                    _assistant_tool_use_line(
                        uuid="u2",
                        input_tokens=200,
                        output_tokens=10,
                    ),
                ],
            )
            messages = parse_trace(path)
            summary = compute_summary(messages)

            assert summary.total_tokens == 360  # 100+50 + 200+10

    def test_deduplicates_token_usage_by_uuid(self) -> None:
        """Multiple TraceMessages from same assistant line share a uuid; tokens counted once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "type": "assistant",
                "sessionId": "sess-001",
                "uuid": "uuid-shared",
                "parentUuid": "p",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Checking..."},
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Read",
                            "input": {"file_path": "/x.py"},
                        },
                    ],
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 100,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                },
            }
            path = _write_jsonl(Path(tmpdir), [data])
            messages = parse_trace(path)
            summary = compute_summary(messages)

            # Both messages share uuid-shared, tokens counted once
            assert summary.total_tokens == 1100

    def test_file_access_tracking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _assistant_tool_use_line(
                        tool_name="Read",
                        tool_input={"file_path": "/workspace/main.py"},
                        uuid="u1",
                    ),
                    _user_tool_result_line(uuid="u2"),
                    _assistant_tool_use_line(
                        tool_name="Edit",
                        tool_input={
                            "file_path": "/workspace/main.py",
                            "old_string": "a",
                            "new_string": "b",
                        },
                        uuid="u3",
                    ),
                    _user_tool_result_line(uuid="u4"),
                    _assistant_tool_use_line(
                        tool_name="Write",
                        tool_input={
                            "file_path": "/workspace/new_file.py",
                            "content": "hello",
                        },
                        uuid="u5",
                    ),
                    _user_tool_result_line(uuid="u6"),
                    _assistant_tool_use_line(
                        tool_name="Read",
                        tool_input={"file_path": "/workspace/main.py"},
                        uuid="u7",
                    ),
                    _user_tool_result_line(uuid="u8"),
                ],
            )
            messages = parse_trace(path)
            summary = compute_summary(messages)

            assert "/workspace/main.py" in summary.files_accessed
            main_access = summary.files_accessed["/workspace/main.py"]
            assert main_access["read_count"] == 2
            assert main_access["edit_count"] == 1
            assert main_access["write_count"] == 0

            assert "/workspace/new_file.py" in summary.files_accessed
            new_access = summary.files_accessed["/workspace/new_file.py"]
            assert new_access["write_count"] == 1
            assert new_access["read_count"] == 0

    def test_tools_sorted_by_count_descending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = []
            for tool, count in [("Bash", 5), ("Read", 3), ("Edit", 1)]:
                for i in range(count):
                    lines.append(
                        _assistant_tool_use_line(
                            tool_name=tool, uuid=f"u-{tool}-{i}"
                        )
                    )
                    lines.append(_user_tool_result_line(uuid=f"ur-{tool}-{i}"))

            path = _write_jsonl(Path(tmpdir), lines)
            messages = parse_trace(path)
            summary = compute_summary(messages)

            tool_names = list(summary.tools_by_name.keys())
            assert tool_names == ["Bash", "Read", "Edit"]

    def test_files_sorted_by_total_access_descending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = [
                # /a.py: 3 reads
                _assistant_tool_use_line(
                    tool_name="Read",
                    tool_input={"file_path": "/a.py"},
                    uuid="u1",
                ),
                _assistant_tool_use_line(
                    tool_name="Read",
                    tool_input={"file_path": "/a.py"},
                    uuid="u2",
                ),
                _assistant_tool_use_line(
                    tool_name="Read",
                    tool_input={"file_path": "/a.py"},
                    uuid="u3",
                ),
                # /b.py: 1 read
                _assistant_tool_use_line(
                    tool_name="Read",
                    tool_input={"file_path": "/b.py"},
                    uuid="u4",
                ),
            ]
            path = _write_jsonl(Path(tmpdir), lines)
            messages = parse_trace(path)
            summary = compute_summary(messages)

            file_paths = list(summary.files_accessed.keys())
            assert file_paths[0] == "/a.py"
            assert file_paths[1] == "/b.py"

    def test_total_messages_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_jsonl(
                Path(tmpdir),
                [
                    _system_init_line(),
                    _user_text_line(),
                    _assistant_text_line(uuid="u1"),
                    _assistant_tool_use_line(uuid="u2"),
                    _user_tool_result_line(uuid="u3"),
                ],
            )
            messages = parse_trace(path)
            summary = compute_summary(messages)

            assert summary.total_messages == 5


# --- Integration Test with Real-like Trace ---


class TestIntegrationTrace:
    """Integration test with a realistic trace sequence."""

    def test_full_trace_scenario(self) -> None:
        """Simulate a realistic agent session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = [
                _queue_operation_line(),
                _system_init_line(session_id="sess-full", model="claude-opus-4-1"),
                _user_text_line(
                    text="Fix the bug in main.py",
                    uuid="uuid-u1",
                    session_id="sess-full",
                ),
                _assistant_text_line(
                    text="Let me read the file first.",
                    uuid="uuid-a1",
                    parent_uuid="uuid-u1",
                    session_id="sess-full",
                    input_tokens=500,
                    output_tokens=20,
                ),
                _assistant_tool_use_line(
                    tool_name="Read",
                    tool_input={"file_path": "/workspace/main.py"},
                    uuid="uuid-a2",
                    parent_uuid="uuid-a1",
                    session_id="sess-full",
                    input_tokens=600,
                    output_tokens=5,
                ),
                _user_tool_result_line(
                    content="def main():\n    print('hello')\n",
                    uuid="uuid-u2",
                    parent_uuid="uuid-a2",
                    session_id="sess-full",
                ),
                _assistant_tool_use_line(
                    tool_name="Edit",
                    tool_input={
                        "file_path": "/workspace/main.py",
                        "old_string": "print('hello')",
                        "new_string": "print('world')",
                    },
                    uuid="uuid-a3",
                    parent_uuid="uuid-u2",
                    session_id="sess-full",
                    input_tokens=700,
                    output_tokens=10,
                ),
                _user_tool_result_line(
                    content="",
                    uuid="uuid-u3",
                    parent_uuid="uuid-a3",
                    session_id="sess-full",
                ),
                _assistant_text_line(
                    text="Done! The bug is fixed.",
                    uuid="uuid-a4",
                    parent_uuid="uuid-u3",
                    session_id="sess-full",
                    input_tokens=800,
                    output_tokens=15,
                ),
            ]

            path = _write_jsonl(Path(tmpdir), lines)
            messages = parse_trace(path)

            # Queue operation is skipped
            assert len(messages) == 8

            # Check system init
            assert messages[0].type == "system"
            assert messages[0].subtype == "init"

            # Check user prompt
            assert messages[1].type == "user"
            assert messages[1].content == "Fix the bug in main.py"

            # Check tool calls
            tool_uses = [m for m in messages if m.subtype == "tool_use"]
            assert len(tool_uses) == 2
            assert tool_uses[0].tool_name == "Read"
            assert tool_uses[1].tool_name == "Edit"

            # Compute summary
            summary = compute_summary(messages)
            assert summary.total_tool_calls == 2
            assert summary.unique_tools == 2
            assert summary.total_tokens == 2650  # 520 + 605 + 710 + 815
            assert summary.tools_by_name == {"Edit": 1, "Read": 1}
            assert "/workspace/main.py" in summary.files_accessed
            assert summary.files_accessed["/workspace/main.py"]["read_count"] == 1
            assert summary.files_accessed["/workspace/main.py"]["edit_count"] == 1
