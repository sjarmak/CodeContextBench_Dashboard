"""
CodeContextBench Evaluation Dashboard

Full-featured benchmark management and evaluation platform.
"""

import streamlit as st
from pathlib import Path

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

    # Navigation items
    nav_items = [
        "Home",
        "Benchmark Manager",
        "Evaluation Runner",
        "Run Results",
        "Comparison Table",
    ]

    # Create navigation buttons
    for item in nav_items:
        # Highlight current page with different styling
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

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Project: {PROJECT_ROOT.name}")

    # Get selected page
    page = st.session_state.current_page

    # Route to appropriate page
    if page == "Home":
        show_home()
    elif page == "Benchmark Manager":
        show_benchmark_manager()
    elif page == "Evaluation Runner":
        show_evaluation_runner()
    elif page == "Run Results":
        show_run_results()
    elif page == "Comparison Table":
        show_comparison_enhanced()


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


def show_comparison_enhanced():
    """Enhanced comparison table."""
    from views.comparison_enhanced import show_comparison_enhanced as show_enhanced
    show_enhanced()


if __name__ == "__main__":
    main()
