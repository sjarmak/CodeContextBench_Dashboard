"""
CodeContextBench Evaluation Dashboard

Full-featured benchmark management and evaluation platform.
"""

import streamlit as st
from pathlib import Path
import os
import sys

# Add project root and dashboard to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
DASHBOARD_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(DASHBOARD_ROOT))

# Load and export environment variables from .env.local
# This ensures Harbor subprocesses have access to API keys
env_file = Path(__file__).parent.parent / ".env.local"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Set in environment
                os.environ[key] = value

    # Explicitly export critical credentials for subprocesses
    critical_vars = ["ANTHROPIC_API_KEY", "SOURCEGRAPH_ACCESS_TOKEN", "SOURCEGRAPH_URL"]
    for var in critical_vars:
        if var in os.environ:
            # Re-set to ensure it's exported (belt and suspenders)
            os.environ[var] = os.environ[var]

# Configure page
st.set_page_config(
    page_title="CodeContextBench Dashboard",
    page_icon="CB",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Session state initialization
if "project_root" not in st.session_state:
    st.session_state.project_root = PROJECT_ROOT

if "selected_experiment" not in st.session_state:
    st.session_state.selected_experiment = None


def main():
    """Main dashboard entry point."""

    # Initialize selected page in session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"

    # Sidebar navigation
    st.sidebar.title("CodeContextBench")
    st.sidebar.markdown("---")

    # Custom CSS for navigation
    st.sidebar.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        border-radius: 0;
        border: none;
        border-bottom: 1px solid #333;
        background-color: transparent;
        color: inherit;
        text-align: left;
        padding: 12px 16px;
        font-weight: normal;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.05);
        border-left: 3px solid #4a9eff;
        padding-left: 13px;
    }
    .stButton > button:focus {
        box-shadow: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # Navigation items - organized by workflow
    # Home is standalone (no section label)
    nav_home = ["Home"]
    
    # Benchmarks section
    nav_benchmarks = [
        "Benchmark Manager",
    ]
    
    # Results section
    nav_results = [
        "Run Results",
    ]

    # Analysis & comparison (Phase 4 Analysis Layer)
    nav_items_analysis = [
        "Analysis Hub",
        "LLM Judge",
        "Comparison Analysis",
        "Statistical Analysis",
        "Time-Series Analysis",
        "Cost Analysis",
        "Failure Analysis",
    ]

    def render_nav_section(items, section_label=None):
        """Render a navigation section with optional label."""
        if section_label:
            st.sidebar.markdown(
                f'<div style="padding: 8px 16px; font-size: 0.75em; '
                f'color: #888; text-transform: uppercase; letter-spacing: 0.05em;">'
                f'{section_label}</div>',
                unsafe_allow_html=True
            )
        for item in items:
            if item == st.session_state.current_page:
                st.sidebar.markdown(
                    f'<div style="background-color: rgba(74, 158, 255, 0.1); '
                    f'border-left: 3px solid #4a9eff; padding: 12px 13px; '
                    f'border-bottom: 1px solid #333; font-weight: 500;">{item}</div>',
                    unsafe_allow_html=True
                )
            else:
                if st.sidebar.button(item, key=f"nav_{item}"):
                    st.session_state.current_page = item
                    st.rerun()

    # Render navigation sections
    render_nav_section(nav_home)  # Home without label
    render_nav_section(nav_benchmarks, "Benchmarks")
    render_nav_section(nav_results, "Results")
    render_nav_section(nav_items_analysis, "Analysis")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Project: {PROJECT_ROOT.name}")

    # Show credential status
    api_key_loaded = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if api_key_loaded:
        st.sidebar.success("✓ API Key Loaded")
    else:
        st.sidebar.error("✗ API Key Missing")
        st.sidebar.caption("Add ANTHROPIC_API_KEY to .env.local")

    # Get selected page
    page = st.session_state.current_page

    # Route to appropriate page
    if page == "Home":
        show_home()
    elif page == "Benchmark Manager":
        show_benchmark_manager()
    elif page == "Run Results":
        show_run_results()
    # Phase 4 Analysis Layer views
    elif page == "Analysis Hub":
        show_analysis_hub()
    elif page == "LLM Judge":
        show_llm_judge()
    elif page == "Comparison Analysis":
        show_comparison_analysis()
    elif page == "Statistical Analysis":
        show_statistical_analysis()
    elif page == "Time-Series Analysis":
        show_timeseries_analysis()
    elif page == "Cost Analysis":
        show_cost_analysis()
    elif page == "Failure Analysis":
        show_failure_analysis()
    # Legacy views (kept for compatibility)
    elif page == "Comparison Table":
        show_comparison_enhanced()
    elif page == "Agent Comparison":
        show_agent_comparison()
    elif page == "Deep Search Analytics":
        show_deep_search()


def show_home():
    """Home page with quick summary of benchmarks and run results."""
    st.title("CodeContextBench Evaluation Platform")

    st.markdown("**Benchmark management and evaluation results viewer**")
    st.markdown("---")

    # Available Benchmarks
    st.subheader("Available Benchmarks")

    from src.benchmark.database import BenchmarkRegistry
    benchmarks = BenchmarkRegistry.list_all()

    if benchmarks:
        benchmark_data = []
        for bm in benchmarks:
            benchmark_data.append({
                "Name": bm["name"],
                "Tasks": bm["task_count"],
                "Type": bm["adapter_type"],
                "Validation": bm.get("validation_status", "Not run"),
            })
        st.dataframe(benchmark_data, use_container_width=True, hide_index=True)
    else:
        st.info("No benchmarks registered. Use 'Add Benchmark' to register benchmarks.")

    st.markdown("---")
    
    # Quick links
    st.subheader("Quick Links")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Benchmark Management**")
        st.markdown("- Use **Benchmark Manager** to view registered benchmarks")
        st.markdown("- Benchmarks are updated via agent collaboration")
    
    with col2:
        st.markdown("**Evaluation Results**")
        st.markdown("- Use **Run Results** to view evaluation outputs from the VM")
        st.markdown("- Results are loaded from `~/evals/custom_agents/agents/claudecode/jobs`")


def show_benchmark_manager():
    """Benchmark manager page."""
    from views.benchmark_manager import show_benchmark_manager as show_manager
    show_manager()


def show_run_results():
    """Run results viewer page."""
    from views.run_results import show_run_results as show_results
    show_results()


# Phase 4 Analysis Layer view functions
def show_analysis_hub():
    """Analysis hub entry point."""
    from views.analysis_hub import show_analysis_hub as show_hub
    show_hub()


def show_llm_judge():
    """LLM Judge configuration and results view."""
    from views.analysis_llm_judge import show_llm_judge as show_judge
    show_judge()


def show_comparison_analysis():
    """Experiment comparison analysis view."""
    from views.analysis_comparison import show_comparison_analysis as show_comp
    show_comp()


def show_statistical_analysis():
    """Statistical significance analysis view."""
    from views.analysis_statistical import show_statistical_analysis as show_stat
    show_stat()


def show_timeseries_analysis():
    """Time-series trend analysis view."""
    from views.analysis_timeseries import show_timeseries_analysis as show_ts
    show_ts()


def show_cost_analysis():
    """Cost analysis view."""
    from views.analysis_cost import show_cost_analysis as show_cost
    show_cost()


def show_failure_analysis():
    """Failure pattern analysis view."""
    from views.analysis_failure import show_failure_analysis as show_failure
    show_failure()


def show_comparison_enhanced():
    """Enhanced comparison table."""
    from views.comparison_enhanced import show_comparison_enhanced as show_enhanced
    show_enhanced()


def show_agent_comparison():
    """Agent comparison charts page."""
    from views.comparison import show_comparison_view as show_compare
    show_compare()


def show_deep_search():
    """Deep Search analytics page."""
    from views.deep_search import show_deep_search_analytics as show_ds
    show_ds()


if __name__ == "__main__":
    main()
