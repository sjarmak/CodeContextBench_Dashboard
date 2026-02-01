"""
Navigation and context management for cross-view functionality.

Provides:
- Navigation context tracking
- Breadcrumb management
- URL query parameter handling
- Context persistence across views
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urlencode, parse_qs
from datetime import datetime
import streamlit as st


@dataclass
class NavigationContext:
    """
    Tracks navigation state across views.
    
    Maintains current view, experiment, agents, and filters to enable
    seamless cross-view navigation and context persistence.
    """
    
    current_view: str = "analysis_hub"
    current_experiment: Optional[str] = None
    selected_agents: List[str] = field(default_factory=list)
    active_filters: Dict[str, Any] = field(default_factory=dict)
    breadcrumb_path: List[Tuple[str, str]] = field(default_factory=list)  # [(view, label)]
    timestamp: float = field(default_factory=datetime.now().timestamp)
    
    def navigate_to(
        self,
        view: str,
        experiment: Optional[str] = None,
        agents: Optional[List[str]] = None,
        label: Optional[str] = None
    ) -> None:
        """
        Navigate to a new view and update context.
        
        Args:
            view: Target view name
            experiment: Experiment ID to load (optional)
            agents: Agents to focus on (optional)
            label: Human-readable label for breadcrumb
        """
        # Update current view
        self.current_view = view
        
        # Update experiment if provided
        if experiment:
            self.current_experiment = experiment
        
        # Update agents if provided
        if agents:
            self.selected_agents = agents
        
        # Add to breadcrumb
        breadcrumb_label = label or view.replace("_", " ").title()
        if not self.breadcrumb_path or self.breadcrumb_path[-1][0] != view:
            self.breadcrumb_path.append((view, breadcrumb_label))
        
        # Update timestamp
        self.timestamp = datetime.now().timestamp()
    
    def go_back(self) -> None:
        """Navigate back to previous view"""
        if len(self.breadcrumb_path) > 1:
            self.breadcrumb_path.pop()
            prev_view, _ = self.breadcrumb_path[-1]
            self.current_view = prev_view
    
    def reset(self) -> None:
        """Reset navigation context"""
        self.current_view = "analysis_hub"
        self.current_experiment = None
        self.selected_agents = []
        self.active_filters = {}
        self.breadcrumb_path = [("analysis_hub", "Analysis Hub")]
        self.timestamp = datetime.now().timestamp()
    
    def to_dict(self) -> Dict[str, Any]:
        """Export context as dictionary"""
        return {
            "current_view": self.current_view,
            "current_experiment": self.current_experiment,
            "selected_agents": self.selected_agents,
            "active_filters": self.active_filters,
            "breadcrumb_path": self.breadcrumb_path,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavigationContext":
        """Create context from dictionary"""
        return cls(
            current_view=data.get("current_view", "analysis_hub"),
            current_experiment=data.get("current_experiment"),
            selected_agents=data.get("selected_agents", []),
            active_filters=data.get("active_filters", {}),
            breadcrumb_path=data.get("breadcrumb_path", [("analysis_hub", "Analysis Hub")]),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
        )


class QueryParams:
    """
    Handles URL query parameter encoding/decoding for navigation state.
    
    Enables bookmarking and sharing of dashboard states via URLs.
    """
    
    PARAM_MAPPINGS = {
        "view": "current_view",
        "exp": "current_experiment",
        "agents": "selected_agents",
        "filters": "active_filters",
    }
    
    @staticmethod
    def encode(context: NavigationContext) -> str:
        """
        Encode navigation context to URL query string.
        
        Args:
            context: Navigation context to encode
            
        Returns:
            URL-encoded query string
        """
        params = {}
        
        # Encode view
        if context.current_view and context.current_view != "analysis_hub":
            params["view"] = context.current_view
        
        # Encode experiment
        if context.current_experiment:
            params["exp"] = context.current_experiment
        
        # Encode agents
        if context.selected_agents:
            params["agents"] = ",".join(context.selected_agents)
        
        # Encode filters (simplified - only key filter info)
        if context.active_filters:
            filter_parts = []
            for key, value in context.active_filters.items():
                if isinstance(value, list):
                    filter_parts.append(f"{key}:{','.join(str(v) for v in value)}")
                else:
                    filter_parts.append(f"{key}:{value}")
            if filter_parts:
                params["filters"] = ";".join(filter_parts)
        
        return urlencode(params)
    
    @staticmethod
    def decode(query_string: str) -> NavigationContext:
        """
        Decode URL query string to navigation context.
        
        Args:
            query_string: URL query string (without '?')
            
        Returns:
            Decoded navigation context
        """
        params = parse_qs(query_string)
        context = NavigationContext()
        
        # Decode view
        if "view" in params:
            context.current_view = params["view"][0]
        
        # Decode experiment
        if "exp" in params:
            context.current_experiment = params["exp"][0]
        
        # Decode agents
        if "agents" in params:
            context.selected_agents = params["agents"][0].split(",")
        
        # Decode filters
        if "filters" in params:
            filter_pairs = params["filters"][0].split(";")
            for pair in filter_pairs:
                key, value = pair.split(":", 1)
                if "," in value:
                    context.active_filters[key] = value.split(",")
                else:
                    context.active_filters[key] = value
        
        return context


class Breadcrumbs:
    """
    Manages breadcrumb display and navigation.
    
    Renders clickable breadcrumb trail showing navigation path.
    """
    
    @staticmethod
    def render(context: NavigationContext) -> None:
        """
        Render breadcrumb navigation.
        
        Args:
            context: Navigation context with breadcrumb path
        """
        if not context.breadcrumb_path or len(context.breadcrumb_path) <= 1:
            return
        
        # Build breadcrumb HTML
        breadcrumb_items = []
        for i, (view, label) in enumerate(context.breadcrumb_path):
            if i == len(context.breadcrumb_path) - 1:
                # Current view (not clickable)
                breadcrumb_items.append(f"<span>{label}</span>")
            else:
                # Previous view (clickable)
                breadcrumb_items.append(f'<a href="?view={view}">{label}</a>')
        
        breadcrumb_html = " → ".join(breadcrumb_items)
        
        st.markdown(
            f'<div style="font-size: 0.9em; color: #666; margin: 8px 0;">{breadcrumb_html}</div>',
            unsafe_allow_html=True
        )
    
    @staticmethod
    def render_simple(labels: List[str]) -> None:
        """
        Render simple breadcrumb (non-clickable).
        
        Args:
            labels: List of breadcrumb labels
        """
        if not labels:
            return
        
        breadcrumb_text = " → ".join(labels)
        st.markdown(
            f'<div style="font-size: 0.9em; color: #666; margin: 8px 0;">{breadcrumb_text}</div>',
            unsafe_allow_html=True
        )


class RecentItems:
    """
    Tracks and displays recently viewed items.
    """
    
    MAX_RECENT = 5
    
    @staticmethod
    def add_experiment(experiment_id: str, max_items: int = MAX_RECENT) -> None:
        """
        Add experiment to recent items.
        
        Args:
            experiment_id: Experiment ID
            max_items: Maximum recent items to keep
        """
        if "recent_experiments" not in st.session_state:
            st.session_state.recent_experiments = []
        
        recent = st.session_state.recent_experiments
        
        # Remove if already in list
        if experiment_id in recent:
            recent.remove(experiment_id)
        
        # Add to front
        recent.insert(0, experiment_id)
        
        # Keep only max items
        st.session_state.recent_experiments = recent[:max_items]
    
    @staticmethod
    def add_agent(agent_name: str, max_items: int = MAX_RECENT) -> None:
        """
        Add agent to recent items.
        
        Args:
            agent_name: Agent name
            max_items: Maximum recent items to keep
        """
        if "recent_agents" not in st.session_state:
            st.session_state.recent_agents = []
        
        recent = st.session_state.recent_agents
        
        # Remove if already in list
        if agent_name in recent:
            recent.remove(agent_name)
        
        # Add to front
        recent.insert(0, agent_name)
        
        # Keep only max items
        st.session_state.recent_agents = recent[:max_items]
    
    @staticmethod
    def get_experiments() -> List[str]:
        """Get recent experiments"""
        return st.session_state.get("recent_experiments", [])
    
    @staticmethod
    def get_agents() -> List[str]:
        """Get recent agents"""
        return st.session_state.get("recent_agents", [])
    
    @staticmethod
    def clear() -> None:
        """Clear all recent items"""
        st.session_state.recent_experiments = []
        st.session_state.recent_agents = []


def get_navigation_context() -> NavigationContext:
    """
    Get or create navigation context from session state.
    
    Returns:
        Navigation context
    """
    if "nav_context" not in st.session_state:
        st.session_state.nav_context = NavigationContext()
    return st.session_state.nav_context


def update_navigation_context(
    view: str,
    experiment: Optional[str] = None,
    agents: Optional[List[str]] = None,
    label: Optional[str] = None
) -> NavigationContext:
    """
    Update navigation context and return it.
    
    Args:
        view: Target view
        experiment: Experiment ID (optional)
        agents: Agent names (optional)
        label: Breadcrumb label (optional)
        
    Returns:
        Updated navigation context
    """
    context = get_navigation_context()
    context.navigate_to(view, experiment, agents, label)
    st.session_state.nav_context = context
    return context


def quick_navigate_sidebar(context: NavigationContext, loader) -> bool:
    """
    Render quick navigation sidebar.
    
    Args:
        context: Navigation context
        loader: AnalysisLoader instance
        
    Returns:
        True if user navigated
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Navigation")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("← Back"):
            context.go_back()
            st.rerun()
            return True
    
    with col2:
        if st.button("🏠 Hub"):
            context.reset()
            st.session_state.current_page = "Analysis Hub"
            st.rerun()
            return True
    
    st.sidebar.markdown("---")
    
    # Recent experiments
    recent_exps = RecentItems.get_experiments()
    if recent_exps:
        st.sidebar.caption("Recent Experiments")
        for exp_id in recent_exps[:3]:
            if st.sidebar.button(f"→ {exp_id}", key=f"recent_exp_{exp_id}"):
                context.navigate_to("analysis_comparison", experiment=exp_id)
                st.session_state.current_page = "Comparison Analysis"
                st.rerun()
                return True
    
    return False
