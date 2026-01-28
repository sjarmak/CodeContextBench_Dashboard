"""Breadcrumb navigation component for dashboard views."""

import streamlit as st
from typing import Optional


class NavigationContext:
    """Navigation context for tracking user location in dashboard."""
    
    def __init__(self):
        self.history = []
        self.current_view = "Home"
        self.current_experiment = None
        self.current_task = None
        self.current_agent = None
    
    def push(self, view: str, **kwargs):
        """Push a new view onto the navigation stack."""
        self.history.append({
            "view": self.current_view,
            "experiment": self.current_experiment,
            "task": self.current_task,
            "agent": self.current_agent,
        })
        self.current_view = view
        self.current_experiment = kwargs.get("experiment", self.current_experiment)
        self.current_task = kwargs.get("task", self.current_task)
        self.current_agent = kwargs.get("agent", self.current_agent)
    
    def pop(self) -> Optional[dict]:
        """Pop the last view from the navigation stack."""
        if self.history:
            prev = self.history.pop()
            self.current_view = prev["view"]
            self.current_experiment = prev["experiment"]
            self.current_task = prev["task"]
            self.current_agent = prev["agent"]
            return prev
        return None
    
    def get_breadcrumb_items(self) -> list:
        """Get breadcrumb items for current location."""
        items = [{"label": "Home", "view": "Home"}]
        
        if self.current_experiment:
            items.append({
                "label": self.current_experiment,
                "view": "Experiment",
                "experiment": self.current_experiment
            })
        
        if self.current_task:
            items.append({
                "label": self.current_task,
                "view": "Task",
                "task": self.current_task
            })
        
        if self.current_agent:
            items.append({
                "label": self.current_agent,
                "view": "Agent",
                "agent": self.current_agent
            })
        
        return items


def render_breadcrumb_navigation(nav_context: Optional[NavigationContext] = None):
    """Render breadcrumb navigation bar.
    
    Args:
        nav_context: Navigation context with current location info.
                    If None, shows minimal breadcrumb.
    """
    if nav_context is None:
        # Minimal breadcrumb
        st.markdown("**Dashboard**")
        return
    
    items = nav_context.get_breadcrumb_items()
    
    if not items:
        return
    
    # Build breadcrumb HTML
    breadcrumb_parts = []
    for i, item in enumerate(items):
        if i == len(items) - 1:
            # Current item (not clickable)
            breadcrumb_parts.append(f"**{item['label']}**")
        else:
            # Previous items (could be clickable in future)
            breadcrumb_parts.append(item['label'])
    
    breadcrumb_text = " > ".join(breadcrumb_parts)
    st.markdown(f"{breadcrumb_text}")
