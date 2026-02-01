"""Tests for ViewBase class."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dashboard.utils.view_base import ViewBase
from dashboard.utils.filters import FilterConfig


class ConcreteView(ViewBase):
    """Concrete implementation for testing."""
    
    def __init__(self):
        super().__init__("Test View", "test")
        self.baseline_agent = None
    
    @property
    def title(self) -> str:
        return "Test Analysis"
    
    @property
    def subtitle(self) -> str:
        return "**Test subtitle**"
    
    def configure_sidebar(self):
        self.baseline_agent = "test_agent"
    
    def load_analysis(self):
        return {"test_data": "value"}
    
    def extract_metrics(self, result):
        return {"extracted": result}
    
    def render_main_content(self, data):
        pass


def test_view_base_init():
    """Test ViewBase initialization."""
    view = ConcreteView()
    
    assert view.view_name == "Test View"
    assert view.view_type == "test"
    assert view.loader is None
    assert view.nav_context is None


def test_view_base_configure_sidebar_default():
    """Test default configure_sidebar is no-op."""
    view = ConcreteView()
    view.configure_sidebar()
    # Should not raise


def test_view_base_extract_metrics_required():
    """Test extract_metrics is abstract."""
    with pytest.raises(TypeError):
        ViewBase("Test", "test")


def test_view_base_load_analysis_required():
    """Test load_analysis is abstract."""
    with pytest.raises(TypeError):
        ViewBase("Test", "test")


def test_view_base_render_main_content_required():
    """Test render_main_content is abstract."""
    with pytest.raises(TypeError):
        ViewBase("Test", "test")


@patch('dashboard.utils.view_base.NavigationContext')
@patch('dashboard.utils.view_base.st')
def test_view_base_initialize_success(mock_st, mock_nav):
    """Test successful initialization."""
    view = ConcreteView()
    view.loader = Mock()
    
    # Mock session state as object with dict-like access
    mock_session = MagicMock()
    mock_session.get.return_value = view.loader
    mock_st.session_state = mock_session
    
    result = view.initialize()
    
    assert result is True
    assert view.loader is not None


@patch('dashboard.utils.view_base.NavigationContext')
@patch('dashboard.utils.view_base.st')
def test_view_base_initialize_no_loader(mock_st, mock_nav):
    """Test initialization fails without loader."""
    view = ConcreteView()
    
    # Mock session state without loader
    mock_session = MagicMock()
    mock_session.get.return_value = None
    mock_st.session_state = mock_session
    
    result = view.initialize()
    
    assert result is False


@patch('dashboard.utils.view_base.st')
def test_view_base_load_and_extract_success(mock_st):
    """Test load_and_extract with valid data."""
    view = ConcreteView()
    view.loader = Mock()
    
    result = view.load_and_extract()
    
    assert result == {"extracted": {"test_data": "value"}}


@patch('dashboard.utils.view_base.st')
def test_view_base_load_and_extract_none_result(mock_st):
    """Test load_and_extract with None result."""
    class NoDataView(ConcreteView):
        def load_analysis(self):
            return None
    
    view = NoDataView()
    result = view.load_and_extract()
    
    assert result is None


@patch('dashboard.utils.view_base.st')
def test_view_base_apply_filters_no_filters(mock_st):
    """Test apply_filters with no active filters."""
    view = ConcreteView()
    view.filter_config = FilterConfig()
    
    data = {"key": "value"}
    result = view.apply_filters(data)
    
    assert result == data


@patch('dashboard.utils.view_base.st')
def test_view_base_apply_filters_with_filters(mock_st):
    """Test apply_filters with active filters."""
    view = ConcreteView()
    view.filter_config = FilterConfig(metrics=["metric1"])
    
    data = {"metric1": 0.5, "metric2": 0.3}
    result = view.apply_filters(data)
    
    # FilterEngine should have been called
    assert view.filter_config.has_filters()


def test_view_base_format_export_data_default():
    """Test default export data formatting."""
    view = ConcreteView()
    view.experiment_id = "test_exp"
    view.filter_config = FilterConfig()
    
    data = {"key": "value"}
    export_data = view.format_export_data(data)
    
    assert export_data["experiment_id"] == "test_exp"
    assert export_data["view_type"] == "test"
    assert export_data["filters_applied"] is False
    assert export_data["data"] == data
