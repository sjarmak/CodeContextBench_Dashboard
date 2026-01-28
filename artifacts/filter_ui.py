"""
UI helpers for advanced filtering in dashboard views.

Provides Streamlit components for:
- Metric selection
- Date range filtering
- Difficulty filtering
- Agent grouping
"""

import streamlit as st
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict
from dashboard.utils.filters import (
    FilterConfig,
    TaskDifficulty,
    get_available_metrics,
    FilterEngine
)


def render_metric_selector(
    view_type: str,
    key_suffix: str = "",
    default: Optional[List[str]] = None,
    help_text: str = "Select metrics to display and analyze"
) -> List[str]:
    """
    Render metric selector for a specific view.
    
    Args:
        view_type: Type of view (comparison, statistical, etc.)
        key_suffix: Unique key suffix
        default: Default selected metrics
        help_text: Help text for selector
        
    Returns:
        List of selected metrics
    """
    available_metrics = get_available_metrics(view_type)
    
    if not available_metrics:
        return []
    
    selected = st.multiselect(
        "Select Metrics",
        available_metrics,
        default=default or available_metrics[:3],
        help=help_text,
        key=f"metrics_{view_type}_{key_suffix}" if key_suffix else f"metrics_{view_type}"
    )
    
    return selected


def render_difficulty_selector(
    key_suffix: str = "",
    help_text: str = "Filter tasks by difficulty level"
) -> List[TaskDifficulty]:
    """
    Render task difficulty filter.
    
    Args:
        key_suffix: Unique key suffix
        help_text: Help text
        
    Returns:
        List of selected difficulty levels
    """
    difficulty_options = [d.value for d in TaskDifficulty]
    
    selected = st.multiselect(
        "Filter by Difficulty",
        difficulty_options,
        default=None,
        help=help_text,
        key=f"difficulty_{key_suffix}" if key_suffix else "difficulty"
    )
    
    return [TaskDifficulty(d) for d in selected] if selected else []


def render_date_range_filter(
    key_suffix: str = "",
    help_text: str = "Filter experiments by date range"
) -> Tuple[Optional[date], Optional[date]]:
    """
    Render date range filter.
    
    Args:
        key_suffix: Unique key suffix
        help_text: Help text
        
    Returns:
        Tuple of (date_from, date_to)
    """
    col1, col2 = st.columns(2)
    
    with col1:
        date_from = st.date_input(
            "From Date",
            value=None,
            help="Start date (inclusive)",
            key=f"date_from_{key_suffix}" if key_suffix else "date_from"
        )
    
    with col2:
        date_to = st.date_input(
            "To Date",
            value=None,
            help="End date (inclusive)",
            key=f"date_to_{key_suffix}" if key_suffix else "date_to"
        )
    
    # Validate date range
    if date_from and date_to and date_from > date_to:
        st.warning("From date must be before to date")
        return None, None
    
    return date_from if date_from else None, date_to if date_to else None


def render_agent_group_selector(
    agents: List[str],
    key_suffix: str = "",
    help_text: str = "Create agent groups for comparison"
) -> Dict[str, List[str]]:
    """
    Render agent grouping selector.
    
    Args:
        agents: Available agents
        key_suffix: Unique key suffix
        help_text: Help text
        
    Returns:
        Dictionary mapping group names to agent lists
    """
    groups = {}
    
    st.subheader("Agent Groups")
    st.caption("Create groups to compare multiple agents together")
    
    # Predefined groups
    if st.checkbox("Use Predefined Groups", key=f"use_predefined_{key_suffix}"):
        predefined_groups = {
            "All MCP Agents": [a for a in agents if "strategic" in a or "full" in a],
            "Baseline Only": [a for a in agents if "baseline" in a],
            "All Agents": agents,
        }
        
        for group_name in predefined_groups:
            if group_name in predefined_groups and predefined_groups[group_name]:
                groups[group_name] = predefined_groups[group_name]
    
    # Custom groups
    if st.checkbox("Create Custom Groups", key=f"use_custom_{key_suffix}"):
        num_groups = st.slider(
            "Number of Groups",
            1, 3, 1,
            key=f"num_groups_{key_suffix}"
        )
        
        for i in range(num_groups):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                group_name = st.text_input(
                    f"Group {i+1} Name",
                    value=f"Group {i+1}",
                    key=f"group_name_{i}_{key_suffix}"
                )
            
            with col2:
                group_agents = st.multiselect(
                    f"Agents for {group_name}",
                    agents,
                    key=f"group_agents_{i}_{key_suffix}"
                )
            
            if group_agents:
                groups[group_name] = group_agents
    
    return groups


def render_filter_panel(
    view_type: str,
    loader,
    experiment_id: str,
    key_suffix: str = ""
) -> FilterConfig:
    """
    Render complete filter panel for a view.
    
    Args:
        view_type: Type of view
        loader: AnalysisLoader instance
        experiment_id: Current experiment ID
        key_suffix: Unique key suffix
        
    Returns:
        Configured FilterConfig object
    """
    st.sidebar.markdown("### Filters")
    
    # Metrics
    metrics = render_metric_selector(view_type, key_suffix)
    
    # Difficulty
    difficulties = render_difficulty_selector(key_suffix)
    
    # Date range
    date_from, date_to = render_date_range_filter(key_suffix)
    
    # Agents
    agents = loader.list_agents(experiment_id)
    selected_agents = st.sidebar.multiselect(
        "Filter Agents",
        agents if agents else [],
        help="Leave empty to show all agents",
        key=f"filter_agents_{key_suffix}" if key_suffix else "filter_agents"
    )
    
    # Create filter config
    config = FilterConfig(
        metrics=metrics,
        difficulty_levels=difficulties,
        date_from=date_from,
        date_to=date_to,
        agents=selected_agents if selected_agents else []
    )
    
    return config


def render_filter_summary(config: FilterConfig) -> None:
    """
    Render summary of active filters.
    
    Args:
        config: Filter configuration
    """
    engine = FilterEngine()
    summary = engine.get_filter_summary(config)
    
    if config.has_filters():
        st.info(f"📊 Filters: {summary}")
    else:
        st.caption("No filters applied")


def render_filter_reset_button(key: str = "reset_filters") -> bool:
    """
    Render filter reset button.
    
    Args:
        key: Button key
        
    Returns:
        True if reset clicked
    """
    if st.sidebar.button("🔄 Reset Filters", key=key):
        return True
    return False


def apply_filters_with_display(
    data: Dict,
    config: FilterConfig,
    view_name: str = ""
) -> Dict:
    """
    Apply filters to data and display filter info.
    
    Args:
        data: Analysis result data
        config: Filter configuration
        view_name: Name of view (for context)
        
    Returns:
        Filtered data
    """
    engine = FilterEngine()
    
    # Apply filters
    filtered_data = engine.apply_filters(data, config)
    
    # Display filter summary
    if config.has_filters():
        st.info(f"Filters applied to {view_name}")
        render_filter_summary(config)
    
    return filtered_data


def render_grouping_options(
    agents: List[str],
    key_suffix: str = ""
) -> Optional[Dict[str, List[str]]]:
    """
    Render agent grouping options.
    
    Args:
        agents: Available agents
        key_suffix: Unique key suffix
        
    Returns:
        Grouping configuration or None
    """
    if not st.sidebar.checkbox(
        "Enable Agent Grouping",
        key=f"enable_grouping_{key_suffix}" if key_suffix else "enable_grouping"
    ):
        return None
    
    return render_agent_group_selector(agents, key_suffix)
