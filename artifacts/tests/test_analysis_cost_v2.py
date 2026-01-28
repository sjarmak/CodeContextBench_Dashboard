"""Tests for refactored CostAnalysisView (Phase 6.4)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dashboard.views.analysis_cost_v2 import CostAnalysisView
from dashboard.utils.filters import FilterConfig


def setup_streamlit_mocks(mock_st):
    """Helper: Configure streamlit mocks for columns and context."""
    def columns_side_effect(n):
        return [MagicMock() for _ in range(n)]
    mock_st.columns.side_effect = columns_side_effect


class TestCostAnalysisViewBasics:
    """Test CostAnalysisView initialization and properties."""
    
    def test_init(self):
        """CostAnalysisView initializes correctly."""
        view = CostAnalysisView()
        assert view.view_name == "Cost Analysis"
        assert view.view_type == "cost"
        assert view.baseline_agent is None
        assert view.selected_metrics is None
    
    def test_title(self):
        """CostAnalysisView returns correct title."""
        view = CostAnalysisView()
        assert view.title == "Cost Analysis"
    
    def test_subtitle(self):
        """CostAnalysisView returns correct subtitle."""
        view = CostAnalysisView()
        assert "cost" in view.subtitle.lower()
        assert "efficiency" in view.subtitle.lower()


class TestCostAnalysisViewConfigureSidebar:
    """Test sidebar configuration."""
    
    @patch('dashboard.views.analysis_cost_v2.st')
    def test_configure_sidebar_with_agents(self, mock_st):
        """configure_sidebar sets up agent and metric selection."""
        view = CostAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.loader.list_agents.return_value = ["agent1", "agent2"]
        
        # Mock selectbox and multiselect
        mock_st.selectbox.return_value = "agent1"
        mock_st.multiselect.return_value = ["total_cost", "efficiency_score"]
        
        view.configure_sidebar()
        
        assert view.baseline_agent == "agent1"
        assert view.selected_metrics == ["total_cost", "efficiency_score"]


class TestCostAnalysisViewLoadAnalysis:
    """Test analysis loading."""
    
    def test_load_analysis(self):
        """load_analysis calls loader with correct parameters."""
        view = CostAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.baseline_agent = "agent1"
        
        expected_result = {"total_cost": 100.0, "agent_costs": {}}
        view.loader.load_cost.return_value = expected_result
        
        result = view.load_analysis()
        
        view.loader.load_cost.assert_called_once_with(
            experiment_id="exp001",
            baseline_agent="agent1"
        )
        assert result == expected_result


class TestCostAnalysisViewExtractMetrics:
    """Test metric extraction."""
    
    def test_extract_metrics(self):
        """extract_metrics converts result to filterable dict."""
        view = CostAnalysisView()
        
        result = Mock()
        result.total_cost = 100.0
        result.total_tokens = 50000
        result.agent_costs = {}
        result.cost_regressions = []
        result.model_breakdown = {}
        
        with patch('dashboard.views.analysis_cost_v2.extract_cost_metrics') as mock_extract:
            expected = {
                "total_cost": 100.0,
                "total_tokens": 50000,
                "agent_costs": {}
            }
            mock_extract.return_value = expected
            
            extracted = view.extract_metrics(result)
            
            assert extracted == expected


class TestCostAnalysisViewRenderContent:
    """Test main content rendering."""
    
    @patch('dashboard.views.analysis_cost_v2.st')
    def test_render_main_content_with_data(self, mock_st):
        """render_main_content displays cost analysis."""
        view = CostAnalysisView()
        setup_streamlit_mocks(mock_st)
        
        data = {
            "total_cost": 150.50,
            "total_tokens": 75000,
            "agent_costs": {
                "agent1": {
                    "total_cost": 75.25,
                    "input_tokens": 35000,
                    "output_tokens": 5000,
                    "cost_per_success": 0.75,
                    "efficiency_score": 4.5,
                    "success_count": 100
                },
                "agent2": {
                    "total_cost": 75.25,
                    "input_tokens": 40000,
                    "output_tokens": 6000,
                    "cost_per_success": 0.85,
                    "efficiency_score": 4.0,
                    "success_count": 88
                }
            },
            "cost_regressions": [],
            "model_breakdown": {
                "haiku": {"input_tokens": 50000, "output_tokens": 8000, "total_tokens": 58000, "cost": 100.0}
            }
        }
        
        # Should not raise
        view.render_main_content(data)
        
        # Verify key sections are rendered
        assert mock_st.subheader.call_count > 0


class TestCostAnalysisViewCostComparison:
    """Test cost comparison functionality."""
    
    @patch('dashboard.views.analysis_cost_v2.st')
    def test_render_agent_cost_rankings(self, mock_st):
        """render_main_content ranks agents by cost."""
        view = CostAnalysisView()
        setup_streamlit_mocks(mock_st)
        
        data = {
            "total_cost": 150.0,
            "total_tokens": 75000,
            "agent_costs": {
                "expensive": {"total_cost": 100.0, "input_tokens": 50000, "output_tokens": 5000, "cost_per_success": 1.0, "efficiency_score": 3.0},
                "cheap": {"total_cost": 50.0, "input_tokens": 25000, "output_tokens": 2000, "cost_per_success": 0.5, "efficiency_score": 5.0}
            },
            "cost_regressions": [],
            "model_breakdown": {}
        }
        
        # Should not raise an exception
        view.render_main_content(data)


class TestCostAnalysisViewErrorHandling:
    """Test error handling."""
    
    @patch('dashboard.views.analysis_cost_v2.st')
    def test_render_with_missing_costs(self, mock_st):
        """render_main_content handles missing cost data."""
        view = CostAnalysisView()
        setup_streamlit_mocks(mock_st)
        
        data = {
            "total_cost": 0,
            "total_tokens": 0,
            "agent_costs": {},
            "cost_regressions": [],
            "model_breakdown": {}
        }
        
        # Should not raise
        view.render_main_content(data)


class TestCostAnalysisViewIntegration:
    """Integration tests."""
    
    @patch('dashboard.views.analysis_cost_v2.st')
    def test_full_view_workflow(self, mock_st):
        """Test complete view workflow."""
        view = CostAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        
        # Mock session state
        mock_session = MagicMock()
        mock_st.session_state = mock_session
        mock_st.session_state.get.return_value = view.loader
        
        # Mock methods
        view.loader.list_agents.return_value = ["agent1", "agent2"]
        view.loader.load_cost.return_value = {"total_cost": 100.0}
        
        mock_st.selectbox.return_value = "agent1"
        mock_st.multiselect.return_value = ["total_cost"]
        
        # Should not raise
        view.load_analysis()
        assert view.loader.load_cost.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
