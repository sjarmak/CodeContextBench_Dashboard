"""
LLM Judge Analysis View

Configure and run LLM-based evaluation of agent run results.
View and compare judge evaluation reports.

Enhanced with:
- Oracle data integration for reference-guided evaluation
- MCP tool effectiveness analysis
- Multi-judge voting for consistency
- 3-point scoring (pass/partial/fail)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import oracle loader from run_results
try:
    from dashboard.views.run_results import (
        analyze_mcp_tool_usage,
        load_locobench_oracle,
    )
except ImportError:
    load_locobench_oracle = None
    analyze_mcp_tool_usage = None

# External jobs directory - same as run_results
EXTERNAL_JOBS_DIR = Path(
    os.environ.get(
        "CCB_EXTERNAL_JOBS_DIR",
        os.path.expanduser("~/evals/custom_agents/agents/claudecode/jobs"),
    )
)

# Default rubrics for LLM judge
DEFAULT_RUBRICS = {
    "code_quality": {
        "name": "Code Quality",
        "description": "Evaluate the quality and appropriateness of code changes.",
        "rubric": {
            0: "Changes are incorrect, harmful, or unrelated to the task",
            1: "Changes attempt to address the task but are largely incorrect",
            2: "Changes partially address the task with some issues",
            3: "Changes correctly address the task with minor issues",
            4: "Changes are correct, minimal, and well-implemented",
        },
        "weight": 1.0,
    },
    "correctness": {
        "name": "Solution Correctness",
        "description": "Does the solution correctly address the stated issue or requirement?",
        "rubric": {
            0: "Solution does not address the issue at all",
            1: "Solution attempts to address the issue but is incorrect",
            2: "Solution partially addresses the issue",
            3: "Solution mostly addresses the issue with edge cases missed",
            4: "Solution fully and correctly addresses the issue",
        },
        "weight": 1.5,
    },
    "completeness": {
        "name": "Completeness",
        "description": "Are all requirements from the task fully addressed?",
        "rubric": {
            0: "No requirements are met",
            1: "Few requirements are met (<25%)",
            2: "Some requirements are met (25-75%)",
            3: "Most requirements are met (75-99%)",
            4: "All requirements are fully met",
        },
        "weight": 1.0,
    },
    "efficiency": {
        "name": "Change Efficiency",
        "description": "Are the changes minimal and focused, without unnecessary modifications?",
        "rubric": {
            0: "Changes are excessive or include unrelated modifications",
            1: "Changes include significant unnecessary code",
            2: "Changes include some unnecessary modifications",
            3: "Changes are mostly focused with minor extras",
            4: "Changes are minimal and precisely targeted",
        },
        "weight": 0.6,
    },
    "retrieval_quality": {
        "name": "Retrieval Quality",
        "description": "Evaluate the agent's use of code search and retrieval tools.",
        "rubric": {
            0: "No relevant searches, missed obvious queries",
            1: "Some relevant searches but missed key areas",
            2: "Found main relevant code but could be more thorough",
            3: "Comprehensive search strategy, found key files",
            4: "Optimal search strategy, efficient queries, perfect context",
        },
        "weight": 0.8,
    },
    "architecture": {
        "name": "Architecture Preservation",
        "description": "Evaluate whether changes respect existing architecture and patterns.",
        "rubric": {
            0: "Changes break or ignore existing architecture entirely",
            1: "Changes significantly deviate from existing patterns",
            2: "Changes partially follow existing patterns",
            3: "Changes mostly follow existing patterns with minor deviations",
            4: "Changes fully respect and integrate with existing architecture",
        },
        "weight": 0.8,
    },
}

# Available LLM models for judging
JUDGE_MODELS = [
    ("claude-haiku-4-5-20251001", "Claude Haiku 4.5 (Fast, Low Cost)"),
    ("claude-sonnet-4-20250514", "Claude Sonnet 4 (Balanced)"),
    ("claude-opus-4-20250514", "Claude Opus 4 (Most Capable)"),
]


def get_judge_results_dir(project_root: Path) -> Path:
    """Get the directory where judge results are stored."""
    return project_root / "data" / "judge_results"


def get_saved_rubrics(project_root: Path) -> dict:
    """Load saved custom rubrics from config file."""
    rubrics_file = project_root / "data" / "judge_rubrics.json"
    if rubrics_file.exists():
        try:
            with open(rubrics_file) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_rubric(project_root: Path, rubric_id: str, rubric_data: dict):
    """Save a custom rubric to config file."""
    rubrics_file = project_root / "data" / "judge_rubrics.json"
    rubrics_file.parent.mkdir(parents=True, exist_ok=True)

    existing = get_saved_rubrics(project_root)
    existing[rubric_id] = rubric_data

    with open(rubrics_file, "w") as f:
        json.dump(existing, f, indent=2)


def load_judge_reports(project_root: Path) -> list:
    """Load all judge report files."""
    results_dir = get_judge_results_dir(project_root)
    reports = []

    if not results_dir.exists():
        return reports

    for report_file in sorted(results_dir.glob("*_judge.json"), reverse=True):
        try:
            with open(report_file) as f:
                data = json.load(f)
                data["_file"] = report_file.name
                data["_path"] = str(report_file)
                reports.append(data)
        except Exception as e:
            st.warning(f"Failed to load {report_file.name}: {e}")

    return reports


def delete_judge_report(report_path: str) -> bool:
    """Delete a judge report file."""
    try:
        path = Path(report_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        st.error(f"Failed to delete report: {e}")
        return False


def show_llm_judge():
    """Display the LLM Judge configuration and results view."""

    st.title("LLM Judge")
    st.markdown(
        "**Configure, run, and compare LLM-based evaluations of agent run results.**"
    )
    st.markdown("---")

    project_root = st.session_state.get(
        "project_root", Path(__file__).parent.parent.parent
    )

    # Initialize session state for judge config
    if "judge_config" not in st.session_state:
        st.session_state.judge_config = {
            "model": JUDGE_MODELS[0][0],
            "selected_dimensions": ["correctness", "code_quality", "completeness"],
            "custom_rubrics": {},
        }

    # Tabs for different sections
    tabs = st.tabs(["🧪 Run Evaluation", "📊 View Reports", "📋 Rubric Configuration"])

    with tabs[0]:
        show_evaluation_config(project_root)

    with tabs[1]:
        show_reports_view(project_root)

    with tabs[2]:
        show_rubric_config(project_root)


def show_reports_view(project_root: Path):
    """Display and compare judge reports."""

    st.subheader("Judge Evaluation Reports")

    # Add refresh button at the top
    col_refresh, col_spacer = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_reports"):
            st.rerun()

    reports = load_judge_reports(project_root)

    if not reports:
        st.info("No judge reports found. Run an evaluation first.")
        return

    st.caption(f"Found {len(reports)} report(s)")

    # Report selector
    report_names = [r.get("_file", "Unknown") for r in reports]

    # Management controls
    col1, col2 = st.columns([3, 1])
    with col1:
        view_mode = st.radio(
            "View Mode",
            ["Single Report", "Compare Reports"],
            horizontal=True,
            key="judge_view_mode",
        )
    with col2:
        # Delete report functionality
        with st.expander("🗑️ Manage"):
            report_to_delete = st.selectbox(
                "Delete Report",
                [""] + report_names,
                key="report_to_delete",
                help="Select a report to delete",
            )
            if report_to_delete:
                report = next(
                    (r for r in reports if r.get("_file") == report_to_delete), None
                )
                if report and st.button(
                    "🗑️ Delete", type="secondary", key="delete_report_btn"
                ):
                    if delete_judge_report(report.get("_path", "")):
                        st.success(f"Deleted {report_to_delete}")
                        st.rerun()

    if view_mode == "Single Report":
        show_single_report(reports, report_names)
    else:
        show_report_comparison(reports, report_names)


def show_single_report(reports: list, report_names: list):
    """Display a single judge report in detail."""

    selected_report = st.selectbox(
        "Select Report", report_names, key="single_report_select"
    )

    if not selected_report:
        return

    report = next((r for r in reports if r.get("_file") == selected_report), None)
    if not report:
        return

    # Report header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Experiment", report.get("experiment", "Unknown"))
    with col2:
        st.metric(
            "Model",
            report.get("model", "Unknown").split("-")[1]
            if "-" in report.get("model", "")
            else report.get("model", "Unknown"),
        )
    with col3:
        st.metric("Tasks Evaluated", len(report.get("results", [])))

    st.markdown("")

    # Dimensions evaluated
    dims = report.get("dimensions", [])
    if dims:
        dim_names = [DEFAULT_RUBRICS.get(d, {}).get("name", d) for d in dims]
        st.markdown(f"**Dimensions:** {', '.join(dim_names)}")

    st.markdown(f"**Timestamp:** {report.get('timestamp', 'Unknown')[:19]}")

    st.markdown("---")

    # Results summary
    st.subheader("Results Summary")

    results = report.get("results", [])
    if not results:
        st.info("No results in this report.")
        return

    # Build summary dataframe
    summary_data = []
    for r in results:
        row = {"Task": r.get("task", "Unknown")}
        scores = r.get("scores", {})

        # Calculate average score
        score_values = [
            s.get("score", 0) for s in scores.values() if isinstance(s, dict)
        ]
        avg_score = sum(score_values) / len(score_values) if score_values else 0

        for dim, score_data in scores.items():
            dim_name = DEFAULT_RUBRICS.get(dim, {}).get("name", dim)
            if isinstance(score_data, dict):
                row[dim_name] = score_data.get("score", "N/A")
            else:
                row[dim_name] = score_data

        row["Avg Score"] = f"{avg_score:.1f}"

        if r.get("error"):
            row["Error"] = "⚠️"

        summary_data.append(row)

    df = pd.DataFrame(summary_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Aggregate statistics
    st.markdown("---")
    st.subheader("Aggregate Statistics")

    col1, col2 = st.columns(2)

    with col1:
        # Per-dimension averages
        dim_avgs = {}
        for r in results:
            for dim, score_data in r.get("scores", {}).items():
                if isinstance(score_data, dict) and "score" in score_data:
                    if dim not in dim_avgs:
                        dim_avgs[dim] = []
                    dim_avgs[dim].append(score_data["score"])

        if dim_avgs:
            avg_data = []
            for dim, scores in dim_avgs.items():
                avg_data.append(
                    {
                        "Dimension": DEFAULT_RUBRICS.get(dim, {}).get("name", dim),
                        "Avg Score": f"{sum(scores) / len(scores):.2f}",
                        "Min": min(scores),
                        "Max": max(scores),
                    }
                )
            st.markdown("**Per-Dimension Averages**")
            st.dataframe(avg_data, use_container_width=True, hide_index=True)

    with col2:
        # Score distribution
        all_scores = []
        for r in results:
            for score_data in r.get("scores", {}).values():
                if isinstance(score_data, dict) and "score" in score_data:
                    all_scores.append(score_data["score"])

        if all_scores:
            st.markdown("**Score Distribution**")
            score_counts = {i: all_scores.count(i) for i in range(5)}
            chart_data = pd.DataFrame(
                {
                    "Score": list(score_counts.keys()),
                    "Count": list(score_counts.values()),
                }
            )
            st.bar_chart(chart_data, x="Score", y="Count")

    # Detailed task view
    st.markdown("---")
    st.subheader("Task Details")

    task_names = [r.get("task", "Unknown") for r in results]
    selected_task = st.selectbox("Select Task", task_names, key="report_task_select")

    if selected_task:
        task_result = next((r for r in results if r.get("task") == selected_task), None)
        if task_result:
            if task_result.get("error"):
                st.error(f"Error: {task_result['error']}")

            for dim, score_data in task_result.get("scores", {}).items():
                dim_info = DEFAULT_RUBRICS.get(dim, {})
                dim_name = dim_info.get("name", dim)

                if isinstance(score_data, dict):
                    score = score_data.get("score", "N/A")
                    reasoning = score_data.get("reasoning", "No reasoning provided")

                    with st.expander(f"**{dim_name}**: Score {score}/4", expanded=True):
                        st.markdown(f"**Reasoning:** {reasoning}")

                        # Show rubric for context
                        rubric = dim_info.get("rubric", {})
                        if rubric and score != "N/A":
                            st.caption(
                                f"Rubric for score {score}: {rubric.get(score, 'N/A')}"
                            )


def show_report_comparison(reports: list, report_names: list):
    """Compare multiple judge reports side by side."""

    st.markdown("Select reports to compare:")

    selected_reports = st.multiselect(
        "Reports",
        report_names,
        default=report_names[:2] if len(report_names) >= 2 else report_names,
        key="compare_reports_select",
        label_visibility="collapsed",
    )

    if len(selected_reports) < 2:
        st.info("Select at least 2 reports to compare.")
        return

    # Load selected reports
    compare_data = []
    for report_name in selected_reports:
        report = next((r for r in reports if r.get("_file") == report_name), None)
        if report:
            compare_data.append(report)

    if not compare_data:
        return

    st.markdown("---")

    # Comparison header
    st.subheader("Report Comparison")

    # Overview comparison
    overview_data = []
    for report in compare_data:
        results = report.get("results", [])

        # Calculate overall average
        all_scores = []
        for r in results:
            for score_data in r.get("scores", {}).values():
                if isinstance(score_data, dict) and "score" in score_data:
                    all_scores.append(score_data["score"])

        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        overview_data.append(
            {
                "Report": report.get("_file", "Unknown"),
                "Experiment": report.get("experiment", "Unknown"),
                "Model": report.get("model", "Unknown").split("-")[1]
                if "-" in report.get("model", "")
                else "Unknown",
                "Tasks": len(results),
                "Avg Score": f"{avg_score:.2f}",
            }
        )

    st.dataframe(overview_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Per-dimension comparison
    st.subheader("Per-Dimension Comparison")

    # Gather all dimensions across reports
    all_dims = set()
    for report in compare_data:
        all_dims.update(report.get("dimensions", []))

    dim_comparison = []
    for dim in sorted(all_dims):
        row = {"Dimension": DEFAULT_RUBRICS.get(dim, {}).get("name", dim)}

        for report in compare_data:
            results = report.get("results", [])
            dim_scores = []
            for r in results:
                score_data = r.get("scores", {}).get(dim, {})
                if isinstance(score_data, dict) and "score" in score_data:
                    dim_scores.append(score_data["score"])

            avg = sum(dim_scores) / len(dim_scores) if dim_scores else 0
            exp_name = report.get("experiment", "Unknown")[:20]
            row[exp_name] = f"{avg:.2f}"

        dim_comparison.append(row)

    if dim_comparison:
        st.dataframe(dim_comparison, use_container_width=True, hide_index=True)

    # Visual comparison
    st.markdown("---")
    st.subheader("Visual Comparison")

    # Build chart data
    chart_rows = []
    for report in compare_data:
        exp_name = report.get("experiment", "Unknown")[:15]
        results = report.get("results", [])

        for dim in sorted(all_dims):
            dim_scores = []
            for r in results:
                score_data = r.get("scores", {}).get(dim, {})
                if isinstance(score_data, dict) and "score" in score_data:
                    dim_scores.append(score_data["score"])

            avg = sum(dim_scores) / len(dim_scores) if dim_scores else 0
            chart_rows.append(
                {
                    "Experiment": exp_name,
                    "Dimension": DEFAULT_RUBRICS.get(dim, {}).get("name", dim)[:15],
                    "Score": avg,
                }
            )

    if chart_rows:
        chart_df = pd.DataFrame(chart_rows)

        # Pivot for grouped bar chart
        pivot_df = chart_df.pivot(
            index="Dimension", columns="Experiment", values="Score"
        )
        st.bar_chart(pivot_df)

    # Task-by-task comparison (for common tasks)
    st.markdown("---")
    st.subheader("Task-by-Task Comparison")

    # Find common tasks
    task_sets = [
        set(r.get("task", "") for r in report.get("results", []))
        for report in compare_data
    ]
    common_tasks = set.intersection(*task_sets) if task_sets else set()

    if common_tasks:
        st.markdown(f"**{len(common_tasks)} common tasks found**")

        task_comparison = []
        for task in sorted(common_tasks):
            row = {"Task": task[:40]}

            for report in compare_data:
                task_result = next(
                    (r for r in report.get("results", []) if r.get("task") == task),
                    None,
                )
                if task_result:
                    scores = task_result.get("scores", {})
                    score_values = [
                        s.get("score", 0)
                        for s in scores.values()
                        if isinstance(s, dict)
                    ]
                    avg = sum(score_values) / len(score_values) if score_values else 0
                    exp_name = report.get("experiment", "Unknown")[:20]
                    row[exp_name] = f"{avg:.1f}"

            task_comparison.append(row)

        st.dataframe(task_comparison, use_container_width=True, hide_index=True)
    else:
        st.info("No common tasks found between selected reports.")


def show_evaluation_config(project_root: Path):
    """Show evaluation configuration and run interface."""

    st.subheader("Run LLM Judge Evaluation")

    config = st.session_state.judge_config

    # Model and dimension selection
    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("**LLM Model**")
        model_options = [m[0] for m in JUDGE_MODELS]
        model_labels = {m[0]: m[1] for m in JUDGE_MODELS}
        selected_model = st.selectbox(
            "Select Model",
            model_options,
            format_func=lambda x: model_labels[x],
            index=model_options.index(config["model"]),
            key="eval_judge_model_select",
            label_visibility="collapsed",
        )
        config["model"] = selected_model

    with col2:
        st.markdown("**Evaluation Dimensions**")
        available_dims = list(DEFAULT_RUBRICS.keys())
        selected_dims = st.multiselect(
            "Select dimensions to evaluate",
            available_dims,
            default=config["selected_dimensions"],
            format_func=lambda x: DEFAULT_RUBRICS[x]["name"],
            key="eval_judge_dims_select",
            label_visibility="collapsed",
        )
        config["selected_dimensions"] = selected_dims

    st.markdown("---")

    # Experiment and task selection
    st.markdown("**Select Results to Evaluate**")

    experiments = []
    paired_experiments = {}  # Track which experiments are paired (baseline/deepsearch)

    if EXTERNAL_JOBS_DIR.exists():
        for d in sorted(
            EXTERNAL_JOBS_DIR.iterdir(),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        ):
            if not d.is_dir() or d.name.startswith("."):
                continue

            # Check for paired experiment structure (baseline/ and/or deepsearch/)
            baseline_dir = d / "baseline"
            deepsearch_dir = d / "deepsearch"

            if baseline_dir.exists() or deepsearch_dir.exists():
                # This is a paired experiment - add both modes as options
                if baseline_dir.exists():
                    exp_name = f"{d.name} [baseline]"
                    experiments.append(exp_name)
                    paired_experiments[exp_name] = ("baseline", baseline_dir)
                if deepsearch_dir.exists():
                    exp_name = f"{d.name} [deepsearch]"
                    experiments.append(exp_name)
                    paired_experiments[exp_name] = ("deepsearch", deepsearch_dir)
            elif (d / "result.json").exists():
                # Standard Harbor format
                experiments.append(d.name)

    if not experiments:
        st.info(
            "No experiments found. Check that CCB_EXTERNAL_JOBS_DIR is set correctly."
        )
        st.caption(f"Current directory: {EXTERNAL_JOBS_DIR}")
        return

    selected_exp = st.selectbox("Experiment", experiments, key="eval_exp_select")

    if not selected_exp:
        return

    # Determine experiment directory based on type
    if selected_exp in paired_experiments:
        mode, mode_dir = paired_experiments[selected_exp]
        # For paired experiments, find tasks inside timestamp subdirectories
        task_dirs = []
        for subdir in mode_dir.iterdir():
            if not subdir.is_dir():
                continue
            # Check if this is a timestamp directory containing task dirs
            for item in subdir.iterdir():
                if item.is_dir() and (item / "result.json").exists():
                    task_dirs.append(f"{subdir.name}/{item.name}")
            # Or if this directory itself is a task
            if (subdir / "result.json").exists():
                task_dirs.append(subdir.name)
    else:
        # Standard Harbor format
        exp_dir = EXTERNAL_JOBS_DIR / selected_exp
        task_dirs = [
            d.name
            for d in exp_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".") and (d / "agent").exists()
        ]

    if not task_dirs:
        st.info("No task instances found in this experiment.")
        return

    # Initialize session state for task selection if needed
    if "eval_tasks_select" not in st.session_state:
        st.session_state.eval_tasks_select = (
            task_dirs[:5] if len(task_dirs) > 5 else task_dirs
        )

    # Handle select all - must be done BEFORE widget is created
    def select_all_tasks():
        st.session_state.eval_tasks_select = task_dirs

    def clear_all_tasks():
        st.session_state.eval_tasks_select = []

    st.caption(f"Found {len(task_dirs)} tasks in this experiment")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        selected_tasks = st.multiselect(
            "Tasks to evaluate",
            task_dirs,
            key="eval_tasks_select",
        )
    with col2:
        st.markdown("")
        st.markdown("")
        st.button("Select All", on_click=select_all_tasks, key="select_all_btn")
    with col3:
        st.markdown("")
        st.markdown("")
        st.button("Clear", on_click=clear_all_tasks, key="clear_all_btn")

    st.markdown("")

    # Enhanced mode options
    st.markdown("**Evaluation Options**")
    col1, col2, col3 = st.columns(3)

    with col1:
        use_enhanced = st.checkbox(
            "Use Enhanced Judge",
            value=config.get("use_enhanced", True),
            help="Use oracle-guided evaluation with 3-point scoring",
            key="use_enhanced_judge",
        )
        config["use_enhanced"] = use_enhanced

    with col2:
        enable_voting = st.checkbox(
            "Enable Voting (3 rounds)",
            value=config.get("enable_voting", False),
            help="Run evaluation 3 times and take majority vote (3x cost)",
            key="enable_voting",
            disabled=not use_enhanced,
        )
        config["enable_voting"] = enable_voting

    with col3:
        if use_enhanced:
            # Add MCP effectiveness dimension if enhanced mode
            if "mcp_effectiveness" not in available_dims:
                available_dims.append("mcp_effectiveness")
                DEFAULT_RUBRICS["mcp_effectiveness"] = {
                    "name": "MCP Tool Effectiveness",
                    "description": "Evaluate agent's use of MCP/Sourcegraph tools",
                    "rubric": {
                        0: "Ineffective",
                        1: "Partially effective",
                        2: "Effective",
                    },
                    "weight": 0.8,
                }
            st.caption("✓ Oracle data will be used if available")

    st.markdown("")

    # Cost estimate and run button
    col1, col2, col3 = st.columns(3)

    voting_multiplier = 3 if enable_voting else 1
    base_cost = 0.002 if not use_enhanced else 0.003  # Enhanced slightly more tokens

    with col1:
        estimated_cost = (
            len(selected_tasks) * len(selected_dims) * base_cost * voting_multiplier
        )
        st.caption(f"💰 Estimated cost: ~${estimated_cost:.3f}")

    with col2:
        st.caption(
            f"📊 {len(selected_tasks)} tasks × {len(selected_dims)} dims × {voting_multiplier}x"
        )

    with col3:
        run_button = st.button(
            "🚀 Run Evaluation", key="run_judge_eval_btn", type="primary"
        )

    if run_button:
        if not selected_tasks:
            st.error("Please select at least one task.")
        elif not selected_dims:
            st.error("Please select at least one evaluation dimension.")
        else:
            run_llm_judge_evaluation(
                project_root,
                selected_exp,
                selected_tasks,
                config,
                paired_experiments,
            )


def show_rubric_config(project_root: Path):
    """Show rubric configuration interface."""

    st.subheader("Rubric Configuration")

    rubric_tabs = st.tabs(["Built-in Rubrics", "Custom Rubrics", "Add New Rubric"])

    with rubric_tabs[0]:
        st.markdown("**Default Evaluation Rubrics**")

        for dim_id, dim in DEFAULT_RUBRICS.items():
            with st.expander(
                f"**{dim.get('name')}** (weight: {dim.get('weight', 1.0)})"
            ):
                st.markdown(dim.get("description", ""))
                st.markdown("**Scoring Rubric:**")
                for score, desc in sorted(dim.get("rubric", {}).items()):
                    st.text(f"  {score}: {desc}")

    with rubric_tabs[1]:
        st.markdown("**Saved Custom Rubrics**")
        custom_rubrics = get_saved_rubrics(project_root)

        if custom_rubrics:
            for rubric_id, rubric_data in custom_rubrics.items():
                with st.expander(f"**{rubric_data.get('name', rubric_id)}**"):
                    st.markdown(rubric_data.get("description", ""))
                    st.markdown(f"**Weight:** {rubric_data.get('weight', 1.0)}")
                    st.markdown("**Scoring Rubric:**")
                    for score, desc in sorted(rubric_data.get("rubric", {}).items()):
                        st.text(f"  {score}: {desc}")

                    if st.button(f"Delete", key=f"delete_rubric_{rubric_id}"):
                        del custom_rubrics[rubric_id]
                        rubrics_file = project_root / "data" / "judge_rubrics.json"
                        with open(rubrics_file, "w") as f:
                            json.dump(custom_rubrics, f, indent=2)
                        st.success(
                            f"Deleted rubric: {rubric_data.get('name', rubric_id)}"
                        )
                        st.rerun()
        else:
            st.info("No custom rubrics saved. Use 'Add New Rubric' to create one.")

    with rubric_tabs[2]:
        st.markdown("**Create New Rubric**")

        new_rubric_name = st.text_input("Rubric Name", key="new_rubric_name")
        new_rubric_desc = st.text_area("Description", key="new_rubric_desc", height=60)
        new_rubric_weight = st.slider(
            "Weight", 0.1, 2.0, 1.0, 0.1, key="new_rubric_weight"
        )

        st.markdown("**Scoring Rubric** (0-4 scale)")
        scores = {}
        for i in range(5):
            scores[i] = st.text_input(
                f"Score {i}",
                key=f"new_rubric_score_{i}",
                placeholder=f"Description for score {i}",
            )

        if st.button("💾 Save Rubric", key="save_new_rubric"):
            if new_rubric_name and all(scores.values()):
                rubric_id = new_rubric_name.lower().replace(" ", "_")
                rubric_data = {
                    "name": new_rubric_name,
                    "description": new_rubric_desc,
                    "weight": new_rubric_weight,
                    "rubric": {int(k): v for k, v in scores.items()},
                }
                save_rubric(project_root, rubric_id, rubric_data)
                st.success(f"✓ Rubric '{new_rubric_name}' saved!")
                st.rerun()
            else:
                st.error("Please fill in the rubric name and all score descriptions.")


def extract_code_changes_from_trace(trace_file: Path, max_chars: int = 15000) -> str:
    """
    Extract actual code changes (diffs/patches) from a claude-code.txt trace file.

    The trace contains JSON messages with Edit tool calls that include:
    - oldString/newString: the before/after content
    - structuredPatch: unified diff format

    Returns a summary of actual code changes for LLM judge evaluation.
    """
    if not trace_file.exists():
        return ""

    try:
        with open(trace_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Find all Edit tool calls and their results
        code_changes = []

        # Look for Edit tool patterns in the JSON trace
        # Pattern: "name":"Edit" followed by input with oldString/newString
        import re

        # Find Edit tool uses with their file paths and changes
        edit_pattern = r'"name"\s*:\s*"Edit"[^}]*"input"\s*:\s*\{[^}]*"file_path"\s*:\s*"([^"]+)"[^}]*"old_string"\s*:\s*"([^"]*)"[^}]*"new_string"\s*:\s*"([^"]*)"'

        for match in re.finditer(edit_pattern, content, re.DOTALL):
            file_path = match.group(1)
            # Unescape the strings
            old_str = match.group(2).replace("\\n", "\n").replace("\\t", "\t")[:500]
            new_str = match.group(3).replace("\\n", "\n").replace("\\t", "\t")[:500]

            if old_str or new_str:
                code_changes.append(
                    f"File: {file_path}\n--- Old:\n{old_str}\n+++ New:\n{new_str}\n"
                )

        # Also look for structuredPatch in tool results
        patch_pattern = r'"structuredPatch"\s*:\s*\[(.*?)\]'
        for match in re.finditer(patch_pattern, content, re.DOTALL):
            patch_content = match.group(1)
            if '"lines"' in patch_content:
                # Extract the lines array
                lines_match = re.search(
                    r'"lines"\s*:\s*\[(.*?)\]', patch_content, re.DOTALL
                )
                if lines_match:
                    lines = lines_match.group(1)
                    # Clean up and format
                    code_changes.append(f"Patch:\n{lines[:1000]}\n")

        if code_changes:
            result = "\n---\n".join(code_changes[:10])  # Limit to 10 changes
            return result[:max_chars]

        # Fallback: look for any file modification indicators
        # Check for "has been updated" messages
        update_pattern = (
            r"The file ([^\s]+) has been updated[^}]*cat -n[^}]*(\d+→[^\}]+)"
        )
        for match in re.finditer(update_pattern, content, re.DOTALL):
            file_path = match.group(1)
            snippet = match.group(2)[:500]
            code_changes.append(f"Updated: {file_path}\n{snippet}\n")

        if code_changes:
            result = "\n---\n".join(code_changes[:10])
            return result[:max_chars]

        # If no structured changes found, return last portion of trace
        return content[-max_chars:] if len(content) > max_chars else content

    except Exception as e:
        return f"Error extracting code changes: {e}"


def extract_tool_counts_from_trace(trace_content: str) -> dict:
    """Extract tool usage counts from trace content."""
    import re

    tool_counts = {}

    # Look for tool_use patterns
    tool_pattern = r'"name"\s*:\s*"([^"]+)"[^}]*"type"\s*:\s*"tool_use"'
    for match in re.finditer(tool_pattern, trace_content):
        tool_name = match.group(1)
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    # Also check for the reverse pattern
    tool_pattern2 = r'"type"\s*:\s*"tool_use"[^}]*"name"\s*:\s*"([^"]+)"'
    for match in re.finditer(tool_pattern2, trace_content):
        tool_name = match.group(1)
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    return tool_counts


def run_llm_judge_evaluation(
    project_root: Path,
    experiment: str,
    tasks: list,
    config: dict,
    paired_experiments: dict = None,
):
    """Execute LLM judge evaluation on selected tasks with oracle data support."""

    # Check for enhanced mode
    use_enhanced = config.get("use_enhanced", True)
    enable_voting = config.get("enable_voting", False)

    mode_desc = "Enhanced" if use_enhanced else "Legacy"
    voting_desc = " with voting" if enable_voting else ""
    st.info(
        f"Running {mode_desc} evaluation{voting_desc} on {len(tasks)} tasks with {config['model']}..."
    )

    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []

    # Determine base directory for this experiment
    if paired_experiments and experiment in paired_experiments:
        mode, mode_dir = paired_experiments[experiment]
        base_dir = mode_dir
    else:
        base_dir = EXTERNAL_JOBS_DIR / experiment

    try:
        if use_enhanced:
            from src.benchmark.llm_judge import EnhancedJudgeInput, EnhancedLLMJudge

            judge = EnhancedLLMJudge(
                model=config["model"],
                enable_voting=enable_voting,
                voting_rounds=config.get("voting_rounds", 3),
            )
        else:
            from src.benchmark.llm_judge import LLMJudge

            judge = LLMJudge(model=config["model"])

        for i, task in enumerate(tasks):
            status_text.text(f"Evaluating task {i + 1}/{len(tasks)}: {task[:50]}...")
            progress_bar.progress((i + 1) / len(tasks))

            task_dir = base_dir / task
            agent_dir = task_dir / "agent"

            task_result = {
                "task": task,
                "scores": {},
                "error": None,
                "oracle_available": False,
            }

            try:
                # Load config for real task name (needed for oracle lookup)
                config_file = task_dir / "config.json"
                real_task_name = task  # fallback to trial name
                if config_file.exists():
                    with open(config_file) as f:
                        task_config = json.load(f)
                        # Extract real task name from path
                        task_path = task_config.get("task", {}).get("path", "")
                        if task_path:
                            # Path like /home/.../tasks/c_api_graphql_expert_079_architectural_understanding_expert_01
                            real_task_name = Path(task_path).name

                # Load result for reward info
                result_file = task_dir / "result.json"
                reward = 0.0
                if result_file.exists():
                    with open(result_file) as f:
                        result_data = json.load(f)
                        # Check both top-level and nested reward
                        if "reward" in result_data:
                            reward = result_data.get("reward", 0.0)
                        elif "verifier_result" in result_data:
                            reward = (
                                result_data.get("verifier_result", {})
                                .get("rewards", {})
                                .get("reward", 0.0)
                            )

                # Try to extract actual task description from command file
                task_description = f"Task ID: {task}"
                command_file = agent_dir / "command-1" / "command.txt"
                if command_file.exists():
                    with open(
                        command_file, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        cmd_content = f.read()
                        # Look for task description in the command (between -p ' and ')
                        if "# Task" in cmd_content:
                            # Extract the task section
                            import re

                            task_match = re.search(
                                r"# Task.*?(?=---|\\'\\'\\'|$)", cmd_content, re.DOTALL
                            )
                            if task_match:
                                task_description = task_match.group(0)[:2000]

                # Load oracle data first to determine task category
                oracle_data = {}
                mcp_analysis = {}
                if use_enhanced and load_locobench_oracle:
                    oracle_data = load_locobench_oracle(real_task_name)
                    if oracle_data.get("ground_truth"):
                        task_result["oracle_available"] = True
                        task_result["real_task_name"] = real_task_name

                # Determine if this is an analysis task vs code modification task
                task_category = oracle_data.get("task_category", "")
                is_analysis_task = task_category in [
                    "architectural_understanding",
                    "code_comprehension",
                    "bug_investigation",
                    "security_analysis",  # Returns vulnerability report, not code
                ]

                # Get agent's solution - prefer solution.md for analysis tasks
                agent_solution = ""
                solution_file = agent_dir / "solution.md"
                if solution_file.exists():
                    with open(
                        solution_file, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        agent_solution = f.read()[:15000]  # Limit to 15k chars

                # For code modification tasks, also extract code changes from trace
                claude_file = agent_dir / "claude-code.txt"
                code_changes = ""
                if not is_analysis_task:
                    code_changes = extract_code_changes_from_trace(claude_file)

                # Use solution.md for analysis tasks, code_changes for modification tasks
                if is_analysis_task and agent_solution:
                    # For analysis tasks, the solution IS the agent's answer
                    effective_solution = agent_solution
                elif code_changes:
                    effective_solution = code_changes
                elif agent_solution:
                    # Fallback to solution.md if no code changes extracted
                    effective_solution = agent_solution
                else:
                    effective_solution = "No solution extracted from agent output"

                # Also load beginning of trace for tool call analysis
                trace_content = ""
                if claude_file.exists():
                    with open(claude_file, "r", encoding="utf-8", errors="ignore") as f:
                        trace_content = f.read()[:20000]

                    # Analyze MCP tool usage
                    if analyze_mcp_tool_usage:
                        tool_counts = extract_tool_counts_from_trace(trace_content)
                        mcp_analysis = analyze_mcp_tool_usage(
                            tool_counts, trace_content
                        )

                # Run evaluation based on mode
                if use_enhanced:
                    # Build enhanced input - use effective_solution (solution.md or code changes)
                    judge_input = EnhancedJudgeInput(
                        task_id=task,
                        task_description=task_description,
                        code_changes=effective_solution,  # This is now the right content for task type
                        tool_calls=trace_content[:10000],
                        reward=reward,
                        trajectory=trace_content[:8000],
                        # Oracle data
                        oracle_ground_truth=oracle_data.get("ground_truth"),
                        oracle_expected_approach=oracle_data.get("expected_approach"),
                        oracle_evaluation_criteria=oracle_data.get(
                            "evaluation_criteria"
                        ),
                        oracle_context_files=oracle_data.get("context_files"),
                        # MCP analysis
                        mcp_tools_used=mcp_analysis.get("sourcegraph_tools_used"),
                        mcp_effectiveness_score=mcp_analysis.get("effectiveness_score"),
                        mcp_recommendations=mcp_analysis.get("recommendations"),
                        # Metadata
                        task_category=task_category,  # Use the extracted task_category
                        difficulty=oracle_data.get("difficulty"),
                    )

                    # Map dimension names to enhanced judge dimensions
                    dim_mapping = {
                        "code_quality": "code_quality",
                        "correctness": "correctness",
                        "completeness": "completeness",
                        "retrieval_quality": "retrieval",
                        "mcp_effectiveness": "mcp_effectiveness",
                    }

                    for dim in config["selected_dimensions"]:
                        enhanced_dim = dim_mapping.get(dim, dim)
                        try:
                            assessment = judge.evaluate(judge_input, enhanced_dim)
                            task_result["scores"][dim] = {
                                "score": assessment.score,
                                "score_label": assessment.score_label,
                                "reasoning": assessment.reasoning,
                                "oracle_alignment": assessment.oracle_alignment,
                                "confidence": assessment.confidence,
                                "num_rounds": assessment.num_rounds,
                            }
                        except ValueError:
                            # Dimension not supported, use fallback
                            task_result["scores"][dim] = {
                                "score": 0,
                                "score_label": "fail",
                                "reasoning": f"Dimension '{dim}' evaluation not yet implemented",
                            }
                else:
                    # Legacy mode - use original judge
                    for dim in config["selected_dimensions"]:
                        if dim == "code_quality":
                            assessment = judge.evaluate_code(
                                task_description=task_description,
                                code_changes=code_changes
                                if code_changes
                                else "No code changes extracted",
                                reward=reward,
                            )
                            task_result["scores"][dim] = {
                                "score": assessment.score,
                                "reasoning": assessment.reasoning,
                            }
                        elif dim == "retrieval_quality":
                            assessment = judge.evaluate_retrieval(
                                task_description=task_description,
                                tool_calls=trace_content[:10000],
                            )
                            task_result["scores"][dim] = {
                                "score": assessment.score,
                                "reasoning": assessment.reasoning,
                            }
                        elif dim == "correctness":
                            assessment = judge.evaluate_correctness(
                                task_description=task_description,
                                code_changes=code_changes
                                if code_changes
                                else "No code changes extracted",
                                trajectory=trace_content[:8000],
                                reward=reward,
                            )
                            task_result["scores"][dim] = {
                                "score": assessment.score,
                                "reasoning": assessment.reasoning,
                            }
                        elif dim == "completeness":
                            assessment = judge.evaluate_completeness(
                                task_description=task_description,
                                code_changes=code_changes
                                if code_changes
                                else "No code changes extracted",
                                trajectory=trace_content[:8000],
                                reward=reward,
                            )
                            task_result["scores"][dim] = {
                                "score": assessment.score,
                                "reasoning": assessment.reasoning,
                            }
                        else:
                            # For other dimensions, use generic evaluation
                            task_result["scores"][dim] = {
                                "score": 0,
                                "reasoning": "Dimension evaluation not yet implemented",
                            }

                results.append(task_result)

            except Exception as e:
                task_result["error"] = str(e)
                results.append(task_result)

        progress_bar.progress(1.0)
        status_text.text("Evaluation complete!")

        # Save results
        output_dir = get_judge_results_dir(project_root)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{experiment}_{timestamp}_judge.json"

        # Count tasks with oracle data
        oracle_count = sum(1 for r in results if r.get("oracle_available"))

        report_data = {
            "experiment": experiment,
            "model": config["model"],
            "dimensions": config["selected_dimensions"],
            "results": results,
            "timestamp": datetime.now().isoformat(),
            # Enhanced mode metadata
            "enhanced_mode": use_enhanced,
            "voting_enabled": enable_voting,
            "voting_rounds": config.get("voting_rounds", 3) if enable_voting else 1,
            "oracle_tasks": oracle_count,
            "total_tasks": len(results),
        }

        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)

        st.success(
            f"✓ Evaluation complete! Switch to 'View Reports' tab to see results."
        )

        # Quick summary
        st.markdown("---")
        st.subheader("Quick Summary")

        summary_data = []
        for r in results:
            row = {"Task": r["task"][:40]}
            for dim, scores in r.get("scores", {}).items():
                row[DEFAULT_RUBRICS.get(dim, {}).get("name", dim)[:15]] = scores.get(
                    "score", "N/A"
                )
            if r.get("error"):
                row["Status"] = "⚠️ Error"
            else:
                row["Status"] = "✓"
            summary_data.append(row)

        st.dataframe(summary_data, use_container_width=True, hide_index=True)

    except ImportError as e:
        st.error(f"LLM Judge module not available: {e}")
        st.info("Make sure anthropic package is installed: pip install anthropic")
    except Exception as e:
        st.error(f"Evaluation failed: {e}")
