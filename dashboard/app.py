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
        "Add Benchmark",
        "Agent Versions",
        "Evaluation Runner",
        "Comparison Table",
        "Deep Search Analytics",
        "Raw Results",
        "Generate Report",
        "LLM Judge",
        "Manifests (Legacy)",
        "Results Browser (Legacy)",
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
    elif page == "Add Benchmark":
        show_add_benchmark()
    elif page == "Agent Versions":
        show_agent_versions()
    elif page == "Evaluation Runner":
        show_evaluation_runner()
    elif page == "Raw Results":
        show_raw_results()
    elif page == "Generate Report":
        show_generate_report()
    elif page == "LLM Judge":
        show_llm_judge()
    elif page == "Comparison Table":
        show_comparison_enhanced()
    elif page == "Deep Search Analytics":
        show_deep_search()
    elif page == "Manifests (Legacy)":
        show_manifests()
    elif page == "Results Browser (Legacy)":
        show_results()


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


def show_add_benchmark():
    """Add benchmark page."""
    from views.add_benchmark import show_add_benchmark as show_add
    show_add()


def show_agent_versions():
    """Agent versions page."""
    from views.agent_versions import show_agent_versions as show_versions
    show_versions()


def show_evaluation_runner():
    """Evaluation runner page."""
    from views.evaluation_runner import show_evaluation_runner as show_runner
    show_runner()


def show_raw_results():
    """Raw results viewer."""
    st.title("Raw Results Viewer")
    st.write("View raw Harbor outputs (trajectory.json, result.json)")
    st.info("Use Legacy: Results Browser for now. Enhanced raw viewer coming soon.")


def show_generate_report():
    """Generate report page."""
    st.title("Generate Report")
    st.write("Generate evaluation reports from runs")
    st.info("Use postprocess script for now. Interactive report builder coming soon.")


def show_llm_judge():
    """LLM judge runner page."""
    st.title("LLM Judge Evaluation")
    st.write("Run LLM-as-judge evaluation on completed runs")
    st.info("Use postprocess script with --judge flag for now. Interactive judge runner coming soon.")


def show_comparison_enhanced():
    """Enhanced comparison table."""
    from views.comparison_enhanced import show_comparison_enhanced as show_enhanced
    show_enhanced()


def show_manifests():
    """Browse benchmark manifests."""
    from views.manifests import show_manifest_viewer
    show_manifest_viewer()


def show_results():
    """Browse experiment results."""
    from views.results import show_results_browser
    show_results_browser()


def show_deep_search():
    """Analyze Deep Search usage."""
    from views.deep_search import show_deep_search_analytics
    show_deep_search_analytics()


if __name__ == "__main__":
    main()
