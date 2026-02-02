"""
CodeContextBench Evaluation Dashboard

Simplified 5-view dashboard for the CodeContextBench paper.
Views: Home, Results Explorer, Comparison, LLM Judge, Export.
"""

import subprocess
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

# Default pipeline output directory
PIPELINE_OUTPUT_DIR = PROJECT_ROOT / "output"


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

    # Navigation items - 5 views
    nav_items = ["Home", "Results Explorer", "Comparison", "LLM Judge", "Export"]

    for item in nav_items:
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
    elif page == "Results Explorer":
        show_results_explorer()
    elif page == "Comparison":
        show_comparison()
    elif page == "LLM Judge":
        show_llm_judge()
    elif page == "Export":
        show_export()


def show_home():
    """Home page with run overview grouped by folder and pipeline trigger."""
    st.title("CodeContextBench Evaluation Platform")
    st.markdown("**Analysis pipeline and evaluation results viewer**")
    st.markdown("---")

    # Dashboard Quick Links
    st.subheader("Quick Links")
    col1, col2, col3, col4 = st.columns(4)

    quick_links = [
        (col1, "Results Explorer", "Browse per-trial results with filtering"),
        (col2, "Comparison", "Interactive analysis matching paper sections"),
        (col3, "LLM Judge", "Review and re-run judge evaluations"),
        (col4, "Export", "Download publication artifacts"),
    ]

    for col, page_name, description in quick_links:
        with col:
            st.markdown(f"**{page_name}**")
            st.caption(description)
            if st.button(f"Go to {page_name}", key=f"home_nav_{page_name}"):
                st.session_state.current_page = page_name
                st.rerun()

    st.markdown("---")

    # Run Analysis Pipeline section
    _render_pipeline_section()

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


def _render_pipeline_section():
    """Render the Run Analysis Pipeline section on the Home page."""
    st.subheader("Run Analysis Pipeline")

    col_cfg, col_action = st.columns([3, 1])

    with col_cfg:
        runs_dir = st.text_input(
            "Runs directory",
            value=str(EXTERNAL_RUNS_DIR),
            key="pipeline_runs_dir",
        )
        output_dir = st.text_input(
            "Output directory",
            value=str(PIPELINE_OUTPUT_DIR),
            key="pipeline_output_dir",
        )
        skip_judge = st.checkbox("Skip LLM Judge step", value=True, key="pipeline_skip_judge")

    with col_action:
        st.markdown("")  # spacing
        st.markdown("")
        run_clicked = st.button(
            "Run Analysis Pipeline",
            key="pipeline_run_btn",
            type="primary",
        )

    if run_clicked:
        _run_pipeline(runs_dir, output_dir, skip_judge)

    # Show previous pipeline output if it exists
    output_path = Path(output_dir) if output_dir else PIPELINE_OUTPUT_DIR
    if output_path.exists() and any(output_path.iterdir()):
        st.success(f"Pipeline artifacts available at: `{output_path}`")
        tables_dir = output_path / "tables"
        figures_dir = output_path / "figures"
        table_count = len(list(tables_dir.glob("*.tex"))) if tables_dir.exists() else 0
        figure_count = len(list(figures_dir.glob("*.*"))) if figures_dir.exists() else 0
        st.caption(f"{table_count} tables, {figure_count} figures")


def _run_pipeline(runs_dir: str, output_dir: str, skip_judge: bool):
    """Execute the analysis pipeline as a subprocess and show progress."""
    cmd = [
        sys.executable, "-m", "scripts.ccb_pipeline",
        "--runs-dir", runs_dir,
        "--output-dir", output_dir,
    ]
    if skip_judge:
        cmd.append("--skip-judge")

    with st.spinner("Running analysis pipeline..."):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=300,
            )
            if result.returncode == 0:
                st.success("Pipeline completed successfully.")
                if result.stdout.strip():
                    st.code(result.stdout, language="text")
            else:
                st.error("Pipeline failed.")
                if result.stderr.strip():
                    st.code(result.stderr, language="text")
                if result.stdout.strip():
                    st.code(result.stdout, language="text")
        except subprocess.TimeoutExpired:
            st.error("Pipeline timed out after 5 minutes.")
        except FileNotFoundError:
            st.error("Could not find Python executable to run pipeline.")


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


def show_results_explorer():
    """Results Explorer view - placeholder until US-014."""
    st.title("Results Explorer")
    st.info("This view will be implemented in US-014. It will load experiment_metrics.json and provide filtering by benchmark, config, and outcome.")


def show_comparison():
    """Comparison view - placeholder until US-015."""
    st.title("Comparison Analysis")
    st.info("This view will be implemented in US-015. It will show interactive comparison with tabs matching paper sections 4.1-4.5.")


def show_llm_judge():
    """LLM Judge view - placeholder until US-016."""
    st.title("LLM Judge")
    st.info("This view will be implemented in US-016. It will show judge results and allow re-running with different templates.")


def show_export():
    """Export view - placeholder until US-017."""
    st.title("Export Artifacts")
    st.info("This view will be implemented in US-017. It will list and preview publication artifacts from output/.")


if __name__ == "__main__":
    main()
