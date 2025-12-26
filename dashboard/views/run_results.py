"""
Run Results Viewer

View individual evaluation run results with:
- Metrics summary (tokens, time, result, tools)
- Agent trace with tool calls and responses
- Diffs and code changes
- LLM judge evaluation
"""

import streamlit as st
from pathlib import Path
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import RunManager, TaskManager


def show_run_results():
    """Main run results page."""
    st.title("Run Results")

    # Get all runs
    runs = RunManager.list_all()

    if not runs:
        st.info("No evaluation runs found. Use 'Evaluation Runner' to start a new evaluation.")
        return

    # Run selector
    run_options = [f"{r['run_id']} - {r.get('benchmark_name', 'Unknown')} ({r.get('status', 'unknown')})" for r in runs]
    run_ids = [r['run_id'] for r in runs]

    selected_index = st.selectbox(
        "Select Run",
        range(len(run_options)),
        format_func=lambda i: run_options[i]
    )

    if selected_index is None:
        return

    selected_run_id = run_ids[selected_index]
    run_data = RunManager.get(selected_run_id)

    if not run_data:
        st.error("Run not found")
        return

    st.markdown("---")

    # Display run overview
    show_run_overview(run_data)

    st.markdown("---")

    # Display task results
    show_task_results(run_data)


def show_run_overview(run_data):
    """Display run overview with metrics."""
    st.subheader("Run Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Status", run_data.get("status", "unknown").upper())

    with col2:
        st.metric("Tasks", f"{run_data.get('completed_tasks', 0)}/{run_data.get('total_tasks', 0)}")

    with col3:
        benchmark_name = run_data.get("benchmark_name", "Unknown")
        st.metric("Benchmark", benchmark_name)

    with col4:
        agents = run_data.get("agents", [])
        agent_display = agents[0].split(":")[-1] if agents else "Unknown"
        st.metric("Agent", agent_display)

    # MCP configuration
    config = run_data.get("config", {})
    mcp_type = config.get("env", {}).get("BASELINE_MCP_TYPE", "none")
    st.write(f"**MCP Configuration:** {mcp_type}")

    # Timing
    if run_data.get("created_at"):
        st.write(f"**Created:** {run_data['created_at'][:19]}")
    if run_data.get("completed_at"):
        st.write(f"**Completed:** {run_data['completed_at'][:19]}")


def show_task_results(run_data):
    """Display task-level results."""
    st.subheader("Task Results")

    # Get task results
    tasks = TaskManager.get_tasks(run_data["run_id"])

    if not tasks:
        st.info("No task results found.")
        return

    # Create summary table
    task_data = []
    for task in tasks:
        task_data.append({
            "Task": task["task_name"],
            "Agent": task["agent_name"].split(":")[-1],
            "Status": task["status"],
            "Reward": task.get("reward", "N/A"),
            "Tokens": task.get("total_tokens", "N/A"),
            "Time (s)": f"{task.get('execution_time', 0):.1f}" if task.get("execution_time") else "N/A",
        })

    st.dataframe(task_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Task detail selector
    task_names = [t["task_name"] for t in tasks]
    selected_task = st.selectbox("View Task Details", task_names)

    if selected_task:
        task_detail = next((t for t in tasks if t["task_name"] == selected_task), None)
        if task_detail:
            show_task_detail(run_data, task_detail)


def show_task_detail(run_data, task):
    """Display detailed task results with trace."""
    st.subheader(f"Task: {task['task_name']}")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Result", task.get("reward", "N/A"))

    with col2:
        st.metric("Tokens", task.get("total_tokens", "N/A"))

    with col3:
        time_val = task.get("execution_time", 0)
        st.metric("Time", f"{time_val:.1f}s" if time_val else "N/A")

    with col4:
        st.metric("Status", task["status"])

    st.markdown("---")

    # Find task output directory
    output_dir = Path(run_data.get("output_dir", f"jobs/{run_data['run_id']}"))
    task_output_dir = output_dir / f"{task['task_name']}_{task['agent_name'].replace(':', '_')}"

    if not task_output_dir.exists():
        st.warning(f"Task output directory not found: {task_output_dir}")
        return

    # Look for trajectory and result files
    trajectory_files = list(task_output_dir.rglob("trajectory.json"))
    result_files = list(task_output_dir.rglob("result.json"))
    claude_files = list(task_output_dir.rglob("claude.txt"))

    # Tabs for different views
    tabs = st.tabs(["Agent Trace", "Result Details", "LLM Judge"])

    with tabs[0]:
        show_agent_trace(claude_files, trajectory_files)

    with tabs[1]:
        show_result_details(result_files)

    with tabs[2]:
        show_llm_judge_section(run_data, task, task_output_dir)


def show_agent_trace(claude_files, trajectory_files):
    """Display agent execution trace."""
    st.subheader("Agent Trace")

    if claude_files:
        claude_file = claude_files[0]
        st.write(f"**Trace file:** `{claude_file}`")

        try:
            with open(claude_file) as f:
                trace_content = f.read()

            # Display with syntax highlighting
            st.text_area("Agent Execution Log", trace_content, height=400)

        except Exception as e:
            st.error(f"Failed to read trace: {e}")
    else:
        st.info("No agent trace file (claude.txt) found.")

    # Also show trajectory.json if available
    if trajectory_files:
        with st.expander("Raw Trajectory (JSON)"):
            try:
                with open(trajectory_files[0]) as f:
                    trajectory = json.load(f)
                st.json(trajectory)
            except Exception as e:
                st.error(f"Failed to load trajectory: {e}")


def show_result_details(result_files):
    """Display result details."""
    st.subheader("Result Details")

    if result_files:
        try:
            with open(result_files[0]) as f:
                result = json.load(f)

            st.json(result)

        except Exception as e:
            st.error(f"Failed to load result: {e}")
    else:
        st.info("No result file found.")


def show_llm_judge_section(run_data, task, task_output_dir):
    """Show LLM judge evaluation section."""
    st.subheader("LLM Judge Evaluation")

    st.info("LLM judge evaluation integration coming soon.")

    st.write("**Features to implement:**")
    st.write("- Run LLM judge on this task")
    st.write("- View judge assessment")
    st.write("- Store evaluation report with run results")
    st.write("- Compare judge scores across runs")

    # Placeholder for judge functionality
    if st.button("Run LLM Judge (Coming Soon)"):
        st.warning("This feature is not yet implemented.")


if __name__ == "__main__":
    show_run_results()
