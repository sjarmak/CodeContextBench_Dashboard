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
from benchmark.trace_parser import TraceParser


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
    # Sanitize agent name same way as orchestrator (replace : with __, / with _)
    safe_agent_name = task['agent_name'].replace(":", "__").replace("/", "_")
    task_output_dir = output_dir / f"{task['task_name']}_{safe_agent_name}"

    if not task_output_dir.exists():
        st.warning(f"Task output directory not found: {task_output_dir}")
        return

    # Look for trajectory and result files
    trajectory_files = list(task_output_dir.rglob("trajectory.json"))
    result_files = list(task_output_dir.rglob("result.json"))
    claude_files = list(task_output_dir.rglob("claude.txt"))

    # Tabs for different views
    tabs = st.tabs(["Agent Trace", "Result Details", "LLM Judge", "Task Report"])

    with tabs[0]:
        show_agent_trace(claude_files, trajectory_files)

    with tabs[1]:
        show_result_details(result_files)

    with tabs[2]:
        show_llm_judge_section(run_data, task, task_output_dir)

    with tabs[3]:
        show_task_report_section(run_data, task, task_output_dir, trajectory_files, result_files)


def show_agent_trace(claude_files, trajectory_files):
    """Display agent execution trace."""
    st.subheader("Agent Trace")

    if not trajectory_files:
        st.info("No trajectory file found.")
        return

    trajectory_file = trajectory_files[0]

    try:
        # Parse trajectory
        steps = TraceParser.parse_trajectory_file(trajectory_file)

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            include_sidechain = st.checkbox("Include sidechain steps", value=False)
        with col2:
            show_tool_calls_only = st.checkbox("Show only tool calls", value=False)

        # Filter steps
        filtered_steps = TraceParser.filter_sidechain(steps, include_sidechain)

        if show_tool_calls_only:
            filtered_steps = [s for s in filtered_steps if s.tool_calls]

        # Token and tool usage summary
        with st.expander("Execution Summary", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Token Usage:**")
                token_summary = TraceParser.get_token_summary(steps)
                st.write(f"- Total: {token_summary['total']:,}")
                st.write(f"- Prompt: {token_summary['total_prompt']:,}")
                st.write(f"- Completion: {token_summary['total_completion']:,}")
                st.write(f"- Cached: {token_summary['total_cached']:,}")

            with col2:
                st.write("**Tool Usage:**")
                tool_summary = TraceParser.get_tool_usage_summary(steps)
                for tool_name, count in sorted(tool_summary.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"- {tool_name}: {count}")

        st.markdown("---")

        # Display steps
        for step in filtered_steps:
            show_trace_step(step)

        # Raw trajectory option
        with st.expander("Raw Trajectory (JSON)"):
            with open(trajectory_file) as f:
                trajectory = json.load(f)
            st.json(trajectory)

    except Exception as e:
        st.error(f"Failed to parse trajectory: {e}")
        import traceback
        st.code(traceback.format_exc())


def show_trace_step(step):
    """Display a single trace step."""
    # Step header
    icon = "👤" if step.source == "user" else "🤖"
    source_label = "User" if step.source == "user" else "Assistant"

    with st.expander(f"{icon} Step {step.step_id}: {source_label}", expanded=False):
        # Timestamp
        st.caption(f"Time: {step.timestamp}")

        # Clean message (without tool calls)
        clean_message = TraceParser.get_clean_message(step)
        if clean_message:
            st.markdown("**Message:**")
            st.markdown(clean_message)

        # Tool calls
        if step.tool_calls:
            st.markdown("**Tool Calls:**")

            for i, tool_call in enumerate(step.tool_calls):
                with st.container():
                    st.markdown(f"**{i+1}. {tool_call.tool_name}**")

                    # Show parameters
                    for param_name, param_value in tool_call.parameters.items():
                        if len(param_value) > 200:
                            with st.expander(f"  {param_name}"):
                                st.code(param_value, language="python" if "content" in param_name else None)
                        else:
                            st.code(f"{param_name}: {param_value}", language=None)

        # Diffs
        diffs = TraceParser.extract_diffs(step.tool_calls)
        if diffs:
            st.markdown("**Code Changes:**")

            for diff in diffs:
                if diff["type"] == "edit":
                    st.markdown(f"📝 **Edit:** `{diff['file_path']}`")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Before:**")
                        st.code(diff["old_string"], language="python")
                    with col2:
                        st.markdown("**After:**")
                        st.code(diff["new_string"], language="python")

                elif diff["type"] == "write":
                    st.markdown(f"📄 **Write:** `{diff['file_path']}`")
                    st.code(diff["content"], language="python")

        # Metrics
        if step.metrics:
            with st.expander("Metrics"):
                st.json(step.metrics)


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

    # Import judge modules
    try:
        from benchmark.llm_judge import (
            LLMJudge,
            extract_tool_calls_from_trajectory,
            extract_code_changes_from_trajectory,
            load_task_description
        )
        from benchmark.database import JudgeEvaluationRegistry
    except ImportError as e:
        st.error(f"Failed to import judge modules: {e}")
        return

    # Check for ANTHROPIC_API_KEY
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("ANTHROPIC_API_KEY environment variable not set. Cannot run LLM judge.")
        return

    # Model selector
    judge_model = st.selectbox(
        "Judge Model",
        ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20251022", "claude-opus-4-5-20251022"],
        help="Model to use for judge evaluation. Haiku is fastest and cheapest."
    )

    # Check if judge evaluation already exists
    existing_evals = JudgeEvaluationRegistry.list_for_task(
        run_data["run_id"],
        task["task_name"]
    )

    if existing_evals:
        st.info(f"Found {len(existing_evals)} existing judge evaluation(s)")

        # Display existing evaluations
        for eval_data in existing_evals:
            with st.expander(f"Judge Evaluation - {eval_data['judge_model']}", expanded=True):
                st.write(f"**Created:** {eval_data['created_at'][:19]}")

                # Parse evaluation data
                if eval_data.get("evaluation_data"):
                    eval_json = eval_data["evaluation_data"]

                    # Display scores
                    col1, col2 = st.columns(2)

                    # Retrieval quality
                    with col1:
                        retrieval = eval_json.get("retrieval_quality", {})
                        if retrieval:
                            st.metric("Retrieval Quality", f"{retrieval.get('score', 0)}/5")
                            st.write(f"**Reasoning:** {retrieval.get('reasoning', 'N/A')}")

                            if retrieval.get("strengths"):
                                st.write("**Strengths:**")
                                for strength in retrieval.get("strengths", []):
                                    st.write(f"- {strength}")

                            if retrieval.get("weaknesses"):
                                st.write("**Weaknesses:**")
                                for weakness in retrieval.get("weaknesses", []):
                                    st.write(f"- {weakness}")

                    # Code quality
                    with col2:
                        code_quality = eval_json.get("code_quality", {})
                        if code_quality:
                            st.metric("Code Quality", f"{code_quality.get('score', 0)}/5")
                            st.write(f"**Reasoning:** {code_quality.get('reasoning', 'N/A')}")

                            if code_quality.get("strengths"):
                                st.write("**Strengths:**")
                                for strength in code_quality.get("strengths", []):
                                    st.write(f"- {strength}")

                            if code_quality.get("weaknesses"):
                                st.write("**Weaknesses:**")
                                for weakness in code_quality.get("weaknesses", []):
                                    st.write(f"- {weakness}")

        st.markdown("---")

    # Run judge button
    if st.button("Run LLM Judge Evaluation", key=f"judge_{task['task_name']}"):
        with st.spinner("Running LLM judge evaluation..."):
            try:
                # Find trajectory and result files
                trajectory_files = list(task_output_dir.rglob("trajectory.json"))
                result_files = list(task_output_dir.rglob("result.json"))

                if not trajectory_files:
                    st.error("No trajectory.json file found")
                    return

                if not result_files:
                    st.error("No result.json file found")
                    return

                # Load trajectory
                with open(trajectory_files[0]) as f:
                    trajectory = json.load(f)

                # Load result
                with open(result_files[0]) as f:
                    result = json.load(f)

                # Get task description
                benchmark_path = Path("benchmarks") / run_data.get("benchmark_name", "")
                task_path = benchmark_path / task["task_name"]

                if task_path.exists():
                    task_description = load_task_description(task_path)
                else:
                    task_description = f"Task: {task['task_name']}"

                # Extract tool calls and code changes
                tool_calls = extract_tool_calls_from_trajectory(trajectory)
                code_changes = extract_code_changes_from_trajectory(trajectory)

                # Get reward
                reward = result.get("verifier_result", {}).get("rewards", {}).get("reward", 0.0)

                # Initialize judge
                judge = LLMJudge(model=judge_model)

                # Evaluate retrieval quality
                st.write("Evaluating retrieval quality...")
                retrieval_assessment = judge.evaluate_retrieval(task_description, tool_calls)

                # Evaluate code quality
                st.write("Evaluating code quality...")
                code_assessment = judge.evaluate_code(task_description, code_changes, reward)

                # Store in database
                evaluation_data = {
                    "retrieval_quality": retrieval_assessment.to_dict(),
                    "code_quality": code_assessment.to_dict()
                }

                # Calculate average score
                avg_score = (retrieval_assessment.score + code_assessment.score) / 2.0

                JudgeEvaluationRegistry.add(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    agent_name=task["agent_name"],
                    judge_model=judge_model,
                    score=avg_score,
                    reasoning=f"Retrieval: {retrieval_assessment.score}/5, Code: {code_assessment.score}/5",
                    evaluation_data=evaluation_data
                )

                st.success("Judge evaluation complete!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to run judge evaluation: {e}")
                import traceback
                st.code(traceback.format_exc())


def show_task_report_section(run_data, task, task_output_dir, trajectory_files, result_files):
    """Show task report generation and export section."""
    st.subheader("Task Report")

    # Import report modules
    try:
        from benchmark.report_generator import (
            generate_task_report,
            format_task_report_markdown,
            format_task_report_json,
            format_task_report_csv_row
        )
        from benchmark.database import EvaluationReportRegistry, JudgeEvaluationRegistry
    except ImportError as e:
        st.error(f"Failed to import report modules: {e}")
        return

    # Check if report already exists
    existing_report = EvaluationReportRegistry.get_latest(
        run_data["run_id"],
        task_name=task["task_name"],
        report_type="task_report"
    )

    if existing_report:
        st.info(f"Report exists - Generated: {existing_report['created_at'][:19]}")

        # Display summary
        report_data = existing_report.get("report_data", {})

        if report_data:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                success = report_data.get("result", {}).get("success", False)
                st.metric("Success", "Yes" if success else "No")

            with col2:
                total_tokens = report_data.get("metrics", {}).get("tokens", {}).get("total_tokens", 0)
                st.metric("Total Tokens", f"{total_tokens:,}")

            with col3:
                exec_time = report_data.get("metrics", {}).get("timing", {}).get("agent_execution_sec", 0)
                st.metric("Execution Time", f"{exec_time:.1f}s")

            with col4:
                judge_score = report_data.get("judge_evaluation", {}).get("score", "N/A")
                if isinstance(judge_score, (int, float)):
                    st.metric("Judge Score", f"{judge_score:.2f}/5")
                else:
                    st.metric("Judge Score", judge_score)

            st.markdown("---")

            # Export options
            st.write("**Export Report:**")

            col1, col2, col3 = st.columns(3)

            with col1:
                markdown = format_task_report_markdown(report_data)
                st.download_button(
                    "Download Markdown",
                    markdown,
                    file_name=f"{task['task_name']}_report.md",
                    mime="text/markdown",
                    key=f"download_md_{task['task_name']}"
                )

            with col2:
                json_str = format_task_report_json(report_data)
                st.download_button(
                    "Download JSON",
                    json_str,
                    file_name=f"{task['task_name']}_report.json",
                    mime="application/json",
                    key=f"download_json_{task['task_name']}"
                )

            with col3:
                csv_row = format_task_report_csv_row(report_data)
                # Add header
                csv_header = "task_name,agent_name,success,reward,total_tokens,input_tokens,output_tokens,cache_tokens,total_time_sec,agent_execution_sec,total_edits,total_writes,files_modified,judge_score,judge_model\n"
                csv_content = csv_header + csv_row
                st.download_button(
                    "Download CSV",
                    csv_content,
                    file_name=f"{task['task_name']}_report.csv",
                    mime="text/csv",
                    key=f"download_csv_{task['task_name']}"
                )

            # Show full report in expander
            with st.expander("View Full Report"):
                st.markdown(markdown)

        st.markdown("---")

    # Generate report button
    if st.button("Generate Task Report", key=f"generate_report_{task['task_name']}"):
        with st.spinner("Generating task report..."):
            try:
                # Load trajectory
                if not trajectory_files:
                    st.error("No trajectory.json file found")
                    return

                with open(trajectory_files[0]) as f:
                    trajectory = json.load(f)

                # Load result
                if not result_files:
                    st.error("No result.json file found")
                    return

                with open(result_files[0]) as f:
                    result = json.load(f)

                # Try to load task metadata
                task_metadata = None
                benchmark_path = Path("benchmarks") / run_data.get("benchmark_name", "")
                task_path = benchmark_path / task["task_name"]

                if task_path.exists():
                    task_toml = task_path / "task.toml"
                    if task_toml.exists():
                        try:
                            import toml
                            with open(task_toml) as f:
                                task_metadata = toml.load(f)
                        except:
                            pass

                # Get judge evaluation if exists
                judge_evals = JudgeEvaluationRegistry.list_for_task(
                    run_data["run_id"],
                    task["task_name"]
                )
                judge_evaluation = judge_evals[0] if judge_evals else None

                # Generate report
                report = generate_task_report(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    agent_name=task["agent_name"],
                    result_data=result,
                    trajectory_data=trajectory,
                    judge_evaluation=judge_evaluation,
                    task_metadata=task_metadata
                )

                # Store in database
                EvaluationReportRegistry.add(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    report_type="task_report",
                    report_data=report
                )

                st.success("Task report generated successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to generate report: {e}")
                import traceback
                st.code(traceback.format_exc())


if __name__ == "__main__":
    show_run_results()
