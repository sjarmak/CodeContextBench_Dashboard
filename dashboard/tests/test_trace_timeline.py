"""
Tests for the tool call timeline visualization.

Tests the data preparation, category assignment, tooltip extraction,
and Plotly chart rendering in dashboard/utils/trace_timeline.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ingest.trace_viewer_parser import TokenUsage, TraceMessage


def _make_tool_msg(
    tool_name: str,
    tool_input: dict | None = None,
    sequence_number: int = 0,
) -> TraceMessage:
    """Helper to create a tool_use TraceMessage."""
    return TraceMessage(
        type="assistant",
        subtype="tool_use",
        content="",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_result="",
        token_usage=None,
        parent_tool_use_id="",
        session_id="test-session",
        uuid=f"uuid-{sequence_number}",
        sequence_number=sequence_number,
    )


def _make_text_msg(sequence_number: int = 0) -> TraceMessage:
    """Helper to create a non-tool TraceMessage."""
    return TraceMessage(
        type="assistant",
        subtype="text",
        content="Some text",
        tool_name="",
        tool_input=None,
        tool_result="",
        token_usage=None,
        parent_tool_use_id="",
        session_id="test-session",
        uuid=f"uuid-text-{sequence_number}",
        sequence_number=sequence_number,
    )


# --- Tests for TOOL_CATEGORIES ---


class TestToolCategories:
    """Tests for the TOOL_CATEGORIES mapping."""

    def test_read_is_file_read(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Read") == "File Read"

    def test_write_is_file_write(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Write") == "File Write"

    def test_edit_is_file_write(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Edit") == "File Write"

    def test_grep_is_search(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Grep") == "Search"

    def test_glob_is_search(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Glob") == "Search"

    def test_bash_is_bash(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("Bash") == "Bash"

    def test_enter_plan_mode_is_planning(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("EnterPlanMode") == "Planning"

    def test_exit_plan_mode_is_planning(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("ExitPlanMode") == "Planning"

    def test_todo_write_is_planning(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("TodoWrite") == "Planning"

    def test_unknown_tool_is_other(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("CustomTool") == "Other"

    def test_empty_string_is_other(self) -> None:
        from dashboard.utils.trace_timeline import get_tool_category

        assert get_tool_category("") == "Other"


# --- Tests for CATEGORY_COLORS ---


class TestCategoryColors:
    """Tests for category color mapping."""

    def test_all_categories_have_colors(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        expected_categories = {
            "File Read",
            "File Write",
            "Search",
            "Bash",
            "Planning",
            "Other",
        }
        assert set(CATEGORY_COLORS.keys()) == expected_categories

    def test_file_read_is_blue(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["File Read"] == "#3b82f6"

    def test_file_write_is_green(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["File Write"] == "#22c55e"

    def test_search_is_yellow(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["Search"] == "#eab308"

    def test_bash_is_gray(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["Bash"] == "#6b7280"

    def test_planning_is_purple(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["Planning"] == "#8b5cf6"

    def test_other_is_orange(self) -> None:
        from dashboard.utils.trace_timeline import CATEGORY_COLORS

        assert CATEGORY_COLORS["Other"] == "#f97316"


# --- Tests for extract_tooltip ---


class TestExtractTooltip:
    """Tests for tooltip extraction from tool input."""

    def test_read_file_path(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Read", {"file_path": "/src/main.py"})
        assert extract_tooltip(msg) == "/src/main.py"

    def test_write_file_path(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Write", {"file_path": "/src/output.py"})
        assert extract_tooltip(msg) == "/src/output.py"

    def test_edit_file_path(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Edit", {"file_path": "/src/edit.py"})
        assert extract_tooltip(msg) == "/src/edit.py"

    def test_bash_command_preview(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Bash", {"command": "npm test"})
        assert extract_tooltip(msg) == "npm test"

    def test_bash_long_command_truncated(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        long_cmd = "a" * 200
        msg = _make_tool_msg("Bash", {"command": long_cmd})
        tooltip = extract_tooltip(msg)
        assert len(tooltip) <= 103  # 100 + "..."
        assert tooltip.endswith("...")

    def test_grep_pattern(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Grep", {"pattern": "import.*foo"})
        assert extract_tooltip(msg) == "import.*foo"

    def test_glob_pattern(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Glob", {"pattern": "**/*.py"})
        assert extract_tooltip(msg) == "**/*.py"

    def test_no_input_returns_empty(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("Read", None)
        assert extract_tooltip(msg) == ""

    def test_unknown_tool_no_known_fields(self) -> None:
        from dashboard.utils.trace_timeline import extract_tooltip

        msg = _make_tool_msg("CustomTool", {"custom_field": "value"})
        assert extract_tooltip(msg) == ""


# --- Tests for extract_tool_calls ---


class TestExtractToolCalls:
    """Tests for extracting tool_use messages from trace."""

    def test_filters_only_tool_use(self) -> None:
        from dashboard.utils.trace_timeline import extract_tool_calls

        messages = [
            _make_tool_msg("Read", {"file_path": "/a.py"}, 0),
            _make_text_msg(1),
            _make_tool_msg("Bash", {"command": "ls"}, 2),
        ]
        result = extract_tool_calls(messages)
        assert len(result) == 2
        assert result[0].tool_name == "Read"
        assert result[1].tool_name == "Bash"

    def test_empty_messages(self) -> None:
        from dashboard.utils.trace_timeline import extract_tool_calls

        assert extract_tool_calls([]) == []

    def test_no_tool_calls(self) -> None:
        from dashboard.utils.trace_timeline import extract_tool_calls

        messages = [_make_text_msg(0), _make_text_msg(1)]
        assert extract_tool_calls(messages) == []

    def test_preserves_order(self) -> None:
        from dashboard.utils.trace_timeline import extract_tool_calls

        messages = [
            _make_tool_msg("Read", None, 0),
            _make_tool_msg("Bash", None, 1),
            _make_tool_msg("Edit", None, 2),
        ]
        result = extract_tool_calls(messages)
        assert [m.tool_name for m in result] == ["Read", "Bash", "Edit"]


# --- Tests for build_timeline_data ---


class TestBuildTimelineData:
    """Tests for building Plotly-ready timeline data."""

    def test_builds_correct_columns(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        messages = [
            _make_tool_msg("Read", {"file_path": "/a.py"}, 0),
            _make_tool_msg("Bash", {"command": "ls"}, 1),
        ]
        df = build_timeline_data(messages)
        expected_cols = {"Tool", "Category", "Sequence", "Description", "Color"}
        assert set(df.columns) == expected_cols

    def test_correct_row_count(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        messages = [
            _make_tool_msg("Read", None, 0),
            _make_text_msg(1),
            _make_tool_msg("Edit", None, 2),
        ]
        df = build_timeline_data(messages)
        assert len(df) == 2  # Only tool_use messages

    def test_empty_messages(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        df = build_timeline_data([])
        assert len(df) == 0
        assert set(df.columns) == {"Tool", "Category", "Sequence", "Description", "Color"}

    def test_category_assignment(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        messages = [
            _make_tool_msg("Read", None, 0),
            _make_tool_msg("Edit", None, 1),
            _make_tool_msg("Grep", None, 2),
            _make_tool_msg("Bash", None, 3),
            _make_tool_msg("TodoWrite", None, 4),
            _make_tool_msg("CustomTool", None, 5),
        ]
        df = build_timeline_data(messages)
        categories = df["Category"].tolist()
        assert categories == [
            "File Read",
            "File Write",
            "Search",
            "Bash",
            "Planning",
            "Other",
        ]

    def test_sequence_numbers_preserved(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        messages = [
            _make_tool_msg("Read", None, 5),
            _make_tool_msg("Bash", None, 10),
        ]
        df = build_timeline_data(messages)
        assert df["Sequence"].tolist() == [5, 10]

    def test_description_from_tooltip(self) -> None:
        from dashboard.utils.trace_timeline import build_timeline_data

        messages = [
            _make_tool_msg("Read", {"file_path": "/a.py"}, 0),
        ]
        df = build_timeline_data(messages)
        assert df["Description"].iloc[0] == "/a.py"


# --- Tests for render_tool_timeline ---


class TestRenderToolTimeline:
    """Tests for the Streamlit rendering function."""

    @patch("dashboard.utils.trace_timeline.st")
    def test_empty_messages_shows_info(self, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_timeline import render_tool_timeline

        render_tool_timeline([])
        mock_st.info.assert_called_once()

    @patch("dashboard.utils.trace_timeline.st")
    @patch("dashboard.utils.trace_timeline.px")
    def test_renders_chart(self, mock_px: MagicMock, mock_st: MagicMock) -> None:
        from dashboard.utils.trace_timeline import render_tool_timeline

        mock_fig = MagicMock()
        mock_px.scatter.return_value = mock_fig

        messages = [
            _make_tool_msg("Read", {"file_path": "/a.py"}, 0),
            _make_tool_msg("Bash", {"command": "ls"}, 1),
        ]

        render_tool_timeline(messages)

        mock_px.scatter.assert_called_once()
        mock_st.plotly_chart.assert_called_once()
        call_kwargs = mock_st.plotly_chart.call_args
        assert call_kwargs[1]["use_container_width"] is True

    @patch("dashboard.utils.trace_timeline.st")
    @patch("dashboard.utils.trace_timeline.px")
    def test_no_tool_calls_shows_info(
        self, mock_px: MagicMock, mock_st: MagicMock
    ) -> None:
        from dashboard.utils.trace_timeline import render_tool_timeline

        messages = [_make_text_msg(0), _make_text_msg(1)]
        render_tool_timeline(messages)
        mock_st.info.assert_called_once()
        mock_px.scatter.assert_not_called()
