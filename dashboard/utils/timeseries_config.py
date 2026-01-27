"""
GUI-driven time series analysis configuration component.

Provides Streamlit UI for configuring and running time series analysis:
- Metric selector (pass_rate, reward, duration, tokens)
- Date range picker (experiment selection for chronological ordering)
- Aggregation level (per-run, per-day, per-week)
- Run analysis with inline results display
- Plotly line chart with trend line, anomaly markers, data table
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


# Available metrics for time series analysis
TIMESERIES_METRICS: tuple[str, ...] = (
    "pass_rate",
    "avg_duration_seconds",
    "avg_mcp_calls",
    "avg_deep_search_calls",
)

TIMESERIES_METRIC_LABELS: dict[str, str] = {
    "pass_rate": "Pass Rate",
    "avg_duration_seconds": "Avg Duration (seconds)",
    "avg_mcp_calls": "Avg MCP Calls",
    "avg_deep_search_calls": "Avg Deep Search Calls",
}

# Aggregation level options
AGGREGATION_LEVELS: tuple[tuple[str, str], ...] = (
    ("per-run", "Per Run (each experiment as a data point)"),
    ("per-day", "Per Day (group experiments by date)"),
    ("per-week", "Per Week (group experiments by week)"),
)

SESSION_KEY_PREFIX = "ts_config"


def _session_key(suffix: str) -> str:
    """Build a session state key for time series config."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class TimeSeriesConfig:
    """Immutable configuration for time series analysis."""

    experiment_ids: tuple[str, ...] = ()
    selected_metrics: tuple[str, ...] = ("pass_rate",)
    aggregation_level: str = "per-run"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "experiment_ids": list(self.experiment_ids),
            "selected_metrics": list(self.selected_metrics),
            "aggregation_level": self.aggregation_level,
        }


def _render_experiment_selector(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> tuple[str, ...]:
    """Render experiment multiselect for chronological selection.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        Tuple of selected experiment IDs
    """
    experiments = loader.list_experiments()
    if not experiments:
        st.warning("No experiments found in database.")
        return ()

    default_count = min(3, len(experiments))
    default_selection = experiments[-default_count:] if experiments else []

    selected = st.multiselect(
        "Select Experiments (chronological order)",
        experiments,
        default=default_selection,
        help="Choose 2+ experiments to analyze trends over time",
        key=f"{session_key}_experiments",
    )
    return tuple(selected)


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
        "Metrics to Track",
        list(TIMESERIES_METRICS),
        default=["pass_rate", "avg_duration_seconds"],
        format_func=lambda m: TIMESERIES_METRIC_LABELS.get(m, m),
        help="Select which metrics to display in the time series chart",
        key=f"{session_key}_metrics",
    )
    return tuple(selected) if selected else ("pass_rate",)


def _render_aggregation_selector(
    session_key: str = SESSION_KEY_PREFIX,
) -> str:
    """Render aggregation level selector.

    Args:
        session_key: Session state key prefix

    Returns:
        Selected aggregation level identifier
    """
    options = [level[0] for level in AGGREGATION_LEVELS]
    labels = {level[0]: level[1] for level in AGGREGATION_LEVELS}

    selected = st.selectbox(
        "Aggregation Level",
        options,
        format_func=lambda x: labels.get(x, x),
        help="How to group experiment data points",
        key=f"{session_key}_aggregation",
    )
    return selected or "per-run"


def render_timeseries_config(
    loader,
    session_key: str = SESSION_KEY_PREFIX,
) -> Optional[TimeSeriesConfig]:
    """Render full time series analysis configuration panel.

    Args:
        loader: AnalysisLoader instance
        session_key: Session state key prefix

    Returns:
        TimeSeriesConfig if valid configuration, None otherwise
    """
    st.subheader("Configuration")

    # Experiment selection
    experiment_ids = _render_experiment_selector(loader, session_key)
    if not experiment_ids:
        return None

    if len(experiment_ids) < 2:
        st.warning("Select at least 2 experiments to view trends.")
        return None

    st.markdown("---")
    st.subheader("Metrics & Aggregation")

    # Metric selection
    selected_metrics = _render_metric_selector(session_key)

    # Aggregation level
    aggregation_level = _render_aggregation_selector(session_key)

    return TimeSeriesConfig(
        experiment_ids=experiment_ids,
        selected_metrics=selected_metrics,
        aggregation_level=aggregation_level,
    )


def _build_timeseries_dataframe(
    analysis_result,
    selected_metrics: tuple[str, ...],
) -> pd.DataFrame:
    """Build a DataFrame from TimeSeriesAnalysisResult trends.

    Args:
        analysis_result: TimeSeriesAnalysisResult from the analyzer
        selected_metrics: Metrics to include

    Returns:
        DataFrame with trend data rows
    """
    rows: list[dict] = []

    trends = getattr(analysis_result, "trends", {})

    for metric_name, agent_trends in trends.items():
        if metric_name not in selected_metrics:
            continue

        for agent_name, trend in agent_trends.items():
            direction = trend.direction.value if hasattr(trend.direction, "value") else str(trend.direction)
            rows.append({
                "Metric": metric_name,
                "Agent": agent_name,
                "Direction": direction.upper(),
                "First Value": round(trend.first_value, 4),
                "Last Value": round(trend.last_value, 4),
                "Change (%)": round(trend.percent_change, 2),
                "Slope": round(trend.slope, 6),
                "Confidence": round(trend.confidence, 4),
                "Data Points": trend.data_points,
                "Anomalies": len(trend.anomaly_indices) if trend.anomaly_indices else 0,
            })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _build_anomaly_dataframe(
    analysis_result,
    selected_metrics: tuple[str, ...],
) -> pd.DataFrame:
    """Build a DataFrame of detected anomalies.

    Args:
        analysis_result: TimeSeriesAnalysisResult from the analyzer
        selected_metrics: Metrics to include

    Returns:
        DataFrame with anomaly details
    """
    rows: list[dict] = []

    trends = getattr(analysis_result, "trends", {})

    for metric_name, agent_trends in trends.items():
        if metric_name not in selected_metrics:
            continue

        for agent_name, trend in agent_trends.items():
            if not trend.has_anomalies:
                continue

            for idx, desc in zip(trend.anomaly_indices, trend.anomaly_descriptions):
                rows.append({
                    "Metric": metric_name,
                    "Agent": agent_name,
                    "Data Point Index": idx,
                    "Description": desc,
                })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _build_trend_line_chart(
    analysis_result,
    selected_metrics: tuple[str, ...],
    experiment_ids: tuple[str, ...],
) -> Optional[go.Figure]:
    """Build Plotly line chart showing metric trends over experiments.

    Args:
        analysis_result: TimeSeriesAnalysisResult from the analyzer
        selected_metrics: Metrics to include
        experiment_ids: Experiment IDs for x-axis labels

    Returns:
        Plotly Figure or None if no data
    """
    trends = getattr(analysis_result, "trends", {})
    if not trends:
        return None

    chart_data: list[dict] = []

    for metric_name, agent_trends in trends.items():
        if metric_name not in selected_metrics:
            continue

        for agent_name, trend in agent_trends.items():
            n_points = trend.data_points
            first_val = trend.first_value
            last_val = trend.last_value

            # Reconstruct approximate data points along the trend line
            for i in range(n_points):
                x_label = experiment_ids[i] if i < len(experiment_ids) else f"Point {i}"
                # Linear interpolation from trend: y = first_value + slope * i
                # Use intercept = first_value (approximate, since slope is from regression)
                y_mean = first_val + (last_val - first_val) * (i / max(n_points - 1, 1))
                chart_data.append({
                    "Experiment": x_label,
                    "Value": round(y_mean, 4),
                    "Series": f"{agent_name} / {TIMESERIES_METRIC_LABELS.get(metric_name, metric_name)}",
                    "Order": i,
                })

    if not chart_data:
        return None

    chart_df = pd.DataFrame(chart_data)
    chart_df = chart_df.sort_values("Order")

    fig = px.line(
        chart_df,
        x="Experiment",
        y="Value",
        color="Series",
        markers=True,
        title="Metric Trends Over Experiments",
    )

    fig.update_layout(
        showlegend=True,
        height=500,
        xaxis_title="Experiment",
        yaxis_title="Value",
        xaxis={"categoryorder": "array", "categoryarray": list(experiment_ids)},
    )

    return fig


def _build_anomaly_markers_chart(
    analysis_result,
    selected_metrics: tuple[str, ...],
    experiment_ids: tuple[str, ...],
) -> Optional[go.Figure]:
    """Build Plotly chart highlighting anomaly data points.

    Args:
        analysis_result: TimeSeriesAnalysisResult from the analyzer
        selected_metrics: Metrics to include
        experiment_ids: Experiment IDs for x-axis labels

    Returns:
        Plotly Figure or None if no anomalies
    """
    trends = getattr(analysis_result, "trends", {})
    if not trends:
        return None

    marker_data: list[dict] = []

    for metric_name, agent_trends in trends.items():
        if metric_name not in selected_metrics:
            continue

        for agent_name, trend in agent_trends.items():
            if not trend.has_anomalies:
                continue

            for idx, desc in zip(trend.anomaly_indices, trend.anomaly_descriptions):
                x_label = experiment_ids[idx] if idx < len(experiment_ids) else f"Point {idx}"
                # Extract value from description "Point N: VALUE"
                try:
                    value = float(desc.split(": ")[1])
                except (IndexError, ValueError):
                    value = 0.0

                marker_data.append({
                    "Experiment": x_label,
                    "Value": value,
                    "Series": f"{agent_name} / {TIMESERIES_METRIC_LABELS.get(metric_name, metric_name)}",
                    "Description": desc,
                })

    if not marker_data:
        return None

    marker_df = pd.DataFrame(marker_data)

    fig = px.scatter(
        marker_df,
        x="Experiment",
        y="Value",
        color="Series",
        hover_data=["Description"],
        title="Anomaly Data Points",
        symbol_sequence=["x"],
    )

    fig.update_traces(marker={"size": 14})

    fig.update_layout(
        showlegend=True,
        height=400,
        xaxis_title="Experiment",
        yaxis_title="Value",
        xaxis={"categoryorder": "array", "categoryarray": list(experiment_ids)},
    )

    return fig


def run_and_display_timeseries(
    loader,
    config: TimeSeriesConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Run time series analysis and display results inline.

    Args:
        loader: AnalysisLoader instance
        config: TimeSeriesConfig with analysis parameters
        session_key: Session state key prefix
    """
    analysis_result = None
    try:
        with st.spinner("Running time series analysis..."):
            analysis_result = loader.load_timeseries(
                experiment_ids=list(config.experiment_ids),
                agent_names=None,
            )
    except Exception as exc:
        display_error_message(f"Failed to run time series analysis: {exc}")
        return

    if analysis_result is None:
        display_no_data_message("No time series analysis data available.")
        return

    ts_df = _build_timeseries_dataframe(analysis_result, config.selected_metrics)
    anomaly_df = _build_anomaly_dataframe(analysis_result, config.selected_metrics)

    st.session_state[f"{session_key}_results"] = ts_df
    st.session_state[f"{session_key}_anomaly_results"] = anomaly_df
    st.session_state[f"{session_key}_analysis_result"] = analysis_result
    st.session_state[f"{session_key}_config_snapshot"] = config.to_dict()

    _render_timeseries_results(ts_df, anomaly_df, analysis_result, config, session_key)


def _render_timeseries_results(
    ts_df: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    analysis_result,
    config: TimeSeriesConfig,
    session_key: str = SESSION_KEY_PREFIX,
) -> None:
    """Render time series analysis results inline.

    Args:
        ts_df: Trend data DataFrame
        anomaly_df: Anomaly DataFrame
        analysis_result: Raw TimeSeriesAnalysisResult
        config: Analysis configuration
        session_key: Session state key prefix
    """
    # Summary cards
    st.subheader("Trend Summary")

    total_trends = len(ts_df) if not ts_df.empty else 0
    improving_count = int((ts_df["Direction"] == "IMPROVING").sum()) if not ts_df.empty else 0
    degrading_count = int((ts_df["Direction"] == "DEGRADING").sum()) if not ts_df.empty else 0
    anomaly_count = int(ts_df["Anomalies"].sum()) if not ts_df.empty and "Anomalies" in ts_df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        display_summary_card(
            "Total Trends",
            str(total_trends),
            f"{len(config.experiment_ids)} experiments",
            color="blue",
        )
    with col2:
        display_summary_card(
            "Improving",
            str(improving_count),
            "metrics trending up",
            color="green" if improving_count > 0 else "gray",
        )
    with col3:
        display_summary_card(
            "Degrading",
            str(degrading_count),
            "metrics trending down",
            color="red" if degrading_count > 0 else "gray",
        )
    with col4:
        display_summary_card(
            "Anomalies",
            str(anomaly_count),
            "unusual data points",
            color="orange" if anomaly_count > 0 else "gray",
        )

    st.markdown("---")

    # Trend line chart
    st.subheader("Metric Trends")

    trend_chart = _build_trend_line_chart(
        analysis_result, config.selected_metrics, config.experiment_ids,
    )
    if trend_chart is not None:
        st.plotly_chart(trend_chart, use_container_width=True)
    else:
        display_no_data_message("No trend data available for chart.")

    st.markdown("---")

    # Data table
    st.subheader("Trend Details")

    if ts_df.empty:
        display_no_data_message("No trend data available.")
    else:
        st.dataframe(ts_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Anomaly chart and table
    st.subheader("Anomaly Detection")

    anomaly_chart = _build_anomaly_markers_chart(
        analysis_result, config.selected_metrics, config.experiment_ids,
    )
    if anomaly_chart is not None:
        st.plotly_chart(anomaly_chart, use_container_width=True)

    if anomaly_df.empty:
        st.success("No anomalies detected in the selected metrics.")
    else:
        st.dataframe(anomaly_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # CSV export
    st.subheader("Export Results")

    if not ts_df.empty:
        csv_data = ts_df.to_csv(index=False)
        st.download_button(
            label="Download Trend Data as CSV",
            data=csv_data,
            file_name="timeseries_analysis_results.csv",
            mime="text/csv",
            key=f"{session_key}_export_csv",
        )
