"""Navigation utilities for dashboard views."""

from typing import Optional, List, Dict, Any


class NavigationContext:
    """Navigation context for tracking user location in dashboard.
    
    Maintains breadcrumb trail and context for analysis views.
    """
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.current_view: str = "Home"
        self.current_experiment: Optional[str] = None
        self.current_task: Optional[str] = None
        self.current_agent: Optional[str] = None
        self.filters: Dict[str, Any] = {}
    
    def push(self, view: str, **kwargs):
        """Push a new view onto the navigation stack.
        
        Args:
            view: Name of the view to navigate to
            **kwargs: Optional context (experiment, task, agent)
        """
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
    
    def pop(self) -> Optional[Dict[str, Any]]:
        """Pop the last view from the navigation stack.
        
        Returns:
            Previous navigation state or None if at root.
        """
        if self.history:
            prev = self.history.pop()
            self.current_view = prev["view"]
            self.current_experiment = prev["experiment"]
            self.current_task = prev["task"]
            self.current_agent = prev["agent"]
            return prev
        return None
    
    def reset(self):
        """Reset navigation to initial state."""
        self.history = []
        self.current_view = "Home"
        self.current_experiment = None
        self.current_task = None
        self.current_agent = None
        self.filters = {}
    
    def set_experiment(self, experiment: str):
        """Set current experiment context."""
        self.current_experiment = experiment
    
    def set_task(self, task: str):
        """Set current task context."""
        self.current_task = task
    
    def set_agent(self, agent: str):
        """Set current agent context."""
        self.current_agent = agent

    def navigate_to(self, view: str, experiment: str = None, agents: List[str] = None, task: str = None):
        """Navigate to a specific view with context.

        Args:
            view: Name of the view to navigate to
            experiment: Optional experiment ID
            agents: Optional list of agent names
            task: Optional task ID
        """
        self.current_view = view
        if experiment is not None:
            self.current_experiment = experiment
        if agents is not None and len(agents) > 0:
            self.current_agent = agents[0]  # Store first agent
        if task is not None:
            self.current_task = task

    def get_breadcrumb_items(self) -> List[Dict[str, Any]]:
        """Get breadcrumb items for current location.
        
        Returns:
            List of breadcrumb items with label and context.
        """
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize navigation context to dictionary."""
        return {
            "current_view": self.current_view,
            "current_experiment": self.current_experiment,
            "current_task": self.current_task,
            "current_agent": self.current_agent,
            "history_depth": len(self.history),
        }
