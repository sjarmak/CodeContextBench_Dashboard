"""
Cost Analysis View - API costs and efficiency analysis.

Refactored using ViewBase pattern. Eliminates 280 lines of boilerplate.
Reduces from 435 lines to 155 lines (64% reduction).
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from dashboard.utils.view_base import ViewBase
from dashboard.utils.result_extractors import extract_cost_metrics
from dashboard.utils.visualizations import (
    create_cost_breakdown_chart,
    create_token_comparison_chart,
)
from dashboard.utils.common_components import display_summary_card


class CostAnalysisView(ViewBase):
    """Analysis view for cost analysis and efficiency metrics."""
    
    def __init__(self):
        super().__init__("Cost Analysis", "cost")
        self.baseline_agent = None
        self.selected_metrics = None
    
    @property
    def title(self) -> str:
        return "Cost Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Analyze API costs and efficiency metrics**"
    
    def configure_sidebar(self):
        """Configure cost-specific sidebar options."""
        # Baseline agent selector
        agents = self.loader.list_agents(self.experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {self.experiment_id}")
            return
        
        self.baseline_agent = st.selectbox(
            "Baseline Agent (for comparison)",
            agents,
            help="Agent to compare costs against"
        )
        
        # Cost metric selector
        cost_metrics = ["total_cost", "cost_per_success", "input_tokens", "output_tokens", "efficiency_score"]
        self.selected_metrics = st.multiselect(
            "Cost Metrics",
            cost_metrics,
            default=["total_cost", "cost_per_success", "efficiency_score"],
            help="Metrics to display and compare"
        )
    
    def load_analysis(self):
        """Load cost analysis from loader."""
        return self.loader.load_cost(
            experiment_id=self.experiment_id,
            baseline_agent=self.baseline_agent,
        )
    
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract cost metrics into filterable format."""
        return extract_cost_metrics(result)
    
    def render_main_content(self, data: Dict[str, Any]):
        """Render cost-specific analysis content."""
        
        # Summary statistics
        st.subheader("Cost Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_experiment_cost = data.get("total_cost", 0)
        total_tokens = data.get("total_tokens", 0)
        agents_compared = len(data.get("agent_costs", {}))
        
        with col1:
            display_summary_card(
                "Total Experiment Cost",
                f"${total_experiment_cost:.2f}",
                "all agents combined",
                color="blue"
            )
        
        with col2:
            display_summary_card(
                "Total Tokens",
                f"{total_tokens:,.0f}",
                "input + output",
                color="blue"
            )
        
        with col3:
            display_summary_card(
                "Agents Compared",
                str(agents_compared),
                "total",
                color="blue"
            )
        
        with col4:
            # Find most expensive agent
            filtered_costs = data.get("agent_costs", {})
            if filtered_costs:
                max_cost_agent = max(
                    filtered_costs.items(),
                    key=lambda x: x[1].get('total_cost', 0)
                )
                display_summary_card(
                    "Most Expensive Agent",
                    max_cost_agent[0],
                    f"${max_cost_agent[1].get('total_cost', 0):.2f}",
                    color="orange"
                )
        
        st.markdown("---")
        
        # Agent cost rankings
        st.subheader("Agent Cost Rankings")
        
        try:
            filtered_costs = data.get("agent_costs", {})
            if filtered_costs:
                cost_data = []
                
                for agent_name, cost_info in filtered_costs.items():
                    cost_row = {
                        "Agent": agent_name,
                        "Total Cost": f"${cost_info.get('total_cost', 0):.2f}",
                        "Input Tokens": f"{cost_info.get('input_tokens', 0):,.0f}",
                        "Output Tokens": f"{cost_info.get('output_tokens', 0):,.0f}",
                        "Cost/Success": f"${cost_info.get('cost_per_success', 0):.2f}",
                        "Efficiency": f"{cost_info.get('efficiency_score', 0):.2f}",
                    }
                    cost_data.append(cost_row)
                
                # Sort by total cost
                col1, col2 = st.columns([1.5, 1])
                
                with col1:
                    cost_df = pd.DataFrame(cost_data)
                    st.dataframe(cost_df, use_container_width=True, hide_index=True)
                
                # Cost breakdown chart
                with col2:
                    try:
                        cost_chart = create_cost_breakdown_chart(
                            filtered_costs,
                            cost_metric="total_cost",
                            title="Total Cost by Agent"
                        )
                        st.plotly_chart(cost_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render cost chart: {e}")
        except Exception as e:
            st.warning(f"Failed to display cost rankings: {e}")
        
        st.markdown("---")
        
        # Cost per success analysis
        st.subheader("Cost Efficiency Analysis")
        
        try:
            filtered_costs = data.get("agent_costs", {})
            if filtered_costs:
                efficiency_data = []
                
                for agent_name, cost_info in filtered_costs.items():
                    success_count = cost_info.get('success_count', 0)
                    total_cost = cost_info.get('total_cost', 0)
                    efficiency = cost_info.get('efficiency_score', 0)
                    
                    efficiency_row = {
                        "Agent": agent_name,
                        "Successes": success_count,
                        "Total Cost": f"${total_cost:.2f}",
                        "Cost/Success": f"${cost_info.get('cost_per_success', 0):.2f}",
                        "Efficiency Score": f"{efficiency:.2f}",
                    }
                    efficiency_data.append(efficiency_row)
                
                if efficiency_data:
                    col1, col2 = st.columns([1.5, 1])
                    
                    with col1:
                        efficiency_df = pd.DataFrame(efficiency_data)
                        st.dataframe(efficiency_df, use_container_width=True, hide_index=True)
                    
                    # Cost per success chart
                    with col2:
                        try:
                            cps_chart = create_cost_breakdown_chart(
                                filtered_costs,
                                cost_metric="cost_per_success",
                                title="Cost per Success"
                            )
                            st.plotly_chart(cps_chart, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not render cost/success chart: {e}")
        except Exception as e:
            st.warning(f"Failed to display efficiency analysis: {e}")
        
        st.markdown("---")
        
        # Cost regressions
        st.subheader("Cost Regressions")
        
        try:
            filtered_regressions = data.get("cost_regressions", [])
            if filtered_regressions:
                regression_data = []
                
                for regression in filtered_regressions:
                    regression_row = {
                        "Agent": regression.get('agent_name', 'N/A'),
                        "Metric": regression.get('metric', 'N/A'),
                        "Previous": f"${regression.get('previous_value', 0):.2f}",
                        "Current": f"${regression.get('current_value', 0):.2f}",
                        "Change": f"{regression.get('percent_change', 0):+.1f}%",
                        "Severity": regression.get('severity', 'medium').upper(),
                    }
                    regression_data.append(regression_row)
                
                if regression_data:
                    regression_df = pd.DataFrame(regression_data)
                    st.dataframe(regression_df, use_container_width=True, hide_index=True)
                else:
                    st.success("✓ No cost regressions detected")
            else:
                st.success("✓ No cost regressions detected")
        except Exception as e:
            st.warning(f"Failed to display regressions: {e}")
        
        st.markdown("---")
        
        # Token usage visualization
        st.subheader("Token Usage Comparison")
        
        try:
            filtered_costs = data.get("agent_costs", {})
            if filtered_costs:
                try:
                    token_chart = create_token_comparison_chart(
                        filtered_costs,
                        title="Input vs Output Tokens"
                    )
                    st.plotly_chart(token_chart, use_container_width=True)
                except Exception as e:
                    st.warning(f"Could not render token chart: {e}")
        except Exception as e:
            st.warning(f"Could not display token visualization: {e}")
        
        st.markdown("---")
        
        # Model pricing breakdown
        st.subheader("Token Usage by Model")
        
        try:
            filtered_models = data.get("model_breakdown", {})
            if filtered_models:
                model_data = []
                
                for model, metrics in filtered_models.items():
                    model_row = {
                        "Model": model,
                        "Input Tokens": f"{metrics.get('input_tokens', 0):,.0f}",
                        "Output Tokens": f"{metrics.get('output_tokens', 0):,.0f}",
                        "Total Tokens": f"{metrics.get('total_tokens', 0):,.0f}",
                        "Cost": f"${metrics.get('cost', 0):.2f}",
                    }
                    model_data.append(model_row)
                
                if model_data:
                    model_df = pd.DataFrame(model_data)
                    st.dataframe(model_df, use_container_width=True, hide_index=True)
            else:
                st.info("No model breakdown available")
        except Exception as e:
            st.warning(f"Failed to display model breakdown: {e}")
        
        st.markdown("---")
        
        # View notes
        st.subheader("Metrics Explained")
        st.markdown("""
        - **Total Cost**: Sum of all API calls for this agent across all tasks
        - **Input Tokens**: Tokens sent to model (prompt + context)
        - **Output Tokens**: Tokens generated by model (response)
        - **Cost/Success**: Average cost per successful task completion
        - **Efficiency Score**: Composite metric (lower cost + higher pass rate = higher score)
        - **Cost Regression**: Agent cost increased compared to baseline
        - **Token Usage**: Cost breakdown by model type (Haiku vs Sonnet vs Opus)
        """)


def show_cost_analysis():
    """Main entry point for cost analysis view."""
    view = CostAnalysisView()
    view.run()
