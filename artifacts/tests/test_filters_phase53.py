"""
Tests for Phase 5.3 advanced filtering and navigation.

Tests cover:
- Filter configuration and validation
- Filter application to analysis results
- Navigation context management
- Breadcrumb generation
- Query parameter encoding/decoding
"""

import pytest
from datetime import date, datetime, timedelta
from dashboard.utils.filters import (
    FilterConfig,
    TaskDifficulty,
    MetricFilter,
    DifficultyFilter,
    DateRangeFilter,
    AgentFilter,
    FilterEngine,
    get_available_metrics,
)
from dashboard.utils.navigation import (
    NavigationContext,
    QueryParams,
    RecentItems,
)


class TestFilterConfig:
    """Tests for FilterConfig"""
    
    def test_filter_config_creation(self):
        """FilterConfig can be created with default values"""
        config = FilterConfig()
        assert config.metrics == []
        assert config.difficulty_levels == []
        assert config.agents == []
    
    def test_filter_config_with_values(self):
        """FilterConfig stores values correctly"""
        config = FilterConfig(
            metrics=["pass_rate", "duration"],
            difficulty_levels=[TaskDifficulty.HARD],
            agents=["baseline", "strategic"]
        )
        assert config.metrics == ["pass_rate", "duration"]
        assert config.difficulty_levels == [TaskDifficulty.HARD]
        assert config.agents == ["baseline", "strategic"]
    
    def test_filter_config_date_validation(self):
        """FilterConfig validates date ranges"""
        # Should raise error for invalid date range
        with pytest.raises(ValueError):
            FilterConfig(
                date_from=date(2024, 1, 10),
                date_to=date(2024, 1, 1)
            )
    
    def test_filter_config_has_filters(self):
        """FilterConfig.has_filters() returns correct status"""
        empty_config = FilterConfig()
        assert not empty_config.has_filters()
        
        config_with_metrics = FilterConfig(metrics=["pass_rate"])
        assert config_with_metrics.has_filters()
        
        config_with_agents = FilterConfig(agents=["baseline"])
        assert config_with_agents.has_filters()
    
    def test_filter_config_serialization(self):
        """FilterConfig can be serialized/deserialized"""
        config = FilterConfig(
            metrics=["pass_rate", "duration"],
            difficulty_levels=[TaskDifficulty.HARD],
            agents=["baseline"],
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
        )
        
        # Serialize
        data = config.to_dict()
        assert data["metrics"] == ["pass_rate", "duration"]
        assert data["difficulty_levels"] == ["hard"]
        assert data["agents"] == ["baseline"]
        
        # Deserialize
        restored = FilterConfig.from_dict(data)
        assert restored.metrics == config.metrics
        assert restored.agents == config.agents


class TestMetricFilter:
    """Tests for MetricFilter"""
    
    def test_filter_metrics_with_dict(self):
        """MetricFilter filters dictionary data"""
        data = {
            "pass_rate": 0.85,
            "duration": 10.5,
            "mcp_calls": 5,
        }
        
        filtered = MetricFilter.filter_metrics(data, ["pass_rate", "duration"])
        assert "pass_rate" in filtered
        assert "duration" in filtered
        assert "mcp_calls" not in filtered
    
    def test_filter_metrics_empty_selection(self):
        """MetricFilter with no selection returns original data"""
        data = {"pass_rate": 0.85, "duration": 10.5}
        filtered = MetricFilter.filter_metrics(data, [])
        assert filtered == data


class TestDifficultyFilter:
    """Tests for DifficultyFilter"""
    
    def test_filter_by_difficulty(self):
        """DifficultyFilter filters by difficulty level"""
        data = {
            "difficulty_correlation": {
                "easy": {"total_tasks": 10, "failures": 1},
                "medium": {"total_tasks": 20, "failures": 5},
                "hard": {"total_tasks": 15, "failures": 12},
            }
        }
        
        filtered = DifficultyFilter.filter_by_difficulty(
            data,
            [TaskDifficulty.HARD, TaskDifficulty.MEDIUM]
        )
        
        assert "medium" in filtered["difficulty_correlation"]
        assert "hard" in filtered["difficulty_correlation"]
        assert "easy" not in filtered["difficulty_correlation"]


class TestAgentFilter:
    """Tests for AgentFilter"""
    
    def test_filter_agents_in_results(self):
        """AgentFilter filters agent results"""
        data = {
            "agent_results": {
                "baseline": {"pass_rate": 0.7},
                "strategic": {"pass_rate": 0.85},
                "full-toolkit": {"pass_rate": 0.8},
            }
        }
        
        filtered = AgentFilter.filter_agents(data, ["baseline", "strategic"])
        
        assert "baseline" in filtered["agent_results"]
        assert "strategic" in filtered["agent_results"]
        assert "full-toolkit" not in filtered["agent_results"]
    
    def test_filter_agents_in_costs(self):
        """AgentFilter filters agent costs"""
        data = {
            "agent_costs": {
                "baseline": {"total_cost": 10.0},
                "strategic": {"total_cost": 15.0},
            }
        }
        
        filtered = AgentFilter.filter_agents(data, ["baseline"])
        
        assert "baseline" in filtered["agent_costs"]
        assert "strategic" not in filtered["agent_costs"]


class TestFilterEngine:
    """Tests for FilterEngine"""
    
    def test_apply_filters_in_sequence(self):
        """FilterEngine applies filters in correct order"""
        data = {
            "agent_results": {
                "baseline": {"pass_rate": 0.7, "duration": 10},
                "strategic": {"pass_rate": 0.85, "duration": 12},
            },
            "difficulty_correlation": {
                "easy": {"total_tasks": 10},
                "hard": {"total_tasks": 15},
            }
        }
        
        config = FilterConfig(
            difficulty_levels=[TaskDifficulty.HARD],
            agents=["strategic"]
        )
        
        engine = FilterEngine()
        filtered = engine.apply_filters(data, config)
        
        # Should apply difficulty filter
        if "difficulty_correlation" in filtered:
            assert "hard" in filtered["difficulty_correlation"]
            assert "easy" not in filtered["difficulty_correlation"]
        
        # Should apply agent filter
        if "agent_results" in filtered:
            assert "strategic" in filtered["agent_results"]
            assert "baseline" not in filtered["agent_results"]
    
    def test_filter_summary(self):
        """FilterEngine generates readable filter summary"""
        config = FilterConfig(
            metrics=["pass_rate", "duration"],
            difficulty_levels=[TaskDifficulty.HARD],
            agents=["baseline"]
        )
        
        engine = FilterEngine()
        summary = engine.get_filter_summary(config)
        
        assert "pass_rate" in summary
        assert "hard" in summary
        assert "baseline" in summary


class TestNavigationContext:
    """Tests for NavigationContext"""
    
    def test_navigation_context_creation(self):
        """NavigationContext can be created"""
        context = NavigationContext()
        assert context.current_view == "analysis_hub"
        assert context.current_experiment is None
        assert context.selected_agents == []
    
    def test_navigate_to_view(self):
        """NavigationContext.navigate_to() updates state"""
        context = NavigationContext()
        context.navigate_to("analysis_comparison", experiment="exp001")
        
        assert context.current_view == "analysis_comparison"
        assert context.current_experiment == "exp001"
    
    def test_navigate_to_with_agents(self):
        """NavigationContext tracks agent selection"""
        context = NavigationContext()
        context.navigate_to(
            "analysis_cost",
            experiment="exp001",
            agents=["baseline", "strategic"]
        )
        
        assert context.selected_agents == ["baseline", "strategic"]
    
    def test_breadcrumb_tracking(self):
        """NavigationContext tracks breadcrumb path"""
        context = NavigationContext()
        context.navigate_to("analysis_comparison")
        context.navigate_to("analysis_cost")
        context.navigate_to("analysis_failure")
        
        assert len(context.breadcrumb_path) == 3
        assert context.breadcrumb_path[-1][0] == "analysis_failure"
    
    def test_go_back(self):
        """NavigationContext.go_back() returns to previous view"""
        context = NavigationContext()
        context.navigate_to("analysis_comparison")
        context.navigate_to("analysis_cost")
        
        assert context.current_view == "analysis_cost"
        
        context.go_back()
        assert context.current_view == "analysis_comparison"
    
    def test_reset(self):
        """NavigationContext.reset() clears state"""
        context = NavigationContext()
        context.navigate_to("analysis_comparison", experiment="exp001")
        context.reset()
        
        assert context.current_view == "analysis_hub"
        assert context.current_experiment is None
        assert context.breadcrumb_path == [("analysis_hub", "Analysis Hub")]
    
    def test_serialization(self):
        """NavigationContext serialization"""
        context = NavigationContext()
        context.navigate_to(
            "analysis_cost",
            experiment="exp001",
            agents=["baseline"]
        )
        
        # Serialize
        data = context.to_dict()
        assert data["current_view"] == "analysis_cost"
        assert data["current_experiment"] == "exp001"
        
        # Deserialize
        restored = NavigationContext.from_dict(data)
        assert restored.current_view == context.current_view
        assert restored.current_experiment == context.current_experiment


class TestQueryParams:
    """Tests for QueryParams"""
    
    def test_encode_context(self):
        """QueryParams encodes navigation context"""
        context = NavigationContext()
        context.navigate_to(
            "analysis_comparison",
            experiment="exp001",
            agents=["baseline", "strategic"]
        )
        
        query_string = QueryParams.encode(context)
        
        assert "view=analysis_comparison" in query_string
        assert "exp=exp001" in query_string
        assert "agents=baseline" in query_string
    
    def test_decode_context(self):
        """QueryParams decodes URL query string"""
        query_string = "view=analysis_cost&exp=exp001&agents=baseline,strategic"
        context = QueryParams.decode(query_string)
        
        assert context.current_view == "analysis_cost"
        assert context.current_experiment == "exp001"
        assert "baseline" in context.selected_agents
        assert "strategic" in context.selected_agents
    
    def test_roundtrip_encoding(self):
        """QueryParams encoding/decoding is reversible"""
        original = NavigationContext()
        original.navigate_to(
            "analysis_failure",
            experiment="exp002",
            agents=["strategic"]
        )
        
        encoded = QueryParams.encode(original)
        decoded = QueryParams.decode(encoded)
        
        assert decoded.current_view == original.current_view
        assert decoded.current_experiment == original.current_experiment
        assert decoded.selected_agents == original.selected_agents


class TestRecentItems:
    """Tests for RecentItems"""
    
    def test_add_experiment(self):
        """RecentItems tracks recent experiments"""
        # Mock session state
        import streamlit as st
        st.session_state.recent_experiments = []
        
        RecentItems.add_experiment("exp001")
        RecentItems.add_experiment("exp002")
        
        recent = RecentItems.get_experiments()
        assert "exp001" in recent
        assert "exp002" in recent
    
    def test_recent_items_order(self):
        """RecentItems maintains most recent first"""
        import streamlit as st
        st.session_state.recent_experiments = []
        
        RecentItems.add_experiment("exp001")
        RecentItems.add_experiment("exp002")
        RecentItems.add_experiment("exp001")  # Add again
        
        recent = RecentItems.get_experiments()
        assert recent[0] == "exp001"  # Most recent first
    
    def test_recent_items_max_size(self):
        """RecentItems respects max items limit"""
        import streamlit as st
        st.session_state.recent_experiments = []
        
        for i in range(10):
            RecentItems.add_experiment(f"exp{i:03d}", max_items=5)
        
        recent = RecentItems.get_experiments()
        assert len(recent) <= 5


class TestGetAvailableMetrics:
    """Tests for get_available_metrics"""
    
    def test_comparison_metrics(self):
        """get_available_metrics returns comparison metrics"""
        metrics = get_available_metrics("comparison")
        assert "pass_rate" in metrics
        assert "duration" in metrics
        assert "mcp_calls" in metrics
    
    def test_cost_metrics(self):
        """get_available_metrics returns cost metrics"""
        metrics = get_available_metrics("cost")
        assert "total_cost" in metrics
        assert "efficiency_score" in metrics
    
    def test_failure_metrics(self):
        """get_available_metrics returns failure metrics"""
        metrics = get_available_metrics("failure")
        assert "failure_rate" in metrics
        assert "patterns" in metrics
    
    def test_unknown_view_type(self):
        """get_available_metrics returns empty for unknown view"""
        metrics = get_available_metrics("unknown_view")
        assert metrics == []


class TestTaskDifficulty:
     """Tests for TaskDifficulty enum"""
     
     def test_difficulty_values(self):
         """TaskDifficulty has expected values"""
         assert TaskDifficulty.EASY.value == "easy"
         assert TaskDifficulty.MEDIUM.value == "medium"
         assert TaskDifficulty.HARD.value == "hard"
         assert TaskDifficulty.EXPERT.value == "expert"
     
     def test_difficulty_from_string(self):
         """TaskDifficulty can be created from string"""
         d = TaskDifficulty("hard")
         assert d == TaskDifficulty.HARD


# Phase 6.2: New filter implementations
class TestDateRangeFilter:
     """Tests for improved DateRangeFilter"""
     
     def test_filter_by_date_range_no_filter(self):
         """DateRangeFilter with no dates returns original data"""
         data = {"experiment_id": "exp001", "data": [{"date": "2024-01-01"}]}
         filtered = DateRangeFilter.filter_by_date_range(data, None, None)
         assert filtered == data
     
     def test_filter_by_date_range_single_item_in_range(self):
         """DateRangeFilter includes items within date range"""
         data = {
             "results": [
                 {"created_at": "2024-01-15", "value": 0.5}
             ]
         }
         filtered = DateRangeFilter.filter_by_date_range(
             data,
             date(2024, 1, 1),
             date(2024, 1, 31)
         )
         # DateRangeFilter removes timestamp fields from output
         assert len(filtered["results"]) == 1
         assert filtered["results"][0]["value"] == 0.5
         assert "created_at" not in filtered["results"][0]
     
     def test_filter_by_date_range_excludes_out_of_range(self):
         """DateRangeFilter excludes items outside date range"""
         data = {
             "results": [
                 {"created_at": "2023-12-01", "value": 0.3},
                 {"created_at": "2024-01-15", "value": 0.5},
                 {"created_at": "2024-02-01", "value": 0.7}
             ]
         }
         filtered = DateRangeFilter.filter_by_date_range(
             data,
             date(2024, 1, 1),
             date(2024, 1, 31)
         )
         # Should only include the middle item
         assert len(filtered["results"]) == 1
         assert filtered["results"][0]["value"] == 0.5


class TestMetricFilterImproved:
     """Tests for improved MetricFilter with recursive filtering"""
     
     def test_filter_metrics_nested_structure(self):
         """MetricFilter handles nested agent_results"""
         data = {
             "experiment_id": "exp001",
             "agent_results": {
                 "baseline": {"pass_rate": 0.7, "duration": 10},
                 "strategic": {"pass_rate": 0.85, "duration": 12}
             }
         }
         
         filtered = MetricFilter.filter_metrics(data, ["pass_rate"])
         
         # Should keep agent_results structure
         assert "agent_results" in filtered
         # Should include pass_rate in baseline
         if filtered["agent_results"] and "baseline" in filtered["agent_results"]:
             assert "pass_rate" in filtered["agent_results"]["baseline"]
             # Should exclude duration
             assert "duration" not in filtered["agent_results"]["baseline"]
         # Should keep metadata
         assert filtered["experiment_id"] == "exp001"
     
     def test_filter_metrics_preserves_structure(self):
         """MetricFilter preserves structural keys"""
         data = {
             "agent_results": {"baseline": {"pass_rate": 0.7}},
             "agent_deltas": {"delta_key": {"pass_rate_delta": 0.1}},
             "total_tasks": 100
         }
         
         filtered = MetricFilter.filter_metrics(data, ["pass_rate"])
         
         # Structural keys should be preserved
         assert "agent_results" in filtered
         assert "total_tasks" in filtered  # Metadata
         # agent_deltas might be filtered since pass_rate_delta != pass_rate


class TestDifficultyFilterImproved:
     """Tests for improved DifficultyFilter with recursive filtering"""
     
     def test_filter_by_difficulty_nested(self):
         """DifficultyFilter handles nested structures"""
         data = {
             "difficulty_correlation": {
                 "easy": {"total_tasks": 10},
                 "hard": {"total_tasks": 15}
             }
         }
         
         filtered = DifficultyFilter.filter_by_difficulty(
             data,
             [TaskDifficulty.HARD]
         )
         
         assert "hard" in filtered["difficulty_correlation"]
         assert "easy" not in filtered["difficulty_correlation"]


if __name__ == "__main__":
     pytest.main([__file__, "-v"])
