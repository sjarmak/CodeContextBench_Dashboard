"""Comparison Analysis View - Refactored using ViewBase."""

import streamlit as st
import pandas as pd
from typing import Dict, Any

from dashboard.utils.view_base import ViewBase
from dashboard.utils.result_extractors import extract_comparison_metrics
from dashboard.utils.visualizations import (
    create_agent_comparison_bar_chart,
    create_multi_metric_comparison_chart,
    create_delta_comparison_chart,
    create_cost_breakdown_chart,
    create_token_comparison_chart,
)
from dashboard.utils.common_components import display_summary_card, display_significance_badge


class ComparisonAnalysisView(ViewBase):
    """Agent performance comparison analysis."""
    
    def __init__(self):
        super().__init__("Comparison Analysis", "comparison")
        self.baseline_agent = None
        self.confidence_level = 0.95
    
    @property
    def title(self) -> str:
        return "Agent Comparison Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Compare agent performance metrics across tasks**"
    
    def configure_sidebar(self):
        """Configure baseline agent and confidence level."""
        agents = self.loader.list_agents(self.experiment_id)
        if not agents:
            st.error(f"No agents found for experiment {self.experiment_id}")
            return
        
        self.baseline_agent = st.selectbox(
            "Baseline Agent",
            agents,
            help="Agent to compare all others against"
        )
        
        self.confidence_level = st.slider(
            "Confidence Level",
            min_value=0.90,
            max_value=0.99,
            value=0.95,
            step=0.01,
            help="Statistical confidence threshold"
        )
    
    def load_analysis(self):
        """Load comparison results."""
        return self.loader.load_comparison(
            self.experiment_id,
            baseline_agent=self.baseline_agent
        )
    
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract comparison metrics."""
        return extract_comparison_metrics(result)
    
    def render_main_content(self, data: Dict[str, Any]):
        """Render comparison analysis content."""
        
        # Summary statistics
        st.subheader("Summary Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            display_summary_card(
                "Total Tasks",
                str(data.get("total_tasks", 0)),
                color="blue"
            )
        
        with col2:
            agent_count = len(data.get("agent_results", {}))
            display_summary_card(
                "Agents Compared",
                str(agent_count),
                color="blue"
            )
        
        with col3:
            best_agent = data.get("best_agent")
            if best_agent:
                display_summary_card(
                    "Best Agent",
                    best_agent,
                    f"({data.get('best_agent_pass_rate', 0):.1%} pass rate)",
                    color="green"
                )
        
        with col4:
            worst_agent = data.get("worst_agent")
            if worst_agent:
                display_summary_card(
                    "Worst Agent",
                    worst_agent,
                    f"({data.get('worst_agent_pass_rate', 0):.1%} pass rate)",
                    color="red"
                )
        
        st.markdown("---")
        
        # Agent metrics table
        st.subheader("Agent Performance Metrics")
        
        try:
            metrics_data = []
            filtered_agents = data.get("agent_results", {})
            
            for agent_name, result in filtered_agents.items():
                metrics_row = {
                    "Agent": agent_name,
                    "Pass Rate": f"{result.get('pass_rate', 0):.1%}",
                    "Passed": result.get('passed_count', 0),
                    "Failed": result.get('failed_count', 0),
                    "Avg Duration": f"{result.get('avg_duration', 0):.1f}s",
                    "MCP Calls": int(result.get('mcp_call_count', 0)),
                    "Local Calls": int(result.get('local_call_count', 0)),
                }
                metrics_data.append(metrics_row)
            
            if metrics_data:
                metrics_df = pd.DataFrame(metrics_data)
                st.dataframe(metrics_df, use_container_width=True, hide_index=True)
        
        except Exception as e:
            st.warning(f"Could not display metrics table: {e}")
        
        st.markdown("---")
        
        # Visualizations
        st.subheader("Performance Visualizations")
        
        try:
            filtered_agents = data.get("agent_results", {})
            if filtered_agents and len(filtered_agents) > 1:
                col1, col2 = st.columns(2)
                
                with col1:
                    try:
                        pass_rate_chart = create_agent_comparison_bar_chart(
                            filtered_agents,
                            metric="pass_rate",
                            title="Pass Rate Comparison"
                        )
                        st.plotly_chart(pass_rate_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render pass rate chart: {e}")
                
                with col2:
                    try:
                        duration_chart = create_agent_comparison_bar_chart(
                            filtered_agents,
                            metric="avg_duration",
                            title="Average Duration Comparison"
                        )
                        st.plotly_chart(duration_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render duration chart: {e}")
                
                # Multi-metric comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    try:
                        call_chart = create_multi_metric_comparison_chart(
                            filtered_agents,
                            metrics=["mcp_call_count", "local_call_count"],
                            title="MCP vs Local Calls"
                        )
                        st.plotly_chart(call_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render call comparison chart: {e}")
                
                with col2:
                    try:
                        if any("deep_search_call_count" in r for r in filtered_agents.values()):
                            deep_search_chart = create_agent_comparison_bar_chart(
                                filtered_agents,
                                metric="deep_search_call_count",
                                title="Deep Search Call Frequency"
                            )
                            st.plotly_chart(deep_search_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not render deep search chart: {e}")
        
        except Exception as e:
            st.warning(f"Could not render visualizations: {e}")
        
        st.markdown("---")
        
        # Deltas vs baseline
        st.subheader(f"Performance Delta vs {self.baseline_agent}")
        
        try:
            filtered_deltas = data.get("agent_deltas", {})
            if filtered_deltas:
                deltas_data = []
                
                for delta_key, delta in filtered_deltas.items():
                    if "__" in delta_key:
                        parts = delta_key.split("__")
                        if parts[0] == self.baseline_agent and parts[1] == self.baseline_agent:
                            continue
                        variant_agent = parts[1] if len(parts) > 1 else delta_key
                    else:
                        variant_agent = delta_key
                    
                    delta_row = {
                        "Agent": variant_agent,
                        "Pass Rate Δ": f"{delta.get('pass_rate_delta', 0):+.1%}",
                        "Duration Δ": f"{delta.get('duration_delta', 0):+.1f}s",
                        "MCP Call Δ": f"{delta.get('mcp_call_delta', 0):+.0f}",
                    }
                    deltas_data.append(delta_row)
                
                if deltas_data:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        deltas_df = pd.DataFrame(deltas_data)
                        st.dataframe(deltas_df, use_container_width=True, hide_index=True)
                    
                    with col2:
                        try:
                            delta_chart = create_delta_comparison_chart(
                                filtered_deltas,
                                metric="pass_rate_delta",
                                title="Pass Rate Delta"
                            )
                            st.plotly_chart(delta_chart, use_container_width=True)
                        except Exception as e:
                            st.warning(f"Could not render delta chart: {e}")
        
        except Exception as e:
            st.warning(f"Could not display deltas: {e}")
        
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


def show_comparison_analysis():
    """Main entry point for comparison analysis view."""
    view = ComparisonAnalysisView()
    view.run()
