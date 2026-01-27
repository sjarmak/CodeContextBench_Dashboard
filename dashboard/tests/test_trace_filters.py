"""Tests for dashboard/utils/trace_filters.py - Trace search and type filtering (US-012)."""

from unittest.mock import MagicMock, patch

from src.ingest.trace_viewer_parser import TraceMessage

from dashboard.utils.trace_filters import (
    MESSAGE_TYPE_OPTIONS,
    TraceFilterState,
    _is_result_for_tool,
    _message_matches_search,
    extract_unique_tool_names,
    filter_messages,
    render_trace_filter_controls,
)


# -- Fixtures --


def _make_msg(
    msg_type: str = "assistant",
    subtype: str = "text",
    content: str = "Hello world",
    tool_name: str = "",
    tool_input: dict | None = None,
    tool_result: str = "",
    parent_tool_use_id: str = "",
    session_id: str = "sess-001",
    uuid: str = "uuid-001",
    sequence_number: int = 0,
) -> TraceMessage:
    """Helper to create a TraceMessage with defaults."""
    return TraceMessage(
        type=msg_type,
        subtype=subtype,
        content=content,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result=tool_result,
        token_usage=None,
        parent_tool_use_id=parent_tool_use_id,
        session_id=session_id,
        uuid=uuid,
        sequence_number=sequence_number,
    )


def _make_filter(
    search_text: str = "",
    selected_types: tuple[str, ...] = (),
    selected_tool: str = "",
    hide_tool_results: bool = False,
) -> TraceFilterState:
    """Helper to create a TraceFilterState with defaults."""
    return TraceFilterState(
        search_text=search_text,
        selected_types=selected_types,
        selected_tool=selected_tool,
        hide_tool_results=hide_tool_results,
    )


def _sample_messages() -> list[TraceMessage]:
    """Create a representative set of trace messages for testing."""
    return [
        _make_msg(
            msg_type="system",
            subtype="init",
            content="Model: claude-3-5-sonnet\nTools: Read, Write",
            sequence_number=0,
        ),
        _make_msg(
            msg_type="assistant",
            subtype="text",
            content="I'll read the file for you.",
            sequence_number=1,
        ),
        _make_msg(
            msg_type="assistant",
            subtype="tool_use",
            tool_name="Read",
            content="",
            tool_input={"file_path": "/src/main.py"},
            parent_tool_use_id="tool-read-1",
            sequence_number=2,
        ),
        _make_msg(
            msg_type="user",
            subtype="tool_result",
            content="",
            tool_result="def main():\n    print('hello')",
            parent_tool_use_id="tool-read-1",
            sequence_number=3,
        ),
        _make_msg(
            msg_type="assistant",
            subtype="text",
            content="Now I'll edit the file.",
            sequence_number=4,
        ),
        _make_msg(
            msg_type="assistant",
            subtype="tool_use",
            tool_name="Edit",
            content="",
            tool_input={"file_path": "/src/main.py", "old_string": "hello", "new_string": "world"},
            parent_tool_use_id="tool-edit-1",
            sequence_number=5,
        ),
        _make_msg(
            msg_type="user",
            subtype="tool_result",
            content="",
            tool_result="File edited successfully",
            parent_tool_use_id="tool-edit-1",
            sequence_number=6,
        ),
        _make_msg(
            msg_type="assistant",
            subtype="tool_use",
            tool_name="Bash",
            content="",
            tool_input={"command": "pytest"},
            parent_tool_use_id="tool-bash-1",
            sequence_number=7,
        ),
        _make_msg(
            msg_type="user",
            subtype="tool_result",
            content="",
            tool_result="All 5 tests passed",
            parent_tool_use_id="tool-bash-1",
            sequence_number=8,
        ),
    ]


# -- Tests for TraceFilterState --


class TestTraceFilterState:
    def test_frozen_dataclass(self):
        state = _make_filter(search_text="test")
        assert state.search_text == "test"
        # Verify frozen
        try:
            state.search_text = "changed"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass

    def test_default_values(self):
        state = _make_filter()
        assert state.search_text == ""
        assert state.selected_types == ()
        assert state.selected_tool == ""
        assert state.hide_tool_results is False

    def test_with_values(self):
        state = _make_filter(
            search_text="read",
            selected_types=("assistant", "system"),
            selected_tool="Read",
            hide_tool_results=True,
        )
        assert state.search_text == "read"
        assert state.selected_types == ("assistant", "system")
        assert state.selected_tool == "Read"
        assert state.hide_tool_results is True


# -- Tests for extract_unique_tool_names --


class TestExtractUniqueToolNames:
    def test_empty_messages(self):
        assert extract_unique_tool_names([]) == []

    def test_no_tool_use_messages(self):
        msgs = [
            _make_msg(msg_type="system"),
            _make_msg(msg_type="assistant", subtype="text"),
        ]
        assert extract_unique_tool_names(msgs) == []

    def test_extracts_unique_tool_names(self):
        msgs = _sample_messages()
        names = extract_unique_tool_names(msgs)
        assert names == ["Bash", "Edit", "Read"]

    def test_deduplicates_tool_names(self):
        msgs = [
            _make_msg(subtype="tool_use", tool_name="Read", sequence_number=0),
            _make_msg(subtype="tool_use", tool_name="Read", sequence_number=1),
            _make_msg(subtype="tool_use", tool_name="Write", sequence_number=2),
        ]
        names = extract_unique_tool_names(msgs)
        assert names == ["Read", "Write"]

    def test_sorted_alphabetically(self):
        msgs = [
            _make_msg(subtype="tool_use", tool_name="Write", sequence_number=0),
            _make_msg(subtype="tool_use", tool_name="Bash", sequence_number=1),
            _make_msg(subtype="tool_use", tool_name="Edit", sequence_number=2),
        ]
        names = extract_unique_tool_names(msgs)
        assert names == ["Bash", "Edit", "Write"]

    def test_ignores_empty_tool_name(self):
        msgs = [
            _make_msg(subtype="tool_use", tool_name="", sequence_number=0),
            _make_msg(subtype="tool_use", tool_name="Read", sequence_number=1),
        ]
        names = extract_unique_tool_names(msgs)
        assert names == ["Read"]


# -- Tests for _message_matches_search --


class TestMessageMatchesSearch:
    def test_matches_content(self):
        msg = _make_msg(content="I'll read the file for you.")
        assert _message_matches_search(msg, "read the file") is True

    def test_matches_tool_name(self):
        msg = _make_msg(subtype="tool_use", tool_name="Read")
        assert _message_matches_search(msg, "read") is True

    def test_matches_tool_result(self):
        msg = _make_msg(tool_result="File edited successfully")
        assert _message_matches_search(msg, "edited successfully") is True

    def test_case_insensitive(self):
        msg = _make_msg(content="Hello World")
        assert _message_matches_search(msg, "hello world") is True

    def test_no_match(self):
        msg = _make_msg(content="Hello World")
        assert _message_matches_search(msg, "goodbye") is False

    def test_empty_search(self):
        msg = _make_msg(content="Hello World")
        assert _message_matches_search(msg, "") is True

    def test_empty_content(self):
        msg = _make_msg(content="", tool_name="", tool_result="")
        assert _message_matches_search(msg, "anything") is False

    def test_partial_match(self):
        msg = _make_msg(content="pytest run completed")
        assert _message_matches_search(msg, "pytest") is True


# -- Tests for _is_result_for_tool --


class TestIsResultForTool:
    def test_matching_result(self):
        msgs = _sample_messages()
        result_msg = msgs[3]  # tool_result with parent_tool_use_id="tool-read-1"
        assert _is_result_for_tool(result_msg, "Read", msgs) is True

    def test_non_matching_result(self):
        msgs = _sample_messages()
        result_msg = msgs[3]  # tool_result for Read
        assert _is_result_for_tool(result_msg, "Edit", msgs) is False

    def test_no_parent_id(self):
        msg = _make_msg(msg_type="user", subtype="tool_result", parent_tool_use_id="")
        assert _is_result_for_tool(msg, "Read", _sample_messages()) is False

    def test_edit_result_matches_edit(self):
        msgs = _sample_messages()
        result_msg = msgs[6]  # tool_result with parent_tool_use_id="tool-edit-1"
        assert _is_result_for_tool(result_msg, "Edit", msgs) is True

    def test_edit_result_doesnt_match_read(self):
        msgs = _sample_messages()
        result_msg = msgs[6]  # tool_result for Edit
        assert _is_result_for_tool(result_msg, "Read", msgs) is False


# -- Tests for filter_messages --


class TestFilterMessages:
    def test_no_filters_returns_all(self):
        msgs = _sample_messages()
        state = _make_filter(
            selected_types=("system", "assistant", "user"),
        )
        result = filter_messages(msgs, state)
        assert len(result) == len(msgs)

    def test_empty_filters_returns_all(self):
        msgs = _sample_messages()
        state = _make_filter()
        result = filter_messages(msgs, state)
        assert len(result) == len(msgs)

    def test_text_search_filters(self):
        msgs = _sample_messages()
        state = _make_filter(search_text="read the file")
        result = filter_messages(msgs, state)
        assert len(result) == 1
        assert result[0].content == "I'll read the file for you."

    def test_text_search_case_insensitive(self):
        msgs = _sample_messages()
        state = _make_filter(search_text="READ THE FILE")
        result = filter_messages(msgs, state)
        assert len(result) == 1

    def test_type_filter_system_only(self):
        msgs = _sample_messages()
        state = _make_filter(selected_types=("system",))
        result = filter_messages(msgs, state)
        assert len(result) == 1
        assert result[0].type == "system"

    def test_type_filter_assistant_only(self):
        msgs = _sample_messages()
        state = _make_filter(selected_types=("assistant",))
        result = filter_messages(msgs, state)
        assert all(msg.type == "assistant" for msg in result)
        # 2 text + 3 tool_use = 5 assistant messages
        assert len(result) == 5

    def test_type_filter_user_only(self):
        msgs = _sample_messages()
        state = _make_filter(selected_types=("user",))
        result = filter_messages(msgs, state)
        assert all(msg.type == "user" for msg in result)
        assert len(result) == 3

    def test_type_filter_multiple_types(self):
        msgs = _sample_messages()
        state = _make_filter(selected_types=("system", "user"))
        result = filter_messages(msgs, state)
        assert all(msg.type in ("system", "user") for msg in result)
        assert len(result) == 4

    def test_hide_tool_results(self):
        msgs = _sample_messages()
        state = _make_filter(hide_tool_results=True)
        result = filter_messages(msgs, state)
        assert all(msg.type != "user" for msg in result)
        # 1 system + 2 text + 3 tool_use = 6 non-user messages
        assert len(result) == 6

    def test_tool_name_filter(self):
        msgs = _sample_messages()
        state = _make_filter(selected_tool="Read")
        result = filter_messages(msgs, state)
        # Should get Read tool_use + its tool_result
        assert len(result) == 2
        tool_use = [m for m in result if m.subtype == "tool_use"]
        assert len(tool_use) == 1
        assert tool_use[0].tool_name == "Read"

    def test_tool_name_filter_edit(self):
        msgs = _sample_messages()
        state = _make_filter(selected_tool="Edit")
        result = filter_messages(msgs, state)
        assert len(result) == 2

    def test_tool_name_filter_bash(self):
        msgs = _sample_messages()
        state = _make_filter(selected_tool="Bash")
        result = filter_messages(msgs, state)
        assert len(result) == 2

    def test_combined_filters_type_and_search(self):
        msgs = _sample_messages()
        state = _make_filter(
            search_text="edit",
            selected_types=("assistant",),
        )
        result = filter_messages(msgs, state)
        # assistant messages containing "edit": "Now I'll edit the file." and Edit tool_use
        assert len(result) == 2

    def test_combined_hide_results_and_search(self):
        msgs = _sample_messages()
        state = _make_filter(
            search_text="read",
            hide_tool_results=True,
        )
        result = filter_messages(msgs, state)
        # Non-user messages containing "read": system (has "Read" in tools list),
        # assistant text ("read the file"), and Read tool_use
        assert all(msg.type != "user" for msg in result)
        assert len(result) == 3

    def test_empty_messages(self):
        state = _make_filter(search_text="anything")
        result = filter_messages([], state)
        assert result == []

    def test_no_match_returns_empty(self):
        msgs = _sample_messages()
        state = _make_filter(search_text="zzz_nonexistent_zzz")
        result = filter_messages(msgs, state)
        assert result == []

    def test_search_matches_tool_result_content(self):
        msgs = _sample_messages()
        state = _make_filter(search_text="5 tests passed")
        result = filter_messages(msgs, state)
        assert len(result) == 1
        assert result[0].tool_result == "All 5 tests passed"

    def test_search_matches_tool_name_in_tool_use(self):
        msgs = _sample_messages()
        state = _make_filter(search_text="Bash")
        result = filter_messages(msgs, state)
        assert any(msg.tool_name == "Bash" for msg in result)

    def test_filters_preserve_order(self):
        msgs = _sample_messages()
        state = _make_filter(selected_types=("assistant",))
        result = filter_messages(msgs, state)
        seq_nums = [msg.sequence_number for msg in result]
        assert seq_nums == sorted(seq_nums)


# -- Tests for MESSAGE_TYPE_OPTIONS --


class TestMessageTypeOptions:
    def test_has_all_types(self):
        assert "system" in MESSAGE_TYPE_OPTIONS
        assert "assistant" in MESSAGE_TYPE_OPTIONS
        assert "user" in MESSAGE_TYPE_OPTIONS

    def test_display_labels(self):
        assert MESSAGE_TYPE_OPTIONS["system"] == "System"
        assert MESSAGE_TYPE_OPTIONS["assistant"] == "Assistant"
        assert MESSAGE_TYPE_OPTIONS["user"] == "User (Tool Result)"


# -- Tests for render_trace_filter_controls --


class TestRenderTraceFilterControls:
    @patch("dashboard.utils.trace_filters.st")
    def test_empty_messages_returns_empty(self, mock_st):
        result = render_trace_filter_controls([])
        assert result == []

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_renders_search_input(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        mock_st.columns.return_value[0].__enter__ = MagicMock(
            return_value=mock_st.columns.return_value[0]
        )
        mock_st.columns.return_value[0].__exit__ = MagicMock(return_value=False)
        mock_st.columns.return_value[1].__enter__ = MagicMock(
            return_value=mock_st.columns.return_value[1]
        )
        mock_st.columns.return_value[1].__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        mock_filter.return_value = msgs

        render_trace_filter_controls(msgs, session_key="test_filter")

        mock_st.text_input.assert_called_once()
        call_kwargs = mock_st.text_input.call_args
        assert call_kwargs[0][0] == "Search messages"

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_renders_type_multiselect(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        mock_filter.return_value = msgs

        render_trace_filter_controls(msgs, session_key="test_filter")

        mock_st.multiselect.assert_called_once()
        call_args = mock_st.multiselect.call_args
        assert call_args[0][0] == "Message type"

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_renders_tool_dropdown(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        mock_filter.return_value = msgs

        render_trace_filter_controls(msgs, session_key="test_filter")

        mock_st.selectbox.assert_called_once()
        call_args = mock_st.selectbox.call_args
        assert call_args[0][0] == "Filter by tool"
        # Options should include "" (All tools) plus the unique tool names
        options = call_args[1].get("options", call_args[0][1] if len(call_args[0]) > 1 else [])
        assert "" in options
        assert "Read" in options
        assert "Edit" in options
        assert "Bash" in options

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_renders_hide_toggle(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        mock_filter.return_value = msgs

        render_trace_filter_controls(msgs, session_key="test_filter")

        mock_st.checkbox.assert_called_once()
        call_args = mock_st.checkbox.call_args
        assert call_args[0][0] == "Hide tool results"

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_shows_result_count_filtered(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = "read"
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        # Simulate filtered result with fewer messages
        mock_filter.return_value = msgs[:3]

        render_trace_filter_controls(msgs, session_key="test_filter")

        # Should show "Showing X of Y messages" with filtered count
        markdown_calls = [
            call[0][0]
            for call in mock_st.markdown.call_args_list
            if call[0]
        ]
        showing_calls = [c for c in markdown_calls if "Showing" in c]
        assert len(showing_calls) == 1
        assert "3 of 9" in showing_calls[0]

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_shows_all_count_when_no_filter(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        mock_filter.return_value = msgs

        render_trace_filter_controls(msgs, session_key="test_filter")

        markdown_calls = [
            call[0][0]
            for call in mock_st.markdown.call_args_list
            if call[0]
        ]
        showing_calls = [c for c in markdown_calls if "Showing" in c]
        assert len(showing_calls) == 1
        assert "all 9" in showing_calls[0]

    @patch("dashboard.utils.trace_filters.filter_messages")
    @patch("dashboard.utils.trace_filters.st")
    def test_returns_filtered_messages(self, mock_st, mock_filter):
        mock_st.session_state = {}
        mock_st.columns.return_value = [MagicMock(), MagicMock()]
        for col in mock_st.columns.return_value:
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)

        mock_st.text_input.return_value = ""
        mock_st.multiselect.return_value = ["system", "assistant", "user"]
        mock_st.selectbox.return_value = ""
        mock_st.checkbox.return_value = False

        msgs = _sample_messages()
        filtered = msgs[:5]
        mock_filter.return_value = filtered

        result = render_trace_filter_controls(msgs, session_key="test_filter")
        assert result == filtered
