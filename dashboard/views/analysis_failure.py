"""
Failure Analysis View - Failure pattern and category analysis.

Displays:
- Experiment selector and agent filter
- Failure pattern detection and distribution
- Error category pie chart
- Failure pattern frequency table
- Root cause summary with suggested fixes
- CSV export
- Category-specific failure breakdown
- Difficulty vs failure correlation
- Suggested fixes display
- Agent comparison on failure rate
- High-risk task identification
"""

import streamlit as st
from pathlib import Path
from typing import Optional
import pandas as pd
import plotly.express as px

from dashboard.utils.failure_config import (
    render_failure_config,
    run_and_display_failures,
    _render_failure_results,
)
from dashboard.utils.common_components import (
    experiment_selector,
    display_no_data_message,
    display_error_message,
    display_summary_card,
    export_json_button,
    export_csv_button,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_failure_analysis():
    """Display GUI-driven failure analysis view."""

    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()

    nav_context = st.session_state.nav_context

    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)


    st.title("Failure Analysis")
    st.markdown("**Understand failure modes and improvement opportunities**")
    st.markdown("---")

    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration inline (no sidebar wrapper)
    config = render_failure_config(loader)

    if config is None:
        st.info("Select an experiment to begin.")
        return

    # Run Analysis button
    run_clicked = st.button(
        "Run Failure Analysis",
        type="primary",
        use_container_width=True,
        key="failure_run_analysis",
    )

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
                key="failure_experiment",
                help="Choose an experiment to analyze"
            )
        except Exception as e:
            st.error(f"Failed to load experiments: {e}")
            return

    # Update navigation context
    nav_context.navigate_to("analysis_failure", experiment=experiment_id)

    with col_agent:
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.warning(f"No agents found for experiment {experiment_id}")
            agents = []

        selected_agent = st.selectbox(
            "Focus Agent (optional)",
            ["All Agents"] + agents,
            key="failure_agent",
            help="Leave as 'All Agents' to see overall patterns"
        )

        agent_name = None if selected_agent == "All Agents" else selected_agent

    # Advanced filtering in expander
    with st.expander("Advanced Filters"):
        filter_config = render_filter_panel("failure", loader, experiment_id, key_suffix="fail")
    
    # Load failure analysis
    try:
        failure_result = loader.load_failures(
            experiment_id=experiment_id,
            agent_name=agent_name,
        )
    except Exception as e:
        display_error_message(f"Failed to load failure analysis: {e}")
        return
    
    if failure_result is None:
        display_no_data_message("No failure analysis data available")
        return
    
    # Apply filters if any are active
    filter_engine = FilterEngine()
    if filter_config.has_filters():
        st.info(f"Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Failure Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        total_failures = failure_result.total_failures if hasattr(failure_result, 'total_failures') else 0
        total_tasks = failure_result.total_tasks if hasattr(failure_result, 'total_tasks') else 0
        failure_rate = (total_failures / total_tasks * 100) if total_tasks > 0 else 0
        category_count = len(failure_result.failure_categories) if hasattr(failure_result, 'failure_categories') else 0
        
        with col1:
            display_summary_card(
                "Total Failures",
                str(total_failures),
                f"out of {total_tasks} tasks",
                color="gray"
            )

        with col2:
            display_summary_card(
                "Failure Rate",
                f"{failure_rate:.1f}%",
                f"{total_failures}/{total_tasks}",
                color="gray"
            )
        
        with col3:
            display_summary_card(
                "Categories",
                str(category_count),
                "failure types",
                color="blue"
            )
        
        with col4:
            # Find most common category
            most_common = ""
            if hasattr(failure_result, 'failure_categories') and failure_result.failure_categories:
                most_common = max(
                    failure_result.failure_categories.items(),
                    key=lambda x: x[1].get('count', 0)
                )[0]
            
            display_summary_card(
                "Most Common",
                most_common if most_common else "N/A",
                "failure category",
                color="gray"
            )
    
    except Exception as e:
        st.warning(f"Could not calculate summary: {e}")
    
    st.markdown("---")
    
    # Failure pattern distribution
    st.subheader("Failure Patterns")
    
    try:
        if hasattr(failure_result, 'failure_patterns') and failure_result.failure_patterns:
            pattern_data = []
            
            for pattern, count in failure_result.failure_patterns.items():
                pattern_row = {
                    "Pattern": pattern,
                    "Occurrences": count,
                    "Percentage": f"{(count / total_failures * 100) if total_failures > 0 else 0:.1f}%",
                }
                pattern_data.append(pattern_row)
            
            # Sort by occurrences
            pattern_df = pd.DataFrame(pattern_data).sort_values("Occurrences", ascending=False)
            st.dataframe(pattern_df, use_container_width=True, hide_index=True)

            # Bar chart for failure pattern frequency
            bar_data = []
            for pattern, count in failure_result.failure_patterns.items():
                if count > 0:
                    bar_data.append({"Pattern": pattern, "Occurrences": count})

            if bar_data:
                bar_df = pd.DataFrame(bar_data).sort_values("Occurrences", ascending=True)
                fig_bar = px.bar(
                    bar_df,
                    x="Occurrences",
                    y="Pattern",
                    orientation="h",
                    title="Failure Pattern Frequency",
                    color="Occurrences",
                    color_continuous_scale="Reds",
                )
                fig_bar.update_layout(
                    xaxis_title="Occurrences",
                    yaxis_title="",
                    showlegend=False,
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            display_no_data_message("No failure pattern data available")
    
    except Exception as e:
        display_error_message(f"Failed to display failure patterns: {e}")
    
    st.markdown("---")
    
    # Category breakdown
    st.subheader("Failure Categories")
    
    try:
        if hasattr(failure_result, 'failure_categories') and failure_result.failure_categories:
            category_data = []
            
            for category, info in failure_result.failure_categories.items():
                category_row = {
                    "Category": category,
                    "Count": info.get('count', 0),
                    "Percentage": f"{(info.get('count', 0) / total_failures * 100) if total_failures > 0 else 0:.1f}%",
                    "Examples": info.get('examples', "N/A")[:60] + "..." if info.get('examples') else "N/A",
                }
                category_data.append(category_row)
            
            # Sort by count
            category_df = pd.DataFrame(category_data).sort_values("Count", ascending=False)
            st.dataframe(category_df, use_container_width=True, hide_index=True)

            # Pie chart for failure category distribution
            pie_data = []
            for category, info in failure_result.failure_categories.items():
                count = info.get('count', 0)
                if count > 0:
                    pie_data.append({"Category": category, "Count": count})

            if pie_data:
                pie_df = pd.DataFrame(pie_data)
                fig_pie = px.pie(
                    pie_df,
                    names="Category",
                    values="Count",
                    title="Error Category Distribution",
                    hole=0.3,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                fig_pie.update_layout(legend_title="Category")
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            display_no_data_message("No failure categories available")
    
    except Exception as e:
        display_error_message(f"Failed to display failure categories: {e}")
    
    st.markdown("---")
    
    # Difficulty vs failure correlation
    st.subheader("Difficulty Analysis")
    
    try:
        if hasattr(failure_result, 'difficulty_correlation') and failure_result.difficulty_correlation:
            difficulty_data = []
            
            for difficulty_level, metrics in failure_result.difficulty_correlation.items():
                difficulty_row = {
                    "Difficulty": difficulty_level,
                    "Total Tasks": metrics.get('total_tasks', 0),
                    "Failures": metrics.get('failures', 0),
                    "Failure Rate": f"{metrics.get('failure_rate', 0):.1%}",
                    "Avg Duration": f"{metrics.get('avg_duration', 0):.1f}s",
                }
                difficulty_data.append(difficulty_row)
            
            if difficulty_data:
                difficulty_df = pd.DataFrame(difficulty_data)
                st.dataframe(difficulty_df, use_container_width=True, hide_index=True)
                
                st.markdown("""
                **Insight**: Higher-difficulty tasks typically have higher failure rates. 
                Consider focusing optimization efforts on high-difficulty tasks with failure concentration.
                """)
        else:
            st.info("No difficulty correlation analysis available")
    
    except Exception as e:
        display_error_message(f"Failed to display difficulty analysis: {e}")
    
    st.markdown("---")
    
    # Suggested fixes
    st.subheader("Suggested Improvements")
    
    try:
        if hasattr(failure_result, 'suggested_fixes') and failure_result.suggested_fixes:
            fixes_data = []
            
            for fix_idx, fix_info in enumerate(failure_result.suggested_fixes, 1):
                fix_row = {
                    "Priority": fix_info.get('priority', 'medium').upper(),
                    "Category": fix_info.get('category', 'N/A'),
                    "Issue": fix_info.get('issue', 'N/A'),
                    "Suggested Fix": fix_info.get('fix', 'N/A'),
                    "Impact": f"{fix_info.get('estimated_impact', 0):.1%}",
                }
                fixes_data.append(fix_row)
            
            if fixes_data:
                # Sort by priority
                priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
                fixes_df = pd.DataFrame(fixes_data)
                fixes_df['_priority'] = fixes_df['Priority'].map(priority_order)
                fixes_df = fixes_df.sort_values('_priority').drop('_priority', axis=1)
                
                st.dataframe(fixes_df, use_container_width=True, hide_index=True)
            else:
                st.info("No improvement suggestions available")
        else:
            st.info("No suggested fixes available")
    
    except Exception as e:
        display_error_message(f"Failed to display suggested fixes: {e}")
    
    st.markdown("---")
    
    # Agent failure rate comparison
    st.subheader("Agent Comparison")
    
    try:
        if hasattr(failure_result, 'agent_failure_rates') and failure_result.agent_failure_rates:
            agent_data = []
            
            for agent, metrics in failure_result.agent_failure_rates.items():
                agent_row = {
                    "Agent": agent,
                    "Total Tasks": metrics.get('total_tasks', 0),
                    "Failures": metrics.get('failures', 0),
                    "Failure Rate": f"{metrics.get('failure_rate', 0):.1%}",
                    "Success Rate": f"{(1 - metrics.get('failure_rate', 0)):.1%}",
                }
                agent_data.append(agent_row)
            
            if agent_data:
                agent_df = pd.DataFrame(agent_data).sort_values("Failure Rate")
                st.dataframe(agent_df, use_container_width=True, hide_index=True)
        else:
            st.info("No agent comparison available")
    
    except Exception as e:
        display_error_message(f"Failed to display agent comparison: {e}")
    
    st.markdown("---")
    
    # High-risk tasks
    st.subheader("High-Risk Tasks")
    
    try:
        if hasattr(failure_result, 'high_risk_tasks') and failure_result.high_risk_tasks:
            risk_data = []
            
            for task in failure_result.high_risk_tasks:
                task_row = {
                    "Task ID": task.get('task_id', 'N/A'),
                    "Failures": task.get('failure_count', 0),
                    "Attempts": task.get('total_attempts', 0),
                    "Failure Rate": f"{task.get('failure_rate', 0):.1%}",
                    "Risk Level": task.get('risk_level', 'MEDIUM').upper(),
                }
                risk_data.append(task_row)
            
            if risk_data:
                risk_df = pd.DataFrame(risk_data)
                st.dataframe(risk_df, use_container_width=True, hide_index=True)
                
                st.markdown(f"""
                **Recommendation**: Focus improvement efforts on these {len(risk_data)} high-risk tasks.
                They have consistently failed across multiple agents.
                """)
            else:
                st.success("Yes No high-risk tasks identified")
        else:
            st.success("Yes No high-risk tasks identified")
    
    except Exception as e:
        display_error_message(f"Failed to display high-risk tasks: {e}")
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")

    try:
        # CSV export of failure summary table
        csv_rows = []
        if hasattr(failure_result, 'failure_patterns') and failure_result.failure_patterns:
            for pattern, count in failure_result.failure_patterns.items():
                csv_rows.append({
                    "Pattern": pattern,
                    "Occurrences": count,
                    "Percentage": (count / total_failures * 100) if total_failures > 0 else 0,
                })

        if hasattr(failure_result, 'failure_categories') and failure_result.failure_categories:
            for category, info in failure_result.failure_categories.items():
                csv_rows.append({
                    "Pattern": f"[Category] {category}",
                    "Occurrences": info.get('count', 0),
                    "Percentage": (info.get('count', 0) / total_failures * 100) if total_failures > 0 else 0,
                })

        if csv_rows:
            csv_df = pd.DataFrame(csv_rows)
            export_csv_button(csv_df, f"failure_{experiment_id}_{agent_name or 'all'}", key="failure_csv_export")

        # Also offer JSON export
        export_data = {
            "experiment_id": experiment_id,
            "focused_agent": agent_name,
            "summary": {
                "total_failures": total_failures,
                "total_tasks": total_tasks,
                "failure_rate": failure_rate,
                "category_count": category_count,
            },
            "failure_patterns": failure_result.failure_patterns if hasattr(failure_result, 'failure_patterns') else {},
            "failure_categories": failure_result.failure_categories if hasattr(failure_result, 'failure_categories') else {},
            "suggested_fixes": failure_result.suggested_fixes if hasattr(failure_result, 'suggested_fixes') else [],
            "high_risk_tasks": failure_result.high_risk_tasks if hasattr(failure_result, 'high_risk_tasks') else [],
        }

        export_json_button(export_data, f"failure_{experiment_id}_{agent_name or 'all'}")

    except Exception as e:
        display_error_message(f"Failed to export data: {e}")
    
    st.markdown("---")
    
    # View notes
    st.subheader("Analysis Guide")
    st.markdown("""
    - **Failure Patterns**: Common error types (timeout, wrong answer, etc.)
    - **Categories**: Grouped by failure root cause (architecture, prompting, tool choice)
    - **Difficulty Correlation**: How task difficulty relates to failure rates
    - **Suggested Fixes**: Prioritized improvements based on impact analysis
    - **High-Risk Tasks**: Tasks failing across multiple agents (good improvement targets)
    - **Impact**: Estimated % improvement if suggestion is implemented
    """)
