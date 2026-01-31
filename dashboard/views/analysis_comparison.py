"""
Comparison Analysis View - GUI-driven two-run comparison.

Displays:
- Two run selectors (baseline and variant experiment+agent)
- Metric selector (pass rate, reward, duration, tokens)
- Task filter
- Run Comparison button
- Results: comparison table with deltas, bar chart, scatter plot
- CSV export
"""

import streamlit as st

from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.comparison_config import (
    render_comparison_config,
    run_and_display_comparison,
    _render_comparison_results,
)
from dashboard.utils.navigation import NavigationContext


def show_comparison_analysis():
    """Display GUI-driven comparison analysis view."""

    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()

    nav_context = st.session_state.nav_context

    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)

    st.title("Comparison Analysis")
    st.markdown("**Configure and run comparison analysis between two runs**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        return

    # Configuration in main content area (not sidebar - sidebar is invisible below nav)
    config = render_comparison_config(loader)

    if config is None:
        st.info("Select baseline and variant runs above to begin.")
        return

    # Update navigation context
    nav_context.navigate_to(
        "analysis_comparison",
        experiment=config.baseline_experiment,
    )

    # Run Comparison button
    run_clicked = st.button(
        "Run Comparison",
        type="primary",
        use_container_width=True,
        key="comparison_run_btn",
    )

    st.markdown("---")

    if run_clicked:
        run_and_display_comparison(loader, config)
    elif "comparison_config_baseline_result" in st.session_state:
        # Re-render cached results if available
        baseline_result = st.session_state.get("comparison_config_baseline_result")
        variant_result = st.session_state.get("comparison_config_variant_result")
        if baseline_result is not None and variant_result is not None:
            _render_comparison_results(baseline_result, variant_result, config)
        else:
            st.info("Click **Run Comparison** to compare the selected runs.")
    else:
        st.info("Click **Run Comparison** to compare the selected runs.")

    # Interpretation guide
    st.markdown("---")

    with st.expander("Comparison Guide"):
        st.markdown("""
### Metrics

- **Pass Rate**: Fraction of tasks completed successfully
- **Reward**: Reward score from the evaluation harness
- **Avg Duration**: Average time per task (in seconds)
- **Total Tokens**: Total tokens used across all tasks

### Reading Results

- **Delta**: Variant value minus Baseline value. Positive delta means the
  variant has a higher value for that metric.
- **Bar Chart**: Visual comparison of pass rates between runs.
- **Scatter Plot**: Each point is a task. Points above the diagonal line
  indicate the variant scored higher than the baseline on that task.
        """)
