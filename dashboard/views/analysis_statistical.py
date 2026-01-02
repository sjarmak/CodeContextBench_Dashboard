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
    """Display statistical significance analysis view."""
    
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
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.subheader("Configuration")
        
        # Experiment selector
        experiment_id = experiment_selector()
        if experiment_id is None:
            return
        
        # Update navigation context
        nav_context.navigate_to("analysis_statistical", experiment=experiment_id)
        
        # Baseline agent selector
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {experiment_id}")
            return
        
        baseline_agent = st.selectbox(
            "Baseline Agent",
            agents,
            help="Agent to compare all others against"
        )
        
        nav_context.navigate_to("analysis_statistical", experiment=experiment_id, agents=[baseline_agent])
        
        # Confidence level
        confidence_level = confidence_level_slider(default=0.95)
        
        alpha = 1.0 - confidence_level
        
        st.markdown("---")
        
        # Advanced filtering section
        st.subheader("Advanced Filters")
        filter_config = render_filter_panel("statistical", loader, experiment_id)
    
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
        st.info(f"📊 Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Test Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Count significant tests
        significant_count = 0
        total_tests = 0
        if statistical_result.test_results:
            for metric_tests in statistical_result.test_results.values():
                for test_info in metric_tests.values():
                    total_tests += 1
                    if test_info.get('p_value', 1.0) < alpha:
                        significant_count += 1
        
        display_summary_card(
            "Significant Tests",
            f"{significant_count}/{total_tests}",
            f"({significant_count/max(total_tests, 1)*100:.0f}% at α={alpha:.2f})",
            color="green" if significant_count > 0 else "gray"
        )
    
    with col2:
        # Count effect size magnitudes
        large_effects = 0
        if statistical_result.effect_sizes:
            for effects in statistical_result.effect_sizes.values():
                for effect_val in effects.values():
                    if isinstance(effect_val, dict):
                        magnitude = effect_val.get('magnitude', 'negligible')
                        if magnitude in ['large', 'very_large']:
                            large_effects += 1
        
        display_summary_card(
            "Large Effect Sizes",
            str(large_effects),
            "Practically significant differences",
            color="red" if large_effects > 0 else "gray"
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
        if statistical_result.test_results:
            results_data = []
            
            for metric, tests in statistical_result.test_results.items():
                for comparison_pair, test_info in tests.items():
                    p_value = test_info.get('p_value')
                    test_type = test_info.get('test_type', 'unknown')
                    statistic = test_info.get('statistic')
                    
                    is_significant = p_value < alpha if p_value else False
                    
                    results_row = {
                        "Metric": metric,
                        "Comparison": comparison_pair,
                        "Test Type": test_type,
                        "Statistic": f"{statistic:.4f}" if statistic else "N/A",
                        "P-Value": f"{p_value:.4f}" if p_value else "N/A",
                        "Significant": "✓" if is_significant else "✗",
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
    
    try:
        if statistical_result.effect_sizes:
            # Create effect size visualization
            col1, col2 = st.columns(2)
            
            effect_data = []
            
            for metric, effects in statistical_result.effect_sizes.items():
                for comparison, effect_info in effects.items():
                    if isinstance(effect_info, dict):
                        effect_size = effect_info.get('value', 0)
                        effect_name = effect_info.get('name', "Cohen's d")
                        magnitude = effect_info.get('magnitude', 'negligible')
                        
                        effect_data.append({
                            "Metric": metric,
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
                
                for metric, effects in statistical_result.effect_sizes.items():
                    st.markdown(f"**{metric}**")
                    
                    for comparison, effect_info in effects.items():
                        if isinstance(effect_info, dict):
                            effect_size = effect_info.get('value', 0)
                            effect_name = effect_info.get('name', "Cohen's d")
                            
                            with st.container():
                                st.markdown(f"*{comparison}*")
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
        if statistical_result.power_analysis:
            power_data = []
            
            for metric, power_info in statistical_result.power_analysis.items():
                power_row = {
                    "Metric": metric,
                    "Sample Size": power_info.get('sample_size', 'N/A'),
                    "Power": f"{power_info.get('power', 0):.2%}" if power_info.get('power') else "N/A",
                    "Min Detectable Effect": f"{power_info.get('min_effect', 0):.4f}" if power_info.get('min_effect') else "N/A",
                }
                power_data.append(power_row)
            
            if power_data:
                power_df = pd.DataFrame(power_data)
                st.dataframe(power_df, use_container_width=True, hide_index=True)
                
                st.info("""
                **Power Analysis Interpretation**:
                - **Power**: Probability of detecting true effect (target: 0.80+)
                - **Min Detectable Effect**: Smallest meaningful difference detectable at given power
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
        if statistical_result.test_results:
            metric_summary = {}
            
            for metric, tests in statistical_result.test_results.items():
                significant = 0
                total = 0
                
                for test_info in tests.values():
                    total += 1
                    if test_info.get('p_value', 1.0) < alpha:
                        significant += 1
                
                metric_summary[metric] = {
                    "Significant": significant,
                    "Total": total,
                    "Percentage": f"{significant/max(total, 1)*100:.0f}%",
                }
            
            summary_data = [
                {"Metric": m, **v} for m, v in metric_summary.items()
            ]
            
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
                "significant_count": significant_count if statistical_result.test_results else 0,
                "total_tests": total_tests if statistical_result.test_results else 0,
            },
            "test_results": statistical_result.test_results or {},
            "effect_sizes": statistical_result.effect_sizes or {},
            "power_analysis": statistical_result.power_analysis or {},
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
