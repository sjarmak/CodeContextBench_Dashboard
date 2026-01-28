"""
GUI-driven comparison analysis configuration component.

Provides Streamlit UI for configuring and running comparison analysis:
- Two run selectors (baseline experiment+agent, variant experiment+agent)
- Metric selector (pass_rate, reward, duration, tokens)
- Task filter
- Run Comparison button with inline results display
- Results: comparison table with deltas, bar chart, scatter plot
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


# Available metrics for comparison
COMPARISON_METRICS: tuple[str, ...] = (
    "pass_rate",
    "reward",
    "avg_duration_seconds",
    "total_tokens",
)

METRIC_LABELS: dict[str, str] = {
    "pass_rate": "Pass Rate",
    "reward": "Reward",
    "avg_duration_seconds": "Avg Duration (s)",
    "total_tokens": "Total Tokens",
}

SESSION_KEY_PREFIX = "comparison_config"


def _session_key(suffix: str) -> str:
    """Build a session state key for comparison config."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class ComparisonConfig:
    """Immutable configuration for comparison analysis."""

    baseline_experiment: str = ""
    baseline_agent: str = ""
    variant_experiment: str = ""
    variant_agent: str = ""
    selected_metrics: tuple[str, ...] = COMPARISON_METRICS
    task_filter: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "baseline_experiment": self.baseline_experiment,
            "baseline_agent": self.baseline_agent,
            "variant_experiment": self.variant_experiment,
            "variant_agent": self.variant_agent,
            "selected_metrics": list(self.selected_metrics),
            "task_filter": self.task_filter,
        }


def _render_run_selector(
    loader,
    label: str,
    session_key: str,
) -> tuple[str, str]:
    """Render experiment + agent selector pair.

    Args:
        loader: AnalysisLoader instance
        label: Display label (e.g., "Baseline" or "Variant")
        session_key: Session state key prefix

    Returns:
        Tuple of (experiment_id, agent_name)
    """
    st.markdown(f"**{label} Run**")

    experiments = loader.list_experiments()
    if not experiments:
        st.warning("No experiments found in database.")
        return ("", "")

    selected_exp = st.selectbox(
        f"{label} Experiment",
        experiments,
        key=f"{session_key}_exp",
        help=f"Select the {label.lower()} experiment",
    )

    if not selected_exp:
        return ("", "")

    agents = loader.list_agents(selected_exp)
    if not agents:
        st.warning(f"No agents found for experiment {selected_exp}.")
        return (selected_exp, "")

    selected_agent = st.selectbox(
        f"{label} Agent",
        agents,
        key=f"{session_key}_agent",
        help=f"Select the {label.lower()} agent",
    )

    return (selected_exp or "", selected_agent or "")


def _render_metric_selector(
    session_key: str = SESSION_KEY_PREFIX,
) -> tuple[str, ...]:
    """Render metric multiselect.

    Args:
        session_key: Session state key prefix

    Returns:
        Tuple of selected metric names
    """
    selected = st.multiselect(
        "Metrics to Compare",
        list(COMPARISON_METRICS),
        default=list(COMPARISON_METRICS),
        format_func=lambda m: METRIC_LABELS.get(m, m),
        help="Select which metrics to include in the comparison",
        key=f"{session_key}_metrics",
    )
    return tuple(selected) if selected else COMPARISON_METRICS


def _render_task_filter(
    session_key: str = SESSION_KEY_PREFIX,
) -> str:
    """Render task filter text input.

    Args:
        session_key: Session state key prefix

    Returns:
        Task filter string (empty if no filter)
    """
    return st.text_input(
        "Task Filter",
        value="",
        help="Filter tasks by ID pattern (e.g., 'swe-bench' or leave empty for all)",
        key=f"{session_key}_task_filter",
    )


def render_comparison_config(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> Optional[ComparisonConfig]:
    """Render full comparison configuration panel.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        ComparisonConfig if valid, None otherwise
    """
    st.subheader("Configuration")

    # Baseline run selector
    baseline_exp, baseline_agent = _render_run_selector(
        loader, "Baseline", f"{session_key}_baseline"
    )
    if not baseline_exp or not baseline_agent:
        return None

    st.markdown("---")

    # Variant run selector
    variant_exp, variant_agent = _render_run_selector(
        loader, "Variant", f"{session_key}_variant"
    )
    if not variant_exp or not variant_agent:
        return None

    st.markdown("---")
    st.subheader("Metrics & Filters")

    # Metric selector
    selected_metrics = _render_metric_selector(session_key)

    # Task filter
    task_filter = _render_task_filter(session_key)

    return ComparisonConfig(
        baseline_experiment=baseline_exp,
        baseline_agent=baseline_agent,
        variant_experiment=variant_exp,
        variant_agent=variant_agent,
        selected_metrics=selected_metrics,
        task_filter=task_filter,
    )


def _build_comparison_dataframe(
    baseline_result,
    variant_result,
    config: ComparisonConfig,
) -> pd.DataFrame:
    """Build comparison DataFrame from two comparison results.

    Shows per-agent metrics side by side with deltas.

    Args:
        baseline_result: ComparisonResult for baseline run
        variant_result: ComparisonResult for variant run
        config: Comparison configuration

    Returns:
        DataFrame with comparison data
    """
    rows: list[dict] = []

    baseline_metrics = baseline_result.agent_results.get(config.baseline_agent, {})
    variant_metrics = variant_result.agent_results.get(config.variant_agent, {})

    for metric in config.selected_metrics:
        label = METRIC_LABELS.get(metric, metric)
        b_val = baseline_metrics.get(metric)
        v_val = variant_metrics.get(metric)

        b_display = _format_metric_value(metric, b_val)
        v_display = _format_metric_value(metric, v_val)

        delta = ""
        if b_val is not None and v_val is not None:
            try:
                diff = float(v_val) - float(b_val)
                if metric == "pass_rate":
                    delta = f"{diff:+.1%}"
                else:
                    delta = f"{diff:+.2f}"
            except (ValueError, TypeError):
                delta = "N/A"

        rows.append({
            "Metric": label,
            "Baseline": b_display,
            "Variant": v_display,
            "Delta": delta,
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _format_metric_value(metric: str, value) -> str:
    """Format a metric value for display.

    Args:
        metric: Metric name
        value: Raw value

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"

    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)

    if metric == "pass_rate":
        return f"{val:.1%}"
    if metric in ("avg_duration_seconds", "reward"):
        return f"{val:.2f}"
    if metric == "total_tokens":
        return f"{val:,.0f}"
    return f"{val:.2f}"


def _build_pass_rate_bar_chart(
    baseline_result,
    variant_result,
    config: ComparisonConfig,
) -> Optional[go.Figure]:
    """Build bar chart comparing pass rates.

    Args:
        baseline_result: ComparisonResult for baseline
        variant_result: ComparisonResult for variant
        config: Comparison config

    Returns:
        Plotly Figure or None if no data
    """
    baseline_metrics = baseline_result.agent_results.get(config.baseline_agent, {})
    variant_metrics = variant_result.agent_results.get(config.variant_agent, {})

    baseline_pr = baseline_metrics.get("pass_rate")
    variant_pr = variant_metrics.get("pass_rate")

    if baseline_pr is None and variant_pr is None:
        return None

    chart_data = []
    if baseline_pr is not None:
        chart_data.append({
            "Run": f"{config.baseline_experiment} / {config.baseline_agent}",
            "Pass Rate": float(baseline_pr),
            "Group": "Baseline",
        })
    if variant_pr is not None:
        chart_data.append({
            "Run": f"{config.variant_experiment} / {config.variant_agent}",
            "Pass Rate": float(variant_pr),
            "Group": "Variant",
        })

    if not chart_data:
        return None

    df = pd.DataFrame(chart_data)

    fig = px.bar(
        df,
        x="Run",
        y="Pass Rate",
        color="Group",
        color_discrete_map={
            "Baseline": "#1f77b4",
            "Variant": "#ff7f0e",
        },
        title="Pass Rate Comparison",
        barmode="group",
    )

    fig.update_layout(
        showlegend=True,
        yaxis_title="Pass Rate",
        xaxis_title="",
        height=400,
    )

    return fig


def _build_per_task_scatter(
    baseline_result,
    variant_result,
    config: ComparisonConfig,
    metric: str = "pass_rate",
) -> Optional[go.Figure]:
    """Build scatter plot of per-task metrics.

    Plots baseline metric (x) vs variant metric (y) for each task.

    Args:
        baseline_result: ComparisonResult for baseline
        variant_result: ComparisonResult for variant
        config: Comparison config
        metric: Metric to plot

    Returns:
        Plotly Figure or None if no data
    """
    # Extract per-task results if available
    baseline_tasks = _extract_per_task_metrics(baseline_result, config.baseline_agent, metric)
    variant_tasks = _extract_per_task_metrics(variant_result, config.variant_agent, metric)

    if not baseline_tasks or not variant_tasks:
        return None

    # Build paired data for tasks present in both
    common_tasks = set(baseline_tasks.keys()) & set(variant_tasks.keys())

    if not common_tasks:
        return None

    scatter_data = [
        {
            "Task": task_id,
            "Baseline": baseline_tasks[task_id],
            "Variant": variant_tasks[task_id],
        }
        for task_id in sorted(common_tasks)
    ]

    if not scatter_data:
        return None

    df = pd.DataFrame(scatter_data)
    label = METRIC_LABELS.get(metric, metric)

    fig = px.scatter(
        df,
        x="Baseline",
        y="Variant",
        hover_data=["Task"],
        title=f"Per-Task {label}: Baseline vs Variant",
    )

    # Add diagonal reference line
    all_vals = list(df["Baseline"]) + list(df["Variant"])
    if all_vals:
        min_val = min(all_vals)
        max_val = max(all_vals)
        fig.add_shape(
            type="line",
            x0=min_val,
            y0=min_val,
            x1=max_val,
            y1=max_val,
            line={"color": "gray", "dash": "dash"},
        )

    fig.update_layout(
        xaxis_title=f"Baseline ({config.baseline_agent})",
        yaxis_title=f"Variant ({config.variant_agent})",
        height=450,
    )

    return fig


def _extract_per_task_metrics(
    comparison_result,
    agent_name: str,
    metric: str,
) -> dict[str, float]:
    """Extract per-task metric values from a comparison result.

    Args:
        comparison_result: ComparisonResult
        agent_name: Agent to extract metrics for
        metric: Metric name

    Returns:
        Dict of task_id -> metric_value
    """
    result: dict[str, float] = {}

    # Try per_task_results if available
    per_task = getattr(comparison_result, "per_task_results", None)
    if per_task is None:
        return result

    for task_id, task_data in per_task.items():
        agent_data = task_data.get(agent_name, {})
        val = agent_data.get(metric)
        if val is not None:
            try:
                result = {**result, task_id: float(val)}
            except (ValueError, TypeError):
                pass

    return result


def run_and_display_comparison(
    loader,
    config: ComparisonConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Run comparison analysis and display results inline.

    Args:
        loader: AnalysisLoader instance
        config: ComparisonConfig with analysis parameters
        session_key: Session state key prefix
    """
    baseline_result = None
    variant_result = None

    try:
        with st.spinner(f"Loading baseline: {config.baseline_experiment}..."):
            baseline_result = loader.load_comparison(
                config.baseline_experiment,
                baseline_agent=config.baseline_agent,
            )
    except Exception as exc:
        display_error_message(f"Failed to load baseline: {exc}")
        return

    try:
        with st.spinner(f"Loading variant: {config.variant_experiment}..."):
            variant_result = loader.load_comparison(
                config.variant_experiment,
                baseline_agent=config.variant_agent,
            )
    except Exception as exc:
        display_error_message(f"Failed to load variant: {exc}")
        return

    if baseline_result is None or variant_result is None:
        display_no_data_message("Could not load comparison data for one or both runs.")
        return

    # Store results in session state
    st.session_state[f"{session_key}_baseline_result"] = baseline_result
    st.session_state[f"{session_key}_variant_result"] = variant_result
    st.session_state[f"{session_key}_config_snapshot"] = config.to_dict()

    _render_comparison_results(baseline_result, variant_result, config, session_key)


def _render_comparison_results(
    baseline_result,
    variant_result,
    config: ComparisonConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Render comparison results inline.

    Args:
        baseline_result: ComparisonResult for baseline
        variant_result: ComparisonResult for variant
        config: Comparison configuration
        session_key: Session state key prefix
    """
    # Summary cards
    st.subheader("Comparison Summary")

    baseline_metrics = baseline_result.agent_results.get(config.baseline_agent, {})
    variant_metrics = variant_result.agent_results.get(config.variant_agent, {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        display_summary_card(
            "Baseline",
            config.baseline_agent,
            config.baseline_experiment,
            color="blue",
        )
    with col2:
        display_summary_card(
            "Variant",
            config.variant_agent,
            config.variant_experiment,
            color="orange",
        )
    with col3:
        b_tasks = baseline_result.total_tasks
        display_summary_card(
            "Baseline Tasks",
            str(b_tasks),
            color="blue",
        )
    with col4:
        v_tasks = variant_result.total_tasks
        display_summary_card(
            "Variant Tasks",
            str(v_tasks),
            color="orange",
        )

    st.markdown("---")

    # Comparison table with deltas
    st.subheader("Metric Comparison")

    comparison_df = _build_comparison_dataframe(baseline_result, variant_result, config)
    if comparison_df.empty:
        display_no_data_message("No comparison data available.")
    else:
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Bar chart of pass rates
    st.subheader("Pass Rate Comparison")

    bar_chart = _build_pass_rate_bar_chart(baseline_result, variant_result, config)
    if bar_chart is not None:
        st.plotly_chart(bar_chart, use_container_width=True)
    else:
        display_no_data_message("No pass rate data available for chart.")

    st.markdown("---")

    # Scatter plot of per-task metrics
    st.subheader("Per-Task Scatter Plot")

    scatter_metric = config.selected_metrics[0] if config.selected_metrics else "pass_rate"
    scatter_chart = _build_per_task_scatter(
        baseline_result, variant_result, config, scatter_metric
    )
    if scatter_chart is not None:
        st.plotly_chart(scatter_chart, use_container_width=True)
    else:
        st.info(
            "Per-task scatter plot requires per-task metrics in both runs. "
            "This data may not be available for all experiment types."
        )

    st.markdown("---")

    # CSV export
    st.subheader("Export Results")

    if not comparison_df.empty:
        csv_data = comparison_df.to_csv(index=False)
        st.download_button(
            label="Download Comparison as CSV",
            data=csv_data,
            file_name="comparison_report.csv",
            mime="text/csv",
            key=f"{session_key}_export_csv",
        )
