"""
Failure Analysis View - GUI-driven failure pattern analysis.

Displays:
- Experiment selector and agent filter
- Failure pattern detection and distribution
- Error category pie chart
- Failure pattern frequency table
- Root cause summary with suggested fixes
- CSV export
"""

import streamlit as st

from dashboard.utils.failure_config import (
    render_failure_config,
    run_and_display_failures,
    _render_failure_results,
)


def show_failure_analysis():
    """Display GUI-driven failure analysis view."""

    st.title("Failure Analysis")
    st.markdown("**Configure and run failure pattern analysis from the GUI**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        return

    # Configuration inline (no sidebar wrapper)
    config = render_failure_config(loader)

    if config is None:
        st.info("Select an experiment to begin.")
        return

    # Run Analysis button
    run_clicked = st.button(
        "Run Failure Analysis",
        type="primary",
        use_container_width=True,
        key="failure_run_analysis",
    )

    st.markdown("---")

    if run_clicked:
        run_and_display_failures(loader, config)
    elif "failure_config_pattern_results" in st.session_state:
        # Re-render cached results if available
        import pandas as pd

        pattern_df = st.session_state.get("failure_config_pattern_results", pd.DataFrame())
        category_df = st.session_state.get("failure_config_category_results", pd.DataFrame())
        difficulty_df = st.session_state.get("failure_config_difficulty_results", pd.DataFrame())
        failure_result = st.session_state.get("failure_config_failure_result")
        if failure_result is not None:
            _render_failure_results(pattern_df, category_df, difficulty_df, failure_result, config)
        else:
            st.info("Click **Run Failure Analysis** to analyze failures with the current configuration.")
    else:
        st.info("Click **Run Failure Analysis** to analyze failures with the current configuration.")

    # Interpretation guide
    st.markdown("---")

    with st.expander("Failure Analysis Guide"):
        st.markdown("""
### Failure Patterns

The analyzer detects four types of failure patterns:

1. **High-Difficulty Task Failures**: Agent struggles with harder tasks (hard/expert difficulty)
2. **Category-Specific Failures**: 30%+ of failures concentrated in one category
3. **Duration-Related Failures**: Tasks exceeding 5 minutes (possible timeouts)
4. **Low-Quality Solutions**: Solutions with reward scores below 0.3

### Reading Results

- **Frequency**: Number of tasks matching this failure pattern
- **Confidence**: How reliably this pattern explains the failures (0.0-1.0)
- **Suggested Fix**: Recommended action to address the pattern
- **Error Category Distribution**: Pie chart showing which task categories fail most

### Using This Analysis

1. Focus on **high-confidence, high-frequency** patterns first
2. Use **suggested fixes** as starting points for agent improvement
3. Compare failure rates across agents to identify strengths/weaknesses
4. Monitor difficulty distribution to set realistic expectations
        """)
