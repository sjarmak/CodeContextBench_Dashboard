"""
Agent Comparison View

Side-by-side comparison of agent performance with:
- Success rate charts
- Token usage comparison
- Judge score radar charts
- Tool usage heatmaps
"""

import streamlit as st
from pathlib import Path
import json
from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def find_evaluation_reports(jobs_dir: Path) -> List[tuple[str, Path]]:
    """Find all evaluation reports."""
    reports = []

    if not jobs_dir.exists():
        return []

    for exp_dir in sorted(jobs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not exp_dir.is_dir() or exp_dir.name.startswith("."):
            continue

        report_file = exp_dir / "evaluation_report.json"
        if report_file.exists():
            reports.append((exp_dir.name, report_file))

    return reports


def load_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Load evaluation report."""
    try:
        with open(report_path) as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load report: {e}")
        return None


def create_success_rate_chart(report: Dict[str, Any]) -> go.Figure:
    """Create success rate comparison bar chart."""
    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if not agents:
        return None

    agent_names = []
    success_rates = []
    total_runs = []

    for agent_name, stats in sorted(agents.items()):
        agent_names.append(agent_name)
        success_rates.append(stats.get("success_rate", 0) * 100)
        total_runs.append(stats.get("total_runs", 0))

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=agent_names,
            y=success_rates,
            text=[f"{sr:.1f}%<br>({tr} runs)" for sr, tr in zip(success_rates, total_runs)],
            textposition="auto",
            marker_color="lightblue",
        )
    )

    fig.update_layout(
        title="Success Rate by Agent",
        xaxis_title="Agent",
        yaxis_title="Success Rate (%)",
        yaxis_range=[0, 100],
        height=400,
    )

    return fig


def create_token_usage_chart(report: Dict[str, Any]) -> go.Figure:
    """Create token usage comparison chart."""
    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if not agents:
        return None

    agent_names = []
    avg_tokens = []

    for agent_name, stats in sorted(agents.items()):
        agent_names.append(agent_name)
        avg_tokens.append(stats.get("avg_tokens", 0))

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=agent_names,
            y=avg_tokens,
            text=[f"{at:,.0f}" for at in avg_tokens],
            textposition="auto",
            marker_color="lightgreen",
        )
    )

    fig.update_layout(
        title="Average Token Usage by Agent",
        xaxis_title="Agent",
        yaxis_title="Avg Tokens per Run",
        height=400,
    )

    return fig


def create_judge_score_radar(report: Dict[str, Any]) -> go.Figure:
    """Create radar chart for judge scores."""
    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if not agents:
        return None

    fig = go.Figure()

    for agent_name, stats in sorted(agents.items()):
        judge_scores = stats.get("judge_scores", {})

        categories = []
        values = []

        for dimension, scores in judge_scores.items():
            if isinstance(scores, dict):
                categories.append(dimension.replace("_", " ").title())
                values.append(scores.get("mean", 0))

        if categories:
            # Close the radar chart
            categories.append(categories[0])
            values.append(values[0])

            fig.add_trace(
                go.Scatterpolar(r=values, theta=categories, fill="toself", name=agent_name)
            )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
        showlegend=True,
        title="Judge Scores by Agent",
        height=500,
    )

    return fig


def create_tool_usage_heatmap(report: Dict[str, Any]) -> go.Figure:
    """Create heatmap of tool usage across agents."""
    agent_runs = report.get("agent_runs", [])

    if not agent_runs:
        return None

    # Collect all tools used by each agent
    agent_tools: Dict[str, Dict[str, int]] = {}

    for run in agent_runs:
        agent_name = run.get("agent_name", "unknown")

        if agent_name not in agent_tools:
            agent_tools[agent_name] = {}

        for tool in run.get("tool_usage", []):
            tool_name = tool.get("tool_name", "unknown")
            calls = tool.get("call_count", 0)

            if tool_name not in agent_tools[agent_name]:
                agent_tools[agent_name][tool_name] = 0

            agent_tools[agent_name][tool_name] += calls

    # Get all unique tools
    all_tools = set()
    for tools in agent_tools.values():
        all_tools.update(tools.keys())

    all_tools = sorted(all_tools)

    # Create matrix
    matrix = []
    agent_names = sorted(agent_tools.keys())

    for agent_name in agent_names:
        row = [agent_tools[agent_name].get(tool, 0) for tool in all_tools]
        matrix.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=all_tools,
            y=agent_names,
            colorscale="Blues",
            text=matrix,
            texttemplate="%{text}",
            textfont={"size": 10},
        )
    )

    fig.update_layout(
        title="Tool Usage Heatmap (Total Calls)",
        xaxis_title="Tool",
        yaxis_title="Agent",
        height=400,
    )

    return fig


def create_cost_comparison(report: Dict[str, Any]) -> go.Figure:
    """Create cost comparison chart."""
    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if not agents:
        return None

    agent_names = []
    costs = []

    for agent_name, stats in sorted(agents.items()):
        agent_names.append(agent_name)
        costs.append(stats.get("total_cost_usd", 0))

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=agent_names,
            y=costs,
            text=[f"${c:.2f}" for c in costs],
            textposition="auto",
            marker_color="lightcoral",
        )
    )

    fig.update_layout(
        title="Total Cost by Agent", xaxis_title="Agent", yaxis_title="Cost (USD)", height=400
    )

    return fig


def show_comparison_view():
    """Main comparison view page."""
    st.title("Agent Comparison")
    st.markdown("Side-by-side comparison of agent performance across metrics.")

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    jobs_dir = project_root / "jobs"

    if not jobs_dir.exists():
        st.error(f"Jobs directory not found: {jobs_dir}")
        return

    # Find evaluation reports
    reports = find_evaluation_reports(jobs_dir)

    if not reports:
        st.warning("No evaluation reports found. Run postprocess script first.")
        return

    # Report selector
    report_names = [name for name, _ in reports]
    selected_name = st.selectbox("Select Experiment", report_names)

    if not selected_name:
        return

    # Load report
    report_path = None
    for name, path in reports:
        if name == selected_name:
            report_path = path
            break

    if not report_path:
        return

    report = load_report(report_path)

    if not report:
        return

    st.markdown("---")

    # Summary table
    st.subheader("Summary Table")

    summary = report.get("summary", {})
    agents = summary.get("agents", {})

    if agents:
        data = []
        for agent_name, stats in sorted(agents.items()):
            judge_scores = stats.get("judge_scores", {})
            retrieval = judge_scores.get("retrieval_quality", {}).get("mean", 0)
            code = judge_scores.get("code_quality", {}).get("mean", 0)

            data.append(
                {
                    "Agent": agent_name,
                    "Runs": stats.get("total_runs", 0),
                    "Success Rate": f"{stats.get('success_rate', 0)*100:.1f}%",
                    "Avg Tokens": f"{stats.get('avg_tokens', 0):,.0f}",
                    "Cost": f"${stats.get('total_cost_usd', 0):.2f}",
                    "Retrieval": f"{retrieval:.2f}/5",
                    "Code": f"{code:.2f}/5",
                }
            )

        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Success rate chart
        success_chart = create_success_rate_chart(report)
        if success_chart:
            st.plotly_chart(success_chart, use_container_width=True)

    with col2:
        # Token usage chart
        token_chart = create_token_usage_chart(report)
        if token_chart:
            st.plotly_chart(token_chart, use_container_width=True)

    # Judge scores radar
    radar_chart = create_judge_score_radar(report)
    if radar_chart:
        st.plotly_chart(radar_chart, use_container_width=True)

    # Tool usage heatmap
    st.subheader("🔧 Tool Usage Analysis")
    heatmap = create_tool_usage_heatmap(report)
    if heatmap:
        st.plotly_chart(heatmap, use_container_width=True)

    # Cost comparison
    col1, col2 = st.columns(2)

    with col1:
        cost_chart = create_cost_comparison(report)
        if cost_chart:
            st.plotly_chart(cost_chart, use_container_width=True)


if __name__ == "__main__":
    show_comparison_view()
