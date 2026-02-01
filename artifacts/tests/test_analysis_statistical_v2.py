"""Tests for refactored StatisticalAnalysisView (Phase 6.4)."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dashboard.views.analysis_statistical_v2 import StatisticalAnalysisView
from dashboard.utils.filters import FilterConfig


def setup_streamlit_mocks(mock_st):
    """Helper: Configure streamlit mocks for columns and context."""
    def columns_side_effect(n):
        return [MagicMock() for _ in range(n)]
    mock_st.columns.side_effect = columns_side_effect


class TestStatisticalAnalysisViewBasics:
    """Test StatisticalAnalysisView initialization and properties."""
    
    def test_init(self):
        """StatisticalAnalysisView initializes correctly."""
        view = StatisticalAnalysisView()
        assert view.view_name == "Statistical Analysis"
        assert view.view_type == "statistical"
        assert view.baseline_agent is None
        assert view.confidence_level == 0.95
    
    def test_title(self):
        """StatisticalAnalysisView returns correct title."""
        view = StatisticalAnalysisView()
        assert view.title == "Statistical Analysis"
    
    def test_subtitle(self):
        """StatisticalAnalysisView returns correct subtitle."""
        view = StatisticalAnalysisView()
        assert "significance" in view.subtitle.lower()


class TestStatisticalAnalysisViewConfigureSidebar:
    """Test sidebar configuration."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_configure_sidebar_with_agents(self, mock_st):
        """configure_sidebar sets up baseline agent and confidence level."""
        view = StatisticalAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.loader.list_agents.return_value = ["baseline", "strategic"]
        
        # Mock selectbox and slider
        mock_st.selectbox.return_value = "baseline"
        
        # Mock confidence_level_slider
        with patch('dashboard.views.analysis_statistical_v2.confidence_level_slider') as mock_slider:
            mock_slider.return_value = 0.95
            
            view.configure_sidebar()
            
            assert view.baseline_agent == "baseline"
            assert view.confidence_level == 0.95


class TestStatisticalAnalysisViewLoadAnalysis:
    """Test analysis loading."""
    
    def test_load_analysis(self):
        """load_analysis calls loader with correct parameters."""
        view = StatisticalAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        view.baseline_agent = "baseline"
        view.confidence_level = 0.95
        
        expected_result = {"test_results": {}, "effect_sizes": {}}
        view.loader.load_statistical.return_value = expected_result
        
        result = view.load_analysis()
        
        view.loader.load_statistical.assert_called_once_with(
            experiment_id="exp001",
            baseline_agent="baseline",
            confidence_level=0.95
        )
        assert result == expected_result


class TestStatisticalAnalysisViewExtractMetrics:
    """Test metric extraction."""
    
    def test_extract_metrics(self):
        """extract_metrics converts result to filterable dict."""
        view = StatisticalAnalysisView()
        
        result = Mock()
        result.test_results = {}
        result.effect_sizes = {}
        result.power_analysis = {}
        
        with patch('dashboard.views.analysis_statistical_v2.extract_statistical_metrics') as mock_extract:
            expected = {
                "test_results": {},
                "effect_sizes": {},
                "power_analysis": {}
            }
            mock_extract.return_value = expected
            
            extracted = view.extract_metrics(result)
            
            assert extracted == expected


class TestStatisticalAnalysisViewRenderContent:
    """Test main content rendering."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_render_main_content_with_data(self, mock_st):
        """render_main_content displays statistical analysis."""
        view = StatisticalAnalysisView()
        view.baseline_agent = "baseline"
        view.confidence_level = 0.95
        view.loader = Mock()
        view.loader.list_agents.return_value = ["baseline", "strategic"]
        setup_streamlit_mocks(mock_st)
        
        data = {
            "test_results": {
                "pass_rate": {
                    "baseline__strategic": {
                        "p_value": 0.05,
                        "test_type": "t-test",
                        "statistic": 1.96
                    }
                }
            },
            "effect_sizes": {
                "pass_rate": {
                    "baseline__strategic": {
                        "value": 0.5,
                        "name": "Cohen's d",
                        "magnitude": "medium"
                    }
                }
            },
            "power_analysis": {
                "pass_rate": {
                    "sample_size": 100,
                    "power": 0.85,
                    "min_effect": 0.2
                }
            }
        }
        
        # Should not raise
        view.render_main_content(data)
        
        # Verify key sections are rendered
        assert mock_st.subheader.call_count > 0


class TestStatisticalAnalysisViewSignificance:
    """Test significance calculation."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_render_significant_results(self, mock_st):
        """render_main_content identifies significant results."""
        view = StatisticalAnalysisView()
        view.baseline_agent = "baseline"
        view.confidence_level = 0.95
        view.loader = Mock()
        view.loader.list_agents.return_value = ["baseline"]
        setup_streamlit_mocks(mock_st)
        
        # Significant p-value (0.01 < 0.05)
        data = {
            "test_results": {
                "metric1": {
                    "baseline__strategic": {"p_value": 0.01, "test_type": "t-test", "statistic": 2.5}
                }
            },
            "effect_sizes": {},
            "power_analysis": {}
        }
        
        view.render_main_content(data)
        
        # Verify significance detected
        assert mock_st.dataframe.called


class TestStatisticalAnalysisViewEffectSizes:
    """Test effect size visualization."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_render_effect_sizes(self, mock_st):
        """render_main_content displays effect sizes."""
        view = StatisticalAnalysisView()
        view.baseline_agent = "baseline"
        view.confidence_level = 0.95
        view.loader = Mock()
        view.loader.list_agents.return_value = ["baseline"]
        setup_streamlit_mocks(mock_st)
        
        data = {
            "test_results": {},
            "effect_sizes": {
                "metric1": {
                    "baseline__strategic": {
                        "value": 0.8,
                        "name": "Cohen's d",
                        "magnitude": "large"
                    }
                }
            },
            "power_analysis": {}
        }
        
        # Should not raise an exception
        view.render_main_content(data)


class TestStatisticalAnalysisViewErrorHandling:
    """Test error handling."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_render_with_missing_data(self, mock_st):
        """render_main_content handles missing statistical data."""
        view = StatisticalAnalysisView()
        view.baseline_agent = "baseline"
        view.confidence_level = 0.95
        view.loader = Mock()
        view.loader.list_agents.return_value = ["baseline"]
        setup_streamlit_mocks(mock_st)
        
        data = {
            "test_results": {},
            "effect_sizes": {},
            "power_analysis": {}
        }
        
        # Should not raise
        view.render_main_content(data)


class TestStatisticalAnalysisViewIntegration:
    """Integration tests."""
    
    @patch('dashboard.views.analysis_statistical_v2.st')
    def test_full_view_workflow(self, mock_st):
        """Test complete view workflow."""
        view = StatisticalAnalysisView()
        view.loader = Mock()
        view.experiment_id = "exp001"
        
        # Mock session state
        mock_session = MagicMock()
        mock_st.session_state = mock_session
        mock_st.session_state.get.return_value = view.loader
        
        # Mock methods
        view.loader.list_agents.return_value = ["baseline", "strategic"]
        view.loader.load_statistical.return_value = {"test_results": {}}
        
        mock_st.selectbox.return_value = "baseline"
        
        with patch('dashboard.views.analysis_statistical_v2.confidence_level_slider') as mock_slider:
            mock_slider.return_value = 0.95
            
            view.load_analysis()
            assert view.loader.load_statistical.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
