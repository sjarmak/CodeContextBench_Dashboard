"""
Statistical Analysis View - GUI-driven significance testing and effect size analysis.

Provides:
- Experiment multiselect for choosing experiments to analyze
- Significance level input (alpha)
- Test type selector (t-test, Mann-Whitney, chi-squared)
- Effect size threshold configuration
- Run Analysis button with inline results display
- P-values table, effect size Plotly charts, confidence intervals
- CSV export of results
"""

import streamlit as st

from dashboard.utils.statistical_config import (
    render_statistical_config,
    run_and_display_results,
    _render_results,
)


def show_statistical_analysis():
    """Display GUI-driven statistical analysis view."""

    st.title("Statistical Analysis")
    st.markdown("**Configure and run statistical significance tests from the GUI**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        return

    # Configuration inline (no sidebar wrapper)
    config = render_statistical_config(loader)

    if config is None:
        st.info("Select experiments and a baseline agent to begin.")
        return

    # Run Analysis button
    run_clicked = st.button(
        "Run Analysis",
        type="primary",
        use_container_width=True,
        key="stat_run_analysis",
    )

    st.markdown("---")

    if run_clicked:
        run_and_display_results(loader, config)
    elif "stat_config_results" in st.session_state:
        # Re-render cached results if available
        import pandas as pd

        cached_df = st.session_state["stat_config_results"]
        if isinstance(cached_df, pd.DataFrame) and not cached_df.empty:
            _render_results(cached_df, config)
        else:
            st.info("Click **Run Analysis** to execute statistical tests with the current configuration.")
    else:
        st.info("Click **Run Analysis** to execute statistical tests with the current configuration.")

    # Interpretation guide at bottom
    st.markdown("---")

    with st.expander("Statistical Interpretation Guide"):
        alpha = config.significance_level if config else 0.05
        st.markdown(f"""
### Key Concepts

**P-Value**: Probability of observing data as extreme given null hypothesis (no difference)
- P < {alpha:.3f}: Reject null hypothesis - **Significant difference**
- P >= {alpha:.3f}: Fail to reject null - **Not significant**

**Effect Size**: Magnitude of the difference (independent of sample size)
- Negligible: < 0.2
- Small: 0.2 - 0.5
- Medium: 0.5 - 0.8
- Large: > 0.8

**Power**: Ability to detect true effect if it exists
- 0.80 = 80% chance to detect true difference
- Higher power requires larger sample size or larger true effect

### Important Notes

1. **Statistically significant does not equal Practically significant**
   - Large samples can show significant p-values for tiny effect sizes
   - Look at effect size to assess practical importance

2. **Multiple comparisons**
   - Many tests increase false positive rate
   - Consider Bonferroni correction for stringent control

3. **Sample size matters**
   - More tasks = higher power to detect effects
   - Check power analysis to assess detection capability
        """)
