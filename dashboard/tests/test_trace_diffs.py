"""Tests for trace diff extraction utility."""

import pytest

from dashboard.utils.trace_diffs import (
    FileOperation,
    _build_read_result_map,
    _extract_edit_operation,
    _extract_read_operation,
    _extract_write_operation,
    _link_read_results,
    extract_file_operations,
)
from src.ingest.trace_viewer_parser import TraceMessage


def _make_tool_use_msg(
    tool_name: str,
    tool_input: dict | None,
    sequence_number: int = 0,
    parent_tool_use_id: str = "",
) -> TraceMessage:
    """Create a tool_use TraceMessage for testing."""
    return TraceMessage(
        type="assistant",
        subtype="tool_use",
        content="",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result="",
        token_usage=None,
        parent_tool_use_id=parent_tool_use_id or f"tool_{sequence_number}",
        session_id="test-session",
        uuid=f"uuid-{sequence_number}",
        sequence_number=sequence_number,
    )


def _make_tool_result_msg(
    parent_tool_use_id: str,
    tool_result: str,
    sequence_number: int = 0,
) -> TraceMessage:
    """Create a tool_result TraceMessage for testing."""
    return TraceMessage(
        type="user",
        subtype="tool_result",
        content="",
        tool_name="",
        tool_input=None,
        tool_result=tool_result,
        token_usage=None,
        parent_tool_use_id=parent_tool_use_id,
        session_id="test-session",
        uuid=f"uuid-result-{sequence_number}",
        sequence_number=sequence_number,
    )


def _make_text_msg(
    msg_type: str = "assistant",
    content: str = "Hello",
    sequence_number: int = 0,
) -> TraceMessage:
    """Create a text TraceMessage for testing."""
    return TraceMessage(
        type=msg_type,
        subtype="text",
        content=content,
        tool_name="",
        tool_input=None,
        tool_result="",
        token_usage=None,
        parent_tool_use_id="",
        session_id="test-session",
        uuid=f"uuid-text-{sequence_number}",
        sequence_number=sequence_number,
    )


# ---- _extract_read_operation tests ----


class TestExtractReadOperation:
    def test_extracts_file_path(self):
        msg = _make_tool_use_msg("Read", {"file_path": "/src/main.py"}, 5)
        result = _extract_read_operation(msg)
        assert result is not None
        assert result.operation == "Read"
        assert result.file_path == "/src/main.py"
        assert result.sequence_number == 5

    def test_read_has_empty_strings(self):
        msg = _make_tool_use_msg("Read", {"file_path": "/src/main.py"}, 3)
        result = _extract_read_operation(msg)
        assert result is not None
        assert result.old_string == ""
        assert result.new_string == ""
        assert result.full_content == ""

    def test_returns_none_for_no_input(self):
        msg = _make_tool_use_msg("Read", None, 0)
        result = _extract_read_operation(msg)
        assert result is None

    def test_returns_none_for_empty_file_path(self):
        msg = _make_tool_use_msg("Read", {"file_path": ""}, 0)
        result = _extract_read_operation(msg)
        assert result is None

    def test_returns_none_for_missing_file_path(self):
        msg = _make_tool_use_msg("Read", {"other": "value"}, 0)
        result = _extract_read_operation(msg)
        assert result is None


# ---- _extract_edit_operation tests ----


class TestExtractEditOperation:
    def test_extracts_old_and_new_strings(self):
        msg = _make_tool_use_msg(
            "Edit",
            {
                "file_path": "/src/utils.py",
                "old_string": "def foo():",
                "new_string": "def bar():",
            },
            10,
        )
        result = _extract_edit_operation(msg)
        assert result is not None
        assert result.operation == "Edit"
        assert result.file_path == "/src/utils.py"
        assert result.old_string == "def foo():"
        assert result.new_string == "def bar():"
        assert result.full_content == ""
        assert result.sequence_number == 10

    def test_handles_missing_old_string(self):
        msg = _make_tool_use_msg(
            "Edit",
            {"file_path": "/src/x.py", "new_string": "new code"},
            0,
        )
        result = _extract_edit_operation(msg)
        assert result is not None
        assert result.old_string == ""
        assert result.new_string == "new code"

    def test_handles_missing_new_string(self):
        msg = _make_tool_use_msg(
            "Edit",
            {"file_path": "/src/x.py", "old_string": "old code"},
            0,
        )
        result = _extract_edit_operation(msg)
        assert result is not None
        assert result.old_string == "old code"
        assert result.new_string == ""

    def test_returns_none_for_no_input(self):
        msg = _make_tool_use_msg("Edit", None, 0)
        result = _extract_edit_operation(msg)
        assert result is None

    def test_returns_none_for_empty_file_path(self):
        msg = _make_tool_use_msg(
            "Edit",
            {"file_path": "", "old_string": "x", "new_string": "y"},
            0,
        )
        result = _extract_edit_operation(msg)
        assert result is None


# ---- _extract_write_operation tests ----


class TestExtractWriteOperation:
    def test_extracts_content(self):
        msg = _make_tool_use_msg(
            "Write",
            {"file_path": "/src/new_file.py", "content": "print('hello')"},
            7,
        )
        result = _extract_write_operation(msg)
        assert result is not None
        assert result.operation == "Write"
        assert result.file_path == "/src/new_file.py"
        assert result.full_content == "print('hello')"
        assert result.old_string == ""
        assert result.new_string == ""
        assert result.sequence_number == 7

    def test_handles_missing_content(self):
        msg = _make_tool_use_msg(
            "Write",
            {"file_path": "/src/empty.py"},
            0,
        )
        result = _extract_write_operation(msg)
        assert result is not None
        assert result.full_content == ""

    def test_returns_none_for_no_input(self):
        msg = _make_tool_use_msg("Write", None, 0)
        result = _extract_write_operation(msg)
        assert result is None

    def test_returns_none_for_empty_file_path(self):
        msg = _make_tool_use_msg(
            "Write",
            {"file_path": "", "content": "something"},
            0,
        )
        result = _extract_write_operation(msg)
        assert result is None


# ---- _build_read_result_map tests ----


class TestBuildReadResultMap:
    def test_maps_parent_id_to_result(self):
        messages = [
            _make_tool_result_msg("tool_1", "file content here", 2),
        ]
        result = _build_read_result_map(messages)
        assert result == {"tool_1": "file content here"}

    def test_multiple_results(self):
        messages = [
            _make_tool_result_msg("tool_1", "content A", 2),
            _make_tool_result_msg("tool_2", "content B", 4),
        ]
        result = _build_read_result_map(messages)
        assert result == {"tool_1": "content A", "tool_2": "content B"}

    def test_ignores_non_tool_result_messages(self):
        messages = [
            _make_text_msg("assistant", "thinking...", 0),
            _make_tool_result_msg("tool_1", "content", 2),
        ]
        result = _build_read_result_map(messages)
        assert result == {"tool_1": "content"}

    def test_uses_content_when_tool_result_empty(self):
        msg = TraceMessage(
            type="user",
            subtype="tool_result",
            content="fallback content",
            tool_name="",
            tool_input=None,
            tool_result="",
            token_usage=None,
            parent_tool_use_id="tool_1",
            session_id="test",
            uuid="u1",
            sequence_number=1,
        )
        result = _build_read_result_map([msg])
        assert result == {"tool_1": "fallback content"}

    def test_empty_messages(self):
        result = _build_read_result_map([])
        assert result == {}

    def test_skips_messages_without_parent_id(self):
        msg = TraceMessage(
            type="user",
            subtype="tool_result",
            content="",
            tool_name="",
            tool_input=None,
            tool_result="content",
            token_usage=None,
            parent_tool_use_id="",
            session_id="test",
            uuid="u1",
            sequence_number=1,
        )
        result = _build_read_result_map([msg])
        assert result == {}


# ---- _link_read_results tests ----


class TestLinkReadResults:
    def test_links_read_content(self):
        read_msg = _make_tool_use_msg("Read", {"file_path": "/a.py"}, 0, "tool_0")
        result_msg = _make_tool_result_msg("tool_0", "def hello(): pass", 1)

        op = FileOperation(
            operation="Read",
            file_path="/a.py",
            old_string="",
            new_string="",
            full_content="",
            sequence_number=0,
        )

        linked = _link_read_results([op], [read_msg, result_msg])
        assert len(linked) == 1
        assert linked[0].full_content == "def hello(): pass"

    def test_preserves_non_read_operations(self):
        edit_op = FileOperation(
            operation="Edit",
            file_path="/b.py",
            old_string="old",
            new_string="new",
            full_content="",
            sequence_number=5,
        )
        linked = _link_read_results([edit_op], [])
        assert len(linked) == 1
        assert linked[0] == edit_op

    def test_handles_missing_result(self):
        read_msg = _make_tool_use_msg("Read", {"file_path": "/a.py"}, 0, "tool_0")

        op = FileOperation(
            operation="Read",
            file_path="/a.py",
            old_string="",
            new_string="",
            full_content="",
            sequence_number=0,
        )

        linked = _link_read_results([op], [read_msg])
        assert len(linked) == 1
        assert linked[0].full_content == ""


# ---- extract_file_operations tests (integration) ----


class TestExtractFileOperations:
    def test_empty_messages(self):
        result = extract_file_operations([])
        assert result == {}

    def test_ignores_non_file_tools(self):
        messages = [
            _make_tool_use_msg("Bash", {"command": "ls"}, 0),
            _make_tool_use_msg("Grep", {"pattern": "foo"}, 1),
        ]
        result = extract_file_operations(messages)
        assert result == {}

    def test_ignores_non_tool_use_messages(self):
        messages = [
            _make_text_msg("assistant", "thinking...", 0),
            _make_text_msg("user", "do something", 1),
        ]
        result = extract_file_operations(messages)
        assert result == {}

    def test_single_read(self):
        messages = [
            _make_tool_use_msg("Read", {"file_path": "/src/a.py"}, 0, "tool_0"),
            _make_tool_result_msg("tool_0", "content of a.py", 1),
        ]
        result = extract_file_operations(messages)
        assert "/src/a.py" in result
        assert len(result["/src/a.py"]) == 1
        op = result["/src/a.py"][0]
        assert op.operation == "Read"
        assert op.full_content == "content of a.py"

    def test_single_edit(self):
        messages = [
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/src/b.py",
                    "old_string": "foo",
                    "new_string": "bar",
                },
                0,
            ),
        ]
        result = extract_file_operations(messages)
        assert "/src/b.py" in result
        assert len(result["/src/b.py"]) == 1
        op = result["/src/b.py"][0]
        assert op.operation == "Edit"
        assert op.old_string == "foo"
        assert op.new_string == "bar"

    def test_single_write(self):
        messages = [
            _make_tool_use_msg(
                "Write",
                {"file_path": "/src/c.py", "content": "new file content"},
                0,
            ),
        ]
        result = extract_file_operations(messages)
        assert "/src/c.py" in result
        assert len(result["/src/c.py"]) == 1
        op = result["/src/c.py"][0]
        assert op.operation == "Write"
        assert op.full_content == "new file content"

    def test_multiple_operations_same_file(self):
        messages = [
            _make_tool_use_msg("Read", {"file_path": "/src/d.py"}, 0, "tool_0"),
            _make_tool_result_msg("tool_0", "original content", 1),
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/src/d.py",
                    "old_string": "original",
                    "new_string": "modified",
                },
                2,
            ),
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/src/d.py",
                    "old_string": "content",
                    "new_string": "code",
                },
                4,
            ),
        ]
        result = extract_file_operations(messages)
        assert "/src/d.py" in result
        ops = result["/src/d.py"]
        assert len(ops) == 3
        assert ops[0].operation == "Read"
        assert ops[0].full_content == "original content"
        assert ops[1].operation == "Edit"
        assert ops[1].old_string == "original"
        assert ops[2].operation == "Edit"
        assert ops[2].old_string == "content"

    def test_multiple_files(self):
        messages = [
            _make_tool_use_msg("Read", {"file_path": "/a.py"}, 0, "tool_0"),
            _make_tool_result_msg("tool_0", "a content", 1),
            _make_tool_use_msg(
                "Edit",
                {"file_path": "/b.py", "old_string": "x", "new_string": "y"},
                2,
            ),
            _make_tool_use_msg(
                "Write",
                {"file_path": "/c.py", "content": "new file"},
                3,
            ),
        ]
        result = extract_file_operations(messages)
        assert len(result) == 3
        assert "/a.py" in result
        assert "/b.py" in result
        assert "/c.py" in result

    def test_operations_sorted_by_sequence_number(self):
        messages = [
            _make_tool_use_msg(
                "Edit",
                {"file_path": "/e.py", "old_string": "c", "new_string": "d"},
                10,
            ),
            _make_tool_use_msg("Read", {"file_path": "/e.py"}, 2, "tool_2"),
            _make_tool_result_msg("tool_2", "baseline", 3),
            _make_tool_use_msg(
                "Edit",
                {"file_path": "/e.py", "old_string": "a", "new_string": "b"},
                5,
            ),
        ]
        result = extract_file_operations(messages)
        ops = result["/e.py"]
        assert len(ops) == 3
        assert ops[0].sequence_number == 2
        assert ops[1].sequence_number == 5
        assert ops[2].sequence_number == 10

    def test_mixed_tools_only_extracts_file_ops(self):
        messages = [
            _make_tool_use_msg("Bash", {"command": "ls"}, 0),
            _make_tool_use_msg("Read", {"file_path": "/f.py"}, 1, "tool_1"),
            _make_tool_result_msg("tool_1", "content", 2),
            _make_tool_use_msg("Grep", {"pattern": "foo"}, 3),
            _make_tool_use_msg(
                "Edit",
                {"file_path": "/f.py", "old_string": "a", "new_string": "b"},
                4,
            ),
            _make_tool_use_msg("Glob", {"pattern": "*.py"}, 5),
        ]
        result = extract_file_operations(messages)
        assert len(result) == 1
        assert "/f.py" in result
        assert len(result["/f.py"]) == 2

    def test_read_write_edit_sequence(self):
        """Full workflow: read baseline, write new file, edit the file."""
        messages = [
            _make_tool_use_msg("Read", {"file_path": "/g.py"}, 0, "tool_0"),
            _make_tool_result_msg("tool_0", "def hello():\n    pass", 1),
            _make_tool_use_msg(
                "Write",
                {
                    "file_path": "/g.py",
                    "content": "def hello():\n    print('hi')\n",
                },
                2,
            ),
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/g.py",
                    "old_string": "print('hi')",
                    "new_string": "print('hello world')",
                },
                4,
            ),
        ]
        result = extract_file_operations(messages)
        ops = result["/g.py"]
        assert len(ops) == 3
        assert ops[0].operation == "Read"
        assert ops[0].full_content == "def hello():\n    pass"
        assert ops[1].operation == "Write"
        assert ops[1].full_content == "def hello():\n    print('hi')\n"
        assert ops[2].operation == "Edit"
        assert ops[2].old_string == "print('hi')"
        assert ops[2].new_string == "print('hello world')"

    def test_skips_tool_use_with_missing_file_path(self):
        messages = [
            _make_tool_use_msg("Read", {"other": "value"}, 0),
            _make_tool_use_msg("Edit", {"old_string": "x", "new_string": "y"}, 1),
            _make_tool_use_msg("Write", {"content": "stuff"}, 2),
        ]
        result = extract_file_operations(messages)
        assert result == {}

    def test_handles_none_tool_input(self):
        messages = [
            _make_tool_use_msg("Read", None, 0),
            _make_tool_use_msg("Edit", None, 1),
            _make_tool_use_msg("Write", None, 2),
        ]
        result = extract_file_operations(messages)
        assert result == {}

    def test_file_operation_is_frozen(self):
        op = FileOperation(
            operation="Read",
            file_path="/a.py",
            old_string="",
            new_string="",
            full_content="content",
            sequence_number=0,
        )
        with pytest.raises(AttributeError):
            op.file_path = "/b.py"  # type: ignore[misc]

    def test_complex_multifile_trace(self):
        """Simulate a realistic trace with multiple files and interleaved operations."""
        messages = [
            # Agent reads config
            _make_text_msg("assistant", "Let me check the config", 0),
            _make_tool_use_msg(
                "Read", {"file_path": "/config.json"}, 1, "tool_1"
            ),
            _make_tool_result_msg("tool_1", '{"key": "value"}', 2),
            # Agent reads source file
            _make_tool_use_msg(
                "Read", {"file_path": "/src/main.py"}, 3, "tool_3"
            ),
            _make_tool_result_msg("tool_3", "import os\ndef main(): pass", 4),
            # Agent searches (not a file op)
            _make_tool_use_msg("Grep", {"pattern": "TODO"}, 5),
            # Agent edits the source file
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/src/main.py",
                    "old_string": "def main(): pass",
                    "new_string": "def main():\n    print('hello')",
                },
                6,
            ),
            # Agent creates a new test file
            _make_tool_use_msg(
                "Write",
                {
                    "file_path": "/tests/test_main.py",
                    "content": "def test_main():\n    assert True",
                },
                8,
            ),
            # Agent edits config
            _make_tool_use_msg(
                "Edit",
                {
                    "file_path": "/config.json",
                    "old_string": '"value"',
                    "new_string": '"new_value"',
                },
                10,
            ),
        ]
        result = extract_file_operations(messages)

        # 3 files accessed
        assert len(result) == 3

        # config.json: read + edit
        config_ops = result["/config.json"]
        assert len(config_ops) == 2
        assert config_ops[0].operation == "Read"
        assert config_ops[0].full_content == '{"key": "value"}'
        assert config_ops[1].operation == "Edit"
        assert config_ops[1].old_string == '"value"'

        # src/main.py: read + edit
        main_ops = result["/src/main.py"]
        assert len(main_ops) == 2
        assert main_ops[0].operation == "Read"
        assert main_ops[0].full_content == "import os\ndef main(): pass"
        assert main_ops[1].operation == "Edit"

        # tests/test_main.py: write
        test_ops = result["/tests/test_main.py"]
        assert len(test_ops) == 1
        assert test_ops[0].operation == "Write"
        assert test_ops[0].full_content == "def test_main():\n    assert True"
