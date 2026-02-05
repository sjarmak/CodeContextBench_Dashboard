"""
CodeContextBench Evaluation Dashboard

Full-featured benchmark management and evaluation platform.
"""

import streamlit as st
from pathlib import Path
import os
import sys

# Add project root and dashboard to Python path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ROOT = Path(__file__).resolve().parent
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

# External runs directory
EXTERNAL_RUNS_DIR = Path(os.environ.get(
    "CCB_EXTERNAL_RUNS_DIR",
    os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs")
))


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

    # Navigation items - simplified sidebar
    nav_home = ["Home"]
    nav_benchmarks = ["Benchmark Manager"]
    nav_results = ["Run Results", "Task Comparison", "Config Comparison"]
    nav_items_analysis = ["Analysis Hub", "LLM Judge", "Unified Judge", "Judge Calibration", "Annotate"]

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
    render_nav_section(nav_home)
    render_nav_section(nav_benchmarks, "Benchmarks")
    render_nav_section(nav_results, "Results")
    render_nav_section(nav_items_analysis, "Analysis")

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Project: {PROJECT_ROOT.name}")

    # Show credential status
    api_key_loaded = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if api_key_loaded:
        st.sidebar.success("Yes API Key Loaded")
    else:
        st.sidebar.error("No API Key Missing")
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
    elif page == "Task Comparison":
        show_task_comparison()
    elif page == "Config Comparison":
        show_config_comparison()
    elif page == "Analysis Hub":
        show_analysis_hub()
    elif page == "LLM Judge":
        show_llm_judge()
    elif page == "Unified Judge":
        show_unified_judge()
    elif page == "Judge Calibration":
        show_judge_calibration()
    elif page == "Annotate":
        show_annotate()


def show_home():
    """Home page with run overview grouped by folder and quick links."""
    st.title("CodeContextBench Evaluation Platform")
    st.markdown("**Benchmark management and evaluation results viewer**")
    st.markdown("---")

    # Dashboard Quick Links
    st.subheader("Dashboard Quick Links")
    col1, col2, col3, col4 = st.columns(4)

    quick_links = [
        (col1, "Benchmark Manager", "View and manage registered benchmarks"),
        (col2, "Run Results", "Browse evaluation outputs from the VM"),
        (col3, "LLM Judge", "LLM-based evaluation and rubric editing"),
        (col4, "Analysis Hub", "Statistical, cost, and comparison analysis"),
    ]

    for col, page_name, description in quick_links:
        with col:
            st.markdown(f"**{page_name}**")
            st.caption(description)
            if st.button(f"Go to {page_name}", key=f"home_nav_{page_name}"):
                st.session_state.current_page = page_name
                st.rerun()

    st.markdown("---")

    # Recent Runs grouped by folder
    st.subheader("Recent Runs")

    from dashboard.utils.home_run_scanner import (
        scan_runs_by_folder,
        FOLDER_ORDER,
        FOLDER_DESCRIPTIONS,
    )

    runs_by_folder = scan_runs_by_folder(EXTERNAL_RUNS_DIR)

    # Official and experiment expanded by default, others collapsed
    expanded_folders = {"official", "experiment"}

    for folder in FOLDER_ORDER:
        runs = runs_by_folder.get(folder, [])
        description = FOLDER_DESCRIPTIONS.get(folder, "")
        header = f"{folder.title()} ({len(runs)} runs) -- {description}"
        expanded = folder in expanded_folders

        with st.expander(header, expanded=expanded):
            _render_runs_table(runs, folder)

    st.markdown("---")

    # Registered Benchmarks (filtered)
    st.subheader("Registered Benchmarks")

    from src.benchmark.database import BenchmarkRegistry
    benchmarks = BenchmarkRegistry.list_all()

    if benchmarks:
        benchmark_data = [
            {
                "Name": bm["name"],
                "Tasks": bm["task_count"],
                "Source": _benchmark_source(bm),
                "Type": bm["adapter_type"],
            }
            for bm in benchmarks
            if bm["name"] != "hello_world_test"
        ]
        if benchmark_data:
            st.dataframe(
                benchmark_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Source": st.column_config.LinkColumn(
                        display_text=r"https?://github\.com/(.+)",
                    ),
                },
            )
        else:
            st.info("No benchmarks registered (excluding test benchmarks).")
    else:
        st.info("No benchmarks registered. Use 'Add Benchmark' to register benchmarks.")


def _benchmark_source(bm: dict) -> str:
    """Return a source string for a benchmark: 'custom' or a GitHub URL."""
    import json as _json

    KNOWN_REPOS = {
        "dibench": "https://github.com/microsoft/DI-Bench",
        "dependeval": "https://github.com/ink7-sudo/DependEval",
        "repoqa": "https://github.com/evalplus/repoqa",
        "locobench_agent": "https://github.com/SalesforceAIResearch/LoCoBench-Agent",
        "swebench_pro": "https://github.com/scaleapi/SWE-bench_Pro-os",
    }

    KNOWN_CUSTOM_REPOS = {
        "big_code_mcp": "https://github.com/sjarmak/ccb-big-code-mcp",
        "github_mined": "https://github.com/sjarmak/ccb-github-mined",
        "kubernetes_docs": "https://github.com/sjarmak/ccb-kubernetes-docs",
        "10figure": "https://github.com/sjarmak/ccb-10figure",
    }

    adapter_type = bm.get("adapter_type", "")

    # Check metadata source first
    raw_meta = bm.get("metadata")
    meta = {}
    if isinstance(raw_meta, str) and raw_meta:
        try:
            meta = _json.loads(raw_meta)
        except (ValueError, TypeError):
            pass
    elif isinstance(raw_meta, dict):
        meta = raw_meta

    source = meta.get("source", "")
    if source and "/" in source and "github" not in source.lower():
        return f"https://github.com/{source}"
    if source and "github.com" in source.lower():
        return source

    if adapter_type in KNOWN_REPOS:
        return KNOWN_REPOS[adapter_type]

    folder_name = bm.get("folder_name", "")
    if folder_name in KNOWN_CUSTOM_REPOS:
        return KNOWN_CUSTOM_REPOS[folder_name]

    return "custom"


def _render_runs_table(runs, folder):
    """Render a dataframe of runs with View buttons."""
    if not runs:
        st.caption("No runs found.")
        return

    import pandas as pd

    rows = []
    for run in runs:
        agent_short = run.agent_import_path.split(":")[-1] if ":" in run.agent_import_path else run.agent_import_path
        model_short = run.model_name.split("/")[-1] if "/" in run.model_name else run.model_name
        rows.append({
            "Name": run.name,
            "Model": model_short,
            "Agent": agent_short,
            "Modes": ", ".join(run.modes),
            "Tasks": run.task_count,
            "Date": run.timestamp,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_benchmark_manager():
    """Benchmark manager page."""
    from views.benchmark_manager import show_benchmark_manager as show_manager
    show_manager()


def show_run_results():
    """Run results viewer page."""
    from views.run_results import show_run_results as show_results
    show_results()


def show_task_comparison():
    """Task comparison view for baseline vs MCP paired analysis."""
    from dashboard.views.task_comparison import show_task_comparison as show_comparison
    show_comparison()


def show_config_comparison():
    """Config comparison view for cross-config side-by-side analysis."""
    from views.config_comparison import show_config_comparison as show_cc
    show_cc()


def show_analysis_hub():
    """Analysis hub entry point."""
    from views.analysis_hub import show_analysis_hub as show_hub
    show_hub()


def show_llm_judge():
    """LLM Judge configuration and results view."""
    from views.analysis_llm_judge import show_llm_judge as show_judge
    show_judge()


def show_unified_judge():
    """Unified LLM Judge view for all evaluation modes."""
    from views.judge_unified import show_judge_unified
    show_judge_unified()


def show_judge_calibration():
    """Judge calibration and quality metrics view."""
    from views.judge_calibration import show_judge_calibration as show_calib
    show_calib()


def show_annotate():
    """Human annotation collection view."""
    from views.judge_annotation import show_judge_annotation
    show_judge_annotation()


if __name__ == "__main__":
    main()
