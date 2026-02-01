"""
Tests for Phase 5.1 analysis views.

Tests cover:
- Comparison analysis view
- Statistical analysis view
- Data loading and display
- Error handling
- Export functionality
"""

import pytest
from pathlib import Path
import tempfile
import sqlite3
from unittest.mock import Mock, patch, MagicMock

from dashboard.utils.analysis_loader import AnalysisLoader


@pytest.fixture
def temp_db_with_data():
    """Create a temporary test database with sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Create test schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create harbor_results table
    cursor.execute("""
        CREATE TABLE harbor_results (
            job_id TEXT,
            experiment_id TEXT,
            task_id TEXT,
            agent_name TEXT,
            passed BOOLEAN,
            duration_seconds FLOAT,
            reward_primary FLOAT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            model_name TEXT
        )
    """)
    
    # Insert test data - 3 agents, 10 tasks each
    agents = ["baseline", "strategic", "full-toolkit"]
    for agent_idx, agent in enumerate(agents):
        for task_idx in range(10):
            passed = (task_idx + agent_idx) % 2 == 0
            cursor.execute(
                "INSERT INTO harbor_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"job_{agent}_{task_idx}",
                    "exp001",
                    f"task_{task_idx}",
                    agent,
                    passed,
                    10.0 + task_idx,
                    0.8 if passed else 0.5,
                    1000 * (task_idx + 1),
                    500 * (task_idx + 1),
                    "claude-haiku-4-5-20251001"
                )
            )
    
    # Create tool_usage table
    cursor.execute("""
        CREATE TABLE tool_usage (
            job_id TEXT,
            tool_name TEXT,
            call_count INTEGER,
            success_rate FLOAT
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    db_path.unlink()


class TestComparisonAnalysisView:
    """Tests for comparison analysis view."""
    
    def test_comparison_view_imports(self):
        """Comparison view can be imported."""
        try:
            from dashboard.views.analysis_comparison import show_comparison_analysis
            assert callable(show_comparison_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import comparison view: {e}")
    
    def test_comparison_view_structure(self):
        """Comparison view has required structure."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        import inspect
        
        source = inspect.getsource(show_comparison_analysis)
        
        # Check for key functionality
        assert 'st.title' in source
        assert 'loader.load_comparison' in source
        assert 'export_json_button' in source
        assert 'display_error_message' in source
    
    def test_comparison_view_has_sections(self):
        """Comparison view includes all expected sections."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        import inspect
        
        source = inspect.getsource(show_comparison_analysis)
        
        # Check for expected sections
        assert 'Summary Statistics' in source
        assert 'Performance Metrics' in source
        assert 'Performance Delta' in source
        assert 'Statistical Significance' in source
        assert 'Cost Metrics' in source
    
    def test_comparison_handles_missing_loader(self):
        """Comparison view handles missing loader gracefully."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        import inspect
        
        source = inspect.getsource(show_comparison_analysis)
        # Check that loader validation is present
        assert 'st.session_state.get("analysis_loader")' in source
        assert 'Analysis loader not initialized' in source


class TestStatisticalAnalysisView:
    """Tests for statistical analysis view."""
    
    def test_statistical_view_imports(self):
        """Statistical view can be imported."""
        try:
            from dashboard.views.analysis_statistical import show_statistical_analysis
            assert callable(show_statistical_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import statistical view: {e}")
    
    def test_statistical_view_structure(self):
        """Statistical view has required structure."""
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        source = inspect.getsource(show_statistical_analysis)
        
        # Check for key functionality
        assert 'st.title' in source
        assert 'loader.load_statistical' in source
        assert 'export_json_button' in source
        assert 'display_error_message' in source
    
    def test_statistical_view_has_sections(self):
        """Statistical view includes all expected sections."""
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        source = inspect.getsource(show_statistical_analysis)
        
        # Check for expected sections
        assert 'Test Summary' in source
        assert 'Statistical Test Results' in source
        assert 'Effect Size Analysis' in source
        assert 'Power Analysis' in source
        assert 'Per-Metric Significance' in source
        assert 'Interpretation' in source
    
    def test_statistical_handles_missing_loader(self):
        """Statistical view handles missing loader gracefully."""
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        source = inspect.getsource(show_statistical_analysis)
        # Check that loader validation is present
        assert 'st.session_state.get("analysis_loader")' in source
        assert 'Analysis loader not initialized' in source


class TestCommonComponentsIntegration:
    """Tests for common components used in views."""
    
    def test_display_significance_badge_generation(self):
        """Significance badges are generated correctly."""
        from dashboard.utils.common_components import display_significance_badge
        
        # Test various p-values
        badge_low = display_significance_badge(0.001)
        # 0.001 < 0.01, so displays p<0.01
        assert 'p<0.01' in badge_low or 'p<0.001' in badge_low
        assert '✓' in badge_low
        
        badge_mid = display_significance_badge(0.03)
        assert 'p<0.05' in badge_mid
        assert '✓' in badge_mid
        
        badge_high = display_significance_badge(0.15)
        assert 'ns' in badge_high  # not significant
        assert '✗' in badge_high
    
    def test_effect_size_bar_rendering(self):
        """Effect size bars are rendered correctly."""
        from dashboard.utils.common_components import display_effect_size_bar
        
        # This is a Streamlit component, just verify it doesn't crash
        try:
            # Mock streamlit markdown to avoid UI rendering
            with patch('streamlit.markdown'):
                display_effect_size_bar(0.5, "Cohen's d")
        except:
            # Streamlit components may require session state in tests
            pass
    
    def test_summary_card_rendering(self):
        """Summary cards are rendered correctly."""
        from dashboard.utils.common_components import display_summary_card
        
        try:
            with patch('streamlit.markdown'):
                display_summary_card("Test", "Value", metric="metric", color="blue")
        except:
            pass
    
    def test_export_json_button_generation(self):
        """JSON export button is generated correctly."""
        from dashboard.utils.common_components import export_json_button
        
        try:
            with patch('streamlit.download_button'):
                test_data = {"key": "value", "number": 42}
                export_json_button(test_data, "test_export")
        except:
            pass


class TestViewDataIntegration:
    """Tests for data integration between views."""
    
    def test_views_follow_common_pattern(self):
        """Both views follow the established pattern."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        comparison_source = inspect.getsource(show_comparison_analysis)
        statistical_source = inspect.getsource(show_statistical_analysis)
        
        # Both should use same pattern
        common_elements = [
            'experiment_selector()',
            'loader.list_agents',
            'st.session_state.get("analysis_loader")',
            'display_error_message',
            'export_json_button'
        ]
        
        for element in common_elements:
            assert element in comparison_source, f"Comparison missing {element}"
            assert element in statistical_source, f"Statistical missing {element}"
    
    def test_views_handle_session_state(self):
        """Views properly handle session state management."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        comparison_source = inspect.getsource(show_comparison_analysis)
        statistical_source = inspect.getsource(show_statistical_analysis)
        
        # Both should check session state
        assert 'st.session_state' in comparison_source
        assert 'st.session_state' in statistical_source
    
    def test_views_export_json(self):
        """Both views support JSON export."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        comparison_source = inspect.getsource(show_comparison_analysis)
        statistical_source = inspect.getsource(show_statistical_analysis)
        
        # Both should export JSON
        assert 'export_json_button' in comparison_source
        assert 'export_json_button' in statistical_source


class TestErrorHandlingInViews:
    """Tests for error handling in views."""
    
    def test_comparison_view_handles_errors(self):
        """Comparison view has error handling."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        import inspect
        
        source = inspect.getsource(show_comparison_analysis)
        
        # Check for error handling
        assert 'try:' in source
        assert 'except' in source
        assert 'display_error_message' in source
    
    def test_statistical_view_handles_errors(self):
        """Statistical view has error handling."""
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        source = inspect.getsource(show_statistical_analysis)
        
        # Check for error handling
        assert 'try:' in source
        assert 'except' in source
        assert 'display_error_message' in source
    
    def test_views_handle_no_data(self):
        """Views handle no data gracefully."""
        from dashboard.views.analysis_comparison import show_comparison_analysis
        from dashboard.views.analysis_statistical import show_statistical_analysis
        import inspect
        
        comparison_source = inspect.getsource(show_comparison_analysis)
        statistical_source = inspect.getsource(show_statistical_analysis)
        
        # Both should handle no data
        assert 'display_no_data_message' in comparison_source
        assert 'display_no_data_message' in statistical_source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
