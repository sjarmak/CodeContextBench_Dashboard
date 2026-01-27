"""
Trace search and type filtering for the Full Trace view.

Provides filtering controls and logic for searching trace messages
by text content, filtering by message type and tool name, and
toggling tool result visibility.

All filter state is persisted in Streamlit session state.
"""

import logging
from dataclasses import dataclass

import streamlit as st

from src.ingest.trace_viewer_parser import TraceMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraceFilterState:
    """Immutable snapshot of the current trace filter settings."""

    search_text: str
    selected_types: tuple[str, ...]
    selected_tool: str
    hide_tool_results: bool


# Display labels for message type filter
MESSAGE_TYPE_OPTIONS: dict[str, str] = {
    "system": "System",
    "assistant": "Assistant",
    "user": "User (Tool Result)",
}


def extract_unique_tool_names(messages: list[TraceMessage]) -> list[str]:
    """Extract sorted unique tool names from trace messages.

    Args:
        messages: List of TraceMessage from the parser

    Returns:
        Sorted list of unique tool names found in tool_use messages
    """
    tool_names: set[str] = set()
    for msg in messages:
        if msg.subtype == "tool_use" and msg.tool_name:
            tool_names.add(msg.tool_name)
    return sorted(tool_names)


def filter_messages(
    messages: list[TraceMessage],
    filter_state: TraceFilterState,
) -> list[TraceMessage]:
    """Apply all active filters to trace messages.

    Filters are combined with AND logic:
    - Text search (case-insensitive) on content, tool_name, tool_result
    - Message type filter (system, assistant, user)
    - Tool name filter (specific tool name)
    - Hide tool results toggle (excludes user/tool_result messages)

    Args:
        messages: Full list of TraceMessage to filter
        filter_state: Current filter settings

    Returns:
        Filtered list of TraceMessage matching all criteria
    """
    result = messages

    # Apply hide tool results toggle
    if filter_state.hide_tool_results:
        result = [msg for msg in result if msg.type != "user"]

    # Apply message type filter
    if filter_state.selected_types:
        result = [msg for msg in result if msg.type in filter_state.selected_types]

    # Apply tool name filter
    if filter_state.selected_tool:
        result = [
            msg
            for msg in result
            if (msg.subtype == "tool_use" and msg.tool_name == filter_state.selected_tool)
            or (
                msg.type == "user"
                and _is_result_for_tool(msg, filter_state.selected_tool, messages)
            )
        ]

    # Apply text search (last, as it's the most expensive)
    if filter_state.search_text:
        search_lower = filter_state.search_text.lower()
        result = [msg for msg in result if _message_matches_search(msg, search_lower)]

    return result


def _is_result_for_tool(
    result_msg: TraceMessage,
    tool_name: str,
    all_messages: list[TraceMessage],
) -> bool:
    """Check if a tool_result message belongs to a specific tool.

    Matches by checking if the result's parent_tool_use_id matches
    any tool_use message with the given tool name.
    """
    if not result_msg.parent_tool_use_id:
        return False

    for msg in all_messages:
        if (
            msg.subtype == "tool_use"
            and msg.tool_name == tool_name
            and msg.parent_tool_use_id == result_msg.parent_tool_use_id
        ):
            return True
    return False


def _message_matches_search(msg: TraceMessage, search_lower: str) -> bool:
    """Check if a message matches the search text (case-insensitive).

    Searches in content, tool_name, and tool_result fields.
    """
    if msg.content and search_lower in msg.content.lower():
        return True
    if msg.tool_name and search_lower in msg.tool_name.lower():
        return True
    if msg.tool_result and search_lower in msg.tool_result.lower():
        return True
    return False


def render_trace_filter_controls(
    messages: list[TraceMessage],
    session_key: str = "trace_filter",
) -> list[TraceMessage]:
    """Render filter controls and return filtered messages.

    Renders a text search input, message type multiselect, tool name
    dropdown, and hide tool results toggle. All filter state is
    persisted in Streamlit session state.

    Args:
        messages: Full list of TraceMessage to filter
        session_key: Prefix for session state keys

    Returns:
        Filtered list of TraceMessage matching all active filters
    """
    if not messages:
        return []

    tool_names = extract_unique_tool_names(messages)

    # Filter controls layout
    search_col, type_col = st.columns([2, 2])

    with search_col:
        search_text = st.text_input(
            "Search messages",
            value=st.session_state.get(f"{session_key}_search", ""),
            placeholder="Search by text content, tool name...",
            key=f"{session_key}_search",
        )

    with type_col:
        all_type_keys = list(MESSAGE_TYPE_OPTIONS.keys())
        selected_types = st.multiselect(
            "Message type",
            options=all_type_keys,
            default=st.session_state.get(f"{session_key}_types", all_type_keys),
            format_func=lambda x: MESSAGE_TYPE_OPTIONS.get(x, x),
            key=f"{session_key}_types",
        )

    tool_col, toggle_col = st.columns([2, 2])

    with tool_col:
        tool_options = [""] + tool_names
        selected_tool = st.selectbox(
            "Filter by tool",
            options=tool_options,
            format_func=lambda x: "All tools" if x == "" else x,
            key=f"{session_key}_tool",
        )

    with toggle_col:
        hide_tool_results = st.checkbox(
            "Hide tool results",
            value=st.session_state.get(f"{session_key}_hide_results", False),
            help="Hide user (tool_result) messages to focus on agent decisions",
            key=f"{session_key}_hide_results",
        )

    # Build filter state
    filter_state = TraceFilterState(
        search_text=search_text or "",
        selected_types=tuple(selected_types) if selected_types else (),
        selected_tool=selected_tool or "",
        hide_tool_results=hide_tool_results,
    )

    # Apply filters
    filtered = filter_messages(messages, filter_state)

    # Result count indicator
    total = len(messages)
    shown = len(filtered)
    if shown < total:
        st.markdown(
            f"**Showing {shown} of {total} messages**"
        )
    else:
        st.markdown(
            f"**Showing all {total} messages**"
        )

    return filtered
