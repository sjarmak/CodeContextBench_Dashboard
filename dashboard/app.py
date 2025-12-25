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

    # Sidebar navigation
    st.sidebar.title("CodeContextBench")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        [
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
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Project: {PROJECT_ROOT.name}")

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
    """Home page with overview and quick stats."""
    st.title("CodeContextBench Evaluation Platform")

    st.markdown(
        """
    **Full-featured benchmark management and evaluation platform**

    ### Benchmark Management
    - Manage 7 registered benchmarks (Kubernetes, GitHub, Big Code, DIBench, DependEval, RepoQA, Synthetic)
    - Oracle validation for task sanity checking
    - Task selection and profiles
    - Add new benchmarks dynamically

    ### Agent Configuration
    - Manage agent versions with model, prompt, and tool configurations
    - Track agent modifications for reproducibility
    - Version control for experimental changes

    ### Evaluation Execution
    - Run evaluations with configurable agents and task selection
    - Live progress monitoring with pause/resume capability
    - Background execution with real-time updates
    - Concurrent task execution

    ### Analysis & Reporting
    - Comprehensive comparison tables with tokens, costs, pass rates
    - Deep Search analytics and query patterns
    - LLM-as-judge evaluation integration
    - Export results for further analysis
    """
    )

    st.markdown("---")

    # Quick stats
    st.subheader("📈 Quick Stats")

    col1, col2, col3, col4 = st.columns(4)

    # Count benchmarks
    benchmarks_dir = PROJECT_ROOT / "benchmarks"
    benchmark_count = len([d for d in benchmarks_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])

    # Count experiments
    jobs_dir = PROJECT_ROOT / "jobs"
    experiment_count = len([d for d in jobs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]) if jobs_dir.exists() else 0

    # Count agents
    agents_dir = PROJECT_ROOT / "agents"
    agent_files = list(agents_dir.glob("*.py")) if agents_dir.exists() else []
    agent_count = len([f for f in agent_files if f.name not in ["__init__.py", "__pycache__"]])

    # Count manifests
    manifest_count = len(list(benchmarks_dir.rglob("MANIFEST.json"))) if benchmarks_dir.exists() else 0

    with col1:
        st.metric("Benchmarks", benchmark_count)

    with col2:
        st.metric("Experiments", experiment_count)

    with col3:
        st.metric("Agents", agent_count)

    with col4:
        st.metric("Manifests", manifest_count)

    st.markdown("---")

    # Recent activity
    st.subheader("🕒 Recent Activity")

    if jobs_dir.exists():
        recent_dirs = sorted(
            [d for d in jobs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )[:5]

        if recent_dirs:
            for exp_dir in recent_dirs:
                # Check for result files
                result_files = list(exp_dir.rglob("result.json"))
                st.markdown(
                    f"- **{exp_dir.name}** - {len(result_files)} runs - {exp_dir.stat().st_mtime}"
                )
        else:
            st.info("No recent experiments found.")
    else:
        st.info("No experiments directory found.")


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
