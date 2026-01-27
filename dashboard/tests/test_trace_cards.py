"""Tests for dashboard/utils/trace_cards.py - Full trace card rendering (US-011)."""

from unittest.mock import MagicMock, patch

from src.ingest.trace_viewer_parser import TokenUsage, TraceMessage

from dashboard.utils.trace_cards import (
    CARD_STYLES,
    MESSAGES_PER_PAGE,
    TOOL_RESULT_LINE_LIMIT,
    _compute_page_count,
    _format_token_usage,
    _get_card_style_key,
    _get_page_slice,
    _render_card_header_html,
    _render_card_wrapper_close,
    _render_card_wrapper_open,
    render_trace_card,
    render_trace_cards,
)


# -- Fixtures --


def _make_msg(
    msg_type: str = "assistant",
    subtype: str = "text",
    content: str = "Hello world",
    tool_name: str = "",
    tool_input: dict | None = None,
    tool_result: str = "",
    token_usage: TokenUsage | None = None,
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
        token_usage=token_usage,
        parent_tool_use_id=parent_tool_use_id,
        session_id=session_id,
        uuid=uuid,
        sequence_number=sequence_number,
    )


def _make_token_usage(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> TokenUsage:
    """Helper to create a TokenUsage with defaults."""
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=cache_creation,
        cache_read_input_tokens=cache_read,
    )


# -- Tests for _get_card_style_key --


class TestGetCardStyleKey:
    def test_system_message(self):
        msg = _make_msg(msg_type="system", subtype="init")
        assert _get_card_style_key(msg) == "system"

    def test_assistant_text(self):
        msg = _make_msg(msg_type="assistant", subtype="text")
        assert _get_card_style_key(msg) == "assistant_text"

    def test_assistant_tool_use(self):
        msg = _make_msg(msg_type="assistant", subtype="tool_use")
        assert _get_card_style_key(msg) == "assistant_tool_use"

    def test_user_tool_result(self):
        msg = _make_msg(msg_type="user", subtype="tool_result")
        assert _get_card_style_key(msg) == "user_tool_result"

    def test_user_text(self):
        msg = _make_msg(msg_type="user", subtype="text")
        assert _get_card_style_key(msg) == "user_tool_result"

    def test_unknown_type_returns_system(self):
        msg = _make_msg(msg_type="unknown", subtype="")
        assert _get_card_style_key(msg) == "system"


# -- Tests for _format_token_usage --


class TestFormatTokenUsage:
    def test_no_token_usage(self):
        msg = _make_msg(token_usage=None)
        assert _format_token_usage(msg) == ""

    def test_basic_token_usage(self):
        usage = _make_token_usage(input_tokens=2349, output_tokens=1)
        msg = _make_msg(token_usage=usage)
        result = _format_token_usage(msg)
        assert "in: 2,349" in result
        assert "out: 1" in result
        assert "cached" not in result

    def test_token_usage_with_cache(self):
        usage = _make_token_usage(
            input_tokens=100, output_tokens=50, cache_read=18000, cache_creation=53
        )
        msg = _make_msg(token_usage=usage)
        result = _format_token_usage(msg)
        assert "in: 100" in result
        assert "out: 50" in result
        assert "cached: 18,053" in result

    def test_token_usage_zero_cache(self):
        usage = _make_token_usage(cache_read=0, cache_creation=0)
        msg = _make_msg(token_usage=usage)
        result = _format_token_usage(msg)
        assert "cached" not in result


# -- Tests for card HTML rendering --


class TestCardHtmlRendering:
    def test_card_wrapper_open_contains_style(self):
        style = CARD_STYLES["system"]
        html = _render_card_wrapper_open(style)
        assert style["background"] in html
        assert style["border_color"] in html
        assert "border-left:" in html

    def test_card_wrapper_close(self):
        assert _render_card_wrapper_close() == "</div>"

    def test_card_header_with_badge(self):
        style = CARD_STYLES["assistant_text"]
        html = _render_card_header_html(style, 42, "")
        assert "ASSISTANT" in html
        assert "#42" in html
        assert style["label_bg"] in html

    def test_card_header_with_token_label(self):
        style = CARD_STYLES["assistant_text"]
        html = _render_card_header_html(style, 1, "in: 100 | out: 50")
        assert "in: 100 | out: 50" in html

    def test_card_header_without_token_label(self):
        style = CARD_STYLES["system"]
        html = _render_card_header_html(style, 0, "")
        assert "float: right" not in html

    def test_system_card_style(self):
        assert CARD_STYLES["system"]["background"] == "#f0f0f0"
        assert CARD_STYLES["system"]["label"] == "SYSTEM"

    def test_assistant_text_card_style(self):
        assert CARD_STYLES["assistant_text"]["background"] == "#ffffff"
        assert CARD_STYLES["assistant_text"]["label"] == "ASSISTANT"

    def test_tool_use_card_style(self):
        assert CARD_STYLES["assistant_tool_use"]["background"] == "#eff6ff"
        assert CARD_STYLES["assistant_tool_use"]["label"] == "TOOL USE"

    def test_tool_result_card_style(self):
        assert CARD_STYLES["user_tool_result"]["background"] == "#f0fdf4"
        assert CARD_STYLES["user_tool_result"]["label"] == "TOOL RESULT"


# -- Tests for pagination --


class TestPagination:
    def test_compute_page_count_empty(self):
        assert _compute_page_count(0) == 1

    def test_compute_page_count_less_than_page(self):
        assert _compute_page_count(25) == 1

    def test_compute_page_count_exact_page(self):
        assert _compute_page_count(50) == 1

    def test_compute_page_count_just_over_page(self):
        assert _compute_page_count(51) == 2

    def test_compute_page_count_multiple_pages(self):
        assert _compute_page_count(150) == 3

    def test_compute_page_count_large(self):
        assert _compute_page_count(1000) == 20

    def test_get_page_slice_first_page(self):
        msgs = [_make_msg(sequence_number=i) for i in range(100)]
        page = _get_page_slice(msgs, 0)
        assert len(page) == 50
        assert page[0].sequence_number == 0
        assert page[-1].sequence_number == 49

    def test_get_page_slice_second_page(self):
        msgs = [_make_msg(sequence_number=i) for i in range(100)]
        page = _get_page_slice(msgs, 1)
        assert len(page) == 50
        assert page[0].sequence_number == 50
        assert page[-1].sequence_number == 99

    def test_get_page_slice_partial_last_page(self):
        msgs = [_make_msg(sequence_number=i) for i in range(75)]
        page = _get_page_slice(msgs, 1)
        assert len(page) == 25
        assert page[0].sequence_number == 50
        assert page[-1].sequence_number == 74

    def test_get_page_slice_beyond_end(self):
        msgs = [_make_msg(sequence_number=i) for i in range(10)]
        page = _get_page_slice(msgs, 5)
        assert len(page) == 0

    def test_messages_per_page_constant(self):
        assert MESSAGES_PER_PAGE == 50


# -- Tests for render_trace_card dispatch --


class TestRenderTraceCard:
    @patch("dashboard.utils.trace_cards._render_system_card")
    def test_dispatches_system(self, mock_render):
        msg = _make_msg(msg_type="system", subtype="init")
        render_trace_card(msg)
        mock_render.assert_called_once_with(msg)

    @patch("dashboard.utils.trace_cards._render_assistant_text_card")
    def test_dispatches_assistant_text(self, mock_render):
        msg = _make_msg(msg_type="assistant", subtype="text")
        render_trace_card(msg)
        mock_render.assert_called_once_with(msg)

    @patch("dashboard.utils.trace_cards._render_tool_use_card")
    def test_dispatches_tool_use(self, mock_render):
        msg = _make_msg(msg_type="assistant", subtype="tool_use", tool_name="Read")
        render_trace_card(msg)
        mock_render.assert_called_once_with(msg)

    @patch("dashboard.utils.trace_cards._render_tool_result_card")
    def test_dispatches_tool_result(self, mock_render):
        msg = _make_msg(msg_type="user", subtype="tool_result")
        render_trace_card(msg)
        mock_render.assert_called_once_with(msg)


# -- Tests for individual card renderers with Streamlit mocking --


class TestSystemCardRenderer:
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_system_card_html(self, mock_st):
        msg = _make_msg(
            msg_type="system",
            subtype="init",
            content="Model: claude-3-5-sonnet\nTools: Read, Write, Edit",
            session_id="sess-123",
        )
        from dashboard.utils.trace_cards import _render_system_card

        _render_system_card(msg)
        # Verify markdown was called with HTML containing system style
        calls = mock_st.markdown.call_args_list
        assert len(calls) >= 1
        html_arg = calls[0][0][0]
        assert "#f0f0f0" in html_arg  # system background
        assert "SYSTEM" in html_arg
        assert "Model:" in html_arg

    @patch("dashboard.utils.trace_cards.st")
    def test_renders_session_id_caption(self, mock_st):
        msg = _make_msg(
            msg_type="system",
            subtype="init",
            content="Model: test",
            session_id="sess-abc",
        )
        from dashboard.utils.trace_cards import _render_system_card

        _render_system_card(msg)
        mock_st.caption.assert_called_once_with("Session: sess-abc")


class TestAssistantTextCardRenderer:
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_assistant_card(self, mock_st):
        msg = _make_msg(
            msg_type="assistant",
            subtype="text",
            content="I'll help you with that.",
            token_usage=_make_token_usage(100, 50),
        )
        from dashboard.utils.trace_cards import _render_assistant_text_card

        _render_assistant_text_card(msg)

        # Should call markdown twice: once for HTML wrapper, once for content
        assert mock_st.markdown.call_count >= 2
        html_call = mock_st.markdown.call_args_list[0]
        assert "#ffffff" in html_call[0][0]  # white background
        content_call = mock_st.markdown.call_args_list[1]
        assert "I'll help you with that." in content_call[0][0]

    @patch("dashboard.utils.trace_cards.st")
    def test_renders_token_usage_in_header(self, mock_st):
        usage = _make_token_usage(2349, 1, cache_read=18053)
        msg = _make_msg(
            msg_type="assistant",
            subtype="text",
            content="Test",
            token_usage=usage,
        )
        from dashboard.utils.trace_cards import _render_assistant_text_card

        _render_assistant_text_card(msg)

        html_call = mock_st.markdown.call_args_list[0][0][0]
        assert "in: 2,349" in html_call
        assert "out: 1" in html_call
        assert "cached: 18,053" in html_call


class TestToolUseCardRenderer:
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_tool_badge(self, mock_st):
        msg = _make_msg(
            msg_type="assistant",
            subtype="tool_use",
            tool_name="Read",
            tool_input={"file_path": "/src/main.py"},
        )
        from dashboard.utils.trace_cards import _render_tool_use_card

        mock_st.expander.return_value.__enter__ = MagicMock()
        mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)

        _render_tool_use_card(msg)

        # Should render HTML with tool badge
        html_call = mock_st.markdown.call_args_list[0][0][0]
        assert "#eff6ff" in html_call  # light blue background
        assert "Read" in html_call  # tool name in badge

    @patch("dashboard.utils.trace_cards.st")
    def test_renders_tool_input_expander(self, mock_st):
        tool_input = {"file_path": "/src/main.py", "offset": 0}
        msg = _make_msg(
            msg_type="assistant",
            subtype="tool_use",
            tool_name="Read",
            tool_input=tool_input,
        )
        from dashboard.utils.trace_cards import _render_tool_use_card

        mock_expander = MagicMock()
        mock_st.expander.return_value = mock_expander
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=False)

        _render_tool_use_card(msg)

        mock_st.expander.assert_called_once_with("Tool Input", expanded=False)


class TestToolResultCardRenderer:
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_short_result(self, mock_st):
        msg = _make_msg(
            msg_type="user",
            subtype="tool_result",
            tool_result="File content here",
        )
        from dashboard.utils.trace_cards import _render_tool_result_card

        _render_tool_result_card(msg)

        html_call = mock_st.markdown.call_args_list[0][0][0]
        assert "#f0fdf4" in html_call  # light green background
        mock_st.code.assert_called_once_with("File content here", language="text")

    @patch("dashboard.utils.trace_cards.st")
    def test_renders_empty_result(self, mock_st):
        msg = _make_msg(
            msg_type="user",
            subtype="tool_result",
            tool_result="",
            content="",
        )
        from dashboard.utils.trace_cards import _render_tool_result_card

        _render_tool_result_card(msg)

        mock_st.caption.assert_called_once_with("(empty result)")

    @patch("dashboard.utils.trace_cards.st")
    def test_truncates_long_result(self, mock_st):
        long_result = "\n".join(f"line {i}" for i in range(200))
        msg = _make_msg(
            msg_type="user",
            subtype="tool_result",
            tool_result=long_result,
        )
        from dashboard.utils.trace_cards import _render_tool_result_card

        mock_expander = MagicMock()
        mock_st.expander.return_value = mock_expander
        mock_expander.__enter__ = MagicMock(return_value=mock_expander)
        mock_expander.__exit__ = MagicMock(return_value=False)

        _render_tool_result_card(msg)

        # Should call st.code for truncated version
        first_code_call = mock_st.code.call_args_list[0]
        truncated_text = first_code_call[0][0]
        assert truncated_text.count("\n") == TOOL_RESULT_LINE_LIMIT - 1

        # Should create expander for full content
        expander_label = mock_st.expander.call_args[0][0]
        assert "more lines" in expander_label

    @patch("dashboard.utils.trace_cards.st")
    def test_uses_content_when_no_tool_result(self, mock_st):
        msg = _make_msg(
            msg_type="user",
            subtype="tool_result",
            tool_result="",
            content="Fallback content",
        )
        from dashboard.utils.trace_cards import _render_tool_result_card

        _render_tool_result_card(msg)

        mock_st.code.assert_called_once_with("Fallback content", language="text")


# -- Tests for render_trace_cards (integration) --


class TestRenderTraceCards:
    @patch("dashboard.utils.trace_cards.st")
    def test_empty_messages_shows_info(self, mock_st):
        render_trace_cards([])
        mock_st.info.assert_called_once_with("No trace messages to display.")

    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_initializes_session_state(self, mock_st, mock_pagination):
        mock_st.session_state = {}
        msgs = [_make_msg(sequence_number=i) for i in range(3)]

        render_trace_cards(msgs, session_key="test_page")
        assert mock_st.session_state["test_page"] == 0

    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_clamps_page_to_valid_range(self, mock_st, mock_pagination):
        mock_st.session_state = {"test_page": 999}
        msgs = [_make_msg(sequence_number=i) for i in range(10)]

        # Should clamp to max valid page (0 since only 10 msgs = 1 page)
        render_trace_cards(msgs, session_key="test_page")
        assert mock_st.session_state["test_page"] == 0

    @patch("dashboard.utils.trace_cards.render_trace_card")
    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_correct_page_size(self, mock_st, mock_pagination, mock_card):
        mock_st.session_state = {"test_page": 0}
        msgs = [_make_msg(sequence_number=i) for i in range(75)]

        render_trace_cards(msgs, session_key="test_page")

        # First page should render 50 cards
        assert mock_card.call_count == 50

    @patch("dashboard.utils.trace_cards.render_trace_card")
    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_renders_second_page(self, mock_st, mock_pagination, mock_card):
        mock_st.session_state = {"test_page": 1}
        msgs = [_make_msg(sequence_number=i) for i in range(75)]

        render_trace_cards(msgs, session_key="test_page")

        # Second page should render 25 remaining cards
        assert mock_card.call_count == 25
        # First card on page 2 should be sequence 50
        first_call_msg = mock_card.call_args_list[0][0][0]
        assert first_call_msg.sequence_number == 50

    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_shows_bottom_pagination_for_multi_page(self, mock_st, mock_pagination):
        mock_st.session_state = {"test_page": 0}
        msgs = [_make_msg(sequence_number=i) for i in range(75)]

        render_trace_cards(msgs, session_key="test_page")

        # Should render pagination controls twice (top and bottom)
        assert mock_pagination.call_count == 2

    @patch("dashboard.utils.trace_cards._render_pagination_controls")
    @patch("dashboard.utils.trace_cards.st")
    def test_no_bottom_pagination_for_single_page(self, mock_st, mock_pagination):
        mock_st.session_state = {"test_page": 0}
        msgs = [_make_msg(sequence_number=i) for i in range(10)]

        render_trace_cards(msgs, session_key="test_page")

        # Only top pagination for single page
        assert mock_pagination.call_count == 1


# -- Tests for TOOL_RESULT_LINE_LIMIT constant --


class TestConstants:
    def test_tool_result_line_limit(self):
        assert TOOL_RESULT_LINE_LIMIT == 100

    def test_all_card_styles_present(self):
        expected_keys = {"system", "assistant_text", "assistant_tool_use", "user_tool_result"}
        assert set(CARD_STYLES.keys()) == expected_keys

    def test_each_style_has_required_fields(self):
        required_fields = {"background", "border_color", "label", "label_bg"}
        for key, style in CARD_STYLES.items():
            assert set(style.keys()) == required_fields, f"Style {key} missing fields"
