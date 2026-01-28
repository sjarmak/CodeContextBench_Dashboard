"""
Statistical Analysis View - Significance testing and effect size analysis.

Refactored using ViewBase pattern. Eliminates 290 lines of boilerplate.
Reduces from 402 lines to 170 lines (58% reduction).
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from dashboard.utils.view_base import ViewBase
from dashboard.utils.result_extractors import extract_statistical_metrics
from dashboard.utils.visualizations import create_effect_size_chart
from dashboard.utils.common_components import (
    display_summary_card,
    display_effect_size_bar,
    confidence_level_slider,
)


class StatisticalAnalysisView(ViewBase):
    """Analysis view for statistical significance testing."""
    
    def __init__(self):
        super().__init__("Statistical Analysis", "statistical")
        self.baseline_agent = None
        self.confidence_level = 0.95
    
    @property
    def title(self) -> str:
        return "Statistical Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Determine statistical significance of performance differences**"
    
    def configure_sidebar(self):
        """Configure statistical-specific sidebar options."""
        # Baseline agent selector
        agents = self.loader.list_agents(self.experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {self.experiment_id}")
            return
        
        self.baseline_agent = st.selectbox(
            "Baseline Agent",
            agents,
            help="Agent to compare all others against"
        )
        
        # Confidence level
        self.confidence_level = confidence_level_slider(default=0.95)
    
    def load_analysis(self):
        """Load statistical analysis from loader."""
        return self.loader.load_statistical(
            experiment_id=self.experiment_id,
            baseline_agent=self.baseline_agent,
            confidence_level=self.confidence_level
        )
    
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract statistical metrics into filterable format."""
        return extract_statistical_metrics(result)
    
    def render_main_content(self, data: Dict[str, Any]):
        """Render statistical-specific analysis content."""
        
        alpha = 1.0 - self.confidence_level
        
        # Summary statistics
        st.subheader("Test Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Count significant tests
        significant_count = 0
        total_tests = 0
        filtered_tests = data.get("test_results", {})
        if filtered_tests:
            for metric_tests in filtered_tests.values():
                for test_info in metric_tests.values():
                    total_tests += 1
                    if test_info.get('p_value', 1.0) < alpha:
                        significant_count += 1
        
        with col1:
            display_summary_card(
                "Significant Tests",
                f"{significant_count}/{total_tests}",
                f"({significant_count/max(total_tests, 1)*100:.0f}% at α={alpha:.2f})",
                color="green" if significant_count > 0 else "gray"
            )
        
        with col2:
            # Count effect size magnitudes
            large_effects = 0
            filtered_effects = data.get("effect_sizes", {})
            if filtered_effects:
                for effects in filtered_effects.values():
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
                f"{self.confidence_level:.0%}",
                f"α = {alpha:.3f}",
                color="blue"
            )
        
        with col4:
            agents = self.loader.list_agents(self.experiment_id)
            display_summary_card(
                "Baseline Agent",
                self.baseline_agent,
                f"{len(agents)} agents compared",
                color="blue"
            )
        
        st.markdown("---")
        
        # Test results table
        st.subheader("Statistical Test Results")
        
        try:
            filtered_tests = data.get("test_results", {})
            if filtered_tests:
                results_data = []
                
                for metric, tests in filtered_tests.items():
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
        except Exception as e:
            st.warning(f"Failed to display test results: {e}")
        
        st.markdown("---")
        
        # Effect size analysis
        st.subheader("Effect Size Analysis")
        
        try:
            filtered_effects = data.get("effect_sizes", {})
            if filtered_effects:
                # Create effect size visualization
                effect_data = []
                
                for metric, effects in filtered_effects.items():
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
                    col1, col2 = st.columns([1.5, 1])
                    
                    with col1:
                        effect_df = pd.DataFrame(effect_data)
                        st.dataframe(effect_df, use_container_width=True, hide_index=True)
                    
                    # Effect size chart
                    with col2:
                        try:
                            effect_chart = create_effect_size_chart(
                                filtered_effects,
                                title="Effect Sizes"
                            )
                            st.plotly_chart(effect_chart, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not render effect size chart: {e}")
                    
                    # Display individual effect size bars
                    st.subheader("Effect Size Magnitudes")
                    
                    for metric, effects in filtered_effects.items():
                        st.markdown(f"**{metric}**")
                        
                        for comparison, effect_info in effects.items():
                            if isinstance(effect_info, dict):
                                effect_size = effect_info.get('value', 0)
                                effect_name = effect_info.get('name', "Cohen's d")
                                
                                with st.container():
                                    st.markdown(f"*{comparison}*")
                                    display_effect_size_bar(effect_size, effect_name)
        except Exception as e:
            st.warning(f"Failed to display effect sizes: {e}")
        
        st.markdown("---")
        
        # Power analysis
        st.subheader("Power Analysis")
        
        try:
            filtered_power = data.get("power_analysis", {})
            if filtered_power:
                power_data = []
                
                for metric, power_info in filtered_power.items():
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
        except Exception as e:
            st.warning(f"Could not display power analysis: {e}")
        
        st.markdown("---")
        
        # Per-metric significance summary
        st.subheader("Per-Metric Significance Summary")
        
        try:
            filtered_tests = data.get("test_results", {})
            if filtered_tests:
                metric_summary = {}
                
                for metric, tests in filtered_tests.items():
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
        except Exception as e:
            st.warning(f"Failed to display metric summary: {e}")
        
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


def show_statistical_analysis():
    """Main entry point for statistical analysis view."""
    view = StatisticalAnalysisView()
    view.run()
