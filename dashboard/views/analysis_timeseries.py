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
        st.info("Click on 'Analysis Hub' in the sidebar to initialize the database connection.")
        return

    # Configuration in main area
    st.subheader("Configuration")

    # Experiment selector - allow multiple
    try:
        all_experiments = loader.list_experiments()
        if not all_experiments:
            st.error("No experiments available")
            return

        selected_experiments = st.multiselect(
            "Select Experiments (in chronological order)",
            all_experiments,
            help="Choose 2+ experiments to analyze trends",
            default=all_experiments[-3:] if len(all_experiments) >= 3 else all_experiments,
            key="timeseries_experiments"
        )

        if not selected_experiments or len(selected_experiments) < 2:
            st.warning("Select at least 2 experiments to view trends")
            return

        # Sort by experiment ID (assumes chronological naming)
        experiment_ids = sorted(selected_experiments)
    except Exception as e:
        st.error(f"Failed to load experiments: {e}")
        return

    col1, col2 = st.columns(2)

    with col1:
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
                default=all_agents,
                key="timeseries_agents"
            )

            agent_names = selected_agents if selected_agents else None
        except Exception as e:
            st.error(f"Failed to load agents: {e}")
            agent_names = None

    with col2:
        # Metric selector
        available_metrics = ["pass_rate", "duration", "mcp_calls", "cost_per_success"]
        selected_metrics = st.multiselect(
            "Select Metrics",
            available_metrics,
            default=["pass_rate", "duration"],
            help="Metrics to display in trends",
            key="timeseries_metrics"
        )

        if not selected_metrics:
            st.warning("Select at least one metric")
            return

    # Update navigation context (with first experiment for reference)
    if experiment_ids:
        nav_context.set_experiment(experiment_ids[0])

    # Advanced filtering in expander
    with st.expander("Advanced Filters"):
        filter_config = render_filter_panel("timeseries", loader, experiment_ids[0] if experiment_ids else None, key_suffix="ts")
    
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
        st.info(f"Filters applied: {filter_engine.get_filter_summary(filter_config)}")
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
        # Count improving/degrading trends from the nested structure
        improving = 0
        degrading = 0
        if timeseries_result.trends:
            for metric_name, agent_trends in timeseries_result.trends.items():
                for agent_name, trend in agent_trends.items():
                    if hasattr(trend, 'direction'):
                        if trend.direction.value == "improving":
                            improving += 1
                        elif trend.direction.value == "degrading":
                            degrading += 1

        display_summary_card(
            "Improving Metrics",
            str(improving),
            f"{degrading} degrading",
            color="green" if improving > degrading else "gray"
        )

    with col4:
        # Use total_anomalies from result
        anomaly_count = timeseries_result.total_anomalies if hasattr(timeseries_result, 'total_anomalies') else 0

        display_summary_card(
            "Anomalies Detected",
            str(anomaly_count),
            "unusual patterns",
            color="gray"
        )
    
    st.markdown("---")
    
    # Trend data by metric
    st.subheader("Metric Trends")

    try:
        if timeseries_result.trends:
            trends_data = []

            # Iterate through metric -> agent -> trend structure
            for metric_name, agent_trends in timeseries_result.trends.items():
                if metric_name not in selected_metrics:
                    continue

                for agent_name, trend in agent_trends.items():
                    direction = trend.direction.value.upper() if hasattr(trend.direction, 'value') else str(trend.direction)
                    percent_change = trend.percent_change if hasattr(trend, 'percent_change') else 0
                    slope = trend.slope if hasattr(trend, 'slope') else 0
                    confidence = trend.confidence if hasattr(trend, 'confidence') else 0

                    trends_row = {
                        "Metric": metric_name,
                        "Agent": agent_name,
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
        if timeseries_result.trends:
            agent_trends_data = []

            # Reorganize: metric -> agent -> trend into agent -> metric view
            for metric_name, agent_trends in timeseries_result.trends.items():
                if metric_name not in selected_metrics:
                    continue

                for agent_name, trend in agent_trends.items():
                    agent_row = {
                        "Agent": agent_name,
                        "Metric": metric_name,
                        "Start": f"{trend.first_value:.2f}" if hasattr(trend, 'first_value') else "N/A",
                        "End": f"{trend.last_value:.2f}" if hasattr(trend, 'last_value') else "N/A",
                        "Change": f"{trend.percent_change:+.1f}%" if hasattr(trend, 'percent_change') else "N/A",
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
        with col1:
            st.markdown("**Best Improving**")
            if timeseries_result.best_improving_metric:
                trend = timeseries_result.best_improving_metric
                best_data = [{
                    "Metric": trend.metric_name,
                    "Agent": trend.agent_name,
                    "Improvement": f"{trend.percent_change:+.1f}%",
                    "Confidence": f"{trend.confidence:.2f}",
                }]
                st.dataframe(pd.DataFrame(best_data), use_container_width=True, hide_index=True)
            else:
                st.info("No improving metrics found")

        with col2:
            st.markdown("**Most Degrading**")
            if timeseries_result.worst_degrading_metric:
                trend = timeseries_result.worst_degrading_metric
                worst_data = [{
                    "Metric": trend.metric_name,
                    "Agent": trend.agent_name,
                    "Degradation": f"{trend.percent_change:+.1f}%",
                    "Confidence": f"{trend.confidence:.2f}",
                }]
                st.dataframe(pd.DataFrame(worst_data), use_container_width=True, hide_index=True)
            else:
                st.info("No degrading metrics found")

    except Exception as e:
        display_error_message(f"Failed to display best/worst metrics: {e}")
    
    st.markdown("---")
    
    # Anomalies
    st.subheader("Detected Anomalies")

    try:
        # Collect anomalies from trend objects
        anomaly_data = []

        if timeseries_result.trends:
            for metric_name, agent_trends in timeseries_result.trends.items():
                for agent_name, trend in agent_trends.items():
                    if hasattr(trend, 'has_anomalies') and trend.has_anomalies:
                        for i, desc in enumerate(trend.anomaly_descriptions):
                            anomaly_data.append({
                                "Agent": agent_name,
                                "Metric": metric_name,
                                "Description": desc,
                            })

        if anomaly_data:
            anomaly_df = pd.DataFrame(anomaly_data)
            st.dataframe(anomaly_df, use_container_width=True, hide_index=True)
        else:
            st.info("No anomalies detected in trends")

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
            "summary": {
                "total_anomalies": timeseries_result.total_anomalies,
                "agents_with_anomalies": timeseries_result.agents_with_anomalies,
            },
            "best_improving": timeseries_result.best_improving_metric.to_dict() if timeseries_result.best_improving_metric else None,
            "worst_degrading": timeseries_result.worst_degrading_metric.to_dict() if timeseries_result.worst_degrading_metric else None,
        }

        # Add trends data
        if timeseries_result.trends:
            export_data["trends"] = timeseries_result.to_dict().get("trends", {})

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
