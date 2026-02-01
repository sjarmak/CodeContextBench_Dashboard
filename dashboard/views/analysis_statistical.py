"""
Statistical Analysis View - Significance testing and effect size analysis.

Displays:
- Significant vs non-significant test results
- Effect size visualization (Cohen's d, Cramér's V)
- Power assessment display
- Per-metric significance badges
- Interpretation of results
"""

import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd

from dashboard.utils.statistical_config import (
    render_statistical_config,
    run_and_display_results,
    _render_results,
)
from dashboard.utils.common_components import (
    experiment_selector,
    export_json_button,
    display_no_data_message,
    display_error_message,
    display_summary_card,
    display_significance_badge,
    display_effect_size_bar,
    confidence_level_slider,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_statistical_analysis():
    """Display GUI-driven statistical analysis view."""

    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()

    nav_context = st.session_state.nav_context

    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)


    st.title("Statistical Analysis")
    st.markdown("**Determine statistical significance of performance differences**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration inline (no sidebar wrapper)
    config = render_statistical_config(loader)

    if config is None:
        st.info("Select experiments and a baseline agent to begin.")

    # Configuration in main area
    st.subheader("Configuration")

    col_exp, col_agent, col_conf = st.columns(3)

    with col_exp:
        try:
            experiments = loader.list_experiments()
            if not experiments:
                st.error("No experiments found in database.")
                return

            experiment_id = st.selectbox(
                "Select Experiment",
                experiments,
                key="statistical_experiment",
                help="Choose an experiment to analyze"
            )
        except Exception as e:
            st.error(f"Failed to load experiments: {e}")
            return

    # Update navigation context
    nav_context.navigate_to("analysis_statistical", experiment=experiment_id)

    with col_agent:
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.warning(f"No agents found for experiment {experiment_id}")
            agents = ["(no agents)"]

        baseline_agent = st.selectbox(
            "Baseline Agent",
            agents,
            key="statistical_baseline",
            help="Agent to compare all others against"
        )

    with col_conf:
        confidence_level = st.slider(
            "Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
            key="statistical_confidence",
            help="Higher confidence requires stronger evidence"
        )

    alpha = 1.0 - confidence_level

    # Advanced filtering in expander
    with st.expander("Advanced Filters"):
        filter_config = render_filter_panel("statistical", loader, experiment_id, key_suffix="stat")

    # Load statistical analysis results
    try:
        statistical_result = loader.load_statistical(
            experiment_id,
            baseline_agent=baseline_agent,
            confidence_level=confidence_level
        )
    except Exception as e:
        display_error_message(f"Failed to load statistical analysis: {e}")
        return
    
    if statistical_result is None:
        display_no_data_message("No statistical analysis data available")
        return
    
    # Apply filters if any are active
    filter_engine = FilterEngine()
    if filter_config.has_filters():
        st.info(f"Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Test Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Use pre-computed summary from result
        significant_count = statistical_result.significant_tests
        total_tests = statistical_result.total_tests

        display_summary_card(
            "Significant Tests",
            f"{significant_count}/{total_tests}",
            f"({statistical_result.significance_rate*100:.0f}% at α={alpha:.2f})",
            color="green" if significant_count > 0 else "gray"
        )

    with col2:
        # Count effect size magnitudes from tests
        large_effects = 0
        if statistical_result.tests:
            for variant_tests in statistical_result.tests.values():
                for test in variant_tests.values():
                    if test.effect_size and test.effect_size.interpretation in ['large', 'very_large']:
                        large_effects += 1

        display_summary_card(
            "Large Effect Sizes",
            str(large_effects),
            "Practically significant differences",
            color="gray" if large_effects > 0 else "gray"
        )

    with col3:
        display_summary_card(
            "Confidence Level",
            f"{confidence_level:.0%}",
            f"α = {alpha:.3f}",
            color="blue"
        )

    with col4:
        display_summary_card(
            "Baseline Agent",
            baseline_agent,
            f"{len(agents)} agents compared",
            color="blue"
        )
    
    st.markdown("---")
    
    # Test results table
    st.subheader("Statistical Test Results")

    try:
        if statistical_result.tests:
            results_data = []

            for variant_agent, variant_tests in statistical_result.tests.items():
                comparison_pair = f"{baseline_agent} vs {variant_agent}"

                for metric, test in variant_tests.items():
                    test_type = "t-test" if test.t_statistic else "Fisher's exact"

                    results_row = {
                        "Metric": test.metric_name,
                        "Comparison": comparison_pair,
                        "Test Type": test_type,
                        "Statistic": f"{test.t_statistic:.4f}" if test.t_statistic else "N/A",
                        "P-Value": f"{test.p_value:.4f}",
                        "Significant": "Yes" if test.is_significant else "No",
                    }
                    results_data.append(results_row)

            if results_data:
                results_df = pd.DataFrame(results_data)
                st.dataframe(results_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No test results available")
        else:
            display_no_data_message("No statistical tests performed")

    except Exception as e:
        display_error_message(f"Failed to display test results: {e}")
    
    st.markdown("---")
    
    # Effect size analysis
    st.subheader("Effect Size Analysis")

    with st.expander("Statistical Interpretation Guide"):
        guide_alpha = config.significance_level if config else 0.05
        st.markdown(f"""
### Key Concepts
        """)

    try:
        if statistical_result.tests:
            effect_data = []

            for variant_agent, variant_tests in statistical_result.tests.items():
                comparison = f"{baseline_agent} vs {variant_agent}"

                for metric, test in variant_tests.items():
                    if test.effect_size:
                        # Use Cohen's d or Cohen's h depending on what's available
                        effect_size = test.effect_size.cohens_d or test.effect_size.cramers_v or 0
                        effect_name = "Cohen's d" if test.effect_size.cohens_d else "Cohen's h/V"
                        magnitude = test.effect_size.interpretation or 'negligible'

                        effect_data.append({
                            "Metric": test.metric_name,
                            "Comparison": comparison,
                            "Effect Size": f"{effect_size:.4f}",
                            "Type": effect_name,
                            "Magnitude": magnitude.replace('_', ' ').title(),
                        })

            if effect_data:
                effect_df = pd.DataFrame(effect_data)
                st.dataframe(effect_df, use_container_width=True, hide_index=True)

                # Display individual effect size bars
                st.subheader("Effect Size Magnitudes")

                for variant_agent, variant_tests in statistical_result.tests.items():
                    comparison = f"{baseline_agent} vs {variant_agent}"
                    st.markdown(f"**{comparison}**")

                    for metric, test in variant_tests.items():
                        if test.effect_size:
                            effect_size = test.effect_size.cohens_d or test.effect_size.cramers_v or 0
                            effect_name = "Cohen's d" if test.effect_size.cohens_d else "Cohen's h/V"

                            with st.container():
                                st.markdown(f"*{test.metric_name}*")
                                display_effect_size_bar(effect_size, effect_name)
            else:
                display_no_data_message("No effect size data available")
        else:
            display_no_data_message("No effect size analysis available")

    except Exception as e:
        display_error_message(f"Failed to display effect sizes: {e}")
    
    st.markdown("---")
    
    # Power analysis
    st.subheader("Power Analysis")

    try:
        if statistical_result.tests:
            power_data = []

            for variant_agent, variant_tests in statistical_result.tests.items():
                for metric, test in variant_tests.items():
                    power_row = {
                        "Metric": test.metric_name,
                        "Comparison": f"{baseline_agent} vs {variant_agent}",
                        "Sample Size (Baseline)": test.baseline_n,
                        "Sample Size (Variant)": test.variant_n,
                        "Observed Power": f"{test.observed_power:.2%}",
                    }
                    power_data.append(power_row)

            if power_data:
                power_df = pd.DataFrame(power_data)
                st.dataframe(power_df, use_container_width=True, hide_index=True)

                st.info("""
                **Power Analysis Interpretation**:
                - **Power**: Probability of detecting true effect (target: 0.80+)
                - If power < 0.80, consider increasing sample size or looking for larger effects
                """)
            else:
                display_no_data_message("No power analysis available")
        else:
            st.info("Power analysis not available for this experiment")

    except Exception as e:
        st.warning(f"Could not display power analysis: {e}")
    
    st.markdown("---")
    
    # Per-metric significance summary
    st.subheader("Per-Metric Significance Summary")

    try:
        if statistical_result.tests:
            metric_summary = {}

            for variant_agent, variant_tests in statistical_result.tests.items():
                for metric, test in variant_tests.items():
                    if test.metric_name not in metric_summary:
                        metric_summary[test.metric_name] = {"Significant": 0, "Total": 0}

                    metric_summary[test.metric_name]["Total"] += 1
                    if test.is_significant:
                        metric_summary[test.metric_name]["Significant"] += 1

            summary_data = []
            for metric, counts in metric_summary.items():
                summary_data.append({
                    "Metric": metric,
                    "Significant": counts["Significant"],
                    "Total": counts["Total"],
                    "Percentage": f"{counts['Significant']/max(counts['Total'], 1)*100:.0f}%",
                })

            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No metric summary available")
        else:
            display_no_data_message("No test results to summarize")

    except Exception as e:
        display_error_message(f"Failed to display metric summary: {e}")
    
    st.markdown("---")
    
    # Interpretation guide
    st.subheader("Statistical Significance Interpretation")
    
    st.markdown(f"""
    ### Key Concepts
    
    **P-Value**: Probability of observing data as extreme given null hypothesis (no difference)
    - P < {alpha:.3f}: Reject null hypothesis → **Significant difference**
    - P ≥ {alpha:.3f}: Fail to reject null → **Not significant**
    
    **Effect Size**: Magnitude of the difference (independent of sample size)
    - Negligible: < 0.2
    - Small: 0.2 - 0.5
    - Medium: 0.5 - 0.8
    - Large: > 0.8
    
    **Power**: Ability to detect true effect if it exists
    - 0.80 = 80% chance to detect true difference
    - Higher power requires larger sample size or larger true effect
    
    ### Important Notes
    
    1. **Statistically significant ≠ Practically significant**
       - Large samples can show significant p-values for tiny effect sizes
       - Look at effect size to assess practical importance
    
    2. **Multiple comparisons**
       - Many tests increase false positive rate
       - Consider Bonferroni correction for stringent control
    
    3. **Sample size matters**
       - More tasks = higher power to detect effects
       - Check power analysis to assess detection capability
    """)
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")
    
    try:
        export_data = {
            "experiment_id": experiment_id,
            "baseline_agent": baseline_agent,
            "confidence_level": confidence_level,
            "alpha": alpha,
            "summary": {
                "significant_count": statistical_result.significant_tests,
                "total_tests": statistical_result.total_tests,
                "significance_rate": statistical_result.significance_rate,
            },
            "tests": statistical_result.to_dict().get("tests", {}),
        }

        export_json_button(export_data, f"statistical_{experiment_id}_{baseline_agent}")
    
    except Exception as e:
        display_error_message(f"Failed to export data: {e}")
    
    st.markdown("---")
    
    st.info("""
    **Next Steps**:
    - If differences are significant AND effect sizes are large → Agent difference is meaningful
    - If significant BUT effect sizes small → May be due to large sample size
    - If not significant BUT effect sizes large → Need more samples to confirm
    - Use Time-Series view to check if trends are consistent
    - Use Cost view to assess efficiency trade-offs
    """)
