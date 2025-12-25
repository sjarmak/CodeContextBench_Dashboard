"""
Evaluation Runner

Run evaluations with:
- Agent selection
- Task selection
- Live progress monitoring
- Pause/resume capability
- Log streaming
"""

import streamlit as st
from pathlib import Path
import sys
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, RunManager, TaskManager, AgentRegistry
from benchmark.run_orchestrator import create_evaluation_run, get_orchestrator
import pandas as pd


def show_run_configuration():
    """Show run configuration form."""
    st.subheader("Configure Evaluation Run")

    # Benchmark selection
    benchmarks = BenchmarkRegistry.list_all()
    if not benchmarks:
        st.error("No benchmarks registered. Please add benchmarks first.")
        return None

    benchmark_names = [b["name"] for b in benchmarks]
    selected_benchmark_name = st.selectbox("Select Benchmark", benchmark_names)

    selected_benchmark = next(b for b in benchmarks if b["name"] == selected_benchmark_name)

    # Get benchmark tasks
    benchmark_path = Path("benchmarks") / selected_benchmark["folder_name"]
    tasks = []

    if benchmark_path.exists():
        for task_dir in sorted(benchmark_path.iterdir()):
            if task_dir.is_dir() and (task_dir / "task.toml").exists():
                tasks.append(task_dir.name)

    if not tasks:
        st.warning("No tasks found in selected benchmark")
        return None

    # Task selection
    st.markdown("#### Task Selection")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("All Tasks"):
            st.session_state["eval_selected_tasks"] = tasks

    with col2:
        if st.button("First 5 Tasks"):
            st.session_state["eval_selected_tasks"] = tasks[:5]

    with col3:
        if st.button("Clear Selection"):
            st.session_state["eval_selected_tasks"] = []

    selected_tasks = st.multiselect(
        "Tasks to Run",
        tasks,
        default=st.session_state.get("eval_selected_tasks", []),
        key="task_selection_multiselect"
    )

    st.session_state["eval_selected_tasks"] = selected_tasks

    if not selected_tasks:
        st.warning("Please select at least one task")
        return None

    st.write(f"**Selected: {len(selected_tasks)} tasks**")

    # Agent selection
    st.markdown("#### Agent Selection")

    # Predefined agents
    default_agents = [
        "agents.claude_baseline_agent:BaselineClaudeCodeAgent",
        "agents.mcp_variants:DeepSearchFocusedAgent",
        "agents.mcp_variants:StrategicDeepSearchAgent",
    ]

    # Get custom agents from registry
    custom_agents = AgentRegistry.list_all(active_only=True)

    agent_options = default_agents + [a["import_path"] for a in custom_agents]

    selected_agents = st.multiselect(
        "Select Agents",
        agent_options,
        default=[agent_options[0]] if agent_options else []
    )

    if not selected_agents:
        st.warning("Please select at least one agent")
        return None

    # Configuration
    st.markdown("#### Run Configuration")

    col1, col2 = st.columns(2)

    with col1:
        concurrency = st.number_input(
            "Concurrency (tasks in parallel)",
            min_value=1,
            max_value=10,
            value=1
        )

    with col2:
        timeout = st.number_input(
            "Timeout per task (seconds)",
            min_value=60,
            max_value=3600,
            value=600
        )

    # Create run button
    st.markdown("---")

    if st.button("Start Evaluation Run", type="primary"):
        try:
            run_id = create_evaluation_run(
                benchmark_name=selected_benchmark["name"],
                agents=selected_agents,
                task_selection=selected_tasks,
                concurrency=concurrency,
                config={"timeout": timeout}
            )

            st.session_state["current_run_id"] = run_id
            st.session_state["show_monitoring"] = True
            st.success(f"Run created: {run_id}")
            st.rerun()

        except Exception as e:
            st.error(f"Failed to create run: {e}")

    return None


def show_run_monitoring():
    """Show live monitoring of current run."""
    run_id = st.session_state.get("current_run_id")

    if not run_id:
        st.info("No active run. Configure and start a run above.")
        return

    st.subheader(f"Monitoring Run: {run_id}")

    # Get orchestrator
    try:
        orchestrator = get_orchestrator(run_id)
    except Exception as e:
        st.error(f"Failed to get run: {e}")
        if st.button("Clear Run"):
            del st.session_state["current_run_id"]
            del st.session_state["show_monitoring"]
            st.rerun()
        return

    # Get progress
    progress = orchestrator.get_progress()

    # Show progress
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Status", progress["status"].upper())

    with col2:
        st.metric("Progress", f"{progress['completed']}/{progress['total_tasks']}")

    with col3:
        st.metric("Running", progress['running'])

    with col4:
        st.metric("Pending", progress['pending'])

    # Progress bar
    st.progress(progress['progress_pct'] / 100)

    # Control buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if progress["status"] == "pending":
            if st.button("Start Run"):
                orchestrator.start()
                st.rerun()

    with col2:
        if progress["status"] == "running":
            if st.button("Pause Run"):
                orchestrator.pause()
                st.rerun()

    with col3:
        if progress["can_resume"]:
            if st.button("Resume Run"):
                orchestrator.resume()
                st.rerun()

    with col4:
        if progress["status"] in ("running", "paused"):
            if st.button("Stop Run"):
                orchestrator.stop()
                st.rerun()

    # Task details
    st.markdown("---")
    st.markdown("#### Task Status")

    tasks = TaskManager.get_tasks(run_id)

    if tasks:
        task_data = []
        for task in tasks:
            task_data.append({
                "Task": task["task_name"],
                "Agent": task["agent_name"].split(":")[-1],
                "Status": task["status"],
                "Reward": task.get("reward", "N/A"),
                "Started": task.get("started_at", "")[:19] if task.get("started_at") else "",
            })

        df = pd.DataFrame(task_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Auto-refresh if running
    if progress["status"] == "running":
        time.sleep(2)
        st.rerun()

    # Completion actions
    if progress["status"] == "completed":
        st.success("Run completed!")

        if st.button("Generate Report"):
            st.session_state["generate_report_run_id"] = run_id
            st.info("Navigate to Report Generator page to generate report")

        if st.button("Clear Run"):
            del st.session_state["current_run_id"]
            del st.session_state["show_monitoring"]
            st.rerun()


def show_recent_runs():
    """Show list of recent runs."""
    st.subheader("Recent Runs")

    runs = RunManager.list_all()

    if not runs:
        st.info("No runs yet. Create a run to get started.")
        return

    # Show recent runs
    run_data = []
    for run in runs[:10]:  # Show last 10
        # Get benchmark name
        benchmark = BenchmarkRegistry.get(run["benchmark_id"])
        benchmark_name = benchmark["name"] if benchmark else "Unknown"

        run_data.append({
            "Run ID": run["run_id"],
            "Benchmark": benchmark_name,
            "Status": run["status"],
            "Agents": len(run.get("agents", [])),
            "Started": run.get("started_at", "")[:19] if run.get("started_at") else "N/A",
        })

    df = pd.DataFrame(run_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Select a run to monitor
    run_ids = [r["run_id"] for r in runs]
    selected_run_id = st.selectbox("Load Run", [""] + run_ids)

    if selected_run_id:
        if st.button("Load Selected Run"):
            st.session_state["current_run_id"] = selected_run_id
            st.session_state["show_monitoring"] = True
            st.rerun()


def show_evaluation_runner():
    """Main evaluation runner page."""
    st.title("Evaluation Runner")
    st.write("Run and monitor benchmark evaluations")

    # Check if we're monitoring a run
    if st.session_state.get("show_monitoring"):
        show_run_monitoring()

        st.markdown("---")

        if st.button("Start New Run"):
            del st.session_state["current_run_id"]
            del st.session_state["show_monitoring"]
            st.rerun()

    else:
        # Show configuration form
        show_run_configuration()

        st.markdown("---")

        # Show recent runs
        show_recent_runs()


if __name__ == "__main__":
    show_evaluation_runner()
