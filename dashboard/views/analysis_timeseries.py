"""
Time-Series Analysis View - Trend analysis across multiple experiments.

Displays:
- Multi-experiment trends (line chart)
- Agent filtering
- Metric selection
- Anomaly highlighting
- Best/worst improving metrics
- Trend slope and confidence display
"""

import streamlit as st
from pathlib import Path
from typing import Optional, List
import pandas as pd

from dashboard.utils.common_components import (
    display_no_data_message,
    display_error_message,
    display_summary_card,
    export_json_button,
    display_trend_indicator,
    display_filter_badge,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


def show_timeseries_analysis():
    """Display time-series trend analysis view."""
    
    # Initialize navigation context if not present
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()
    
    nav_context = st.session_state.nav_context
    
    # Render breadcrumb navigation
    render_breadcrumb_navigation(nav_context)
    
    st.title("Time-Series Analysis")
    st.markdown("**Track metric changes across experiments**")
    st.markdown("---")
    
    # Initialize loader from session state
    loader = st.session_state.get("analysis_loader")
    if loader is None:
        st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.subheader("Configuration")
        
        # Experiment selector - allow multiple
        try:
            all_experiments = loader.list_experiments()
            if not all_experiments:
                st.error("No experiments available")
                return
            
            selected_experiments = st.multiselect(
                "Select Experiments (in order)",
                all_experiments,
                help="Choose 2+ experiments to analyze trends",
                default=all_experiments[-3:] if len(all_experiments) >= 3 else all_experiments
            )
            
            if not selected_experiments or len(selected_experiments) < 2:
                st.warning("Select at least 2 experiments to view trends")
                return
            
            # Sort by experiment ID (assumes chronological naming)
            experiment_ids = sorted(selected_experiments)
        except Exception as e:
            st.error(f"Failed to load experiments: {e}")
            return
        
        # Agent filter
        try:
            all_agents = set()
            for exp_id in experiment_ids:
                agents = loader.list_agents(exp_id)
                all_agents.update(agents)
            
            all_agents = sorted(list(all_agents))
            
            selected_agents = st.multiselect(
                "Filter Agents (optional)",
                all_agents,
                help="Leave empty to show all agents",
                default=all_agents
            )
            
            agent_names = selected_agents if selected_agents else None
        except Exception as e:
            st.error(f"Failed to load agents: {e}")
            agent_names = None
        
        # Metric selector
        available_metrics = ["pass_rate", "duration", "mcp_calls", "cost_per_success"]
        selected_metrics = st.multiselect(
            "Select Metrics",
            available_metrics,
            default=["pass_rate", "duration"],
            help="Metrics to display in trends"
        )
        
        if not selected_metrics:
            st.warning("Select at least one metric")
            return
        
        # Update navigation context (with first experiment for reference)
        if experiment_ids:
            nav_context.navigate_to("analysis_timeseries", experiment=experiment_ids[0], agents=selected_agents)
        
        st.markdown("---")
        
        # Advanced filtering section
        st.subheader("Advanced Filters")
        filter_config = render_filter_panel("timeseries", loader, experiment_ids[0] if experiment_ids else None)
    
    # Load time-series analysis
    try:
        timeseries_result = loader.load_timeseries(
            experiment_ids=experiment_ids,
            agent_names=agent_names,
        )
    except Exception as e:
        display_error_message(f"Failed to load time-series analysis: {e}")
        return
    
    if timeseries_result is None:
        display_no_data_message("No time-series data available")
        return
    
    # Apply filters if any are active
    filter_engine = FilterEngine()
    if filter_config.has_filters():
        st.info(f"📈 Filters applied: {filter_engine.get_filter_summary(filter_config)}")
        # Note: Filter application would go here when metrics are extracted
    
    # Summary statistics
    st.subheader("Trend Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        display_summary_card(
            "Experiments",
            str(len(experiment_ids)),
            "chronological order",
            color="blue"
        )
    
    with col2:
        display_summary_card(
            "Agents Tracked",
            str(len(selected_agents) if selected_agents else "All"),
            f"{len(all_agents) if not selected_agents else len(selected_agents)} total",
            color="blue"
        )
    
    with col3:
        improving = 0
        degrading = 0
        if timeseries_result.trends:
            for trend in timeseries_result.trends.values():
                if trend.get("direction") == "IMPROVING":
                    improving += 1
                elif trend.get("direction") == "DEGRADING":
                    degrading += 1
        
        display_summary_card(
            "Improving Metrics",
            str(improving),
            f"{degrading} degrading",
            color="green" if improving > degrading else "red"
        )
    
    with col4:
        anomaly_count = 0
        if timeseries_result.anomalies:
            anomaly_count = len(timeseries_result.anomalies)
        
        display_summary_card(
            "Anomalies Detected",
            str(anomaly_count),
            "unusual patterns",
            color="orange" if anomaly_count > 0 else "gray"
        )
    
    st.markdown("---")
    
    # Trend data by metric
    st.subheader("Metric Trends")
    
    try:
        if timeseries_result.trends:
            trends_data = []
            
            for metric, trend_info in timeseries_result.trends.items():
                if metric not in selected_metrics:
                    continue
                
                direction = trend_info.get("direction", "STABLE")
                percent_change = trend_info.get("percent_change", 0)
                slope = trend_info.get("slope", 0)
                confidence = trend_info.get("confidence", 0)
                
                trends_row = {
                    "Metric": metric,
                    "Direction": direction,
                    "Change": f"{percent_change:+.1f}%",
                    "Slope": f"{slope:+.4f}",
                    "Confidence": f"{confidence:.2f}",
                }
                trends_data.append(trends_row)
            
            if trends_data:
                trends_df = pd.DataFrame(trends_data)
                st.dataframe(trends_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No trend data for selected metrics")
        else:
            display_no_data_message("No trend analysis available")
    
    except Exception as e:
        display_error_message(f"Failed to display trends: {e}")
    
    st.markdown("---")
    
    # Agent trends
    st.subheader("Agent Performance Trends")
    
    try:
        if timeseries_result.agent_trends:
            agent_trends_data = []
            
            for agent, agent_metrics in timeseries_result.agent_trends.items():
                for metric, metric_trend in agent_metrics.items():
                    if metric not in selected_metrics:
                        continue
                    
                    agent_row = {
                        "Agent": agent,
                        "Metric": metric,
                        "Start": f"{metric_trend.get('start_value', 0):.2f}",
                        "End": f"{metric_trend.get('end_value', 0):.2f}",
                        "Change": f"{metric_trend.get('change_percent', 0):+.1f}%",
                    }
                    agent_trends_data.append(agent_row)
            
            if agent_trends_data:
                agent_trends_df = pd.DataFrame(agent_trends_data)
                st.dataframe(agent_trends_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No agent trend data available")
        else:
            display_no_data_message("No agent trends available")
    
    except Exception as e:
        display_error_message(f"Failed to display agent trends: {e}")
    
    st.markdown("---")
    
    # Best and worst improving
    st.subheader("Best & Worst Improving Metrics")
    
    col1, col2 = st.columns(2)
    
    try:
        if timeseries_result.best_improving:
            with col1:
                st.markdown("**Best Improving**")
                best_data = []
                for metric, change in timeseries_result.best_improving.items():
                    best_data.append({
                        "Metric": metric,
                        "Improvement": f"{change:+.1f}%",
                    })
                if best_data:
                    st.dataframe(pd.DataFrame(best_data), use_container_width=True, hide_index=True)
        
        if timeseries_result.worst_improving:
            with col2:
                st.markdown("**Most Degrading**")
                worst_data = []
                for metric, change in timeseries_result.worst_improving.items():
                    worst_data.append({
                        "Metric": metric,
                        "Degradation": f"{change:+.1f}%",
                    })
                if worst_data:
                    st.dataframe(pd.DataFrame(worst_data), use_container_width=True, hide_index=True)
    
    except Exception as e:
        display_error_message(f"Failed to display best/worst metrics: {e}")
    
    st.markdown("---")
    
    # Anomalies
    st.subheader("Detected Anomalies")
    
    try:
        if timeseries_result.anomalies:
            anomaly_data = []
            
            for anomaly in timeseries_result.anomalies:
                anomaly_row = {
                    "Experiment": anomaly.get("experiment_id", "N/A"),
                    "Agent": anomaly.get("agent_name", "N/A"),
                    "Metric": anomaly.get("metric", "N/A"),
                    "Severity": anomaly.get("severity", "normal").upper(),
                    "Description": anomaly.get("description", ""),
                }
                anomaly_data.append(anomaly_row)
            
            if anomaly_data:
                anomaly_df = pd.DataFrame(anomaly_data)
                st.dataframe(anomaly_df, use_container_width=True, hide_index=True)
            else:
                display_no_data_message("No anomalies detected")
        else:
            st.info("ℹ️ No anomalies detected in trends")
    
    except Exception as e:
        display_error_message(f"Failed to display anomalies: {e}")
    
    st.markdown("---")
    
    # Export functionality
    st.subheader("Export Results")
    
    try:
        export_data = {
            "experiment_ids": experiment_ids,
            "selected_agents": selected_agents,
            "selected_metrics": selected_metrics,
            "trends": timeseries_result.trends or {},
            "agent_trends": timeseries_result.agent_trends or {},
            "anomalies": timeseries_result.anomalies or [],
            "best_improving": timeseries_result.best_improving or {},
            "worst_improving": timeseries_result.worst_improving or {},
        }
        
        export_json_button(export_data, f"timeseries_{'_'.join(experiment_ids)}")
    
    except Exception as e:
        display_error_message(f"Failed to export data: {e}")
    
    st.markdown("---")
    
    # View notes
    st.subheader("View Notes")
    st.markdown("""
    - **Direction**: IMPROVING (better), DEGRADING (worse), or STABLE (no change)
    - **Change**: Percent change from first to last experiment
    - **Slope**: Rate of change per experiment
    - **Confidence**: How confident we are in the trend (0.0-1.0)
    - **Anomalies**: Unusual values detected in the time series
    - **Start/End**: First and last values in the experiment sequence
    """)
