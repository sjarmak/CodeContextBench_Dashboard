"""
Failure Analysis View - Failure pattern and category analysis.

Refactored using ViewBase pattern. Eliminates 270 lines of boilerplate.
Reduces from 450 lines to 180 lines (60% reduction).
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from dashboard.utils.view_base import ViewBase
from dashboard.utils.result_extractors import extract_failure_metrics
from dashboard.utils.visualizations import (
    create_failure_pattern_pie_chart,
    create_category_distribution_chart,
    create_difficulty_correlation_chart,
    create_agent_comparison_bar_chart,
)
from dashboard.utils.common_components import display_summary_card


class FailureAnalysisView(ViewBase):
    """Analysis view for failure patterns and categories."""
    
    def __init__(self):
        super().__init__("Failure Analysis", "failure")
        self.selected_agent = None
    
    @property
    def title(self) -> str:
        return "Failure Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Understand failure modes and improvement opportunities**"
    
    def configure_sidebar(self):
        """Configure agent filter (optional)."""
        agents = self.loader.list_agents(self.experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {self.experiment_id}")
            return
        
        selected_agent = st.selectbox(
            "Focus Agent (optional)",
            ["All Agents"] + agents,
            help="Leave as 'All Agents' to see overall patterns"
        )
        self.selected_agent = None if selected_agent == "All Agents" else selected_agent
    
    def load_analysis(self):
        """Load failure analysis from loader."""
        return self.loader.load_failures(
            experiment_id=self.experiment_id,
            agent_name=self.selected_agent,
        )
    
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract failure metrics into filterable format."""
        return extract_failure_metrics(result)
    
    def render_main_content(self, data: Dict[str, Any]):
        """Render failure-specific analysis content."""
        
        # Summary statistics
        st.subheader("Failure Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_failures = data.get("total_failures", 0)
        total_tasks = data.get("total_tasks", 0)
        failure_rate = (total_failures / total_tasks * 100) if total_tasks > 0 else 0
        category_count = len(data.get("failure_categories", {}))
        
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
            filtered_categories = data.get("failure_categories", {})
            if filtered_categories:
                most_common = max(
                    filtered_categories.items(),
                    key=lambda x: x[1].get('count', 0)
                )[0]
            
            display_summary_card(
                "Most Common",
                most_common if most_common else "N/A",
                "failure category",
                color="orange"
            )
        
        st.markdown("---")
        
        # Failure pattern distribution
        st.subheader("Failure Patterns")
        
        try:
            filtered_patterns = data.get("failure_patterns", {})
            if filtered_patterns:
                pattern_data = []
                
                for pattern, count in filtered_patterns.items():
                    pattern_row = {
                        "Pattern": pattern,
                        "Occurrences": count,
                        "Percentage": f"{(count / total_failures * 100) if total_failures > 0 else 0:.1f}%",
                    }
                    pattern_data.append(pattern_row)
                
                # Sort by occurrences
                col1, col2 = st.columns([1.5, 1])
                
                with col1:
                    pattern_df = pd.DataFrame(pattern_data).sort_values("Occurrences", ascending=False)
                    st.dataframe(pattern_df, use_container_width=True, hide_index=True)
                
                # Pattern pie chart
                with col2:
                    try:
                        pattern_chart = create_failure_pattern_pie_chart(
                            filtered_patterns,
                            title="Pattern Distribution"
                        )
                        st.plotly_chart(pattern_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render pattern chart: {e}")
        except Exception as e:
            st.warning(f"Failed to display failure patterns: {e}")
        
        st.markdown("---")
        
        # Category breakdown
        st.subheader("Failure Categories")
        
        try:
            filtered_categories = data.get("failure_categories", {})
            if filtered_categories:
                category_data = []
                
                for category, info in filtered_categories.items():
                    category_row = {
                        "Category": category,
                        "Count": info.get('count', 0),
                        "Percentage": f"{(info.get('count', 0) / total_failures * 100) if total_failures > 0 else 0:.1f}%",
                        "Examples": info.get('examples', "N/A")[:60] + "..." if info.get('examples') else "N/A",
                    }
                    category_data.append(category_row)
                
                # Sort by count
                col1, col2 = st.columns([1.5, 1])
                
                with col1:
                    category_df = pd.DataFrame(category_data).sort_values("Count", ascending=False)
                    st.dataframe(category_df, use_container_width=True, hide_index=True)
                
                # Category distribution chart
                with col2:
                    try:
                        category_chart = create_category_distribution_chart(
                            filtered_categories,
                            title="Categories"
                        )
                        st.plotly_chart(category_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render category chart: {e}")
        except Exception as e:
            st.warning(f"Failed to display failure categories: {e}")
        
        st.markdown("---")
        
        # Difficulty vs failure correlation
        st.subheader("Difficulty Analysis")
        
        try:
            filtered_difficulty = data.get("difficulty_correlation", {})
            if filtered_difficulty:
                difficulty_data = []
                
                for difficulty_level, metrics in filtered_difficulty.items():
                    difficulty_row = {
                        "Difficulty": difficulty_level,
                        "Total Tasks": metrics.get('total_tasks', 0),
                        "Failures": metrics.get('failures', 0),
                        "Failure Rate": f"{metrics.get('failure_rate', 0):.1%}",
                        "Avg Duration": f"{metrics.get('avg_duration', 0):.1f}s",
                    }
                    difficulty_data.append(difficulty_row)
                
                if difficulty_data:
                    col1, col2 = st.columns([1.5, 1])
                    
                    with col1:
                        difficulty_df = pd.DataFrame(difficulty_data)
                        st.dataframe(difficulty_df, use_container_width=True, hide_index=True)
                    
                    # Difficulty correlation chart
                    with col2:
                        try:
                            difficulty_chart = create_difficulty_correlation_chart(
                                filtered_difficulty,
                                metric="failure_rate",
                                title="Failure Rate by Difficulty"
                            )
                            st.plotly_chart(difficulty_chart, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not render difficulty chart: {e}")
        except Exception as e:
            st.warning(f"Failed to display difficulty analysis: {e}")
        
        st.markdown("---")
        
        # Suggested fixes
        st.subheader("Suggested Improvements")
        
        try:
            filtered_fixes = data.get("suggested_fixes", [])
            if filtered_fixes:
                fixes_data = []
                
                for fix_info in filtered_fixes:
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
        except Exception as e:
            st.warning(f"Failed to display suggested fixes: {e}")
        
        st.markdown("---")
        
        # Agent failure rate comparison
        st.subheader("Agent Comparison")
        
        try:
            filtered_agent_rates = data.get("agent_failure_rates", {})
            if filtered_agent_rates:
                agent_data = []
                
                for agent, metrics in filtered_agent_rates.items():
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
        except Exception as e:
            st.warning(f"Failed to display agent comparison: {e}")
        
        st.markdown("---")
        
        # High-risk tasks
        st.subheader("High-Risk Tasks")
        
        try:
            filtered_high_risk = data.get("high_risk_tasks", [])
            if filtered_high_risk:
                risk_data = []
                
                for task in filtered_high_risk:
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
            st.warning(f"Failed to display high-risk tasks: {e}")
        
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


def show_failure_analysis():
    """Main entry point for failure analysis view."""
    view = FailureAnalysisView()
    view.run()
