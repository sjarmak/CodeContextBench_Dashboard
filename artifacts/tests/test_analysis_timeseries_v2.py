"""Tests for refactored TimeSeriesAnalysisView (Phase 6.4)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dashboard.views.analysis_timeseries_v2 import TimeSeriesAnalysisView
from dashboard.utils.filters import FilterConfig


def setup_streamlit_mocks(mock_st):
    """Helper: Configure streamlit mocks for columns and context."""
    def columns_side_effect(n):
        return [MagicMock() for _ in range(n)]
    mock_st.columns.side_effect = columns_side_effect


class TestTimeSeriesAnalysisViewBasics:
    """Test TimeSeriesAnalysisView initialization and properties."""
    
    def test_init(self):
        """TimeSeriesAnalysisView initializes correctly."""
        view = TimeSeriesAnalysisView()
        assert view.view_name == "Time-Series Analysis"
        assert view.view_type == "timeseries"
        assert view.experiment_ids == []
        assert view.selected_agents == []
        assert view.selected_metrics == []
    
    def test_title(self):
        """TimeSeriesAnalysisView returns correct title."""
        view = TimeSeriesAnalysisView()
        assert view.title == "Time-Series Analysis"
    
    def test_subtitle(self):
        """TimeSeriesAnalysisView returns correct subtitle."""
        view = TimeSeriesAnalysisView()
        assert "metric" in view.subtitle.lower() or "experiment" in view.subtitle.lower()


class TestTimeSeriesAnalysisViewLoadAnalysis:
    """Test analysis loading."""
    
    def test_load_analysis(self):
        """load_analysis calls loader with correct parameters."""
        view = TimeSeriesAnalysisView()
        view.loader = Mock()
        view.experiment_ids = ["exp001", "exp002"]
        view.selected_agents = ["agent1"]
        
        expected_result = {"trends": {}}
        view.loader.load_timeseries.return_value = expected_result
        
        result = view.load_analysis()
        
        view.loader.load_timeseries.assert_called_once_with(
            experiment_ids=["exp001", "exp002"],
            agent_names=["agent1"]
        )
        assert result == expected_result
    
    def test_load_analysis_with_no_agent_filter(self):
        """load_analysis handles no agent filter (None)."""
        view = TimeSeriesAnalysisView()
        view.loader = Mock()
        view.experiment_ids = ["exp001", "exp002"]
        view.selected_agents = []
        
        expected_result = {"trends": {}}
        view.loader.load_timeseries.return_value = expected_result
        
        result = view.load_analysis()
        
        view.loader.load_timeseries.assert_called_once_with(
            experiment_ids=["exp001", "exp002"],
            agent_names=None
        )


class TestTimeSeriesAnalysisViewExtractMetrics:
    """Test metric extraction."""
    
    def test_extract_metrics(self):
        """extract_metrics converts result to filterable dict."""
        view = TimeSeriesAnalysisView()
        
        result = Mock()
        result.trends = {}
        result.agent_trends = {}
        result.anomalies = []
        result.best_improving = {}
        result.worst_improving = {}
        
        with patch('dashboard.views.analysis_timeseries_v2.extract_timeseries_metrics') as mock_extract:
            expected = {
                "trends": {},
                "agent_trends": {},
                "anomalies": []
            }
            mock_extract.return_value = expected
            
            extracted = view.extract_metrics(result)
            
            assert extracted == expected


class TestTimeSeriesAnalysisViewRenderContent:
    """Test main content rendering."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_main_content_with_data(self, mock_st):
        """render_main_content displays time-series analysis."""
        view = TimeSeriesAnalysisView()
        view.experiment_ids = ["exp001", "exp002", "exp003"]
        view.selected_agents = ["agent1", "agent2"]
        view.selected_metrics = ["pass_rate", "duration"]
        view.all_agents = ["agent1", "agent2"]
        setup_streamlit_mocks(mock_st)
        
        data = {
            "trends": {
                "pass_rate": {
                    "direction": "IMPROVING",
                    "percent_change": 5.0,
                    "slope": 0.05,
                    "confidence": 0.85
                }
            },
            "agent_trends": {
                "agent1": {
                    "pass_rate": {
                        "start_value": 0.80,
                        "end_value": 0.85,
                        "change_percent": 5.0
                    }
                }
            },
            "anomalies": [],
            "best_improving": {"pass_rate": 5.0},
            "worst_improving": {"duration": -3.0}
        }
        
        # Should not raise
        view.render_main_content(data)
        
        # Verify key sections are rendered
        assert mock_st.subheader.call_count > 0


class TestTimeSeriesAnalysisViewTrendAnalysis:
    """Test trend analysis functionality."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_improving_metrics(self, mock_st):
        """render_main_content identifies improving metrics."""
        view = TimeSeriesAnalysisView()
        view.experiment_ids = ["exp001", "exp002"]
        view.selected_agents = []
        view.selected_metrics = ["pass_rate"]
        view.all_agents = []
        setup_streamlit_mocks(mock_st)
        
        data = {
            "trends": {
                "pass_rate": {"direction": "IMPROVING", "percent_change": 10.0, "slope": 0.1, "confidence": 0.95}
            },
            "agent_trends": {},
            "anomalies": [],
            "best_improving": {"pass_rate": 10.0},
            "worst_improving": {}
        }
        
        view.render_main_content(data)
        
        # Verify improving metrics detected
        assert mock_st.dataframe.called


class TestTimeSeriesAnalysisViewAnomalies:
    """Test anomaly detection."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_anomalies(self, mock_st):
        """render_main_content displays detected anomalies."""
        view = TimeSeriesAnalysisView()
        view.experiment_ids = ["exp001", "exp002", "exp003"]
        view.selected_agents = []
        view.selected_metrics = ["pass_rate"]
        view.all_agents = []
        setup_streamlit_mocks(mock_st)
        
        data = {
            "trends": {},
            "agent_trends": {},
            "anomalies": [
                {
                    "experiment_id": "exp002",
                    "agent_name": "agent1",
                    "metric": "pass_rate",
                    "severity": "high",
                    "description": "Sudden drop in pass rate"
                }
            ],
            "best_improving": {},
            "worst_improving": {}
        }
        
        # Should not raise an exception
        view.render_main_content(data)


class TestTimeSeriesAnalysisViewRenderSidebarConfig:
    """Test sidebar configuration override for multiple experiments."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_sidebar_with_multiple_experiments(self, mock_st):
        """render_sidebar_config handles multiple experiment selection."""
        view = TimeSeriesAnalysisView()
        view.loader = Mock()
        
        # Mock experiments and agents
        view.loader.list_experiments.return_value = ["exp001", "exp002", "exp003"]
        view.loader.list_agents.side_effect = lambda exp_id: ["agent1", "agent2"]
        
        # Mock sidebar inputs
        mock_st.multiselect.side_effect = [
            ["exp001", "exp002"],  # Selected experiments
            ["agent1", "agent2"],   # Selected agents
            ["pass_rate", "duration"]  # Selected metrics
        ]
        
        result = view.render_sidebar_config()
        
        assert result is True
        assert view.experiment_ids == ["exp001", "exp002"]
        assert view.selected_agents == ["agent1", "agent2"]
        assert view.selected_metrics == ["pass_rate", "duration"]
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_sidebar_insufficient_experiments(self, mock_st):
        """render_sidebar_config validates minimum experiment count."""
        view = TimeSeriesAnalysisView()
        view.loader = Mock()
        
        view.loader.list_experiments.return_value = ["exp001", "exp002"]
        
        # Select only 1 experiment (need at least 2)
        mock_st.multiselect.return_value = ["exp001"]
        
        result = view.render_sidebar_config()
        
        assert result is False


class TestTimeSeriesAnalysisViewErrorHandling:
    """Test error handling."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_render_with_missing_data(self, mock_st):
        """render_main_content handles missing time-series data."""
        view = TimeSeriesAnalysisView()
        view.experiment_ids = ["exp001", "exp002"]
        view.selected_agents = []
        view.selected_metrics = []
        view.all_agents = []
        setup_streamlit_mocks(mock_st)
        
        data = {
            "trends": {},
            "agent_trends": {},
            "anomalies": [],
            "best_improving": {},
            "worst_improving": {}
        }
        
        # Should not raise
        view.render_main_content(data)


class TestTimeSeriesAnalysisViewIntegration:
    """Integration tests."""
    
    @patch('dashboard.views.analysis_timeseries_v2.st')
    def test_full_view_workflow(self, mock_st):
        """Test complete view workflow."""
        view = TimeSeriesAnalysisView()
        view.loader = Mock()
        
        # Mock session state
        mock_session = MagicMock()
        mock_st.session_state = mock_session
        mock_st.session_state.get.return_value = view.loader
        
        # Mock methods
        view.loader.list_experiments.return_value = ["exp001", "exp002"]
        view.loader.list_agents.return_value = ["agent1"]
        view.loader.load_timeseries.return_value = {"trends": {}}
        
        # Mock sidebar inputs
        mock_st.multiselect.side_effect = [
            ["exp001", "exp002"],
            ["agent1"],
            ["pass_rate"]
        ]
        
        # Configure sidebar
        result = view.render_sidebar_config()
        
        if result:
            # Load analysis
            view.load_analysis()
            assert view.loader.load_timeseries.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
