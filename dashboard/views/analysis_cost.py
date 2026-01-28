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
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration in main area
    st.subheader("Configuration")

    col_exp, col_agent = st.columns(2)

    with col_exp:
        try:
            experiments = loader.list_experiments()
            if not experiments:
                st.error("No experiments found in database.")
                return

            experiment_id = st.selectbox(
                "Select Experiment",
                experiments,
                key="cost_experiment",
                help="Choose an experiment to analyze"
            )
        except Exception as e:
            st.error(f"Failed to load experiments: {e}")
            return

    # Update navigation context
    nav_context.navigate_to("analysis_cost", experiment=experiment_id)

    with col_agent:
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.warning(f"No agents found for experiment {experiment_id}")
            agents = ["(no agents)"]

        baseline_agent = st.selectbox(
            "Baseline Agent (for comparison)",
            agents,
            key="cost_baseline",
            help="Agent to compare costs against"
        )

    # Advanced filtering in expander
    with st.expander("Advanced Filters"):
        filter_config = render_filter_panel("cost", loader, experiment_id, key_suffix="cost")
    
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
        st.info(f"Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Cost Summary")

    col1, col2, col3, col4 = st.columns(4)

    try:
        total_experiment_cost = cost_result.total_experiment_cost if hasattr(cost_result, 'total_experiment_cost') else 0
        total_tokens = cost_result.total_tokens if hasattr(cost_result, 'total_tokens') else 0
        total_cached = cost_result.total_cached_tokens if hasattr(cost_result, 'total_cached_tokens') else 0
        agents_compared = len(cost_result.agent_metrics) if hasattr(cost_result, 'agent_metrics') else 0

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
                f"cached: {total_cached:,.0f}",
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
            if hasattr(cost_result, 'agent_metrics') and cost_result.agent_metrics:
                max_cost_agent = max(
                    cost_result.agent_metrics.items(),
                    key=lambda x: x[1].total_cost_usd
                )
                display_summary_card(
                    "Most Expensive Agent",
                    max_cost_agent[0],
                    f"${max_cost_agent[1].total_cost_usd:.2f}",
                    color="gray"
                )

    except Exception as e:
        st.warning(f"Could not calculate summary: {e}")
    
    st.markdown("---")

    # Token Breakdown by Category (NEW SECTION)
    st.subheader("Token Usage by Category")

    try:
        tokens_by_cat = cost_result.tokens_by_category if hasattr(cost_result, 'tokens_by_category') else {}

        if tokens_by_cat:
            cat_data = []
            total_prompt = 0
            total_completion = 0

            for category, tokens in tokens_by_cat.items():
                prompt = tokens.get("prompt", 0)
                completion = tokens.get("completion", 0)
                cached = tokens.get("cached", 0)
                total_prompt += prompt
                total_completion += completion

                cat_data.append({
                    "Category": category.upper(),
                    "Prompt Tokens": f"{prompt:,}",
                    "Completion Tokens": f"{completion:,}",
                    "Cached Tokens": f"{cached:,}",
                    "Total": f"{prompt + completion:,}",
                })

            if cat_data:
                cat_df = pd.DataFrame(cat_data)
                st.dataframe(cat_df, use_container_width=True, hide_index=True)

                # Show MCP vs Local comparison
                mcp_tokens = tokens_by_cat.get("mcp", {})
                local_tokens = tokens_by_cat.get("local", {})
                mcp_total = mcp_tokens.get("prompt", 0) + mcp_tokens.get("completion", 0)
                local_total = local_tokens.get("prompt", 0) + local_tokens.get("completion", 0)

                if mcp_total > 0 or local_total > 0:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("MCP Tool Tokens", f"{mcp_total:,}")
                    with col2:
                        st.metric("Local Tool Tokens", f"{local_total:,}")
                    with col3:
                        if local_total > 0:
                            ratio = mcp_total / local_total
                            st.metric("MCP/Local Ratio", f"{ratio:.2f}")
                        else:
                            st.metric("MCP/Local Ratio", "N/A (no local)")
        else:
            st.info("No token category breakdown available. Re-ingest data with trajectory.json files to see this breakdown.")

    except Exception as e:
        st.warning(f"Could not display token breakdown: {e}")

    st.markdown("---")

    # Agent cost rankings
    st.subheader("Agent Cost Rankings")

    try:
        if hasattr(cost_result, 'agent_metrics') and cost_result.agent_metrics:
            cost_data = []

            for agent_name, metrics in cost_result.agent_metrics.items():
                cost_row = {
                    "Agent": agent_name,
                    "Total Cost": f"${metrics.total_cost_usd:.2f}",
                    "Input Tokens": f"{metrics.total_input_tokens:,.0f}",
                    "Output Tokens": f"{metrics.total_output_tokens:,.0f}",
                    "Cached Tokens": f"{metrics.total_cached_tokens:,.0f}",
                    "Cost/Success": f"${metrics.cost_per_success:.2f}",
                    "Cost Rank": metrics.cost_rank or "N/A",
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
        if hasattr(cost_result, 'agent_metrics') and cost_result.agent_metrics:
            efficiency_data = []

            for agent_name, metrics in cost_result.agent_metrics.items():
                efficiency_row = {
                    "Agent": agent_name,
                    "Tasks": metrics.total_tasks,
                    "Passed": metrics.passed_tasks,
                    "Pass Rate": f"{metrics.pass_rate:.1%}",
                    "Total Cost": f"${metrics.total_cost_usd:.2f}",
                    "Cost/Success": f"${metrics.cost_per_success:.2f}",
                    "Efficiency Rank": metrics.efficiency_rank or "N/A",
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
        if hasattr(cost_result, 'regressions') and cost_result.regressions:
            regression_data = []

            for regression in cost_result.regressions:
                regression_row = {
                    "Agent": regression.agent_name,
                    "Metric": regression.metric_name,
                    "Baseline": f"${regression.baseline_value:.2f}",
                    "Current": f"${regression.regression_value:.2f}",
                    "Change": f"{regression.delta_percent:+.1f}%",
                    "Severity": regression.severity.upper(),
                }
                regression_data.append(regression_row)

            if regression_data:
                regression_df = pd.DataFrame(regression_data)
                st.dataframe(regression_df, use_container_width=True, hide_index=True)
            else:
                st.success("No cost regressions detected")
        else:
            st.success("No cost regressions detected")

    except Exception as e:
        display_error_message(f"Failed to display regressions: {e}")
    
    st.markdown("---")

    # Per-Tool Token Breakdown (NEW - shows which tools consume most tokens)
    st.subheader("Top Token-Consuming Tools")

    try:
        # Aggregate tokens by tool across all agents
        all_tools = {}
        if hasattr(cost_result, 'agent_metrics') and cost_result.agent_metrics:
            for agent_name, metrics in cost_result.agent_metrics.items():
                for tool, tokens in metrics.tokens_by_tool.items():
                    if tool not in all_tools:
                        all_tools[tool] = {"prompt": 0, "completion": 0, "cached": 0}
                    for key in ["prompt", "completion", "cached"]:
                        all_tools[tool][key] += tokens.get(key, 0)

        if all_tools:
            # Sort by total tokens (prompt + completion)
            sorted_tools = sorted(
                all_tools.items(),
                key=lambda x: x[1]["prompt"] + x[1]["completion"],
                reverse=True
            )[:15]  # Top 15 tools

            tool_data = []
            for tool, tokens in sorted_tools:
                total = tokens["prompt"] + tokens["completion"]
                tool_data.append({
                    "Tool": tool,
                    "Prompt Tokens": f"{tokens['prompt']:,}",
                    "Completion Tokens": f"{tokens['completion']:,}",
                    "Total": f"{total:,}",
                    "Cached": f"{tokens['cached']:,}",
                })

            if tool_data:
                tool_df = pd.DataFrame(tool_data)
                st.dataframe(tool_df, use_container_width=True, hide_index=True)
            else:
                st.info("No per-tool token data available")
        else:
            st.info("No per-tool token data available. Re-ingest data with trajectory.json files to see this breakdown.")

    except Exception as e:
        display_error_message(f"Failed to display tool breakdown: {e}")
    
    st.markdown("---")

    # Cost vs performance trade-off
    st.subheader("Cost vs Performance Trade-Off")

    try:
        if hasattr(cost_result, 'agent_metrics') and cost_result.agent_metrics:
            tradeoff_data = []

            for agent_name, metrics in cost_result.agent_metrics.items():
                tradeoff_row = {
                    "Agent": agent_name,
                    "Pass Rate": f"{metrics.pass_rate:.1%}",
                    "Cost/Success": f"${metrics.cost_per_success:.2f}",
                    "Total Cost": f"${metrics.total_cost_usd:.2f}",
                    "Avg Cost/Task": f"${metrics.avg_cost_per_task:.2f}",
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
        export_data = cost_result.to_dict() if hasattr(cost_result, 'to_dict') else {
            "experiment_id": experiment_id,
            "baseline_agent": baseline_agent,
            "summary": {
                "total_experiment_cost": total_experiment_cost,
                "total_tokens": total_tokens,
                "agents_compared": agents_compared,
            },
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
    - **Cached Tokens**: Tokens served from cache (reduced cost)
    - **Cost/Success**: Average cost per successful task completion
    - **Efficiency Rank**: Ranking based on pass rate per dollar (higher is better)
    - **Cost Regression**: Agent cost increased compared to baseline

    **Token Categories**:
    - **MCP**: Tokens used by MCP tools (Sourcegraph, Deep Search servers)
    - **LOCAL**: Tokens used by local tools (Bash, Read, Write, Grep, etc.)
    - **OTHER**: Tokens from steps without tool calls (reasoning, planning)

    Token category data requires trajectory.json files (ATIF format) from agent runs.
    """)
