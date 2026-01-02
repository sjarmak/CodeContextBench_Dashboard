"""
Cost Analysis View - API costs and efficiency analysis.

Displays:
- Total experiment cost and token summary
- Agent cost rankings (cheap/expensive/efficient)
- Cost per success metrics
- Cost regressions warning display
- Model pricing breakdown
- Cost vs performance trade-off analysis
"""

import streamlit as st
from pathlib import Path
from typing import Optional
import pandas as pd

from dashboard.utils.common_components import (
    experiment_selector,
    display_no_data_message,
    display_error_message,
    display_summary_card,
    export_json_button,
    display_cost_indicator,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_cost_analysis():
    """Display cost analysis view."""
    
    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()
    
    nav_context = st.session_state.nav_context
    
    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)
    
    st.title("Cost Analysis")
    st.markdown("**Analyze API costs and efficiency metrics**")
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
        nav_context.navigate_to("analysis_cost", experiment=experiment_id)
        
        # Baseline agent selector
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {experiment_id}")
            return
        
        baseline_agent = st.selectbox(
            "Baseline Agent (for comparison)",
            agents,
            help="Agent to compare costs against"
        )
        
        nav_context.navigate_to("analysis_cost", experiment=experiment_id, agents=[baseline_agent])
        
        # Cost metric selector
        cost_metrics = ["total_cost", "cost_per_success", "input_tokens", "output_tokens", "efficiency_score"]
        selected_metrics = st.multiselect(
            "Cost Metrics",
            cost_metrics,
            default=["total_cost", "cost_per_success", "efficiency_score"],
            help="Metrics to display and compare"
        )
        
        st.markdown("---")
        
        # Advanced filtering section
        st.subheader("Advanced Filters")
        filter_config = render_filter_panel("cost", loader, experiment_id)
    
    # Load cost analysis
    try:
        cost_result = loader.load_cost(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
        )
    except Exception as e:
        display_error_message(f"Failed to load cost analysis: {e}")
        return
    
    if cost_result is None:
        display_no_data_message("No cost analysis data available")
        return
    
    # Apply filters if any are active
    filter_engine = FilterEngine()
    if filter_config.has_filters():
        st.info(f"💰 Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Cost Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        total_experiment_cost = cost_result.total_cost if hasattr(cost_result, 'total_cost') else 0
        total_tokens = cost_result.total_tokens if hasattr(cost_result, 'total_tokens') else 0
        agents_compared = len(cost_result.agent_costs) if hasattr(cost_result, 'agent_costs') else 0
        
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
            if hasattr(cost_result, 'agent_costs') and cost_result.agent_costs:
                max_cost_agent = max(
                    cost_result.agent_costs.items(),
                    key=lambda x: x[1].get('total_cost', 0)
                )
                display_summary_card(
                    "Most Expensive Agent",
                    max_cost_agent[0],
                    f"${max_cost_agent[1].get('total_cost', 0):.2f}",
                    color="orange"
                )
    
    except Exception as e:
        st.warning(f"Could not calculate summary: {e}")
    
    st.markdown("---")
    
    # Agent cost rankings
    st.subheader("Agent Cost Rankings")
    
    try:
        if hasattr(cost_result, 'agent_costs') and cost_result.agent_costs:
            cost_data = []
            
            for agent_name, cost_info in cost_result.agent_costs.items():
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
            cost_df = pd.DataFrame(cost_data)
            st.dataframe(cost_df, use_container_width=True, hide_index=True)
        else:
            display_no_data_message("No cost data available")
    
    except Exception as e:
        display_error_message(f"Failed to display cost rankings: {e}")
    
    st.markdown("---")
    
    # Cost per success analysis
    st.subheader("Cost Efficiency Analysis")
    
    try:
        if hasattr(cost_result, 'agent_costs') and cost_result.agent_costs:
            efficiency_data = []
            
            for agent_name, cost_info in cost_result.agent_costs.items():
                # Calculate efficiency metrics
                success_count = cost_info.get('success_count', 0)
                total_cost = cost_info.get('total_cost', 0)
                efficiency = cost_info.get('efficiency_score', 0)
                
                efficiency_row = {
                    "Agent": agent_name,
                    "Successes": success_count,
                    "Total Cost": f"${total_cost:.2f}",
                    "Cost/Success": f"${cost_info.get('cost_per_success', 0):.2f}",
                    "Efficiency Score": f"{efficiency:.2f}",
                    "Efficiency Rank": "⭐" * min(5, int(efficiency))
                }
                efficiency_data.append(efficiency_row)
            
            if efficiency_data:
                efficiency_df = pd.DataFrame(efficiency_data)
                st.dataframe(efficiency_df, use_container_width=True, hide_index=True)
    
    except Exception as e:
        display_error_message(f"Failed to display efficiency analysis: {e}")
    
    st.markdown("---")
    
    # Cost regressions
    st.subheader("Cost Regressions")
    
    try:
        if hasattr(cost_result, 'cost_regressions') and cost_result.cost_regressions:
            regression_data = []
            
            for regression in cost_result.cost_regressions:
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
        display_error_message(f"Failed to display regressions: {e}")
    
    st.markdown("---")
    
    # Model pricing breakdown
    st.subheader("Token Usage by Model")
    
    try:
        if hasattr(cost_result, 'model_breakdown') and cost_result.model_breakdown:
            model_data = []
            
            for model, metrics in cost_result.model_breakdown.items():
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
        else:
            st.info("No model breakdown available")
    
    except Exception as e:
        display_error_message(f"Failed to display model breakdown: {e}")
    
    st.markdown("---")
    
    # Cost vs performance trade-off
    st.subheader("Cost vs Performance Trade-Off")
    
    try:
        if hasattr(cost_result, 'agent_costs') and cost_result.agent_costs:
            tradeoff_data = []
            
            for agent_name, cost_info in cost_result.agent_costs.items():
                # Get pass rate from comparison (attempt to load)
                try:
                    comparison = loader.load_comparison(experiment_id, baseline_agent=agent_name)
                    agent_metrics = comparison.agent_results.get(agent_name, {})
                    pass_rate = agent_metrics.get('pass_rate', 0)
                except:
                    pass_rate = 0
                
                tradeoff_row = {
                    "Agent": agent_name,
                    "Pass Rate": f"{pass_rate:.1%}" if pass_rate else "N/A",
                    "Cost/Success": f"${cost_info.get('cost_per_success', 0):.2f}",
                    "Total Cost": f"${cost_info.get('total_cost', 0):.2f}",
                }
                tradeoff_data.append(tradeoff_row)
            
            if tradeoff_data:
                tradeoff_df = pd.DataFrame(tradeoff_data)
                st.dataframe(tradeoff_df, use_container_width=True, hide_index=True)
                
                st.markdown("""
                **Interpretation**:
                - Agents with high pass rate AND low cost/success are most efficient
                - Agents with high cost/success may need prompt/tool optimization
                - Consider pass rate when evaluating cost improvements
                """)
    
    except Exception as e:
        display_error_message(f"Failed to display trade-off analysis: {e}")
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")
    
    try:
        export_data = {
            "experiment_id": experiment_id,
            "baseline_agent": baseline_agent,
            "summary": {
                "total_experiment_cost": total_experiment_cost,
                "total_tokens": total_tokens,
                "agents_compared": agents_compared,
            },
            "agent_costs": cost_result.agent_costs if hasattr(cost_result, 'agent_costs') else {},
            "cost_regressions": cost_result.cost_regressions if hasattr(cost_result, 'cost_regressions') else [],
            "model_breakdown": cost_result.model_breakdown if hasattr(cost_result, 'model_breakdown') else {},
        }
        
        export_json_button(export_data, f"cost_{experiment_id}_{baseline_agent}")
    
    except Exception as e:
        display_error_message(f"Failed to export data: {e}")
    
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
