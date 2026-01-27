"""
Tool call timeline visualization for the dashboard.

Renders a Plotly scatter chart showing tool calls in sequence order,
color-coded by category (file read, file write, search, bash, planning, other).
Hover tooltips show tool name, sequence number, and a brief description.
"""

import logging

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ingest.trace_viewer_parser import TraceMessage

logger = logging.getLogger(__name__)

# Tool name -> category mapping
TOOL_TO_CATEGORY: dict[str, str] = {
    "Read": "File Read",
    "Write": "File Write",
    "Edit": "File Write",
    "Grep": "Search",
    "Glob": "Search",
    "Bash": "Bash",
    "EnterPlanMode": "Planning",
    "ExitPlanMode": "Planning",
    "TodoWrite": "Planning",
}

# Category -> color mapping
CATEGORY_COLORS: dict[str, str] = {
    "File Read": "#3b82f6",
    "File Write": "#22c55e",
    "Search": "#eab308",
    "Bash": "#6b7280",
    "Planning": "#8b5cf6",
    "Other": "#f97316",
}

# Ordered categories for consistent legend display
CATEGORY_ORDER = [
    "File Read",
    "File Write",
    "Search",
    "Bash",
    "Planning",
    "Other",
]

_TOOLTIP_MAX_LEN = 100


def get_tool_category(tool_name: str) -> str:
    """Return the category for a given tool name.

    Args:
        tool_name: Name of the tool (e.g., "Read", "Bash")

    Returns:
        Category string (e.g., "File Read", "Search", "Other")
    """
    return TOOL_TO_CATEGORY.get(tool_name, "Other")


def extract_tooltip(msg: TraceMessage) -> str:
    """Extract a brief description for hover tooltip.

    Returns file path for file operations, command preview for Bash,
    pattern for search tools, or empty string for others.

    Args:
        msg: A tool_use TraceMessage

    Returns:
        Brief description string for the tooltip
    """
    if msg.tool_input is None:
        return ""

    # File operations: show file_path
    file_path = msg.tool_input.get("file_path", "")
    if file_path:
        return file_path

    # Bash: show command preview
    command = msg.tool_input.get("command", "")
    if command:
        if len(command) > _TOOLTIP_MAX_LEN:
            return command[:_TOOLTIP_MAX_LEN] + "..."
        return command

    # Search: show pattern
    pattern = msg.tool_input.get("pattern", "")
    if pattern:
        return pattern

    return ""


def extract_tool_calls(messages: list[TraceMessage]) -> list[TraceMessage]:
    """Filter messages to only tool_use subtypes.

    Args:
        messages: Full list of TraceMessage

    Returns:
        List of tool_use TraceMessages in original order
    """
    return [msg for msg in messages if msg.subtype == "tool_use"]


def build_timeline_data(messages: list[TraceMessage]) -> pd.DataFrame:
    """Build a DataFrame for the Plotly timeline chart.

    Extracts tool_use messages and assigns categories, colors, and tooltips.

    Args:
        messages: Full list of TraceMessage

    Returns:
        DataFrame with columns: Tool, Category, Sequence, Description, Color
    """
    tool_calls = extract_tool_calls(messages)

    if not tool_calls:
        return pd.DataFrame(
            columns=["Tool", "Category", "Sequence", "Description", "Color"]
        )

    rows = []
    for msg in tool_calls:
        category = get_tool_category(msg.tool_name)
        rows.append(
            {
                "Tool": msg.tool_name,
                "Category": category,
                "Sequence": msg.sequence_number,
                "Description": extract_tooltip(msg),
                "Color": CATEGORY_COLORS[category],
            }
        )

    return pd.DataFrame(rows)


def render_tool_timeline(messages: list[TraceMessage]) -> None:
    """Render the tool call timeline visualization.

    Displays a Plotly scatter chart with tool calls on the vertical axis
    (sequence order) and horizontal position by tool category.
    Color-coded by category with legend toggle.

    Args:
        messages: Full list of TraceMessage from the parser
    """
    if not messages:
        st.info("No trace messages to display.")
        return

    df = build_timeline_data(messages)

    if df.empty:
        st.info("No tool calls found in trace.")
        return

    fig = px.scatter(
        df,
        x="Category",
        y="Sequence",
        color="Category",
        color_discrete_map=CATEGORY_COLORS,
        category_orders={"Category": CATEGORY_ORDER},
        hover_data={
            "Tool": True,
            "Sequence": True,
            "Description": True,
            "Category": False,
            "Color": False,
        },
        labels={
            "Sequence": "Sequence Number",
            "Category": "Tool Category",
        },
        title="Tool Call Timeline",
    )

    fig.update_traces(marker={"size": 8, "opacity": 0.8})

    fig.update_layout(
        yaxis={
            "autorange": "reversed",
            "title": "Sequence Number (execution order)",
        },
        xaxis={"title": "Tool Category"},
        legend_title="Category",
        hovermode="closest",
        height=max(400, min(len(df) * 4, 800)),
        margin={"t": 40, "b": 60},
    )

    st.plotly_chart(fig, use_container_width=True)
