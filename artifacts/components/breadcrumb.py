"""
Breadcrumb navigation component for dashboard.

Provides clickable breadcrumb trails showing navigation path.
"""

import streamlit as st
from typing import List, Tuple, Optional
from dashboard.utils.navigation import NavigationContext


def render_breadcrumb_navigation(
    context: NavigationContext,
    show_reset: bool = True
) -> None:
    """
    Render breadcrumb navigation with context info.
    
    Args:
        context: Navigation context
        show_reset: Show reset button
    """
    if not context.breadcrumb_path or len(context.breadcrumb_path) <= 1:
        return
    
    # Create columns for breadcrumb and controls
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        # Build breadcrumb items
        items = []
        for i, (view, label) in enumerate(context.breadcrumb_path):
            if i == 0:
                items.append(f"🏠 {label}")
            elif i == len(context.breadcrumb_path) - 1:
                # Current view
                items.append(f"<b>{label}</b>")
            else:
                # Previous views
                items.append(label)
        
        breadcrumb_text = " → ".join(items)
        st.markdown(
            f'<div style="font-size: 0.95em; color: #444;">{breadcrumb_text}</div>',
            unsafe_allow_html=True
        )
    
    with col2:
        # Context info
        context_items = []
        if context.current_experiment:
            context_items.append(f"Exp: {context.current_experiment[:8]}...")
        if context.selected_agents:
            context_items.append(f"Agents: {len(context.selected_agents)}")
        
        if context_items:
            context_text = " | ".join(context_items)
            st.caption(context_text)
    
    with col3:
        if show_reset:
            if st.button("↻ Reset", key="breadcrumb_reset"):
                context.reset()
                st.session_state.current_page = "Analysis Hub"
                st.rerun()
    
    st.markdown("---")


def render_simple_breadcrumb(labels: List[str]) -> None:
    """
    Render simple non-interactive breadcrumb.
    
    Args:
        labels: Breadcrumb labels
    """
    if not labels:
        return
    
    # Highlight last item
    display_labels = []
    for i, label in enumerate(labels):
        if i == len(labels) - 1:
            display_labels.append(f"<b>{label}</b>")
        else:
            display_labels.append(label)
    
    breadcrumb_text = " → ".join(display_labels)
    st.markdown(
        f'<div style="font-size: 0.95em; color: #444; margin: 12px 0;">{breadcrumb_text}</div>',
        unsafe_allow_html=True
    )


def render_context_badge(
    experiment: Optional[str] = None,
    agents: Optional[List[str]] = None,
    view: Optional[str] = None
) -> None:
    """
    Render context information as badges.
    
    Args:
        experiment: Current experiment ID
        agents: Selected agents
        view: Current view name
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if view:
            view_label = view.replace("_", " ").title()
            st.markdown(
                f'<div style="background: #e3f2fd; padding: 4px 8px; border-radius: 4px; '
                f'font-size: 0.85em;">📊 {view_label}</div>',
                unsafe_allow_html=True
            )
    
    with col2:
        if experiment:
            st.markdown(
                f'<div style="background: #f3e5f5; padding: 4px 8px; border-radius: 4px; '
                f'font-size: 0.85em;">📁 {experiment}</div>',
                unsafe_allow_html=True
            )
    
    with col3:
        if agents:
            agent_label = f"{len(agents)} agent" + ("s" if len(agents) != 1 else "")
            st.markdown(
                f'<div style="background: #e8f5e9; padding: 4px 8px; border-radius: 4px; '
                f'font-size: 0.85em;">🤖 {agent_label}</div>',
                unsafe_allow_html=True
            )
