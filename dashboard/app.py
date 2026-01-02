"""
CodeContextBench Evaluation Dashboard

Full-featured benchmark management and evaluation platform.
"""

import streamlit as st
from pathlib import Path
import os

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

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

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
    # Primary workflow
    nav_items = [
        "Home",
        "Benchmark Manager",
        "Add Benchmark",
        "Evaluation Runner",
        "Run Results",
    ]

    # Analysis & comparison (Phase 4 Analysis Layer)
    nav_items_analysis = [
        "Analysis Hub",
        "Comparison Analysis",
        "Statistical Analysis",
        "Time-Series Analysis",
        "Cost Analysis",
        "Failure Analysis",
    ]

    # Advanced views
    nav_items_advanced = [
        "Experiment Results",
        "Manifests",
        "Agent Versions",
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
    render_nav_section(nav_items, "Benchmarks")
    render_nav_section(nav_items_analysis, "Analysis")
    render_nav_section(nav_items_advanced, "Advanced")

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
    elif page == "Add Benchmark":
        show_add_benchmark()
    elif page == "Evaluation Runner":
        show_evaluation_runner()
    elif page == "Run Results":
        show_run_results()
    # Phase 4 Analysis Layer views
    elif page == "Analysis Hub":
        show_analysis_hub()
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
    elif page == "Experiment Results":
        show_experiment_results()
    elif page == "Manifests":
        show_manifests()
    elif page == "Agent Versions":
        show_agent_versions()


def show_home():
    """Home page with quick summary of agents, benchmarks, and run status."""
    st.title("CodeContextBench Evaluation Platform")

    st.markdown("**Full-featured benchmark management and evaluation platform**")
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

    # Available Agents
    st.subheader("Available Agents")

    agents_dir = PROJECT_ROOT / "agents"
    if agents_dir.exists():
        agent_files = [f for f in agents_dir.glob("*.py") if f.name not in ["__init__.py", "README.md"]]

        if agent_files:
            agent_data = []
            for agent_file in agent_files:
                agent_name = agent_file.stem
                # Try to extract docstring or first comment
                try:
                    with open(agent_file) as f:
                        lines = f.readlines()
                        description = "No description"
                        for line in lines[:20]:
                            if '"""' in line or "'''" in line:
                                description = line.strip().strip('"""').strip("'''")
                                break
                except:
                    description = "No description"

                agent_data.append({
                    "Agent": agent_name,
                    "File": agent_file.name,
                    "Description": description[:60] + "..." if len(description) > 60 else description,
                })
            st.dataframe(agent_data, use_container_width=True, hide_index=True)
        else:
            st.info("No agent files found in agents/ directory.")
    else:
        st.info("Agents directory not found.")

    st.markdown("---")

    # Current Evaluation Run Status
    st.subheader("Current Evaluation Run Status")

    from src.benchmark.database import RunManager
    runs = RunManager.list_all()

    if runs:
        # Get most recent runs
        recent_runs = sorted(runs, key=lambda x: x.get("created_at", ""), reverse=True)[:10]

        run_data = []
        for run in recent_runs:
            status = run.get("status", "unknown")
            run_data.append({
                "Run ID": run["run_id"][:12] + "...",
                "Benchmark": run.get("benchmark_name", "Unknown"),
                "Status": status,
                "Tasks": f"{run.get('completed_tasks', 0)}/{run.get('total_tasks', 0)}",
                "Agents": ", ".join(run.get("agents", [])) if isinstance(run.get("agents"), list) else str(run.get("agents", "")),
            })

        st.dataframe(run_data, use_container_width=True, hide_index=True)

        # Show any running evaluations
        running_runs = [r for r in runs if r.get("status") == "running"]
        if running_runs:
            st.warning(f"{len(running_runs)} evaluation(s) currently running. Check 'Evaluation Runner' for details.")
    else:
        st.info("No evaluation runs found. Use 'Evaluation Runner' to start a new evaluation.")


def show_benchmark_manager():
    """Benchmark manager page."""
    from views.benchmark_manager import show_benchmark_manager as show_manager
    show_manager()


def show_evaluation_runner():
    """Evaluation runner page."""
    from views.evaluation_runner import show_evaluation_runner as show_runner
    show_runner()


def show_run_results():
    """Run results viewer page."""
    from views.run_results import show_run_results as show_results
    show_results()


# Phase 4 Analysis Layer view functions
def show_analysis_hub():
    """Analysis hub entry point."""
    from views.analysis_hub import show_analysis_hub as show_hub
    show_hub()


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


def show_add_benchmark():
    """Add benchmark page."""
    from views.add_benchmark import show_add_benchmark as show_add
    show_add()


def show_agent_comparison():
    """Agent comparison charts page."""
    from views.comparison import show_comparison_view as show_compare
    show_compare()


def show_deep_search():
    """Deep Search analytics page."""
    from views.deep_search import show_deep_search_analytics as show_ds
    show_ds()


def show_experiment_results():
    """Experiment results browser page."""
    from views.results import show_results_browser as show_exp
    show_exp()


def show_manifests():
    """Manifests viewer page."""
    from views.manifests import show_manifest_viewer as show_mf
    show_mf()


def show_agent_versions():
    """Agent versions management page."""
    from views.agent_versions import show_agent_versions as show_av
    show_av()


if __name__ == "__main__":
    main()
