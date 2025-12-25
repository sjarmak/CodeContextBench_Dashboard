"""
Experiment Results Browser

Browse and display experiment evaluation reports including:
- evaluation_report.json data
- REPORT.md content
- Individual agent run metrics
- Judge assessments
"""

import streamlit as st
from pathlib import Path
import json
from typing import Optional, Dict, Any, List
import pandas as pd


def find_experiments(jobs_dir: Path) -> List[Path]:
    """Find all experiment directories with evaluation reports."""
    experiments = []

    if not jobs_dir.exists():
        return []

    # Look for directories containing evaluation_report.json
    for exp_dir in sorted(jobs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not exp_dir.is_dir() or exp_dir.name.startswith("."):
            continue

        report_file = exp_dir / "evaluation_report.json"
        if report_file.exists():
            experiments.append(exp_dir)

    return experiments


def load_evaluation_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Load evaluation_report.json."""
    try:
        with open(report_path) as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load evaluation report: {e}")
        return None


def render_experiment_selector(jobs_dir: Path) -> Optional[Path]:
    """Render experiment selector."""
    experiments = find_experiments(jobs_dir)

    if not experiments:
        st.warning("No evaluation reports found. Run postprocess script first.")

        # Show raw experiment directories
        all_dirs = [d for d in jobs_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if all_dirs:
            st.info(f"Found {len(all_dirs)} experiment directories without evaluation reports.")

        return None

    exp_names = [exp.name for exp in experiments]
    selected_name = st.selectbox("Select Experiment", exp_names)

    if selected_name:
        for exp in experiments:
            if exp.name == selected_name:
                return exp

    return None


def render_summary_metrics(report: Dict[str, Any]):
    """Render summary metrics from evaluation report."""
    st.subheader("Summary Metrics")

    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if not agents:
        st.info("No agent summary available.")
        return

    # Create comparison table
    data = []
    for agent_name, stats in agents.items():
        judge_scores = stats.get("judge_scores", {})

        retrieval_mean = judge_scores.get("retrieval_quality", {}).get("mean", 0)
        code_mean = judge_scores.get("code_quality", {}).get("mean", 0)

        data.append(
            {
                "Agent": agent_name,
                "Total Runs": stats.get("total_runs", 0),
                "Success Rate": f"{stats.get('success_rate', 0)*100:.1f}%",
                "Avg Tokens": f"{stats.get('avg_tokens', 0):,.0f}",
                "Total Cost": f"${stats.get('total_cost_usd', 0):.2f}",
                "Retrieval Quality": f"{retrieval_mean:.2f}/5",
                "Code Quality": f"{code_mean:.2f}/5",
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)


def render_agent_runs(report: Dict[str, Any]):
    """Render individual agent run details."""
    st.subheader("Agent Runs")

    agent_runs = report.get("agent_runs", [])

    if not agent_runs:
        st.info("No agent runs in report.")
        return

    # Group by agent
    agents = {}
    for run in agent_runs:
        agent_name = run.get("agent_name", "unknown")
        if agent_name not in agents:
            agents[agent_name] = []
        agents[agent_name].append(run)

    # Agent selector
    agent_names = sorted(agents.keys())
    selected_agent = st.selectbox("Select Agent", agent_names)

    if not selected_agent:
        return

    runs = agents[selected_agent]

    # Task selector
    task_names = [run.get("task_name", "unknown") for run in runs]
    selected_task = st.selectbox("Select Task", task_names)

    # Find selected run
    selected_run = None
    for run in runs:
        if run.get("task_name") == selected_task:
            selected_run = run
            break

    if not selected_run:
        return

    # Display run details
    st.markdown("---")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        reward = selected_run.get("reward", 0)
        st.metric("Reward", f"{reward:.2f}", delta="Success" if reward > 0 else "Failed")

    with col2:
        token_metrics = selected_run.get("token_metrics", {})
        total_tokens = token_metrics.get("total_input_tokens", 0) + token_metrics.get(
            "total_output_tokens", 0
        )
        st.metric("Total Tokens", f"{total_tokens:,}")

    with col3:
        timing = selected_run.get("timing_metrics", {})
        exec_time = timing.get("agent_execution_sec", 0)
        st.metric("Execution Time", f"{exec_time:.1f}s")

    with col4:
        tool_usage = selected_run.get("tool_usage", [])
        total_tool_calls = sum(t.get("call_count", 0) for t in tool_usage)
        st.metric("Tool Calls", total_tool_calls)

    # Judge assessments
    st.markdown("### Judge Assessments")

    assessments = selected_run.get("judge_assessments", [])

    if not assessments:
        st.info("No judge assessments for this run.")
    else:
        for assessment in assessments:
            dimension = assessment.get("dimension", "unknown")
            score = assessment.get("score", 0)
            reasoning = assessment.get("reasoning", "")
            strengths = assessment.get("strengths", [])
            weaknesses = assessment.get("weaknesses", [])

            with st.expander(f"{dimension.replace('_', ' ').title()}: {score}/5"):
                st.markdown(f"**Reasoning:** {reasoning}")

                if strengths:
                    st.markdown("**Strengths:**")
                    for s in strengths:
                        st.markdown(f"- {s}")

                if weaknesses:
                    st.markdown("**Weaknesses:**")
                    for w in weaknesses:
                        st.markdown(f"- {w}")

    # Tool usage details
    st.markdown("### 🔧 Tool Usage")

    if tool_usage:
        tool_data = []
        for tool in tool_usage:
            tool_data.append(
                {
                    "Tool": tool.get("tool_name", "unknown"),
                    "Calls": tool.get("call_count", 0),
                    "Success": tool.get("success_count", 0),
                    "Failure": tool.get("failure_count", 0),
                    "Avg Tokens": f"{tool.get('avg_tokens_per_call', 0):.0f}",
                }
            )

        df = pd.DataFrame(tool_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No tool usage data available.")

    # Links to raw files
    st.markdown("### 📁 Raw Files")

    trajectory_path = selected_run.get("trajectory_path", "")
    result_path = selected_run.get("result_path", "")

    col1, col2 = st.columns(2)

    with col1:
        if trajectory_path and Path(trajectory_path).exists():
            st.markdown(f"**Trajectory:** `{trajectory_path}`")
        else:
            st.markdown("**Trajectory:** Not found")

    with col2:
        if result_path and Path(result_path).exists():
            st.markdown(f"**Result:** `{result_path}`")
        else:
            st.markdown("**Result:** Not found")


def render_report_md(exp_dir: Path):
    """Render REPORT.md if available."""
    report_md = exp_dir / "REPORT.md"

    if not report_md.exists():
        return

    st.markdown("---")
    st.subheader("📄 Human-Readable Report")

    with open(report_md) as f:
        content = f.read()

    st.markdown(content)


def show_results_browser():
    """Main results browser page."""
    st.title("Experiment Results")
    st.markdown("Explore Harbor execution results and LLM judge assessments.")

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    jobs_dir = project_root / "jobs"

    if not jobs_dir.exists():
        st.error(f"Jobs directory not found: {jobs_dir}")
        return

    # Experiment selector
    selected_exp = render_experiment_selector(jobs_dir)

    if not selected_exp:
        return

    # Load evaluation report
    report_path = selected_exp / "evaluation_report.json"
    report = load_evaluation_report(report_path)

    if not report:
        return

    st.markdown("---")

    # Experiment overview
    st.subheader("Experiment Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Experiment ID:** {report.get('experiment_id', 'N/A')}")
        st.markdown(f"**Description:** {report.get('experiment_description', 'N/A')}")

    with col2:
        st.markdown(f"**Profile:** {report.get('profile_name', 'N/A')}")
        st.markdown(f"**Generated:** {report.get('generated_at', 'N/A')}")

    st.markdown("---")

    # Render sections
    render_summary_metrics(report)
    st.markdown("---")

    render_agent_runs(report)
    st.markdown("---")

    render_report_md(selected_exp)

    # Raw JSON view
    st.markdown("---")
    if st.checkbox("Show Raw Evaluation Report JSON"):
        st.json(report)


if __name__ == "__main__":
    show_results_browser()
