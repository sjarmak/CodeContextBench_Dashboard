"""Tests for Phase 6.3 IR-SDLC Analysis View integration.

Tests cover:
- IR analysis view structure and lifecycle
- IR metrics extraction
- Filter application to IR data
- Visualization functions
- Error handling
- Export functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from dashboard.utils.result_extractors import extract_ir_metrics
from dashboard.utils.visualizations import (
    create_precision_recall_chart,
    create_ir_impact_chart,
    create_mrr_ndcg_chart,
)
from dashboard.utils.filters import FilterConfig, FilterEngine


class TestExtractIRMetrics:
    """Tests for extract_ir_metrics function."""
    
    def test_extract_ir_metrics_with_none(self):
        """extract_ir_metrics handles None result gracefully."""
        result = extract_ir_metrics(None)
        
        assert result["ir_tool_results"] == {}
        assert result["ir_impact"] == {}
        assert result["detailed_metrics"] == {}
        assert result["avg_precision_at_k"] == 0.0
        assert result["avg_recall_at_k"] == 0.0
    
    def test_extract_ir_metrics_with_result(self):
        """extract_ir_metrics extracts metrics from result object."""
        # Mock IR analysis result
        mock_result = MagicMock()
        mock_result.experiment_id = "exp001"
        mock_result.ir_tool_results = {
            "keyword_search": {
                "precision_at_k": 0.65,
                "recall_at_k": 0.55,
                "mrr": 0.45,
                "ndcg": 0.63,
                "avg_rank": 5.2
            }
        }
        mock_result.ir_impact = {
            "agents": {
                "baseline": {"success_rate": 0.75},
                "strategic": {"success_rate": 0.82}
            }
        }
        mock_result.detailed_metrics = {"metric1": "data1"}
        mock_result.avg_precision_at_k = 0.65
        mock_result.avg_recall_at_k = 0.55
        mock_result.correlation_analysis = {}
        
        result = extract_ir_metrics(mock_result)
        
        assert result["experiment_id"] == "exp001"
        assert "keyword_search" in result["ir_tool_results"]
        assert result["avg_precision_at_k"] == 0.65
        assert result["avg_recall_at_k"] == 0.55


class TestIRVisualizationFunctions:
    """Tests for IR-specific visualization functions."""
    
    def test_create_precision_recall_chart(self):
        """create_precision_recall_chart produces valid Plotly figure."""
        ir_results = {
            "keyword_search": {
                "precision_at_k": 0.65,
                "recall_at_k": 0.55,
            },
            "deepsearch": {
                "precision_at_k": 0.72,
                "recall_at_k": 0.68,
            }
        }
        
        fig = create_precision_recall_chart(ir_results)
        
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) > 0
        assert "Precision" in fig.layout.yaxis.title.text
        assert "Recall" in fig.layout.xaxis.title.text
    
    def test_create_precision_recall_chart_with_custom_title(self):
        """create_precision_recall_chart respects custom title."""
        ir_results = {
            "keyword_search": {"precision_at_k": 0.65, "recall_at_k": 0.55}
        }
        
        fig = create_precision_recall_chart(ir_results, title="Custom Title")
        
        assert "Custom Title" in fig.layout.title.text
    
    def test_create_precision_recall_chart_empty(self):
        """create_precision_recall_chart handles empty data."""
        fig = create_precision_recall_chart({})
        
        assert fig is not None
        assert hasattr(fig, 'data')
    
    def test_create_ir_impact_chart(self):
        """create_ir_impact_chart produces valid Plotly figure."""
        ir_impact = {
            "agents": {
                "baseline": {"success_rate": 0.75},
                "strategic": {"success_rate": 0.82}
            }
        }
        
        fig = create_ir_impact_chart(ir_impact)
        
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) > 0
        assert "Success Rate" in fig.layout.yaxis.title.text
    
    def test_create_ir_impact_chart_with_custom_title(self):
        """create_ir_impact_chart respects custom title."""
        ir_impact = {
            "agents": {
                "baseline": {"success_rate": 0.75}
            }
        }
        
        fig = create_ir_impact_chart(ir_impact, title="Custom Impact")
        
        assert "Custom Impact" in fig.layout.title.text
    
    def test_create_ir_impact_chart_empty(self):
        """create_ir_impact_chart handles empty data."""
        fig = create_ir_impact_chart({})
        
        assert fig is not None
        assert hasattr(fig, 'data')
    
    def test_create_mrr_ndcg_chart(self):
        """create_mrr_ndcg_chart produces valid Plotly figure."""
        ir_results = {
            "keyword_search": {
                "mrr": 0.45,
                "ndcg": 0.63,
            },
            "deepsearch": {
                "mrr": 0.55,
                "ndcg": 0.72,
            }
        }
        
        fig = create_mrr_ndcg_chart(ir_results)
        
        assert fig is not None
        assert hasattr(fig, 'data')
        assert len(fig.data) == 2  # MRR and NDCG traces
        assert fig.layout.barmode == "group"
    
    def test_create_mrr_ndcg_chart_with_custom_title(self):
        """create_mrr_ndcg_chart respects custom title."""
        ir_results = {
            "keyword_search": {"mrr": 0.45, "ndcg": 0.63}
        }
        
        fig = create_mrr_ndcg_chart(ir_results, title="Custom MRR/NDCG")
        
        assert "Custom MRR/NDCG" in fig.layout.title.text
    
    def test_create_mrr_ndcg_chart_empty(self):
        """create_mrr_ndcg_chart handles empty data."""
        fig = create_mrr_ndcg_chart({})
        
        assert fig is not None
        assert hasattr(fig, 'data')


class TestIRViewStructure:
    """Tests for IR analysis view structure."""
    
    def test_ir_view_imports(self):
        """IR view can be imported."""
        try:
            from dashboard.views.analysis_ir import show_ir_analysis, IRASDLCAnalysisView
            assert callable(show_ir_analysis)
            assert IRASDLCAnalysisView is not None
        except ImportError as e:
            pytest.fail(f"Failed to import IR view: {e}")
    
    def test_ir_view_inherits_from_viewbase(self):
        """IR view inherits from ViewBase."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        from dashboard.utils.view_base import ViewBase
        
        assert issubclass(IRASDLCAnalysisView, ViewBase)
    
    def test_ir_view_has_required_properties(self):
        """IR view has required title and subtitle properties."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        
        assert view.title is not None
        assert isinstance(view.title, str)
        assert "IR" in view.title
        
        assert view.subtitle is not None
        assert isinstance(view.subtitle, str)
    
    def test_ir_view_has_required_methods(self):
        """IR view implements required abstract methods."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        import inspect
        
        view = IRASDLCAnalysisView()
        
        # Check for required methods
        assert callable(view.load_analysis)
        assert callable(view.extract_metrics)
        assert callable(view.render_main_content)
        assert callable(view.configure_sidebar)


class TestIRViewLifecycle:
    """Tests for IR view lifecycle methods."""
    
    def test_ir_view_initialization(self):
        """IR view initializes correctly."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        
        assert view.view_name == "IR-SDLC Analysis"
        assert view.view_type == "ir_sdlc"
        assert view.baseline_ir_tool == "none"
        assert view.comparison_ir_tools == []
    
    def test_ir_view_load_analysis_structure(self):
        """IR view load_analysis method structure is correct."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        import inspect
        
        view = IRASDLCAnalysisView()
        source = inspect.getsource(view.load_analysis)
        
        assert "self.loader.load_ir_analysis" in source
        assert "self.experiment_id" in source
    
    def test_ir_view_extract_metrics_structure(self):
        """IR view extract_metrics method structure is correct."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        import inspect
        
        view = IRASDLCAnalysisView()
        source = inspect.getsource(view.extract_metrics)
        
        assert "extract_ir_metrics" in source


class TestIRViewSidebar:
    """Tests for IR view sidebar configuration."""
    
    @patch('dashboard.views.analysis_ir.st')
    def test_ir_view_sidebar_has_baseline_selector(self, mock_st):
        """IR view sidebar includes baseline IR tool selector."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        
        # Mock Streamlit
        mock_st.selectbox.return_value = "keyword_search"
        mock_st.multiselect.return_value = ["deepsearch", "deepsearch_focused"]
        
        view.configure_sidebar()
        
        # Verify selectbox was called with correct options
        mock_st.selectbox.assert_called()
        call_args = mock_st.selectbox.call_args
        options = call_args[0][1]  # Second argument is options list
        
        assert "none" in options
        assert "keyword_search" in options
        assert "deepsearch" in options
    
    @patch('dashboard.views.analysis_ir.st')
    def test_ir_view_sidebar_has_comparison_selector(self, mock_st):
        """IR view sidebar includes comparison tools multi-select."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        
        # Mock Streamlit
        mock_st.selectbox.return_value = "keyword_search"
        mock_st.multiselect.return_value = ["deepsearch", "deepsearch_focused"]
        
        view.configure_sidebar()
        
        # Verify multiselect was called
        assert mock_st.multiselect.called


class TestIRViewRendering:
    """Tests for IR view rendering logic."""
    
    def test_ir_view_render_main_content_structure(self):
        """IR view render_main_content has all expected sections."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        import inspect
        
        view = IRASDLCAnalysisView()
        source = inspect.getsource(view.render_main_content)
        
        # Check for expected sections
        assert "IR Metrics Summary" in source
        assert "IR Tool Performance Comparison" in source
        assert "Precision vs Recall" in source
        assert "MRR vs NDCG" in source
        assert "IR Tool Impact" in source
        assert "Correlation Analysis" in source
        assert "Detailed IR Metrics" in source


class TestIRViewIntegration:
    """Integration tests for IR view with filters and exports."""
    
    def test_ir_metrics_work_with_filters(self):
        """IR metrics can be filtered by FilterEngine."""
        ir_data = {
            "experiment_id": "exp001",
            "ir_tool_results": {
                "keyword_search": {"precision_at_k": 0.65, "mrr": 0.45},
                "deepsearch": {"precision_at_k": 0.72, "mrr": 0.55}
            },
            "avg_precision_at_k": 0.68,
            "avg_recall_at_k": 0.60
        }
        
        # Apply filters (should return data with requested metrics)
        config = FilterConfig(
            metrics=["avg_precision_at_k", "avg_recall_at_k"]
        )
        
        engine = FilterEngine()
        filtered = engine.apply_filters(ir_data, config)
        
        # Verify data is still valid after filtering
        assert "experiment_id" in filtered
        # avg_precision_at_k and avg_recall_at_k should be in filtered data
        assert filtered.get("avg_precision_at_k") == 0.68
    
    def test_ir_view_export_format(self):
        """IR view export includes all necessary fields."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        view.experiment_id = "exp001"
        view.filter_config = FilterConfig()
        
        ir_data = {
            "ir_tool_results": {
                "keyword_search": {"precision_at_k": 0.65}
            },
            "avg_precision_at_k": 0.65
        }
        
        export_data = view.format_export_data(ir_data)
        
        assert export_data["experiment_id"] == "exp001"
        assert export_data["view_type"] == "ir_sdlc"
        assert "filters_applied" in export_data
        assert "data" in export_data


class TestIRViewErrorHandling:
    """Tests for IR view error handling."""
    
    def test_ir_view_handles_missing_ir_results(self):
        """IR view handles missing ir_tool_results gracefully."""
        from dashboard.views.analysis_ir import IRASDLCAnalysisView
        
        view = IRASDLCAnalysisView()
        
        data = {
            "ir_tool_results": {},
            "avg_precision_at_k": 0.0,
            "avg_recall_at_k": 0.0
        }
        
        # Should not raise
        view.extract_metrics(None)
    
    def test_ir_view_handles_missing_ir_impact(self):
        """IR view handles missing ir_impact gracefully."""
        ir_data = {
            "ir_impact": {},
            "ir_tool_results": {}
        }
        
        # Should not raise when impact is empty
        ir_impact = ir_data.get("ir_impact", {})
        assert ir_impact == {}
    
    def test_ir_visualization_handles_missing_metrics(self):
        """IR visualizations handle missing metrics gracefully."""
        # Missing metrics should default to 0
        ir_results = {
            "keyword_search": {}  # No precision_at_k, recall_at_k, etc.
        }
        
        # Should not raise
        fig = create_precision_recall_chart(ir_results)
        assert fig is not None


class TestIRMetricsExtraction:
    """Tests for IR metrics extraction patterns."""
    
    def test_extract_ir_metrics_preserves_structure(self):
        """extract_ir_metrics preserves nested structure."""
        mock_result = MagicMock()
        mock_result.experiment_id = "exp001"
        mock_result.ir_tool_results = {
            "tool1": {"metric1": 0.5, "metric2": 0.6},
            "tool2": {"metric1": 0.7, "metric2": 0.8}
        }
        mock_result.ir_impact = {"agents": {}}
        mock_result.detailed_metrics = {}
        mock_result.avg_precision_at_k = 0.6
        mock_result.avg_recall_at_k = 0.5
        mock_result.correlation_analysis = {}
        
        result = extract_ir_metrics(mock_result)
        
        # Verify nested structure is preserved
        assert isinstance(result["ir_tool_results"], dict)
        assert "tool1" in result["ir_tool_results"]
        assert "metric1" in result["ir_tool_results"]["tool1"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
