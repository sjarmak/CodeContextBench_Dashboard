"""
Enhanced Comparison Table with A/B Analysis

Comprehensive comparison of evaluation runs including:
- Agent type comparison (baseline vs MCP variants)
- Paired A/B analysis (same task across tool stacks)
- Benchmark (full vs subset)
- Tokens, time, pass/fail
- Visualizations (bar charts, radar charts)
- Tool stack comparison
"""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import RunManager, TaskManager, BenchmarkRegistry, ToolStackRegistry
from benchmark.cost_calculator import calculate_cost
import pandas as pd
import json

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


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
            # Handle None rewards from old runs
            passed = len([t for t in agent_tasks if (t.get("reward") or 0) > 0])
            failed = total_tasks - passed

            # Load result data for tokens/cost
            total_input_tokens = 0
            total_output_tokens = 0
            total_cached_tokens = 0
            total_cost = 0.0
            total_time = 0.0

            for task in agent_tasks:
                if task.get("result_path"):
                    try:
                        with open(task["result_path"]) as f:
                            result_data = json.load(f)

                        agent_result = result_data.get("agent_result", {})
                        total_input_tokens += agent_result.get("n_input_tokens", 0)
                        total_output_tokens += agent_result.get("n_output_tokens", 0)
                        total_cached_tokens += agent_result.get("n_cache_tokens", 0)

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

            # Calculate total billable tokens (all tokens, including cached)
            total_tokens = total_input_tokens + total_output_tokens + total_cached_tokens

            comparison_data.append({
                "Run ID": run["run_id"],
                "Benchmark": benchmark_name,
                "Run Type": run_type,
                "Agent": agent_name.split(":")[-1],
                "Tasks": total_tasks,
                "Passed": passed,
                "Failed": failed,
                "Pass Rate": f"{passed/total_tasks*100:.1f}%" if total_tasks > 0 else "0%",
                "Input Tokens": f"{total_input_tokens:,}",
                "Output Tokens": f"{total_output_tokens:,}",
                "Cached Tokens": f"{total_cached_tokens:,}",
                "Total Tokens": f"{total_tokens:,}",
                "Cost (USD)": f"${total_cost:.4f}",
                "Avg Time (s)": f"{total_time/total_tasks:.1f}" if total_tasks > 0 else "0",
            })

    return comparison_data


def create_paired_comparison(df):
    """Create paired comparison data for same tasks across agents."""
    # Group by benchmark and task to find paired runs
    paired_data = []

    # Get unique benchmarks
    benchmarks = df["Benchmark"].unique()

    for benchmark in benchmarks:
        benchmark_df = df[df["Benchmark"] == benchmark]
        agents = benchmark_df["Agent"].unique()

        if len(agents) < 2:
            continue

        # Compare each pair of agents
        for i, agent_a in enumerate(agents):
            for agent_b in agents[i+1:]:
                a_data = benchmark_df[benchmark_df["Agent"] == agent_a].iloc[0] if len(benchmark_df[benchmark_df["Agent"] == agent_a]) > 0 else None
                b_data = benchmark_df[benchmark_df["Agent"] == agent_b].iloc[0] if len(benchmark_df[benchmark_df["Agent"] == agent_b]) > 0 else None

                if a_data is not None and b_data is not None:
                    # Parse pass rates
                    a_pass = float(a_data["Pass Rate"].replace("%", "")) if isinstance(a_data["Pass Rate"], str) else a_data["Pass Rate"]
                    b_pass = float(b_data["Pass Rate"].replace("%", "")) if isinstance(b_data["Pass Rate"], str) else b_data["Pass Rate"]

                    # Parse costs
                    a_cost = float(a_data["Cost (USD)"].replace("$", "")) if isinstance(a_data["Cost (USD)"], str) else a_data["Cost (USD)"]
                    b_cost = float(b_data["Cost (USD)"].replace("$", "")) if isinstance(b_data["Cost (USD)"], str) else b_data["Cost (USD)"]

                    paired_data.append({
                        "Benchmark": benchmark,
                        "Agent A": agent_a,
                        "Agent B": agent_b,
                        "A Pass Rate": a_pass,
                        "B Pass Rate": b_pass,
                        "Pass Rate Delta": b_pass - a_pass,
                        "A Cost": a_cost,
                        "B Cost": b_cost,
                        "Cost Delta": b_cost - a_cost,
                        "A Tasks": a_data["Tasks"],
                        "B Tasks": b_data["Tasks"],
                    })

    return pd.DataFrame(paired_data) if paired_data else pd.DataFrame()


def show_comparison_charts(df):
    """Show comparison charts using Plotly."""
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly not installed. Run `pip install plotly` for charts.")
        return

    col1, col2 = st.columns(2)

    with col1:
        # Success rate by agent
        st.subheader("Pass Rate by Agent")

        # Parse pass rate
        df_chart = df.copy()
        df_chart["Pass Rate Value"] = df_chart["Pass Rate"].apply(
            lambda x: float(x.replace("%", "")) if isinstance(x, str) else x
        )

        fig = px.bar(
            df_chart,
            x="Agent",
            y="Pass Rate Value",
            color="Benchmark",
            barmode="group",
            title="Pass Rate by Agent and Benchmark"
        )
        fig.update_yaxes(title="Pass Rate (%)", range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Token usage comparison
        st.subheader("Token Usage by Agent")

        # Parse token values
        df_chart = df.copy()
        for col in ["Input Tokens", "Output Tokens", "Cached Tokens"]:
            df_chart[f"{col} Value"] = df_chart[col].apply(
                lambda x: int(x.replace(",", "")) if isinstance(x, str) else x
            )

        # Aggregate by agent
        agent_tokens = df_chart.groupby("Agent").agg({
            "Input Tokens Value": "sum",
            "Output Tokens Value": "sum",
            "Cached Tokens Value": "sum"
        }).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Input", x=agent_tokens["Agent"], y=agent_tokens["Input Tokens Value"]))
        fig.add_trace(go.Bar(name="Output", x=agent_tokens["Agent"], y=agent_tokens["Output Tokens Value"]))
        fig.add_trace(go.Bar(name="Cached", x=agent_tokens["Agent"], y=agent_tokens["Cached Tokens Value"]))
        fig.update_layout(barmode="stack", title="Token Usage by Agent (Stacked)")
        fig.update_yaxes(title="Tokens")
        st.plotly_chart(fig, use_container_width=True)

    # Cost comparison
    st.subheader("Cost Comparison")
    df_chart = df.copy()
    df_chart["Cost Value"] = df_chart["Cost (USD)"].apply(
        lambda x: float(x.replace("$", "")) if isinstance(x, str) else x
    )

    fig = px.bar(
        df_chart,
        x="Agent",
        y="Cost Value",
        color="Benchmark",
        barmode="group",
        title="Cost by Agent and Benchmark (USD)"
    )
    fig.update_yaxes(title="Cost (USD)")
    st.plotly_chart(fig, use_container_width=True)


def show_paired_analysis(df):
    """Show paired A/B analysis."""
    paired_df = create_paired_comparison(df)

    if paired_df.empty:
        st.info("Need at least 2 agents on the same benchmark for paired comparison.")
        return

    st.subheader("Paired Agent Comparison")
    st.write("Compare performance between agent pairs on the same benchmark")

    # Show paired comparison table
    st.dataframe(
        paired_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pass Rate Delta": st.column_config.NumberColumn(
                "Pass Rate Delta (%)",
                format="%.1f",
                help="Positive = Agent B better, Negative = Agent A better"
            ),
            "Cost Delta": st.column_config.NumberColumn(
                "Cost Delta ($)",
                format="%.4f",
                help="Positive = Agent B more expensive"
            )
        }
    )

    # Delta visualization
    if PLOTLY_AVAILABLE and len(paired_df) > 0:
        st.subheader("Pass Rate Delta (Agent B - Agent A)")

        fig = px.bar(
            paired_df,
            x="Benchmark",
            y="Pass Rate Delta",
            color="Agent B",
            title="Pass Rate Improvement (Positive = B Better)",
            hover_data=["Agent A", "Agent B", "A Pass Rate", "B Pass Rate"]
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_yaxes(title="Pass Rate Delta (%)")
        st.plotly_chart(fig, use_container_width=True)


def show_comparison_enhanced():
    """Main enhanced comparison page."""
    st.title("Evaluation Comparison")
    st.write("Compare evaluation runs across agents, benchmarks, and tool stacks")

    # Load data
    comparison_data = load_comparison_data()

    if not comparison_data:
        st.info("No completed runs to compare. Run evaluations first.")
        return

    # Create dataframe
    df = pd.DataFrame(comparison_data)

    # Filters in sidebar-style expander
    with st.expander("Filters", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            benchmarks = df["Benchmark"].unique().tolist()
            selected_benchmarks = st.multiselect("Benchmarks", benchmarks, default=benchmarks, key="cmp_bench")

        with col2:
            agents = df["Agent"].unique().tolist()
            selected_agents = st.multiselect("Agents", agents, default=agents, key="cmp_agent")

        with col3:
            run_types = df["Run Type"].unique().tolist()
            selected_run_types = st.multiselect("Run Type", run_types, default=run_types, key="cmp_type")

    # Filter dataframe
    filtered_df = df[
        (df["Benchmark"].isin(selected_benchmarks)) &
        (df["Agent"].isin(selected_agents)) &
        (df["Run Type"].isin(selected_run_types))
    ]

    if filtered_df.empty:
        st.warning("No runs match the selected filters.")
        return

    # Summary metrics at top
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_pass_rate = filtered_df["Passed"].sum() / filtered_df["Tasks"].sum() * 100 if filtered_df["Tasks"].sum() > 0 else 0
        st.metric("Avg Pass Rate", f"{avg_pass_rate:.1f}%")

    with col2:
        total_cost = filtered_df["Cost (USD)"].str.replace("$", "").astype(float).sum()
        st.metric("Total Cost", f"${total_cost:.2f}")

    with col3:
        total_tasks = filtered_df["Tasks"].sum()
        st.metric("Total Tasks", total_tasks)

    with col4:
        unique_agents = filtered_df["Agent"].nunique()
        st.metric("Agents", unique_agents)

    st.markdown("---")

    # Tabs for different views
    tab_table, tab_charts, tab_paired = st.tabs(["Table", "Charts", "A/B Comparison"])

    with tab_table:
        st.subheader(f"Comparison Table ({len(filtered_df)} runs)")

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
        )

        st.caption("💡 **Cached Tokens:** Charged at ~10% of regular input rates.")

        # Download option
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "Download as CSV",
            csv,
            "evaluation_comparison.csv",
            "text/csv",
        )

    with tab_charts:
        show_comparison_charts(filtered_df)

    with tab_paired:
        show_paired_analysis(filtered_df)

    # Tool stack legend
    st.markdown("---")
    st.caption("**Tool Stacks:** Baseline (no MCP) | Sourcegraph MCP (full toolkit) | Deep Search MCP (semantic search only)")


if __name__ == "__main__":
    show_comparison_enhanced()
