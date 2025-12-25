"""
Enhanced Comparison Table

Comprehensive comparison of evaluation runs including:
- Agent type
- Benchmark (full vs subset)
- Tokens, time, pass/fail
- Tool usage
- LLM evaluation summary
"""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import RunManager, TaskManager, BenchmarkRegistry
from benchmark.cost_calculator import calculate_cost
import pandas as pd
import json


def load_comparison_data():
    """Load data for comparison table."""
    runs = RunManager.list_all(status="completed")

    if not runs:
        return []

    comparison_data = []

    for run in runs:
        # Get benchmark
        benchmark = BenchmarkRegistry.get(run["benchmark_id"])
        benchmark_name = benchmark["name"] if benchmark else "Unknown"

        # Get tasks
        tasks = TaskManager.get_tasks(run["run_id"])

        # Calculate metrics per agent
        agents = list(set(t["agent_name"] for t in tasks))

        for agent_name in agents:
            agent_tasks = [t for t in tasks if t["agent_name"] == agent_name]

            # Calculate stats
            total_tasks = len(agent_tasks)
            passed = len([t for t in agent_tasks if t.get("reward", 0) > 0])
            failed = total_tasks - passed

            # Load result data for tokens/cost
            total_tokens = 0
            total_cost = 0.0
            total_time = 0.0

            for task in agent_tasks:
                if task.get("result_path"):
                    try:
                        with open(task["result_path"]) as f:
                            result_data = json.load(f)

                        agent_result = result_data.get("agent_result", {})
                        total_tokens += agent_result.get("n_input_tokens", 0)
                        total_tokens += agent_result.get("n_output_tokens", 0)

                        # Calculate cost
                        cost_breakdown = calculate_cost(
                            model_name=result_data.get("config", {}).get("agent", {}).get("model_name", "unknown"),
                            input_tokens=agent_result.get("n_input_tokens", 0),
                            output_tokens=agent_result.get("n_output_tokens", 0),
                            cache_read_tokens=agent_result.get("n_cache_tokens", 0),
                        )
                        total_cost += cost_breakdown.get("total_cost", 0)

                        # Calculate time
                        from datetime import datetime
                        started = result_data.get("started_at", "")
                        finished = result_data.get("finished_at", "")

                        if started and finished:
                            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                            end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                            total_time += (end_dt - start_dt).total_seconds()

                    except Exception:
                        pass

            # Determine if subset or full
            run_type = "Subset" if run.get("task_selection") else "Full"

            comparison_data.append({
                "Run ID": run["run_id"],
                "Benchmark": benchmark_name,
                "Run Type": run_type,
                "Agent": agent_name.split(":")[-1],
                "Tasks": total_tasks,
                "Passed": passed,
                "Failed": failed,
                "Pass Rate": f"{passed/total_tasks*100:.1f}%" if total_tasks > 0 else "0%",
                "Total Tokens": f"{total_tokens:,}",
                "Cost (USD)": f"${total_cost:.4f}",
                "Avg Time (s)": f"{total_time/total_tasks:.1f}" if total_tasks > 0 else "0",
            })

    return comparison_data


def show_comparison_enhanced():
    """Main enhanced comparison page."""
    st.title("Evaluation Comparison Table")
    st.write("Comprehensive comparison of all evaluation runs")

    # Load data
    comparison_data = load_comparison_data()

    if not comparison_data:
        st.info("No completed runs to compare. Run evaluations first.")
        return

    # Create dataframe
    df = pd.DataFrame(comparison_data)

    # Filters
    st.subheader("Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        benchmarks = df["Benchmark"].unique().tolist()
        selected_benchmarks = st.multiselect("Benchmarks", benchmarks, default=benchmarks)

    with col2:
        agents = df["Agent"].unique().tolist()
        selected_agents = st.multiselect("Agents", agents, default=agents)

    with col3:
        run_types = df["Run Type"].unique().tolist()
        selected_run_types = st.multiselect("Run Type", run_types, default=run_types)

    # Filter dataframe
    filtered_df = df[
        (df["Benchmark"].isin(selected_benchmarks)) &
        (df["Agent"].isin(selected_agents)) &
        (df["Run Type"].isin(selected_run_types))
    ]

    # Display table
    st.subheader(f"Comparison Table ({len(filtered_df)} runs)")

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )

    # Download option
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        "Download as CSV",
        csv,
        "evaluation_comparison.csv",
        "text/csv",
    )

    # Summary statistics
    st.markdown("---")
    st.subheader("Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_pass_rate = filtered_df["Passed"].sum() / filtered_df["Tasks"].sum() * 100 if filtered_df["Tasks"].sum() > 0 else 0
        st.metric("Average Pass Rate", f"{avg_pass_rate:.1f}%")

    with col2:
        total_cost = filtered_df["Cost (USD)"].str.replace("$", "").astype(float).sum()
        st.metric("Total Cost", f"${total_cost:.2f}")

    with col3:
        total_tasks = filtered_df["Tasks"].sum()
        st.metric("Total Tasks", total_tasks)

    with col4:
        unique_benchmarks = filtered_df["Benchmark"].nunique()
        st.metric("Benchmarks", unique_benchmarks)


if __name__ == "__main__":
    show_comparison_enhanced()
