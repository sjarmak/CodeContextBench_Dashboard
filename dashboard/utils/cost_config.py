"""
GUI-driven cost analysis configuration component.

Provides Streamlit UI for configuring and running cost analysis:
- Experiment selector
- Baseline agent selector for comparison
- View token costs (input/output/cached), execution time, cost per model
- Cost results: Plotly bar charts for token distribution, cost breakdown table
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


# Available cost metrics
COST_METRICS: tuple[str, ...] = (
    "total_cost_usd",
    "cost_per_success",
    "input_cost_usd",
    "output_cost_usd",
    "total_input_tokens",
    "total_output_tokens",
)

COST_METRIC_LABELS: dict[str, str] = {
    "total_cost_usd": "Total Cost (USD)",
    "cost_per_success": "Cost per Success (USD)",
    "input_cost_usd": "Input Cost (USD)",
    "output_cost_usd": "Output Cost (USD)",
    "total_input_tokens": "Total Input Tokens",
    "total_output_tokens": "Total Output Tokens",
}

SESSION_KEY_PREFIX = "cost_config"


def _session_key(suffix: str) -> str:
    """Build a session state key for cost config."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class CostConfig:
    """Immutable configuration for cost analysis."""

    experiment_id: str = ""
    baseline_agent: str = ""
    selected_metrics: tuple[str, ...] = COST_METRICS

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "experiment_id": self.experiment_id,
            "baseline_agent": self.baseline_agent,
            "selected_metrics": list(self.selected_metrics),
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
        help="Choose the experiment to analyze costs for",
        key=f"{session_key}_experiment",
    )
    return selected or ""


def _render_baseline_selector(
    loader,
    experiment_id: str,
    session_key: str = SESSION_KEY_PREFIX,
) -> str:
    """Render baseline agent selector.

    Args:
        loader: AnalysisLoader instance
        experiment_id: Selected experiment ID
        session_key: Session state key prefix

    Returns:
        Selected baseline agent name or empty string
    """
    agents = loader.list_agents(experiment_id)
    if not agents:
        st.warning(f"No agents found for experiment {experiment_id}.")
        return ""

    selected = st.selectbox(
        "Baseline Agent",
        agents,
        help="Agent to compare costs against (others are variants)",
        key=f"{session_key}_baseline",
    )
    return selected or ""


def _render_metric_selector(
    session_key: str = SESSION_KEY_PREFIX,
) -> tuple[str, ...]:
    """Render cost metric multiselect.

    Args:
        session_key: Session state key prefix

    Returns:
        Tuple of selected cost metric names
    """
    selected = st.multiselect(
        "Cost Metrics",
        list(COST_METRICS),
        default=list(COST_METRICS[:4]),
        format_func=lambda m: COST_METRIC_LABELS.get(m, m),
        help="Select which cost metrics to display",
        key=f"{session_key}_metrics",
    )
    return tuple(selected) if selected else COST_METRICS[:4]


def render_cost_config(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> Optional[CostConfig]:
    """Render full cost analysis configuration panel.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        CostConfig if valid configuration, None otherwise
    """
    st.subheader("Configuration")

    experiment_id = _render_experiment_selector(loader, session_key)
    if not experiment_id:
        return None

    baseline_agent = _render_baseline_selector(loader, experiment_id, session_key)
    if not baseline_agent:
        return None

    st.markdown("---")
    st.subheader("Metrics")

    selected_metrics = _render_metric_selector(session_key)

    return CostConfig(
        experiment_id=experiment_id,
        baseline_agent=baseline_agent,
        selected_metrics=selected_metrics,
    )


def _build_cost_dataframe(
    cost_result,
) -> pd.DataFrame:
    """Build a DataFrame from CostAnalysisResult agent metrics.

    Args:
        cost_result: CostAnalysisResult from the analyzer

    Returns:
        DataFrame with one row per agent
    """
    rows: list[dict] = []

    agent_metrics = getattr(cost_result, "agent_metrics", {})
    for agent_name, metrics in agent_metrics.items():
        rows.append({
            "Agent": agent_name,
            "Total Cost (USD)": metrics.total_cost_usd,
            "Input Cost (USD)": metrics.input_cost_usd,
            "Output Cost (USD)": metrics.output_cost_usd,
            "Cost per Success (USD)": metrics.cost_per_success,
            "Total Input Tokens": metrics.total_input_tokens,
            "Total Output Tokens": metrics.total_output_tokens,
            "Total Tasks": metrics.total_tasks,
            "Passed Tasks": metrics.passed_tasks,
            "Pass Rate": metrics.pass_rate,
            "Cost Rank": metrics.cost_rank,
            "Efficiency Rank": metrics.efficiency_rank,
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _build_regression_dataframe(
    cost_result,
) -> pd.DataFrame:
    """Build a DataFrame from CostAnalysisResult regressions.

    Args:
        cost_result: CostAnalysisResult from the analyzer

    Returns:
        DataFrame with one row per regression
    """
    regressions = getattr(cost_result, "regressions", [])
    if not regressions:
        return pd.DataFrame()

    rows: list[dict] = []
    for reg in regressions:
        rows.append({
            "Agent": reg.agent_name,
            "Metric": reg.metric_name,
            "Baseline Value": reg.baseline_value,
            "Regression Value": reg.regression_value,
            "Delta (%)": reg.delta_percent,
            "Severity": reg.severity.upper(),
        })

    return pd.DataFrame(rows)


def _format_cost_value(value) -> str:
    """Format a cost value for display.

    Args:
        value: Raw cost value

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)

    if abs(val) < 0.01 and val != 0:
        return f"${val:.4f}"
    return f"${val:.2f}"


def _format_token_value(value) -> str:
    """Format a token count for display.

    Args:
        value: Raw token count

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
    return f"{val:,.0f}"


def _build_token_distribution_chart(
    cost_df: pd.DataFrame,
) -> Optional[go.Figure]:
    """Build Plotly bar chart showing token distribution per agent.

    Args:
        cost_df: DataFrame with cost data

    Returns:
        Plotly Figure or None if no data
    """
    if cost_df.empty:
        return None

    chart_data: list[dict] = []
    for _, row in cost_df.iterrows():
        chart_data.append({
            "Agent": row["Agent"],
            "Token Type": "Input Tokens",
            "Count": row["Total Input Tokens"],
        })
        chart_data.append({
            "Agent": row["Agent"],
            "Token Type": "Output Tokens",
            "Count": row["Total Output Tokens"],
        })

    if not chart_data:
        return None

    chart_df = pd.DataFrame(chart_data)

    fig = px.bar(
        chart_df,
        x="Agent",
        y="Count",
        color="Token Type",
        barmode="group",
        color_discrete_map={
            "Input Tokens": "#1f77b4",
            "Output Tokens": "#ff7f0e",
        },
        title="Token Distribution by Agent",
    )

    fig.update_layout(
        showlegend=True,
        yaxis_title="Token Count",
        xaxis_title="",
        height=400,
    )

    return fig


def _build_cost_breakdown_chart(
    cost_df: pd.DataFrame,
) -> Optional[go.Figure]:
    """Build Plotly bar chart showing cost breakdown per agent.

    Args:
        cost_df: DataFrame with cost data

    Returns:
        Plotly Figure or None if no data
    """
    if cost_df.empty:
        return None

    chart_data: list[dict] = []
    for _, row in cost_df.iterrows():
        chart_data.append({
            "Agent": row["Agent"],
            "Cost Type": "Input Cost",
            "Cost (USD)": row["Input Cost (USD)"],
        })
        chart_data.append({
            "Agent": row["Agent"],
            "Cost Type": "Output Cost",
            "Cost (USD)": row["Output Cost (USD)"],
        })

    if not chart_data:
        return None

    chart_df = pd.DataFrame(chart_data)

    fig = px.bar(
        chart_df,
        x="Agent",
        y="Cost (USD)",
        color="Cost Type",
        barmode="stack",
        color_discrete_map={
            "Input Cost": "#2ca02c",
            "Output Cost": "#d62728",
        },
        title="Cost Breakdown by Agent",
    )

    fig.update_layout(
        showlegend=True,
        yaxis_title="Cost (USD)",
        xaxis_title="",
        height=400,
    )

    return fig


def run_and_display_cost(
    loader,
    config: CostConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Run cost analysis and display results inline.

    Args:
        loader: AnalysisLoader instance
        config: CostConfig with analysis parameters
        session_key: Session state key prefix
    """
    cost_result = None
    try:
        with st.spinner(f"Analyzing costs for {config.experiment_id}..."):
            cost_result = loader.load_cost(
                config.experiment_id,
                baseline_agent=config.baseline_agent,
            )
    except Exception as exc:
        display_error_message(f"Failed to load cost analysis: {exc}")
        return

    if cost_result is None:
        display_no_data_message("No cost analysis data available.")
        return

    cost_df = _build_cost_dataframe(cost_result)
    regression_df = _build_regression_dataframe(cost_result)

    st.session_state[f"{session_key}_results"] = cost_df
    st.session_state[f"{session_key}_regression_results"] = regression_df
    st.session_state[f"{session_key}_cost_result"] = cost_result
    st.session_state[f"{session_key}_config_snapshot"] = config.to_dict()

    _render_cost_results(cost_df, regression_df, cost_result, config, session_key)


def _render_cost_results(
    cost_df: pd.DataFrame,
    regression_df: pd.DataFrame,
    cost_result,
    config: CostConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Render cost analysis results inline.

    Args:
        cost_df: Agent cost metrics DataFrame
        regression_df: Regression detections DataFrame
        cost_result: Raw CostAnalysisResult
        config: Analysis configuration
        session_key: Session state key prefix
    """
    # Summary cards
    st.subheader("Cost Summary")

    total_cost = getattr(cost_result, "total_experiment_cost", 0.0)
    cheapest = getattr(cost_result, "cheapest_agent", "N/A")
    most_efficient = getattr(cost_result, "most_efficient_agent", "N/A")
    regression_count = len(regression_df) if not regression_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        display_summary_card(
            "Total Cost",
            _format_cost_value(total_cost),
            "all agents combined",
            color="blue",
        )
    with col2:
        display_summary_card(
            "Cheapest Agent",
            cheapest,
            "lowest total cost",
            color="green",
        )
    with col3:
        display_summary_card(
            "Most Efficient",
            most_efficient,
            "best pass rate per dollar",
            color="green",
        )
    with col4:
        display_summary_card(
            "Regressions",
            str(regression_count),
            "cost regressions detected",
            color="red" if regression_count > 0 else "gray",
        )

    st.markdown("---")

    # Cost breakdown table
    st.subheader("Agent Cost Breakdown")

    if cost_df.empty:
        display_no_data_message("No agent cost data available.")
    else:
        display_cols = [
            "Agent", "Total Cost (USD)", "Input Cost (USD)", "Output Cost (USD)",
            "Cost per Success (USD)", "Total Tasks", "Passed Tasks", "Pass Rate",
            "Cost Rank", "Efficiency Rank",
        ]
        available_cols = [c for c in display_cols if c in cost_df.columns]
        st.dataframe(cost_df[available_cols], use_container_width=True, hide_index=True)

    st.markdown("---")

    # Token distribution chart
    st.subheader("Token Distribution")

    token_chart = _build_token_distribution_chart(cost_df)
    if token_chart is not None:
        st.plotly_chart(token_chart, use_container_width=True)
    else:
        display_no_data_message("No token data available for chart.")

    st.markdown("---")

    # Cost breakdown chart
    st.subheader("Cost Breakdown")

    cost_chart = _build_cost_breakdown_chart(cost_df)
    if cost_chart is not None:
        st.plotly_chart(cost_chart, use_container_width=True)
    else:
        display_no_data_message("No cost data available for chart.")

    st.markdown("---")

    # Regressions table
    st.subheader("Cost Regressions")

    if regression_df.empty:
        st.success("No cost regressions detected.")
    else:
        st.dataframe(regression_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # CSV export
    st.subheader("Export Results")

    if not cost_df.empty:
        csv_data = cost_df.to_csv(index=False)
        st.download_button(
            label="Download Cost Analysis as CSV",
            data=csv_data,
            file_name="cost_analysis_results.csv",
            mime="text/csv",
            key=f"{session_key}_export_csv",
        )
