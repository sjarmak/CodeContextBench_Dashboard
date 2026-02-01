"""
Advanced filtering system for dashboard views.

Provides:
- Multi-metric selection
- Date range filtering
- Task difficulty filtering
- Agent group comparisons
- Filter application to analysis results
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class TaskDifficulty(Enum):
    """Task difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class MetricCategory(Enum):
    """Metric categories across different views"""
    PERFORMANCE = "performance"
    COST = "cost"
    STATISTICAL = "statistical"
    TIME_SERIES = "time_series"


@dataclass
class FilterConfig:
    """
    Configuration object for filtering analysis results.
    
    Stores all active filters and provides methods to apply them
    to analysis data.
    """
    
    # Basic filters
    metrics: List[str] = field(default_factory=list)
    difficulty_levels: List[TaskDifficulty] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    
    # Date range filtering
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    
    # Aggregation controls
    aggregate_by_group: bool = False
    group_name: Optional[str] = None
    group_operation: str = "average"  # average, sum, median, min, max
    
    def __post_init__(self):
        """Validate filter configuration"""
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError("date_from must be before date_to")
        
        if self.group_operation not in ["average", "sum", "median", "min", "max"]:
            raise ValueError(f"Invalid group_operation: {self.group_operation}")
    
    def has_filters(self) -> bool:
        """Check if any filters are active"""
        return bool(
            self.metrics or
            self.difficulty_levels or
            self.agents or
            self.date_from or
            self.date_to
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Export filter config as dictionary"""
        return {
            "metrics": self.metrics,
            "difficulty_levels": [d.value for d in self.difficulty_levels],
            "agents": self.agents,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "aggregate_by_group": self.aggregate_by_group,
            "group_name": self.group_name,
            "group_operation": self.group_operation,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterConfig":
        """Create filter config from dictionary"""
        return cls(
            metrics=data.get("metrics", []),
            difficulty_levels=[
                TaskDifficulty(d) for d in data.get("difficulty_levels", [])
            ],
            agents=data.get("agents", []),
            date_from=datetime.fromisoformat(data["date_from"]).date() if data.get("date_from") else None,
            date_to=datetime.fromisoformat(data["date_to"]).date() if data.get("date_to") else None,
            aggregate_by_group=data.get("aggregate_by_group", False),
            group_name=data.get("group_name"),
            group_operation=data.get("group_operation", "average"),
        )


class MetricFilter:
    """Filters results by selected metrics"""
    
    @staticmethod
    def filter_metrics(data: Dict[str, Any], selected_metrics: List[str]) -> Dict[str, Any]:
        """
        Filter data to include only selected metrics.
        
        Recursively filters nested structures and keeps structural keys
        (like 'agent_results', 'trends') while filtering their contents.
        
        Args:
            data: Analysis result data
            selected_metrics: List of metric names to include
            
        Returns:
            Filtered data with only selected metrics
        """
        if not selected_metrics:
            return data
        
        # Keep structural keys that contain metrics
        structural_keys = {'agent_results', 'agent_deltas', 'failure_patterns', 
                          'failure_categories', 'difficulty_correlation', 'trends',
                          'agent_trends', 'effect_sizes', 'test_results'}
        
        return MetricFilter._filter_recursive(data, selected_metrics, structural_keys)
    
    @staticmethod
    def _filter_recursive(obj: Any, selected_metrics: List[str], structural_keys: set) -> Any:
        """Recursively filter object to include only selected metrics."""
        if isinstance(obj, dict):
            filtered = {}
            for key, value in obj.items():
                # Keep structural keys (they organize metrics)
                if key in structural_keys:
                    filtered[key] = MetricFilter._filter_recursive(value, selected_metrics, structural_keys)
                # Keep selected metrics
                elif key in selected_metrics:
                    filtered[key] = value
                # Keep non-metric metadata (id, name, etc.)
                elif key in {'experiment_id', 'agent_name', 'baseline_agent', 'total_tasks', 'total_failures'}:
                    filtered[key] = value
            return filtered
        
        elif isinstance(obj, list):
            # Recursively filter list items
            return [MetricFilter._filter_recursive(item, selected_metrics, structural_keys) for item in obj]
        
        return obj


class DifficultyFilter:
    """Filters tasks by difficulty level"""
    
    @staticmethod
    def filter_by_difficulty(
        data: Dict[str, Any],
        difficulty_levels: List[TaskDifficulty]
    ) -> Dict[str, Any]:
        """
        Filter data by task difficulty.
        
        Recursively filters nested structures containing difficulty information.
        
        Args:
            data: Analysis result data
            difficulty_levels: List of difficulty levels to include
            
        Returns:
            Filtered data with only selected difficulties
        """
        if not difficulty_levels or not data:
            return data
        
        difficulty_values = [d.value for d in difficulty_levels]
        
        # Recursively filter data for difficulty-related structures
        return DifficultyFilter._filter_recursive(data, difficulty_values)
    
    @staticmethod
    def _filter_recursive(obj: Any, difficulty_values: List[str]) -> Any:
        """Recursively filter object by difficulty levels."""
        if isinstance(obj, dict):
            filtered = {}
            for key, value in obj.items():
                # Special handling for difficulty_correlation structure
                if key == "difficulty_correlation" and isinstance(value, dict):
                    filtered_correlation = {
                        k: v for k, v in value.items()
                        if k in difficulty_values
                    }
                    if filtered_correlation:  # Only include if non-empty
                        filtered[key] = filtered_correlation
                else:
                    # Recursively process nested structures
                    filtered[key] = DifficultyFilter._filter_recursive(value, difficulty_values)
            return filtered
        
        elif isinstance(obj, list):
            # Recursively filter list items
            return [DifficultyFilter._filter_recursive(item, difficulty_values) for item in obj]
        
        return obj


class DateRangeFilter:
    """Filters experiments by date range"""
    
    @staticmethod
    def filter_by_date_range(
        data: Dict[str, Any],
        date_from: Optional[date],
        date_to: Optional[date]
    ) -> Dict[str, Any]:
        """
        Filter data by date range.
        
        Args:
            data: Analysis result data
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            
        Returns:
            Filtered data within date range
        """
        if not date_from and not date_to:
            return data
        
        # Recursively filter data structure by timestamp fields
        return DateRangeFilter._filter_recursive(data, date_from, date_to)
    
    @staticmethod
    def _filter_recursive(obj: Any, date_from: Optional[date], date_to: Optional[date]) -> Any:
        """Recursively filter object by date range."""
        if isinstance(obj, dict):
            filtered = {}
            for key, value in obj.items():
                # Check if this looks like a date/timestamp field
                if key.lower() in ['date', 'timestamp', 'created_at', 'updated_at', 'run_date']:
                    # Skip timestamp fields in the output (they're for filtering, not display)
                    continue
                
                # Recursively filter nested structures
                filtered[key] = DateRangeFilter._filter_recursive(value, date_from, date_to)
            return filtered
        
        elif isinstance(obj, list):
            # Filter list items that have timestamp fields
            filtered_list = []
            for item in obj:
                if isinstance(item, dict) and DateRangeFilter._in_date_range(item, date_from, date_to):
                    filtered_list.append(DateRangeFilter._filter_recursive(item, date_from, date_to))
            return filtered_list if filtered_list else obj  # Return original if filtering yields empty
        
        return obj
    
    @staticmethod
    def _in_date_range(obj: Dict[str, Any], date_from: Optional[date], date_to: Optional[date]) -> bool:
        """Check if object's date fields fall within range."""
        # Look for timestamp fields
        for key in ['date', 'timestamp', 'created_at', 'updated_at', 'run_date']:
            if key in obj:
                try:
                    from datetime import datetime
                    # Try to parse the date
                    date_val = obj[key]
                    if isinstance(date_val, str):
                        date_val = datetime.fromisoformat(date_val).date()
                    elif isinstance(date_val, datetime):
                        date_val = date_val.date()
                    
                    if date_from and date_val < date_from:
                        return False
                    if date_to and date_val > date_to:
                        return False
                except (ValueError, TypeError):
                    continue
        
        # If no date fields found, include the item
        return True


class AgentFilter:
    """Filters results by selected agents"""
    
    @staticmethod
    def filter_agents(
        data: Dict[str, Any],
        selected_agents: List[str]
    ) -> Dict[str, Any]:
        """
        Filter data to include only selected agents.
        
        Args:
            data: Analysis result data
            selected_agents: List of agent names to include
            
        Returns:
            Filtered data with only selected agents
        """
        if not selected_agents:
            return data
        
        if "agent_results" in data:
            filtered_results = {
                agent: result
                for agent, result in data["agent_results"].items()
                if agent in selected_agents
            }
            filtered = data.copy()
            filtered["agent_results"] = filtered_results
            return filtered
        
        if "agent_costs" in data:
            filtered_costs = {
                agent: cost
                for agent, cost in data["agent_costs"].items()
                if agent in selected_agents
            }
            filtered = data.copy()
            filtered["agent_costs"] = filtered_costs
            return filtered
        
        return data


class FilterEngine:
    """
    Main filter engine that applies filters in sequence.
    
    Coordinates all filter types and applies them to analysis results.
    """
    
    def apply_filters(
        self,
        data: Dict[str, Any],
        config: FilterConfig
    ) -> Dict[str, Any]:
        """
        Apply all active filters to data.
        
        Filters are applied in order:
        1. Metrics
        2. Difficulty
        3. Date range
        4. Agents
        
        Args:
            data: Analysis result data
            config: Filter configuration
            
        Returns:
            Filtered data
        """
        result = data.copy() if isinstance(data, dict) else data
        
        if config.metrics:
            result = MetricFilter.filter_metrics(result, config.metrics)
        
        if config.difficulty_levels:
            result = DifficultyFilter.filter_by_difficulty(result, config.difficulty_levels)
        
        if config.date_from or config.date_to:
            result = DateRangeFilter.filter_by_date_range(
                result,
                config.date_from,
                config.date_to
            )
        
        if config.agents:
            result = AgentFilter.filter_agents(result, config.agents)
        
        return result
    
    def get_filter_summary(self, config: FilterConfig) -> str:
        """
        Get human-readable summary of active filters.
        
        Args:
            config: Filter configuration
            
        Returns:
            Summary string
        """
        parts = []
        
        if config.metrics:
            parts.append(f"Metrics: {', '.join(config.metrics)}")
        
        if config.difficulty_levels:
            difficulties = [d.value for d in config.difficulty_levels]
            parts.append(f"Difficulties: {', '.join(difficulties)}")
        
        if config.date_from and config.date_to:
            parts.append(f"Dates: {config.date_from} to {config.date_to}")
        elif config.date_from:
            parts.append(f"From: {config.date_from}")
        elif config.date_to:
            parts.append(f"Until: {config.date_to}")
        
        if config.agents:
            parts.append(f"Agents: {', '.join(config.agents)}")
        
        if not parts:
            return "No filters active"
        
        return " | ".join(parts)


# Metric definitions by view
METRICS_BY_VIEW = {
    "comparison": [
        "pass_rate",
        "duration",
        "mcp_calls",
        "local_calls",
        "cost",
        "cost_per_success"
    ],
    "statistical": [
        "p_value",
        "effect_size",
        "test_statistic",
        "power",
        "confidence_level"
    ],
    "timeseries": [
        "pass_rate",
        "duration",
        "mcp_calls",
        "cost_per_success"
    ],
    "cost": [
        "total_cost",
        "input_tokens",
        "output_tokens",
        "cost_per_success",
        "efficiency_score"
    ],
    "failure": [
        "failure_rate",
        "failure_count",
        "patterns",
        "categories",
        "difficulty_correlation"
    ]
}


def get_available_metrics(view_type: str) -> List[str]:
    """
    Get available metrics for a specific view.
    
    Args:
        view_type: Type of view (comparison, statistical, etc.)
        
    Returns:
        List of available metric names
    """
    return METRICS_BY_VIEW.get(view_type, [])
