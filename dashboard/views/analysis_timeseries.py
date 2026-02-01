"""
Time-Series Analysis View - GUI-driven trend analysis across multiple experiments.

Displays:
- Metric selector (pass_rate, duration, mcp_calls, deep_search_calls)
- Aggregation level (per-run, per-day, per-week)
- Run Analysis button calling time_series_analyzer.py
- Plotly line chart with trend line and anomaly markers
- Data table below chart
- CSV export
"""

import streamlit as st

from dashboard.utils.timeseries_config import (
    render_timeseries_config,
    run_and_display_timeseries,
)
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_timeseries_analysis():
    """Display GUI-driven time series analysis view."""

    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()

    nav_context = st.session_state.nav_context

    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)

    st.title("Time-Series Analysis")
    st.markdown("**Track metric changes across experiments over time**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration panel (experiment selector, metric selector, aggregation level)
    config = render_timeseries_config(loader)

    if config is None:
        st.info("Select at least 2 experiments to begin trend analysis.")
        return

    # Update navigation context with first experiment for reference
    if config.experiment_ids:
        nav_context.set_experiment(config.experiment_ids[0])

    st.markdown("---")

    # Run Analysis button
    run_clicked = st.button(
        "Run Time Series Analysis",
        type="primary",
        use_container_width=True,
        key="ts_run_analysis",
    )

    # Check for cached results
    cached_config = st.session_state.get("ts_config_config_snapshot")
    has_cached = cached_config == config.to_dict()

    if run_clicked or has_cached:
        run_and_display_timeseries(loader, config)
    else:
        st.info("Click **Run Time Series Analysis** to generate trend charts and anomaly detection.")

    st.markdown("---")

    # View notes
    st.subheader("Metrics Explained")
    st.markdown("""
    - **Pass Rate**: Percentage of tasks that passed verification
    - **Avg Duration**: Mean execution time per task (seconds)
    - **Avg MCP Calls**: Mean number of MCP tool invocations per task
    - **Avg Deep Search Calls**: Mean number of Deep Search queries per task
    - **Direction**: IMPROVING (better), DEGRADING (worse), or STABLE (no change)
    - **Slope**: Rate of change per experiment (from linear regression)
    - **Confidence**: How confident we are in the trend direction (0.0-1.0)
    - **Anomalies**: Unusual values detected via statistical outlier detection

    **Aggregation Levels**:
    - **Per Run**: Each experiment treated as a single data point
    - **Per Day**: Experiments grouped by date for daily trends
    - **Per Week**: Experiments grouped by week for weekly trends
    """)
