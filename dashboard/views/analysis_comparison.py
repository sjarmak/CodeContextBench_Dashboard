"""
Comparison Analysis View - Agent performance comparison with cost and statistical overlays.

Displays:
- Agent performance metrics table (pass rate, duration, MCP calls)
- Side-by-side agent metrics
- Cost metrics overlay
- Statistical significance indicators
- Export as JSON
"""

import streamlit as st
from pathlib import Path
from typing import Optional
import pandas as pd

from dashboard.utils.common_components import (
    experiment_selector,
    export_json_button,
    display_no_data_message,
    display_error_message,
    display_summary_card,
    display_metric_delta,
    display_significance_badge,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_comparison_analysis():
    """Display experiment comparison analysis view."""
    
    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()
    
    nav_context = st.session_state.nav_context
    
    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)
    
    st.title("Agent Comparison Analysis")
    st.markdown("**Compare agent performance metrics across tasks**")
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
        
        # Update navigation context with current view
        nav_context.navigate_to("analysis_comparison", experiment=experiment_id)
        
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
        
        # Update navigation with baseline agent
        nav_context.navigate_to("analysis_comparison", experiment=experiment_id, agents=[baseline_agent])
        
        # Confidence level for significance tests
        confidence_level = st.slider(
            "Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
            help="Statistical confidence threshold"
        )
        
        st.markdown("---")
        
        # Advanced filtering section
        st.subheader("Advanced Filters")
        filter_config = render_filter_panel("comparison", loader, experiment_id)
    
    # Load comparison results
    try:
        comparison_result = loader.load_comparison(
            experiment_id,
            baseline_agent=baseline_agent
        )
    except Exception as e:
        display_error_message(f"Failed to load comparison: {e}")
        return
    
    if comparison_result is None:
        display_no_data_message("No comparison data available")
        return
    
    # Apply filters if any are active
    filter_engine = FilterEngine()
    if filter_config.has_filters():
        st.info(f"📊 Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
        # For now, show that filters are ready
    
    # Summary statistics
    st.subheader("Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        display_summary_card(
            "Total Tasks",
            str(comparison_result.total_tasks),
            color="blue"
        )
    
    with col2:
        display_summary_card(
            "Agents Compared",
            str(len(comparison_result.agent_results)),
            color="blue"
        )
    
    with col3:
        if comparison_result.best_agent:
            display_summary_card(
                "Best Agent",
                comparison_result.best_agent,
                f"({comparison_result.best_agent_pass_rate:.1%} pass rate)",
                color="green"
            )
        else:
            display_summary_card(
                "Best Agent",
                "N/A",
                color="gray"
            )
    
    with col4:
        if comparison_result.worst_agent:
            display_summary_card(
                "Worst Agent",
                comparison_result.worst_agent,
                f"({comparison_result.worst_agent_pass_rate:.1%} pass rate)",
                color="red"
            )
        else:
            display_summary_card(
                "Worst Agent",
                "N/A",
                color="gray"
            )
    
    st.markdown("---")
    
    # Agent metrics table
    st.subheader("Agent Performance Metrics")
    
    try:
        metrics_data = []
        
        for agent_name, result in comparison_result.agent_results.items():
            metrics_row = {
                "Agent": agent_name,
                "Pass Rate": f"{result.get('pass_rate', 0):.1%}",
                "Passed": result.get('passed_count', 0),
                "Failed": result.get('failed_count', 0),
                "Avg Duration": f"{result.get('avg_duration', 0):.1f}s",
                "MCP Calls": result.get('mcp_call_count', 0),
                "Local Calls": result.get('local_call_count', 0),
            }
            
            # Add cost metrics if available
            if result.get('total_cost'):
                metrics_row["Total Cost"] = f"${result.get('total_cost', 0):.2f}"
                metrics_row["Cost/Success"] = f"${result.get('cost_per_success', 0):.2f}"
            
            metrics_data.append(metrics_row)
        
        metrics_df = pd.DataFrame(metrics_data)
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        display_error_message(f"Failed to display metrics table: {e}")
        return
    
    st.markdown("---")
    
    # Deltas vs baseline
    st.subheader(f"Performance Delta vs {baseline_agent}")
    
    try:
        if comparison_result.agent_deltas:
            deltas_data = []
            
            for agent_name, delta in comparison_result.agent_deltas.items():
                if agent_name == baseline_agent:
                    continue
                
                delta_row = {
                    "Agent": agent_name,
                    "Pass Rate Δ": f"{delta.get('pass_rate_delta', 0):+.1%}",
                    "Duration Δ": f"{delta.get('duration_delta', 0):+.1f}s",
                    "MCP Call Δ": f"{delta.get('mcp_call_delta', 0):+.0f}",
                }
                
                # Add cost delta if available
                if delta.get('cost_delta') is not None:
                    delta_row["Cost Δ"] = f"${delta.get('cost_delta', 0):+.2f}"
                
                deltas_data.append(delta_row)
            
            if deltas_data:
                deltas_df = pd.DataFrame(deltas_data)
                st.dataframe(deltas_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No delta data available")
        else:
            display_no_data_message("No delta data available")
    
    except Exception as e:
        display_error_message(f"Failed to display deltas: {e}")
    
    st.markdown("---")
    
    # Statistical significance overlay
    st.subheader("Statistical Significance (p-values)")
    
    try:
        # Try to load statistical analysis for significance badges
        statistical_result = loader.load_statistical(
            experiment_id,
            baseline_agent=baseline_agent,
            confidence_level=confidence_level
        )
        
        if statistical_result and statistical_result.test_results:
            sig_data = []
            
            for metric, tests in statistical_result.test_results.items():
                for comparison_pair, test_info in tests.items():
                    p_value = test_info.get('p_value')
                    if p_value is not None:
                        sig_badge = display_significance_badge(p_value, alpha=1-confidence_level)
                        sig_data.append({
                            "Metric": metric,
                            "Comparison": comparison_pair,
                            "P-Value": f"{p_value:.4f}",
                            "Significant": "✓" if p_value < (1-confidence_level) else "✗"
                        })
            
            if sig_data:
                sig_df = pd.DataFrame(sig_data)
                st.dataframe(sig_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No statistical tests available")
        else:
            st.info("Statistical analysis not available for this experiment")
    
    except Exception as e:
        st.warning(f"Could not load statistical significance: {e}")
    
    st.markdown("---")
    
    # Cost overlay section
    st.subheader("Cost Metrics Overlay")
    
    try:
        cost_result = loader.load_cost(
            experiment_id,
            baseline_agent=baseline_agent
        )
        
        if cost_result and cost_result.agent_costs:
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
            
            if cost_data:
                cost_df = pd.DataFrame(cost_data)
                st.dataframe(cost_df, use_container_width=True, hide_index=True)
        else:
            st.info("Cost analysis not available for this experiment")
    
    except Exception as e:
        st.warning(f"Could not load cost analysis: {e}")
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")
    
    try:
        export_data = {
            "experiment_id": experiment_id,
            "baseline_agent": baseline_agent,
            "summary": {
                "total_tasks": comparison_result.total_tasks,
                "agents_compared": len(comparison_result.agent_results),
                "best_agent": comparison_result.best_agent,
                "best_agent_pass_rate": comparison_result.best_agent_pass_rate,
            },
            "agent_results": comparison_result.agent_results,
            "agent_deltas": comparison_result.agent_deltas,
        }
        
        export_json_button(export_data, f"comparison_{experiment_id}_{baseline_agent}")
    
    except Exception as e:
        display_error_message(f"Failed to export data: {e}")
    
    st.markdown("---")
    
    # View notes
    st.subheader("View Notes")
    st.markdown("""
    - **Pass Rate**: Percentage of tasks completed successfully
    - **Duration**: Average time per task (in seconds)
    - **MCP Calls**: Deep Search and other MCP tool invocations
    - **Local Calls**: Keyboard/tool calls without MCP
    - **Cost/Success**: Average cost per successful task completion
    - **Δ (Delta)**: Difference relative to baseline agent
    - **P-Value**: Statistical significance of difference (lower = more significant)
    - **Efficiency**: Cost-adjusted performance score
    """)
