"""
GUI-driven failure analysis configuration component.

Provides Streamlit UI for configuring and running failure analysis:
- Experiment selector
- Agent filter (optional)
- View error clusters, failure patterns, top error messages
- Failure results: error category pie chart, failure pattern table, root cause summary
- CSV export
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.utils.common_components import (
    display_error_message,
    display_no_data_message,
    display_summary_card,
)


SESSION_KEY_PREFIX = "failure_config"


def _session_key(suffix: str) -> str:
    """Build a session state key for failure config."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class FailureConfig:
    """Immutable configuration for failure analysis."""

    experiment_id: str = ""
    agent_name: str = ""
    include_all_agents: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "experiment_id": self.experiment_id,
            "agent_name": self.agent_name,
            "include_all_agents": self.include_all_agents,
        }


def _render_experiment_selector(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> str:
    """Render experiment selector.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        Selected experiment ID or empty string
    """
    experiments = loader.list_experiments()
    if not experiments:
        st.warning("No experiments found in database.")
        return ""

    selected = st.selectbox(
        "Select Experiment",
        experiments,
        help="Choose the experiment to analyze failures for",
        key=f"{session_key}_experiment",
    )
    return selected or ""


def _render_agent_selector(
    loader,
    experiment_id: str,
    session_key: str = SESSION_KEY_PREFIX,
) -> tuple[str, bool]:
    """Render agent selector with 'All Agents' option.

    Args:
        loader: AnalysisLoader instance
        experiment_id: Selected experiment ID
        session_key: Session state key prefix

    Returns:
        Tuple of (agent_name, include_all_agents).
        When include_all_agents is True, agent_name is empty.
    """
    agents = loader.list_agents(experiment_id)
    if not agents:
        st.warning(f"No agents found for experiment {experiment_id}.")
        return ("", True)

    options = ["All Agents"] + agents
    selected = st.selectbox(
        "Focus Agent",
        options,
        help="Leave as 'All Agents' to see overall patterns, or select a specific agent",
        key=f"{session_key}_agent",
    )

    if selected == "All Agents" or selected is None:
        return ("", True)
    return (selected, False)


def render_failure_config(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> Optional[FailureConfig]:
    """Render full failure analysis configuration panel.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        FailureConfig if valid configuration, None otherwise
    """
    st.subheader("Configuration")

    experiment_id = _render_experiment_selector(loader, session_key)
    if not experiment_id:
        return None

    agent_name, include_all = _render_agent_selector(loader, experiment_id, session_key)

    return FailureConfig(
        experiment_id=experiment_id,
        agent_name=agent_name,
        include_all_agents=include_all,
    )


def _build_pattern_dataframe(
    failure_result,
) -> pd.DataFrame:
    """Build a DataFrame from FailureAnalysisResult patterns.

    Args:
        failure_result: FailureAnalysisResult from the analyzer

    Returns:
        DataFrame with one row per failure pattern
    """
    patterns = getattr(failure_result, "patterns", [])
    if not patterns:
        return pd.DataFrame()

    rows: list[dict] = []
    for pattern in patterns:
        rows.append({
            "Pattern": pattern.pattern_name,
            "Description": pattern.description,
            "Frequency": pattern.frequency,
            "Affected Tasks": len(pattern.affected_tasks),
            "Avg Duration (s)": round(pattern.avg_duration_seconds, 1) if pattern.avg_duration_seconds else 0.0,
            "Suggested Fix": pattern.suggested_fix,
            "Confidence": round(pattern.confidence, 2),
        })

    return pd.DataFrame(rows).sort_values("Frequency", ascending=False)


def _build_category_dataframe(
    failure_result,
) -> pd.DataFrame:
    """Build a DataFrame from FailureAnalysisResult top failing categories.

    Args:
        failure_result: FailureAnalysisResult from the analyzer

    Returns:
        DataFrame with one row per failing category
    """
    categories = getattr(failure_result, "top_failing_categories", [])
    if not categories:
        return pd.DataFrame()

    total_failures = getattr(failure_result, "total_failures", 0)

    rows: list[dict] = []
    for category, count in categories:
        pct = (count / total_failures * 100) if total_failures > 0 else 0.0
        rows.append({
            "Category": category,
            "Failures": count,
            "Percentage": round(pct, 1),
        })

    return pd.DataFrame(rows)


def _build_difficulty_dataframe(
    failure_result,
) -> pd.DataFrame:
    """Build a DataFrame from FailureAnalysisResult top failing difficulties.

    Args:
        failure_result: FailureAnalysisResult from the analyzer

    Returns:
        DataFrame with one row per difficulty level
    """
    difficulties = getattr(failure_result, "top_failing_difficulties", [])
    if not difficulties:
        return pd.DataFrame()

    total_failures = getattr(failure_result, "total_failures", 0)

    rows: list[dict] = []
    for difficulty, count in difficulties:
        pct = (count / total_failures * 100) if total_failures > 0 else 0.0
        rows.append({
            "Difficulty": difficulty,
            "Failures": count,
            "Percentage": round(pct, 1),
        })

    return pd.DataFrame(rows)


def _build_category_pie_chart(
    category_df: pd.DataFrame,
) -> Optional[go.Figure]:
    """Build Plotly pie chart showing failure category distribution.

    Args:
        category_df: DataFrame with category data

    Returns:
        Plotly Figure or None if no data
    """
    if category_df.empty:
        return None

    fig = px.pie(
        category_df,
        values="Failures",
        names="Category",
        title="Error Category Distribution",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")

    fig.update_layout(
        showlegend=True,
        height=400,
    )

    return fig


def _build_pattern_bar_chart(
    pattern_df: pd.DataFrame,
) -> Optional[go.Figure]:
    """Build Plotly horizontal bar chart showing failure pattern frequencies.

    Args:
        pattern_df: DataFrame with pattern data

    Returns:
        Plotly Figure or None if no data
    """
    if pattern_df.empty:
        return None

    sorted_df = pattern_df.sort_values("Frequency", ascending=True)

    fig = px.bar(
        sorted_df,
        x="Frequency",
        y="Pattern",
        orientation="h",
        color="Confidence",
        color_continuous_scale="RdYlGn",
        title="Failure Pattern Frequencies",
        hover_data=["Description", "Suggested Fix"],
    )

    fig.update_layout(
        showlegend=False,
        yaxis_title="",
        xaxis_title="Occurrence Count",
        height=max(300, len(sorted_df) * 50 + 100),
    )

    return fig


def run_and_display_failures(
    loader,
    config: FailureConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Run failure analysis and display results inline.

    Args:
        loader: AnalysisLoader instance
        config: FailureConfig with analysis parameters
        session_key: Session state key prefix
    """
    agent_arg = None if config.include_all_agents else config.agent_name

    failure_result = None
    try:
        with st.spinner(f"Analyzing failures for {config.experiment_id}..."):
            failure_result = loader.load_failures(
                config.experiment_id,
                agent_name=agent_arg,
            )
    except Exception as exc:
        display_error_message(f"Failed to load failure analysis: {exc}")
        return

    if failure_result is None:
        display_no_data_message("No failure analysis data available.")
        return

    pattern_df = _build_pattern_dataframe(failure_result)
    category_df = _build_category_dataframe(failure_result)
    difficulty_df = _build_difficulty_dataframe(failure_result)

    st.session_state[f"{session_key}_pattern_results"] = pattern_df
    st.session_state[f"{session_key}_category_results"] = category_df
    st.session_state[f"{session_key}_difficulty_results"] = difficulty_df
    st.session_state[f"{session_key}_failure_result"] = failure_result
    st.session_state[f"{session_key}_config_snapshot"] = config.to_dict()

    _render_failure_results(
        pattern_df, category_df, difficulty_df, failure_result, config, session_key
    )


def _render_failure_results(
    pattern_df: pd.DataFrame,
    category_df: pd.DataFrame,
    difficulty_df: pd.DataFrame,
    failure_result,
    config: FailureConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Render failure analysis results inline.

    Args:
        pattern_df: Failure patterns DataFrame
        category_df: Category distribution DataFrame
        difficulty_df: Difficulty distribution DataFrame
        failure_result: Raw FailureAnalysisResult
        config: Analysis configuration
        session_key: Session state key prefix
    """
    # Summary cards
    st.subheader("Failure Summary")

    total_failures = getattr(failure_result, "total_failures", 0)
    total_tasks = getattr(failure_result, "total_tasks", 0)
    failure_rate = getattr(failure_result, "failure_rate", 0.0)
    pattern_count = len(pattern_df) if not pattern_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        display_summary_card(
            "Total Failures",
            str(total_failures),
            f"out of {total_tasks} tasks",
            color="red",
        )
    with col2:
        rate_color = "red" if failure_rate > 0.5 else "orange" if failure_rate > 0.25 else "blue"
        display_summary_card(
            "Failure Rate",
            f"{failure_rate:.1%}",
            f"{total_failures}/{total_tasks}",
            color=rate_color,
        )
    with col3:
        display_summary_card(
            "Patterns Detected",
            str(pattern_count),
            "failure patterns",
            color="orange" if pattern_count > 0 else "gray",
        )
    with col4:
        agent_label = config.agent_name if config.agent_name else "All Agents"
        display_summary_card(
            "Agent",
            agent_label,
            config.experiment_id,
            color="blue",
        )

    st.markdown("---")

    # Error category pie chart
    st.subheader("Error Category Distribution")

    pie_chart = _build_category_pie_chart(category_df)
    if pie_chart is not None:
        st.plotly_chart(pie_chart, use_container_width=True)
    else:
        display_no_data_message("No category data available for chart.")

    if not category_df.empty:
        st.dataframe(category_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Failure pattern table and chart
    st.subheader("Failure Patterns")

    pattern_chart = _build_pattern_bar_chart(pattern_df)
    if pattern_chart is not None:
        st.plotly_chart(pattern_chart, use_container_width=True)
    else:
        display_no_data_message("No failure patterns detected.")

    if not pattern_df.empty:
        st.dataframe(
            pattern_df[["Pattern", "Description", "Frequency", "Affected Tasks", "Confidence"]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")

    # Root cause summary (suggested fixes)
    st.subheader("Root Cause Summary")

    if not pattern_df.empty:
        fixes = pattern_df[pattern_df["Suggested Fix"] != ""][["Pattern", "Suggested Fix", "Confidence"]]
        if not fixes.empty:
            fixes_sorted = fixes.sort_values("Confidence", ascending=False)
            st.dataframe(fixes_sorted, use_container_width=True, hide_index=True)
        else:
            st.info("No suggested fixes available.")
    else:
        st.info("No root cause analysis available.")

    st.markdown("---")

    # Difficulty distribution
    st.subheader("Difficulty Distribution")

    if not difficulty_df.empty:
        st.dataframe(difficulty_df, use_container_width=True, hide_index=True)
    else:
        st.info("No difficulty distribution data available.")

    st.markdown("---")

    # CSV export
    st.subheader("Export Results")

    if not pattern_df.empty:
        csv_data = pattern_df.to_csv(index=False)
        st.download_button(
            label="Download Failure Analysis as CSV",
            data=csv_data,
            file_name="failure_analysis_results.csv",
            mime="text/csv",
            key=f"{session_key}_export_csv",
        )
