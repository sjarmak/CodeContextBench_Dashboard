"""Base class for analysis views - eliminates boilerplate."""

import streamlit as st
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from dashboard.utils.common_components import (
    experiment_selector,
    export_json_button,
    display_no_data_message,
    display_error_message,
)
from dashboard.utils.filter_ui import render_filter_panel
from dashboard.utils.filters import FilterEngine, FilterConfig
from dashboard.components.breadcrumb import render_breadcrumb_navigation
from dashboard.utils.navigation import NavigationContext


class ViewBase(ABC):
    """Base class for all analysis views - eliminates boilerplate."""
    
    def __init__(self, view_name: str, view_type: str):
        """Initialize view with name and type."""
        self.view_name = view_name
        self.view_type = view_type
        self.loader = None
        self.nav_context = None
        self.experiment_id = None
        self.filter_config = None
    
    def initialize(self) -> bool:
        """Initialize session state and loader. Return False if init failed."""
        # Initialize navigation context
        if "nav_context" not in st.session_state:
            st.session_state.nav_context = NavigationContext()
        self.nav_context = st.session_state.nav_context
        
        # Get analysis loader
        self.loader = st.session_state.get("analysis_loader")
        if self.loader is None:
            st.error("Analysis loader not initialized. Please visit Analysis Hub first.")
            return False
        
        return True
    
    def render_header(self):
        """Render breadcrumb navigation, title, and description."""
        render_breadcrumb_navigation(self.nav_context)
        st.title(self.title)
        st.markdown(self.subtitle)
        st.markdown("---")
    
    def render_sidebar_config(self) -> bool:
        """Render sidebar configuration. Return False if user didn't select experiment."""
        with st.sidebar:
            st.subheader("Configuration")
            
            # Experiment selector
            self.experiment_id = experiment_selector()
            if self.experiment_id is None:
                return False
            
            # View-specific configuration (override in subclass)
            self.configure_sidebar()
            
            st.markdown("---")
            
            # Advanced filters
            st.subheader("Advanced Filters")
            self.filter_config = render_filter_panel(
                self.view_type,
                self.loader,
                self.experiment_id
            )
            
            return True
    
    def load_and_extract(self) -> Optional[Dict[str, Any]]:
        """Load analysis result and extract metrics. Return None if failed."""
        try:
            result = self.load_analysis()
            if result is None:
                display_no_data_message(f"No {self.view_name} data available")
                return None
            
            extracted_data = self.extract_metrics(result)
            return extracted_data
        
        except Exception as e:
            display_error_message(f"Failed to load {self.view_name}: {e}")
            return None
    
    def apply_filters(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to extracted data and display feedback."""
        if not self.filter_config.has_filters():
            return data
        
        filter_engine = FilterEngine()
        filtered_data = filter_engine.apply_filters(data, self.filter_config)
        
        st.info(f"📊 Filters applied: {filter_engine.get_filter_summary(self.filter_config)}")
        
        return filtered_data
    
    def render_export(self, data: Dict[str, Any]):
        """Render export section with formatted data."""
        st.subheader("Export Results")
        
        try:
            export_data = self.format_export_data(data)
            export_json_button(
                export_data,
                f"{self.view_type}_{self.experiment_id}"
            )
        except Exception as e:
            display_error_message(f"Failed to export {self.view_name}: {e}")
    
    # ==================== Abstract Methods (Override in Subclass) ====================
    
    @property
    @abstractmethod
    def title(self) -> str:
        """View title. Example: 'Agent Comparison Analysis'"""
        pass
    
    @property
    @abstractmethod
    def subtitle(self) -> str:
        """View subtitle. Example: '**Compare agent performance metrics across tasks**'"""
        pass
    
    def configure_sidebar(self):
        """Override to add view-specific sidebar configuration.
        Called automatically by render_sidebar_config().
        
        Example:
            def configure_sidebar(self):
                agents = self.loader.list_agents(self.experiment_id)
                self.baseline_agent = st.selectbox("Baseline Agent", agents)
        """
        pass
    
    @abstractmethod
    def load_analysis(self):
        """Load the analysis result. Override to call appropriate loader method.
        
        Example:
            def load_analysis(self):
                return self.loader.load_comparison(
                    self.experiment_id,
                    baseline_agent=self.baseline_agent
                )
        """
        pass
    
    @abstractmethod
    def extract_metrics(self, result) -> Dict[str, Any]:
        """Extract metrics from result into filterable dict format.
        
        Example:
            def extract_metrics(self, result):
                return extract_comparison_metrics(result)
        """
        pass
    
    @abstractmethod
    def render_main_content(self, data: Dict[str, Any]):
        """Render view-specific content (summary cards, tables, charts).
        
        Example:
            def render_main_content(self, data: Dict[str, Any]):
                st.subheader("Summary Statistics")
                # ... render summary cards
                st.subheader("Performance Metrics")
                # ... render table
                st.subheader("Visualizations")
                # ... render charts
        """
        pass
    
    def format_export_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format data for JSON export. Override to customize.
        
        Default implementation includes experiment_id and filters_applied.
        """
        return {
            "experiment_id": self.experiment_id,
            "view_type": self.view_type,
            "filters_applied": self.filter_config.has_filters(),
            "filters": self.filter_config.to_dict(),
            "data": data,
        }
    
    def run(self):
        """Main entry point - orchestrates the view lifecycle."""
        # Initialize
        if not self.initialize():
            return
        
        # Render header
        self.render_header()
        
        # Render sidebar config
        if not self.render_sidebar_config():
            return
        
        # Load and extract
        data = self.load_and_extract()
        if data is None:
            return
        
        # Apply filters
        filtered_data = self.apply_filters(data)
        
        # Render main content
        try:
            self.render_main_content(filtered_data)
        except Exception as e:
            display_error_message(f"Failed to render {self.view_name}: {e}")
            return
        
        st.markdown("---")
        
        # Render export
        self.render_export(filtered_data)
