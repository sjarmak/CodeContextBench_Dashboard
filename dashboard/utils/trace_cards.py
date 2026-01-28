"""
Full trace card rendering for the dashboard.

Renders each TraceMessage as a styled card with type-specific formatting,
token usage labels, and pagination (50 messages per page).
"""

import json
import logging
import math

import streamlit as st

from src.ingest.trace_viewer_parser import TraceMessage

logger = logging.getLogger(__name__)

MESSAGES_PER_PAGE = 50

# CSS class names mapped to background colors per message type
CARD_STYLES: dict[str, dict[str, str]] = {
    "system": {
        "background": "#f0f0f0",
        "border_color": "#999999",
        "label": "SYSTEM",
        "label_bg": "#999999",
    },
    "assistant_text": {
        "background": "#ffffff",
        "border_color": "#6366f1",
        "label": "ASSISTANT",
        "label_bg": "#6366f1",
    },
    "assistant_tool_use": {
        "background": "#eff6ff",
        "border_color": "#3b82f6",
        "label": "TOOL USE",
        "label_bg": "#3b82f6",
    },
    "user_tool_result": {
        "background": "#f0fdf4",
        "border_color": "#22c55e",
        "label": "TOOL RESULT",
        "label_bg": "#22c55e",
    },
}

TOOL_RESULT_LINE_LIMIT = 100


def _get_card_style_key(msg: TraceMessage) -> str:
    """Determine the card style key based on message type and subtype."""
    if msg.type == "system":
        return "system"
    if msg.type == "assistant" and msg.subtype == "tool_use":
        return "assistant_tool_use"
    if msg.type == "assistant":
        return "assistant_text"
    if msg.type == "user":
        return "user_tool_result"
    return "system"


def _format_token_usage(msg: TraceMessage) -> str:
    """Format token usage as a compact label string.

    Returns empty string if no token usage available.
    """
    if msg.token_usage is None:
        return ""

    usage = msg.token_usage
    parts = [
        f"in: {usage.input_tokens:,}",
        f"out: {usage.output_tokens:,}",
    ]

    cached = usage.cache_read_input_tokens + usage.cache_creation_input_tokens
    if cached > 0:
        parts.append(f"cached: {cached:,}")

    return " | ".join(parts)


def _render_card_header_html(
    style: dict[str, str],
    sequence_number: int,
    token_label: str,
) -> str:
    """Build HTML for the card header with type badge and optional token label."""
    badge_html = (
        f'<span style="'
        f"background-color: {style['label_bg']};"
        f"color: white;"
        f"padding: 2px 8px;"
        f"border-radius: 4px;"
        f"font-size: 0.75em;"
        f"font-weight: bold;"
        f"margin-right: 8px;"
        f'">{style["label"]}</span>'
    )

    seq_html = (
        f'<span style="color: #888; font-size: 0.8em;">#{sequence_number}</span>'
    )

    token_html = ""
    if token_label:
        token_html = (
            f'<span style="'
            f"color: #666;"
            f"font-size: 0.75em;"
            f"float: right;"
            f'">{token_label}</span>'
        )

    return (
        f'<div style="margin-bottom: 6px;">'
        f"{badge_html}{seq_html}{token_html}"
        f"</div>"
    )


def _render_card_wrapper_open(style: dict[str, str]) -> str:
    """Build the opening HTML for a card wrapper div."""
    return (
        f'<div style="'
        f"background-color: {style['background']};"
        f"border-left: 4px solid {style['border_color']};"
        f"padding: 12px 16px;"
        f"border-radius: 4px;"
        f"margin: 8px 0;"
        f'">'
    )


def _render_card_wrapper_close() -> str:
    """Build the closing HTML for a card wrapper div."""
    return "</div>"


def _render_system_card(msg: TraceMessage) -> None:
    """Render a system message card with init metadata."""
    style = CARD_STYLES["system"]
    header = _render_card_header_html(style, msg.sequence_number, "")

    content_lines = msg.content.split("\n") if msg.content else []
    content_html = "<br>".join(
        f'<span style="font-size: 0.9em; color: #555;">{line}</span>'
        for line in content_lines
        if line.strip()
    )

    html = (
        _render_card_wrapper_open(style)
        + header
        + content_html
        + _render_card_wrapper_close()
    )
    st.markdown(html, unsafe_allow_html=True)

    if msg.subtype == "init" and msg.session_id:
        st.caption(f"Session: {msg.session_id}")


def _render_assistant_text_card(msg: TraceMessage) -> None:
    """Render an assistant text message card with markdown content."""
    style = CARD_STYLES["assistant_text"]
    token_label = _format_token_usage(msg)
    header = _render_card_header_html(style, msg.sequence_number, token_label)

    html = _render_card_wrapper_open(style) + header + _render_card_wrapper_close()
    st.markdown(html, unsafe_allow_html=True)

    if msg.content:
        st.markdown(msg.content)


def _render_tool_use_card(msg: TraceMessage) -> None:
    """Render an assistant tool_use card with tool badge and JSON input."""
    style = CARD_STYLES["assistant_tool_use"]
    token_label = _format_token_usage(msg)

    tool_badge = (
        f'<span style="'
        f"background-color: #2563eb;"
        f"color: white;"
        f"padding: 3px 10px;"
        f"border-radius: 12px;"
        f"font-size: 0.85em;"
        f"font-weight: 600;"
        f'">{msg.tool_name}</span>'
    )

    header = _render_card_header_html(style, msg.sequence_number, token_label)
    html = (
        _render_card_wrapper_open(style)
        + header
        + f'<div style="margin-top: 4px;">{tool_badge}</div>'
        + _render_card_wrapper_close()
    )
    st.markdown(html, unsafe_allow_html=True)

    if msg.tool_input:
        with st.expander("Tool Input", expanded=False):
            try:
                formatted = json.dumps(msg.tool_input, indent=2)
                st.code(formatted, language="json")
            except (TypeError, ValueError):
                st.json(msg.tool_input)


def _render_tool_result_card(msg: TraceMessage) -> None:
    """Render a user tool_result card with syntax highlighting and truncation."""
    style = CARD_STYLES["user_tool_result"]
    header = _render_card_header_html(style, msg.sequence_number, "")

    html = _render_card_wrapper_open(style) + header + _render_card_wrapper_close()
    st.markdown(html, unsafe_allow_html=True)

    result_text = msg.tool_result if msg.tool_result else msg.content
    if not result_text:
        st.caption("(empty result)")
        return

    lines = result_text.split("\n")
    if len(lines) > TOOL_RESULT_LINE_LIMIT:
        truncated = "\n".join(lines[:TOOL_RESULT_LINE_LIMIT])
        st.code(truncated, language="text")
        with st.expander(
            f"Show more ({len(lines) - TOOL_RESULT_LINE_LIMIT} more lines)",
            expanded=False,
        ):
            st.code(result_text, language="text")
    else:
        st.code(result_text, language="text")


def render_trace_card(msg: TraceMessage) -> None:
    """Render a single trace message as a styled card.

    Dispatches to type-specific renderers based on message type and subtype.

    Args:
        msg: TraceMessage to render
    """
    style_key = _get_card_style_key(msg)

    if style_key == "system":
        _render_system_card(msg)
    elif style_key == "assistant_text":
        _render_assistant_text_card(msg)
    elif style_key == "assistant_tool_use":
        _render_tool_use_card(msg)
    elif style_key == "user_tool_result":
        _render_tool_result_card(msg)


def _compute_page_count(total_messages: int) -> int:
    """Compute number of pages needed for the given message count."""
    if total_messages <= 0:
        return 1
    return max(1, math.ceil(total_messages / MESSAGES_PER_PAGE))


def _get_page_slice(
    messages: list[TraceMessage], page: int
) -> list[TraceMessage]:
    """Get the slice of messages for the given page (0-indexed)."""
    start = page * MESSAGES_PER_PAGE
    end = start + MESSAGES_PER_PAGE
    return messages[start:end]


def _render_pagination_controls(
    total_messages: int,
    current_page: int,
    total_pages: int,
    session_key: str,
) -> None:
    """Render pagination buttons and page indicator."""
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_info:
        start_msg = current_page * MESSAGES_PER_PAGE + 1
        end_msg = min((current_page + 1) * MESSAGES_PER_PAGE, total_messages)
        st.markdown(
            f"<div style='text-align: center; padding: 8px; color: #666;'>"
            f"Showing {start_msg}-{end_msg} of {total_messages} messages "
            f"(Page {current_page + 1} of {total_pages})"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_prev:
        if current_page > 0:
            if st.button("Previous", key=f"{session_key}_prev"):
                st.session_state[session_key] = current_page - 1
                st.rerun()

    with col_next:
        if current_page < total_pages - 1:
            if st.button("Next", key=f"{session_key}_next"):
                st.session_state[session_key] = current_page + 1
                st.rerun()


def render_trace_cards(
    messages: list[TraceMessage],
    session_key: str = "trace_page",
) -> None:
    """Render trace messages as styled cards with pagination.

    Displays 50 messages per page with Previous/Next navigation.

    Args:
        messages: List of TraceMessage to render
        session_key: Session state key for storing current page number
    """
    if not messages:
        st.info("No trace messages to display.")
        return

    total_messages = len(messages)
    total_pages = _compute_page_count(total_messages)

    # Initialize page state
    if session_key not in st.session_state:
        st.session_state[session_key] = 0

    current_page = st.session_state[session_key]
    # Clamp page to valid range
    current_page = max(0, min(current_page, total_pages - 1))
    st.session_state[session_key] = current_page

    # Top pagination controls
    _render_pagination_controls(total_messages, current_page, total_pages, session_key)

    # Render page of cards
    page_messages = _get_page_slice(messages, current_page)
    for msg in page_messages:
        render_trace_card(msg)

    # Bottom pagination controls
    if total_pages > 1:
        st.markdown("---")
        _render_pagination_controls(
            total_messages, current_page, total_pages, f"{session_key}_bottom"
        )
