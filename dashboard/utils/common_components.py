"""
Common UI components and helpers for analysis views.

Provides reusable Streamlit components for:
- Experiment selection
- Agent filtering
- Metric selection
- Result export
- Summary cards
"""

import streamlit as st
import json
from typing import List, Optional, Dict, Any
from datetime import datetime


def display_metric_delta(label: str, value: float, is_percentage: bool = True, 
                         better_direction: str = "up") -> None:
    """
    Display a metric with delta indicator (up/down arrow).
    
    Args:
        label: Metric label
        value: Delta value (positive or negative)
        is_percentage: Whether to format as percentage
        better_direction: "up" if increasing is better, "down" if decreasing is better
    """
    if value == 0:
        indicator = "→"
        color = "gray"
    elif (value > 0 and better_direction == "up") or (value < 0 and better_direction == "down"):
        indicator = "↑"
        color = "green"
    else:
        indicator = "↓"
        color = "red"
    
    format_str = f"{value:+.1f}%" if is_percentage else f"{value:+.2f}"
    
    st.metric(
        label,
        format_str,
        delta=None,
        delta_color="off"
    )
    st.markdown(f"<span style='color:{color}'>{indicator}</span>", unsafe_allow_html=True)


def display_summary_card(title: str, value: str, metric: str = None, 
                        color: str = "blue") -> None:
    """
    Display a summary metric card.
    
    Args:
        title: Card title
        value: Main value to display
        metric: Optional secondary metric
        color: Card color theme (blue, green, red, orange)
    """
    color_map = {
        "blue": "#1f77b4",
        "green": "#2ca02c",
        "red": "#d62728",
        "orange": "#ff7f0e",
    }
    
    color_hex = color_map.get(color, "#1f77b4")
    
    html = f"""
    <div style="
        background-color: rgba({color_hex}, 0.1);
        border-left: 4px solid {color_hex};
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    ">
        <div style="font-size: 0.9em; color: #666; margin-bottom: 4px;">{title}</div>
        <div style="font-size: 1.4em; font-weight: bold; color: {color_hex};">{value}</div>
        {f'<div style="font-size: 0.85em; color: #888; margin-top: 4px;">{metric}</div>' if metric else ''}
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)


def display_significance_badge(p_value: float, alpha: float = 0.05) -> str:
    """
    Get HTML badge for statistical significance.
    
    Args:
        p_value: P-value from statistical test
        alpha: Significance threshold (default 0.05)
        
    Returns:
        HTML badge string
    """
    if p_value < 0.001:
        return '<span style="background: #2ca02c; color: white; padding: 2px 6px; border-radius: 3px;">✓ p<0.001</span>'
    elif p_value < 0.01:
        return '<span style="background: #2ca02c; color: white; padding: 2px 6px; border-radius: 3px;">✓ p<0.01</span>'
    elif p_value < alpha:
        return '<span style="background: #2ca02c; color: white; padding: 2px 6px; border-radius: 3px;">✓ p<0.05</span>'
    else:
        return '<span style="background: #888; color: white; padding: 2px 6px; border-radius: 3px;">✗ ns (p={:.3f})</span>'.format(p_value)


def display_effect_size_bar(effect_size: float, effect_name: str = "Cohen's d") -> None:
    """
    Display effect size as a horizontal bar.
    
    Args:
        effect_size: Effect size value
        effect_name: Name of effect size metric (Cohen's d, Cramér's V, etc.)
    """
    # Interpret effect size magnitude
    abs_size = abs(effect_size)
    
    if abs_size < 0.2:
        magnitude = "negligible"
        color = "#999"
    elif abs_size < 0.5:
        magnitude = "small"
        color = "#ffb81c"
    elif abs_size < 0.8:
        magnitude = "medium"
        color = "#ff6b6b"
    else:
        magnitude = "large"
        color = "#d62728"
    
    # Create bar visualization
    bar_width = min(abs_size * 100, 100)  # Cap at 100%
    
    html = f"""
    <div style="margin: 8px 0;">
        <div style="font-size: 0.9em; margin-bottom: 4px;">
            {effect_name}: <strong>{effect_size:.3f}</strong> ({magnitude})
        </div>
        <div style="
            background-color: #eee;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
        ">
            <div style="
                background-color: {color};
                height: 100%;
                width: {bar_width}%;
                transition: width 0.3s ease;
            "></div>
        </div>
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)


def experiment_selector() -> Optional[str]:
    """
    Render experiment selector in sidebar.
    
    Returns:
        Selected experiment ID or None
    """
    # Try to get loader from session state
    try:
        loader = st.session_state.get("analysis_loader")
        if loader is None:
            st.warning("Analysis database not initialized. Please go to Analysis Hub first.")
            return None
        
        experiments = loader.list_experiments()
        
        if not experiments:
            st.warning("No experiments found in database.")
            return None
        
        selected = st.selectbox(
            "Select Experiment",
            experiments,
            key="selected_experiment",
            help="Choose an experiment to analyze"
        )
        
        return selected
    except Exception as e:
        st.error(f"Failed to load experiments: {e}")
        return None


def agent_multiselect(experiment_id: str) -> List[str]:
    """
    Render agent multi-select in sidebar.
    
    Args:
        experiment_id: Experiment ID to load agents from
        
    Returns:
        List of selected agent names
    """
    try:
        loader = st.session_state.get("analysis_loader")
        if loader is None:
            return []
        
        agents = loader.list_agents(experiment_id)
        
        if not agents:
            return []
        
        selected = st.multiselect(
            "Filter Agents (optional)",
            agents,
            key="selected_agents",
            help="Leave empty to show all agents"
        )
        
        return selected if selected else agents
    except Exception as e:
        st.error(f"Failed to load agents: {e}")
        return []


def metric_selector(available_metrics: List[str], default: List[str] = None) -> List[str]:
    """
    Render metric selector.
    
    Args:
        available_metrics: List of available metric names
        default: Default metrics to select
        
    Returns:
        List of selected metrics
    """
    if default is None:
        default = available_metrics[:3]  # Select first 3 by default
    
    selected = st.multiselect(
        "Select Metrics",
        available_metrics,
        default=default,
        key="selected_metrics",
        help="Choose metrics to display"
    )
    
    return selected if selected else default


def export_json_button(data: Dict[str, Any], filename: str) -> None:
    """
    Render JSON export button.
    
    Args:
        data: Data to export (will be converted to JSON)
        filename: Name of file to download (without extension)
    """
    json_data = json.dumps(data, indent=2, default=str)
    
    st.download_button(
        label="📥 Export as JSON",
        data=json_data,
        file_name=f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json"
    )


def display_no_data_message(message: str = "No data available") -> None:
    """
    Display an informational message for no data.
    
    Args:
        message: Message to display
    """
    st.info(f"ℹ️ {message}")


def display_error_message(error: str) -> None:
    """
    Display an error message.
    
    Args:
        error: Error message to display
    """
    st.error(f"❌ {error}")


def display_warning_message(message: str) -> None:
    """
    Display a warning message.
    
    Args:
        message: Warning message to display
    """
    st.warning(f"⚠️ {message}")


def display_success_message(message: str) -> None:
    """
    Display a success message.
    
    Args:
        message: Success message to display
    """
    st.success(f"✓ {message}")


def display_metric_table(data: List[Dict[str, Any]], title: str = None) -> None:
    """
    Display a formatted metric table.
    
    Args:
        data: List of dicts to display as table
        title: Optional table title
    """
    if title:
        st.subheader(title)
    
    if not data:
        display_no_data_message()
        return
    
    st.dataframe(data, use_container_width=True, hide_index=True)


def confidence_level_slider(default: float = 0.95) -> float:
    """
    Render confidence level slider for statistical tests.
    
    Args:
        default: Default confidence level (0.90-0.99)
        
    Returns:
        Selected confidence level
    """
    return st.slider(
        "Confidence Level",
        min_value=0.90,
        max_value=0.99,
        value=default,
        step=0.01,
        help="Higher confidence requires stronger evidence of significance"
    )


def display_trend_indicator(trend_direction: str, percent_change: float) -> str:
    """
    Get HTML badge for trend indicator.
    
    Args:
        trend_direction: "IMPROVING", "DEGRADING", or "STABLE"
        percent_change: Percent change value
        
    Returns:
        HTML badge string
    """
    if trend_direction == "IMPROVING":
        return f'<span style="background: #2ca02c; color: white; padding: 2px 6px; border-radius: 3px;">↑ {percent_change:+.1f}%</span>'
    elif trend_direction == "DEGRADING":
        return f'<span style="background: #d62728; color: white; padding: 2px 6px; border-radius: 3px;">↓ {percent_change:+.1f}%</span>'
    else:
        return f'<span style="background: #888; color: white; padding: 2px 6px; border-radius: 3px;">→ {percent_change:+.1f}%</span>'


def display_cost_indicator(is_regression: bool, percent_change: float) -> str:
    """
    Get HTML badge for cost indicator.
    
    Args:
        is_regression: Whether cost increased
        percent_change: Percent change in cost
        
    Returns:
        HTML badge string
    """
    if is_regression:
        return f'<span style="background: #d62728; color: white; padding: 2px 6px; border-radius: 3px;">⚠️ +{percent_change:.1f}%</span>'
    else:
        return f'<span style="background: #2ca02c; color: white; padding: 2px 6px; border-radius: 3px;">✓ {percent_change:+.1f}%</span>'


def display_filter_badge(filter_name: str, value: Any, removable: bool = True) -> None:
    """
    Display a filter badge showing an active filter.
    
    Args:
        filter_name: Name of the filter
        value: Current filter value
        removable: Whether to show a remove button
    """
    badge_html = f"""
    <span style="
        display: inline-block;
        background: #e3f2fd;
        color: #1565c0;
        padding: 4px 8px;
        border-radius: 16px;
        font-size: 0.85em;
        margin: 2px;
    ">
        <strong>{filter_name}:</strong> {value}
        {' ×' if removable else ''}
    </span>
    """
    st.markdown(badge_html, unsafe_allow_html=True)
