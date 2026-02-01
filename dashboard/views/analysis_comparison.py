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

from dashboard.utils.comparison_config import (
    render_comparison_config,
    run_and_display_comparison,
    _render_comparison_results,
)
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
    """Display GUI-driven comparison analysis view."""

    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()

    nav_context = st.session_state.nav_context

    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)

    st.title("Agent Comparison Analysis")
    st.markdown("**Configure and run comparison analysis between two runs**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration in main content area (GUI-driven)
    config = render_comparison_config(loader)

    if config is None:
        st.info("Select baseline and variant runs above to begin.")
        return

    # Run Comparison button
    run_clicked = st.button(
        "Run Comparison",
        type="primary",
        use_container_width=True,
        key="comparison_run_btn",
    )

    # Alternative configuration in main area (not sidebar) for better visibility
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
                key="comparison_experiment",
                help="Choose an experiment to analyze"
            )
        except Exception as e:
            st.error(f"Failed to load experiments: {e}")
            return

    # Update navigation context with current view
    nav_context.navigate_to("analysis_comparison", experiment=experiment_id)

    with col_agent:
        # Baseline agent selector
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.warning(f"No agents found for experiment {experiment_id}")
            agents = ["(no agents)"]

        baseline_agent = st.selectbox(
            "Baseline Agent",
            agents,
            key="comparison_baseline",
            help="Agent to compare all others against"
        )

    with col_conf:
        # Confidence level for significance tests
        confidence_level = st.slider(
            "Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
            key="comparison_confidence",
            help="Statistical confidence threshold"
        )

    # Advanced filtering in expander
    with st.expander("Advanced Filters"):
        filter_config = render_filter_panel("comparison", loader, experiment_id, key_suffix="comp")
        
    st.markdown("---")

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
        st.info(f"Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
        # For now, show that filters are ready
    
    # Summary statistics
    st.subheader("Summary Statistics")

    # Calculate total tasks from agent metrics
    total_tasks = sum(m.total_tasks for m in comparison_result.agent_metrics.values())

    # Get best/worst agent pass rates
    best_pass_rate = 0.0
    worst_pass_rate = 1.0
    if comparison_result.best_agent and comparison_result.best_agent in comparison_result.agent_metrics:
        best_pass_rate = comparison_result.agent_metrics[comparison_result.best_agent].pass_rate
    if comparison_result.worst_agent and comparison_result.worst_agent in comparison_result.agent_metrics:
        worst_pass_rate = comparison_result.agent_metrics[comparison_result.worst_agent].pass_rate

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        display_summary_card(
            "Total Tasks",
            str(total_tasks),
            color="blue"
        )

    with col2:
        display_summary_card(
            "Agents Compared",
            str(len(comparison_result.agent_metrics)),
            color="blue"
        )

    with col3:
        if comparison_result.best_agent:
            display_summary_card(
                "Best Agent",
                comparison_result.best_agent,
                f"({best_pass_rate:.1%} pass rate)",
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
                f"({worst_pass_rate:.1%} pass rate)",
                color="gray"
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

        for agent_name, metrics in comparison_result.agent_metrics.items():
            metrics_row = {
                "Agent": agent_name,
                "Pass Rate": f"{metrics.pass_rate:.1%}",
                "Passed": metrics.passed_tasks,
                "Failed": metrics.total_tasks - metrics.passed_tasks,
                "Avg Duration": f"{metrics.avg_duration_seconds:.1f}s",
                "MCP Calls": f"{metrics.avg_mcp_calls:.1f}",
                "Local Calls": f"{metrics.avg_local_calls:.1f}",
            }

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
        if comparison_result.deltas:
            deltas_data = []

            for delta_key, delta in comparison_result.deltas.items():
                delta_row = {
                    "Agent": delta.variant_agent,
                    "Pass Rate Δ": f"{delta.pass_rate_delta:+.1%}",
                    "Duration Δ": f"{delta.duration_delta_seconds:+.1f}s",
                    "MCP Call Δ": f"{delta.mcp_calls_delta:+.1f}",
                    "MCP Impact": delta.mcp_impact.title(),
                    "Efficiency": delta.efficiency_impact.title(),
                }

                deltas_data.append(delta_row)

            if deltas_data:
                deltas_df = pd.DataFrame(deltas_data)
                st.dataframe(deltas_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No delta data available")
        else:
            display_no_data_message("No delta data available (single agent)")

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
        
        if statistical_result and statistical_result.tests:
            sig_data = []

            for variant_agent, variant_tests in statistical_result.tests.items():
                comparison_pair = f"{baseline_agent} vs {variant_agent}"
                for metric, test in variant_tests.items():
                    sig_data.append({
                        "Metric": test.metric_name,
                        "Comparison": comparison_pair,
                        "P-Value": f"{test.p_value:.4f}",
                        "Significant": "Yes" if test.is_significant else "No"
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
                "total_tasks": total_tasks,
                "agents_compared": len(comparison_result.agent_metrics),
                "best_agent": comparison_result.best_agent,
                "best_agent_pass_rate": best_pass_rate,
            },
            "agent_metrics": {
                name: metrics.to_dict()
                for name, metrics in comparison_result.agent_metrics.items()
            },
            "deltas": {
                key: delta.to_dict()
                for key, delta in comparison_result.deltas.items()
            },
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
