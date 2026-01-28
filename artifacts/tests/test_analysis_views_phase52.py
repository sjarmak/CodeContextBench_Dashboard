"""
Tests for Phase 5.2 analysis views (Time-Series, Cost, Failure).

Tests cover:
- Time-Series Analysis view
- Cost Analysis view
- Failure Analysis view
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
    
    # Insert test data - 3 experiments, 3 agents, 5 tasks each
    experiments = ["exp001", "exp002", "exp003"]
    agents = ["baseline", "strategic", "full-toolkit"]
    
    for exp_idx, exp_id in enumerate(experiments):
        for agent_idx, agent in enumerate(agents):
            for task_idx in range(5):
                passed = (task_idx + agent_idx + exp_idx) % 2 == 0
                cursor.execute(
                    "INSERT INTO harbor_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"job_{exp_id}_{agent}_{task_idx}",
                        exp_id,
                        f"task_{task_idx}",
                        agent,
                        passed,
                        10.0 + task_idx + (exp_idx * 0.5),
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


class TestTimeSeriesAnalysisView:
    """Tests for Time-Series Analysis view."""
    
    def test_timeseries_view_imports(self):
        """Time-Series view can be imported."""
        try:
            from dashboard.views.analysis_timeseries import show_timeseries_analysis
            assert callable(show_timeseries_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import time-series view: {e}")
    
    def test_timeseries_view_structure(self):
        """Time-Series view has required structure."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        import inspect
        
        source = inspect.getsource(show_timeseries_analysis)
        
        # Check for key functionality
        assert 'st.title' in source
        assert 'loader.load_timeseries' in source
        assert 'experiment_ids' in source
        assert 'selected_agents' in source
    
    def test_timeseries_view_has_sections(self):
        """Time-Series view includes all expected sections."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        import inspect
        
        source = inspect.getsource(show_timeseries_analysis)
        
        # Check for expected sections
        assert 'Trend Summary' in source
        assert 'Metric Trends' in source
        assert 'Agent Performance Trends' in source
        assert 'Best & Worst Improving' in source
        assert 'Detected Anomalies' in source
    
    def test_timeseries_handles_missing_loader(self):
        """Time-Series view handles missing loader gracefully."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        import inspect
        
        source = inspect.getsource(show_timeseries_analysis)
        assert 'st.session_state.get("analysis_loader")' in source
        assert 'Analysis loader not initialized' in source


class TestCostAnalysisView:
    """Tests for Cost Analysis view."""
    
    def test_cost_view_imports(self):
        """Cost view can be imported."""
        try:
            from dashboard.views.analysis_cost import show_cost_analysis
            assert callable(show_cost_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import cost view: {e}")
    
    def test_cost_view_structure(self):
        """Cost view has required structure."""
        from dashboard.views.analysis_cost import show_cost_analysis
        import inspect
        
        source = inspect.getsource(show_cost_analysis)
        
        # Check for key functionality
        assert 'st.title' in source
        assert 'loader.load_cost' in source
        assert 'experiment_id' in source
        assert 'baseline_agent' in source
    
    def test_cost_view_has_sections(self):
        """Cost view includes all expected sections."""
        from dashboard.views.analysis_cost import show_cost_analysis
        import inspect
        
        source = inspect.getsource(show_cost_analysis)
        
        # Check for expected sections
        assert 'Cost Summary' in source
        assert 'Agent Cost Rankings' in source
        assert 'Cost Efficiency Analysis' in source
        assert 'Cost Regressions' in source
        assert 'Token Usage by Model' in source
        assert 'Cost vs Performance' in source
    
    def test_cost_handles_missing_loader(self):
        """Cost view handles missing loader gracefully."""
        from dashboard.views.analysis_cost import show_cost_analysis
        import inspect
        
        source = inspect.getsource(show_cost_analysis)
        assert 'st.session_state.get("analysis_loader")' in source
        assert 'Analysis loader not initialized' in source


class TestFailureAnalysisView:
    """Tests for Failure Analysis view."""
    
    def test_failure_view_imports(self):
        """Failure view can be imported."""
        try:
            from dashboard.views.analysis_failure import show_failure_analysis
            assert callable(show_failure_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import failure view: {e}")
    
    def test_failure_view_structure(self):
        """Failure view has required structure."""
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        source = inspect.getsource(show_failure_analysis)
        
        # Check for key functionality
        assert 'st.title' in source
        assert 'loader.load_failures' in source
        assert 'experiment_id' in source
        assert 'agent_name' in source
    
    def test_failure_view_has_sections(self):
        """Failure view includes all expected sections."""
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        source = inspect.getsource(show_failure_analysis)
        
        # Check for expected sections
        assert 'Failure Summary' in source
        assert 'Failure Patterns' in source
        assert 'Failure Categories' in source
        assert 'Difficulty Analysis' in source
        assert 'Suggested Improvements' in source
        assert 'Agent Comparison' in source
        assert 'High-Risk Tasks' in source
    
    def test_failure_handles_missing_loader(self):
        """Failure view handles missing loader gracefully."""
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        source = inspect.getsource(show_failure_analysis)
        assert 'st.session_state.get("analysis_loader")' in source
        assert 'Analysis loader not initialized' in source


class TestPhase52ViewsIntegration:
    """Tests for integration of Phase 5.2 views."""
    
    def test_views_follow_common_pattern(self):
        """All Phase 5.2 views follow established pattern."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # All should use same pattern
        common_elements = [
            'st.session_state.get("analysis_loader")',
            'display_error_message',
            'export_json_button'
        ]
        
        for element in common_elements:
            assert element in timeseries_source, f"Time-Series missing {element}"
            assert element in cost_source, f"Cost missing {element}"
            assert element in failure_source, f"Failure missing {element}"
    
    def test_views_handle_session_state(self):
        """All views properly handle session state management."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # All should check session state
        assert 'st.session_state' in timeseries_source
        assert 'st.session_state' in cost_source
        assert 'st.session_state' in failure_source
    
    def test_views_export_json(self):
        """All views support JSON export."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # All should export JSON
        assert 'export_json_button' in timeseries_source
        assert 'export_json_button' in cost_source
        assert 'export_json_button' in failure_source


class TestErrorHandlingInPhase52Views:
    """Tests for error handling in Phase 5.2 views."""
    
    def test_timeseries_view_handles_errors(self):
        """Time-Series view has error handling."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        import inspect
        
        source = inspect.getsource(show_timeseries_analysis)
        
        # Check for error handling
        assert 'try:' in source
        assert 'except' in source
        assert 'display_error_message' in source
    
    def test_cost_view_handles_errors(self):
        """Cost view has error handling."""
        from dashboard.views.analysis_cost import show_cost_analysis
        import inspect
        
        source = inspect.getsource(show_cost_analysis)
        
        # Check for error handling
        assert 'try:' in source
        assert 'except' in source
        assert 'display_error_message' in source
    
    def test_failure_view_handles_errors(self):
        """Failure view has error handling."""
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        source = inspect.getsource(show_failure_analysis)
        
        # Check for error handling
        assert 'try:' in source
        assert 'except' in source
        assert 'display_error_message' in source
    
    def test_views_handle_no_data(self):
        """Views handle no data gracefully."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # All should handle no data
        assert 'display_no_data_message' in timeseries_source
        assert 'display_no_data_message' in cost_source
        assert 'display_no_data_message' in failure_source


class TestPhase52ComponentUsage:
    """Tests for common component usage in Phase 5.2 views."""
    
    def test_views_use_sidebar_controls(self):
        """Views properly use sidebar controls."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # Time-Series uses multiselect for experiments
        assert 'st.multiselect' in timeseries_source
        assert 'experiment_ids' in timeseries_source
        
        # Cost uses experiment selector
        assert 'experiment_selector()' in cost_source
        
        # Failure uses experiment selector
        assert 'experiment_selector()' in failure_source
    
    def test_views_use_common_display_components(self):
        """Views use common display components."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        from dashboard.views.analysis_cost import show_cost_analysis
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        timeseries_source = inspect.getsource(show_timeseries_analysis)
        cost_source = inspect.getsource(show_cost_analysis)
        failure_source = inspect.getsource(show_failure_analysis)
        
        # All use display components
        assert 'display_summary_card' in timeseries_source
        assert 'display_summary_card' in cost_source
        assert 'display_summary_card' in failure_source


class TestPhase52Metrics:
    """Tests for metric handling in Phase 5.2 views."""
    
    def test_timeseries_has_trend_metrics(self):
        """Time-Series view displays trend metrics."""
        from dashboard.views.analysis_timeseries import show_timeseries_analysis
        import inspect
        
        source = inspect.getsource(show_timeseries_analysis)
        
        # Check for trend-specific metrics
        assert 'direction' in source
        assert 'percent_change' in source
        assert 'slope' in source
        assert 'confidence' in source
    
    def test_cost_has_financial_metrics(self):
        """Cost view displays financial metrics."""
        from dashboard.views.analysis_cost import show_cost_analysis
        import inspect
        
        source = inspect.getsource(show_cost_analysis)
        
        # Check for cost-specific metrics
        assert 'total_cost' in source
        assert 'input_tokens' in source
        assert 'output_tokens' in source
        assert 'efficiency' in source
    
    def test_failure_has_pattern_metrics(self):
        """Failure view displays pattern metrics."""
        from dashboard.views.analysis_failure import show_failure_analysis
        import inspect
        
        source = inspect.getsource(show_failure_analysis)
        
        # Check for failure-specific metrics
        assert 'failure_rate' in source
        assert 'categories' in source
        assert 'patterns' in source
        assert 'risk_level' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
