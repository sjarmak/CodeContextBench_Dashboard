"""
CodeContextBench Evaluation Dashboard

Streamlit UI for:
- Browsing benchmark manifests
- Viewing experiment results
- Comparing agent performance
- Analyzing Deep Search usage
- Triggering benchmark runs
"""

import streamlit as st
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="CodeContextBench Dashboard",
    page_icon="📊",
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
    st.sidebar.title("📊 CodeContextBench")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Home",
            "📋 Benchmark Manifests",
            "📊 Experiment Results",
            "🔍 Agent Comparison",
            "🔎 Deep Search Analytics",
            "▶️ Run Benchmarks",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        f"""
        **Project Root:** `{PROJECT_ROOT.name}`

        **Quick Links:**
        - [Documentation](../docs/)
        - [Benchmarks](../benchmarks/)
        - [Agents](../agents/)
        """
    )

    # Route to appropriate page
    if page == "🏠 Home":
        show_home()
    elif page == "📋 Benchmark Manifests":
        show_manifests()
    elif page == "📊 Experiment Results":
        show_results()
    elif page == "🔍 Agent Comparison":
        show_comparison()
    elif page == "🔎 Deep Search Analytics":
        show_deep_search()
    elif page == "▶️ Run Benchmarks":
        show_run_triggers()


def show_home():
    """Home page with overview and quick stats."""
    st.title("CodeContextBench Evaluation Dashboard")

    st.markdown(
        """
    Welcome to the CodeContextBench evaluation dashboard! This interface helps you:

    - **Browse Benchmark Manifests**: View benchmark configurations, datasets, and validation logs
    - **Explore Experiment Results**: Dive into Harbor execution results and LLM judge assessments
    - **Compare Agents**: Side-by-side comparison of agent performance across metrics
    - **Analyze Deep Search**: Understand MCP Deep Search usage patterns and effectiveness
    - **Trigger Runs**: Launch benchmark lifecycle, profile runs, or evaluation pipelines
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


def show_manifests():
    """Browse benchmark manifests."""
    from pages.manifests import show_manifest_viewer

    show_manifest_viewer()


def show_results():
    """Browse experiment results."""
    from pages.results import show_results_browser

    show_results_browser()


def show_comparison():
    """Compare agents side-by-side."""
    from pages.comparison import show_comparison_view

    show_comparison_view()


def show_deep_search():
    """Analyze Deep Search usage."""
    from pages.deep_search import show_deep_search_analytics

    show_deep_search_analytics()


def show_run_triggers():
    """Trigger benchmark runs."""
    from pages.run_triggers import show_run_triggers as show_triggers

    show_triggers()


if __name__ == "__main__":
    main()
