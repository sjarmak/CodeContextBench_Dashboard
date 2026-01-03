"""Tests for refactored FailureAnalysisView (Phase 6.4)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from dashboard.views.analysis_failure_v2 import FailureAnalysisView
from dashboard.utils.filters import FilterConfig


def setup_streamlit_mocks(mock_st):
    """Helper: Configure streamlit mocks for columns and context."""
    def columns_side_effect(n):
        return [MagicMock() for _ in range(n)]
    mock_st.columns.side_effect = columns_side_effect


class TestFailureAnalysisViewBasics:
    """Test FailureAnalysisView initialization and properties."""
    
    def test_init(self):
        """FailureAnalysisView initializes correctly."""
        view = FailureAnalysisView()
        assert view.view_name == "Failure Analysis"
        assert view.view_type == "failure"
        assert view.selected_agent is None
    
    def test_title(self):
        """FailureAnalysisView returns correct title."""
        view = FailureAnalysisView()
        assert view.title == "Failure Analysis"
    
    def test_subtitle(self):
        """FailureAnalysisView returns correct subtitle."""
        view = FailureAnalysisView()
        assert "failure modes" in view.subtitle.lower()


class TestFailureAnalysisViewConfigureSidebar:
    """Test sidebar configuration."""
    
    @patch('dashboard.views.analysis_failure_v2.st')
    def test_configure_sidebar_with_agents(self, mock_st):
        """configure_sidebar sets up agent selection."""
        view = FailureAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.loader.list_agents.return_value = ["agent1", "agent2"]
        
        # Mock selectbox
        mock_st.selectbox.return_value = "agent1"
        
        view.configure_sidebar()
        
        assert view.selected_agent == "agent1"
    
    @patch('dashboard.views.analysis_failure_v2.st')
    def test_configure_sidebar_all_agents(self, mock_st):
        """configure_sidebar handles 'All Agents' selection."""
        view = FailureAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.loader.list_agents.return_value = ["agent1", "agent2"]
        
        mock_st.selectbox.return_value = "All Agents"
        
        view.configure_sidebar()
        
        assert view.selected_agent is None


class TestFailureAnalysisViewLoadAnalysis:
    """Test analysis loading."""
    
    def test_load_analysis(self):
        """load_analysis calls loader with correct parameters."""
        view = FailureAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.selected_agent = "agent1"
        
        expected_result = {"total_failures": 5, "total_tasks": 100}
        view.loader.load_failures.return_value = expected_result
        
        result = view.load_analysis()
        
        view.loader.load_failures.assert_called_once_with(
            experiment_id="exp001",
            agent_name="agent1"
        )
        assert result == expected_result


class TestFailureAnalysisViewExtractMetrics:
    """Test metric extraction."""
    
    def test_extract_metrics(self):
        """extract_metrics converts result to filterable dict."""
        view = FailureAnalysisView()
        
        result = Mock()
        result.total_failures = 5
        result.total_tasks = 100
        result.failure_patterns = {"timeout": 3, "error": 2}
        result.failure_categories = {"architecture": {"count": 3}}
        result.difficulty_correlation = {}
        result.suggested_fixes = []
        result.agent_failure_rates = {}
        result.high_risk_tasks = []
        
        with patch('dashboard.views.analysis_failure_v2.extract_failure_metrics') as mock_extract:
            expected = {
                "total_failures": 5,
                "total_tasks": 100,
                "failure_patterns": {"timeout": 3, "error": 2}
            }
            mock_extract.return_value = expected
            
            extracted = view.extract_metrics(result)
            
            assert extracted == expected


class TestFailureAnalysisViewRenderContent:
    """Test main content rendering."""
    
    @patch('dashboard.views.analysis_failure_v2.st')
    def test_render_main_content_with_data(self, mock_st):
        """render_main_content displays failure analysis."""
        view = FailureAnalysisView()
        setup_streamlit_mocks(mock_st)
        
        data = {
            "total_failures": 15,
            "total_tasks": 100,
            "failure_rate": 0.15,
            "failure_categories": {
                "timeout": {"count": 10, "examples": "task1, task2"},
                "error": {"count": 5, "examples": "task3"}
            },
            "failure_patterns": {"timeout": 10, "error": 5},
            "difficulty_correlation": {
                "hard": {"total_tasks": 30, "failures": 12, "failure_rate": 0.4}
            },
            "suggested_fixes": [
                {"priority": "high", "category": "timeout", "issue": "Slow queries", "fix": "Add caching", "estimated_impact": 0.3}
            ],
            "agent_failure_rates": {
                "agent1": {"total_tasks": 50, "failures": 7, "failure_rate": 0.14}
            },
            "high_risk_tasks": [
                {"task_id": "task1", "failure_count": 5, "total_attempts": 5, "failure_rate": 1.0, "risk_level": "HIGH"}
            ]
        }
        
        # Should not raise
        view.render_main_content(data)
        
        # Verify key sections are rendered
        assert mock_st.subheader.call_count > 0


class TestFailureAnalysisViewIntegration:
    """Integration tests."""
    
    @patch('dashboard.views.analysis_failure_v2.st')
    def test_full_view_workflow(self, mock_st):
        """Test complete view workflow."""
        view = FailureAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        
        # Mock session state
        mock_session = MagicMock()
        mock_st.session_state = mock_session
        mock_st.session_state.get.return_value = view.loader
        
        # Mock methods
        view.loader.list_agents.return_value = ["agent1"]
        view.loader.load_failures.return_value = {
            "total_failures": 5,
            "total_tasks": 100
        }
        
        mock_st.selectbox.return_value = "All Agents"
        mock_st.multiselect.return_value = []
        
        # Should not raise
        view.load_analysis()
        assert view.loader.load_failures.called


class TestFailureAnalysisViewErrorHandling:
    """Test error handling."""
    
    @patch('dashboard.views.analysis_failure_v2.st')
    def test_render_with_missing_data(self, mock_st):
        """render_main_content handles missing data gracefully."""
        view = FailureAnalysisView()
        setup_streamlit_mocks(mock_st)
        
        data = {
            "total_failures": 0,
            "total_tasks": 0,
            "failure_patterns": {},
            "failure_categories": {},
            "difficulty_correlation": {},
            "suggested_fixes": [],
            "agent_failure_rates": {},
            "high_risk_tasks": []
        }
        
        # Should not raise
        view.render_main_content(data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
