"""
Trace summary overview panel for the dashboard.

Renders metric cards, tool call bar chart (Plotly), and file access table
from parsed trace data (US-009 trace_viewer_parser output).
"""

import logging
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ingest.trace_viewer_parser import (
    TraceSummary,
    compute_summary,
    parse_trace,
)

logger = logging.getLogger(__name__)


def _render_metric_cards(summary: TraceSummary, session_duration: float | None) -> None:
    """Render a row of metric cards for key trace statistics."""
    cols = st.columns(5)

    with cols[0]:
        st.metric("Total Messages", f"{summary.total_messages:,}")

    with cols[1]:
        st.metric("Tool Calls", f"{summary.total_tool_calls:,}")

    with cols[2]:
        st.metric("Unique Tools", f"{summary.unique_tools:,}")

    with cols[3]:
        st.metric("Total Tokens", f"{summary.total_tokens:,}")

    with cols[4]:
        if session_duration is not None and session_duration > 0:
            minutes = int(session_duration // 60)
            seconds = int(session_duration % 60)
            st.metric("Session Duration", f"{minutes}m {seconds}s")
        else:
            st.metric("Session Duration", "N/A")


def _render_tool_call_chart(tools_by_name: dict[str, int]) -> None:
    """Render a Plotly bar chart of tool call counts sorted descending."""
    if not tools_by_name:
        st.info("No tool calls found in trace.")
        return

    df = pd.DataFrame(
        [{"Tool": name, "Calls": count} for name, count in tools_by_name.items()]
    )

    fig = px.bar(
        df,
        x="Tool",
        y="Calls",
        title="Tool Calls by Name",
        labels={"Calls": "Call Count", "Tool": "Tool Name"},
        color="Tool",
        hover_data={"Calls": True},
    )

    fig.update_layout(
        showlegend=False,
        hovermode="x unified",
        xaxis_tickangle=-45,
        margin={"t": 40, "b": 80},
        height=350,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_file_access_table(files_accessed: dict[str, dict[str, int]]) -> None:
    """Render a table of file access counts sorted by total access descending."""
    if not files_accessed:
        st.info("No file access recorded in trace.")
        return

    rows = []
    for file_path, counts in files_accessed.items():
        read_count = counts.get("read_count", 0)
        write_count = counts.get("write_count", 0)
        edit_count = counts.get("edit_count", 0)
        total = read_count + write_count + edit_count
        rows.append(
            {
                "File Path": file_path,
                "Reads": read_count,
                "Writes": write_count,
                "Edits": edit_count,
                "Total": total,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("Total", ascending=False).reset_index(drop=True)

    st.dataframe(df, hide_index=True, use_container_width=True)


def render_trace_summary_panel(
    summary: TraceSummary,
    session_duration: float | None = None,
) -> None:
    """
    Render the trace summary overview panel.

    Displays metric cards, tool call bar chart, and file access table
    at the top of the trace view.

    Args:
        summary: TraceSummary from compute_summary()
        session_duration: Optional session duration in seconds
    """
    st.markdown("### Trace Summary")

    _render_metric_cards(summary, session_duration)

    col_chart, col_table = st.columns([1, 1])

    with col_chart:
        _render_tool_call_chart(summary.tools_by_name)

    with col_table:
        st.markdown("**File Access Summary**")
        _render_file_access_table(summary.files_accessed)


def load_and_render_trace_summary(
    claude_file: Path,
    session_duration: float | None = None,
) -> TraceSummary | None:
    """
    Parse a claude-code.txt file and render the trace summary panel.

    Convenience function that combines parsing and rendering.

    Args:
        claude_file: Path to claude-code.txt JSONL file
        session_duration: Optional session duration in seconds

    Returns:
        TraceSummary if parsing succeeded, None otherwise
    """
    if not claude_file.exists():
        logger.warning(f"Trace file not found: {claude_file}")
        return None

    messages = parse_trace(claude_file)
    if not messages:
        return None

    summary = compute_summary(messages)
    render_trace_summary_panel(summary, session_duration)
    return summary
