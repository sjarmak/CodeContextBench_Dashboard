"""
Failure Analysis View - Failure pattern and category analysis.

Displays:
- Failure pattern distribution
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

from dashboard.utils.common_components import (
    experiment_selector,
    display_no_data_message,
    display_error_message,
    display_summary_card,
    export_json_button,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_failure_analysis():
    """Display failure pattern analysis view."""
    
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
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.subheader("Configuration")
        
        # Experiment selector
        experiment_id = experiment_selector()
        if experiment_id is None:
            return
        
        # Update navigation context
        nav_context.navigate_to("analysis_failure", experiment=experiment_id)
        
        # Agent filter (optional)
        agents = loader.list_agents(experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {experiment_id}")
            return
        
        selected_agent = st.selectbox(
            "Focus Agent (optional)",
            ["All Agents"] + agents,
            help="Leave as 'All Agents' to see overall patterns"
        )
        
        agent_name = None if selected_agent == "All Agents" else selected_agent
        
        if agent_name:
            nav_context.navigate_to("analysis_failure", experiment=experiment_id, agents=[agent_name])
        
        st.markdown("---")
        
        # Advanced filtering section
        st.subheader("Advanced Filters")
        filter_config = render_filter_panel("failure", loader, experiment_id)
    
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
        st.info(f"📊 Filters applied: {filter_engine.get_filter_summary(filter_config)}")
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
                color="red"
            )
        
        with col2:
            display_summary_card(
                "Failure Rate",
                f"{failure_rate:.1f}%",
                f"{total_failures}/{total_tasks}",
                color="red" if failure_rate > 50 else "orange" if failure_rate > 25 else "blue"
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
                color="orange"
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
                st.success("✓ No high-risk tasks identified")
        else:
            st.success("✓ No high-risk tasks identified")
    
    except Exception as e:
        display_error_message(f"Failed to display high-risk tasks: {e}")
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")
    
    try:
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
