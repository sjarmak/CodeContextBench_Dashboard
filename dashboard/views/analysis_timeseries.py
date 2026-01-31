"""
Time-Series Analysis View - GUI-driven trend analysis across experiments.

Provides:
- Metric selector (pass_rate, reward, duration, tokens)
- Date range picker (experiment selection for chronological ordering)
- Aggregation level selector (per-run, per-day, per-week)
- Run Analysis button with inline results display
- Plotly line chart with trend line, anomaly markers
- Data table below chart
- CSV export of results
"""

import streamlit as st

from dashboard.utils.timeseries_config import (
    render_timeseries_config,
    run_and_display_timeseries,
    _render_timeseries_results,
)


def show_timeseries_analysis():
    """Display GUI-driven time series analysis view."""

    st.title("Time-Series Analysis")
    st.markdown("**Configure and run trend analysis across experiments from the GUI**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        return

    # Configuration inline (no sidebar wrapper)
    config = render_timeseries_config(loader)

    if config is None:
        st.info("Select at least 2 experiments to begin trend analysis.")
        return

    # Run Analysis button
    run_clicked = st.button(
        "Run Analysis",
        type="primary",
        use_container_width=True,
        key="ts_run_analysis",
    )

    st.markdown("---")

    if run_clicked:
        run_and_display_timeseries(loader, config)
    elif "ts_config_results" in st.session_state:
        # Re-render cached results if available
        import pandas as pd

        cached_df = st.session_state["ts_config_results"]
        cached_anomaly_df = st.session_state.get("ts_config_anomaly_results", pd.DataFrame())
        cached_result = st.session_state.get("ts_config_analysis_result")

        if isinstance(cached_df, pd.DataFrame) and not cached_df.empty and cached_result is not None:
            _render_timeseries_results(cached_df, cached_anomaly_df, cached_result, config)
        else:
            st.info("Click **Run Analysis** to execute time series analysis with the current configuration.")
    else:
        st.info("Click **Run Analysis** to execute time series analysis with the current configuration.")

    # Interpretation guide at bottom
    st.markdown("---")

    with st.expander("Time Series Interpretation Guide"):
        st.markdown("""
### Key Concepts

**Direction**: The overall trend direction for each metric
- IMPROVING: Metric is getting better over time
- DEGRADING: Metric is getting worse over time
- STABLE: No significant change detected

**Slope**: Rate of change per experiment
- Steeper slopes indicate faster change
- Positive slope for pass_rate = improvement
- Negative slope for duration = improvement (faster)

**Confidence**: How well the trend line fits the data (R-squared)
- 0.0-0.3: Weak trend (high variability)
- 0.3-0.7: Moderate trend
- 0.7-1.0: Strong trend (consistent pattern)

**Anomalies**: Data points that deviate significantly from the trend
- Detected using z-score method (>2 standard deviations)
- May indicate regression, infrastructure issues, or data quality problems

### Important Notes

1. **Minimum 2 experiments required** for trend detection
2. **Experiment order matters** - experiments are analyzed chronologically
3. **Per-run aggregation** treats each experiment as one data point
4. **Anomalies are relative** to the dataset's distribution
        """)
