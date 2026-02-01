"""
Deep Search Analytics Dashboard

Analyzes MCP Deep Search usage patterns:
- Search query types and frequency
- Tool usage distribution (deep_search vs keyword_search vs nls_search)
- Retrieval success patterns
- Token efficiency metrics
"""

import streamlit as st
from pathlib import Path
import json
from typing import Dict, Any, List
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from collections import defaultdict


def analyze_deep_search_usage(trajectory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze Deep Search tool usage from a trajectory.

    Returns:
        Dictionary with analysis metrics
    """
    analysis = {
        "sg_deepsearch_calls": 0,
        "sg_keyword_calls": 0,
        "sg_nls_calls": 0,
        "local_grep_calls": 0,
        "local_glob_calls": 0,
        "total_search_calls": 0,
        "queries": [],
        "avg_tokens_per_search": 0,
        "search_tokens": [],
    }

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if not tool_name:
            continue

        # Categorize search tools
        if "sg_deepsearch" in tool_name or "mcp__sg__sg_deepsearch" in tool_name:
            analysis["sg_deepsearch_calls"] += 1
            analysis["total_search_calls"] += 1

            # Extract query
            raw_args = extra.get("raw_arguments", {})
            query = raw_args.get("query", "")
            if query:
                analysis["queries"].append({"type": "deep_search", "query": query})

        elif "sg_keyword_search" in tool_name or "mcp__sg__sg_keyword_search" in tool_name:
            analysis["sg_keyword_calls"] += 1
            analysis["total_search_calls"] += 1

            raw_args = extra.get("raw_arguments", {})
            query = raw_args.get("query", "")
            if query:
                analysis["queries"].append({"type": "keyword_search", "query": query})

        elif "sg_nls_search" in tool_name or "mcp__sg__sg_nls_search" in tool_name:
            analysis["sg_nls_calls"] += 1
            analysis["total_search_calls"] += 1

            raw_args = extra.get("raw_arguments", {})
            query = raw_args.get("query", "")
            if query:
                analysis["queries"].append({"type": "nls_search", "query": query})

        elif "grep" in tool_name.lower() and "mcp__" not in tool_name:
            analysis["local_grep_calls"] += 1
            analysis["total_search_calls"] += 1

        elif "glob" in tool_name.lower() and "mcp__" not in tool_name:
            analysis["local_glob_calls"] += 1
            analysis["total_search_calls"] += 1

        # Track tokens for search steps
        if analysis["total_search_calls"] > 0:
            metrics = step.get("metrics", {})
            prompt_tokens = metrics.get("prompt_tokens", 0)
            completion_tokens = metrics.get("completion_tokens", 0)
            total = prompt_tokens + completion_tokens
            if total > 0:
                analysis["search_tokens"].append(total)

    if analysis["search_tokens"]:
        analysis["avg_tokens_per_search"] = sum(analysis["search_tokens"]) / len(
            analysis["search_tokens"]
        )

    return analysis


def load_trajectories_from_experiment(exp_dir: Path) -> List[tuple[str, str, Dict]]:
    """
    Load all trajectories from an experiment.

    Returns:
        List of (agent_name, task_name, trajectory) tuples
    """
    trajectories = []

    for trial_dir in exp_dir.rglob("*"):
        if not trial_dir.is_dir():
            continue

        trajectory_file = trial_dir / "agent" / "trajectory.json"
        result_file = trial_dir / "result.json"

        if not trajectory_file.exists() or not result_file.exists():
            continue

        # Load result to get agent and task names
        with open(result_file) as f:
            result = json.load(f)

        agent_config = result.get("config", {}).get("agent", {})
        agent_import = agent_config.get("import_path", "unknown")
        agent_name = agent_import.split(":")[-1] if ":" in agent_import else "unknown"

        task_name = result.get("task_name", "unknown")

        # Load trajectory
        with open(trajectory_file) as f:
            trajectory = json.load(f)

        trajectories.append((agent_name, task_name, trajectory))

    return trajectories


def create_tool_distribution_pie(analyses: List[Dict[str, Any]]) -> go.Figure:
    """Create pie chart of tool usage distribution."""
    # Aggregate across all analyses
    total_deep = sum(a["sg_deepsearch_calls"] for a in analyses)
    total_keyword = sum(a["sg_keyword_calls"] for a in analyses)
    total_nls = sum(a["sg_nls_calls"] for a in analyses)
    total_grep = sum(a["local_grep_calls"] for a in analyses)
    total_glob = sum(a["local_glob_calls"] for a in analyses)

    labels = ["Deep Search", "Keyword Search", "NLS Search", "Local Grep", "Local Glob"]
    values = [total_deep, total_keyword, total_nls, total_grep, total_glob]

    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])

    fig.update_layout(title="Search Tool Distribution", height=400)

    return fig


def create_agent_tool_comparison(
    agent_analyses: Dict[str, List[Dict[str, Any]]]
) -> go.Figure:
    """Create stacked bar chart comparing tool usage across agents."""
    agents = sorted(agent_analyses.keys())

    deep_search = []
    keyword_search = []
    nls_search = []
    local_tools = []

    for agent in agents:
        analyses = agent_analyses[agent]

        deep_search.append(sum(a["sg_deepsearch_calls"] for a in analyses))
        keyword_search.append(sum(a["sg_keyword_calls"] for a in analyses))
        nls_search.append(sum(a["sg_nls_calls"] for a in analyses))
        local_tools.append(
            sum(a["local_grep_calls"] + a["local_glob_calls"] for a in analyses)
        )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(name="Deep Search", x=agents, y=deep_search, marker_color="blue")
    )
    fig.add_trace(
        go.Bar(name="Keyword Search", x=agents, y=keyword_search, marker_color="lightblue")
    )
    fig.add_trace(
        go.Bar(name="NLS Search", x=agents, y=nls_search, marker_color="cyan")
    )
    fig.add_trace(
        go.Bar(name="Local Tools", x=agents, y=local_tools, marker_color="gray")
    )

    fig.update_layout(
        barmode="stack",
        title="Search Tool Usage by Agent",
        xaxis_title="Agent",
        yaxis_title="Number of Calls",
        height=400,
    )

    return fig


def show_deep_search_analytics():
    """Main Deep Search analytics page."""
    st.title("Deep Search Analytics")
    st.markdown("Analyze MCP Deep Search usage patterns and effectiveness.")

    # Get project root
    project_root = st.session_state.get("project_root", Path.cwd())
    jobs_dir = project_root / "jobs"

    if not jobs_dir.exists():
        st.error(f"Jobs directory not found: {jobs_dir}")
        return

    # Experiment selector
    exp_dirs = [
        d.name
        for d in sorted(jobs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if d.is_dir() and not d.name.startswith(".")
    ]

    selected_exp = st.selectbox("Select Experiment", exp_dirs)

    if not selected_exp:
        return

    exp_path = jobs_dir / selected_exp

    # Load trajectories
    with st.spinner("Loading trajectories..."):
        trajectories = load_trajectories_from_experiment(exp_path)

    if not trajectories:
        st.warning("No trajectories found in experiment.")
        return

    st.success(f"Loaded {len(trajectories)} trajectories")

    # Analyze all trajectories
    with st.spinner("Analyzing Deep Search usage..."):
        all_analyses = []
        agent_analyses: Dict[str, List[Dict]] = defaultdict(list)

        for agent_name, task_name, trajectory in trajectories:
            analysis = analyze_deep_search_usage(trajectory)
            analysis["agent_name"] = agent_name
            analysis["task_name"] = task_name

            all_analyses.append(analysis)
            agent_analyses[agent_name].append(analysis)

    st.markdown("---")

    # Summary metrics
    st.subheader("Summary Metrics")

    col1, col2, col3, col4 = st.columns(4)

    total_deep = sum(a["sg_deepsearch_calls"] for a in all_analyses)
    total_keyword = sum(a["sg_keyword_calls"] for a in all_analyses)
    total_nls = sum(a["sg_nls_calls"] for a in all_analyses)
    total_local = sum(
        a["local_grep_calls"] + a["local_glob_calls"] for a in all_analyses
    )

    with col1:
        st.metric("Deep Search Calls", total_deep)

    with col2:
        st.metric("Keyword Search Calls", total_keyword)

    with col3:
        st.metric("NLS Search Calls", total_nls)

    with col4:
        st.metric("Local Tool Calls", total_local)

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Pie chart
        pie_chart = create_tool_distribution_pie(all_analyses)
        st.plotly_chart(pie_chart, use_container_width=True)

    with col2:
        # Agent comparison
        bar_chart = create_agent_tool_comparison(agent_analyses)
        st.plotly_chart(bar_chart, use_container_width=True)

    st.markdown("---")

    # Query analysis
    st.subheader("Query Analysis")

    all_queries = []
    for analysis in all_analyses:
        for query_info in analysis["queries"]:
            all_queries.append(
                {
                    "Agent": analysis["agent_name"],
                    "Task": analysis["task_name"],
                    "Type": query_info["type"],
                    "Query": query_info["query"],
                }
            )

    if all_queries:
        df = pd.DataFrame(all_queries)

        # Filter by type
        query_types = df["Type"].unique().tolist()
        selected_type = st.selectbox("Filter by Search Type", ["All"] + query_types)

        if selected_type != "All":
            df = df[df["Type"] == selected_type]

        st.dataframe(df, use_container_width=True, height=400)

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            "Download Queries as CSV",
            csv,
            f"{selected_exp}_queries.csv",
            "text/csv",
        )
    else:
        st.info("No search queries found in experiment.")

    st.markdown("---")

    # Per-agent breakdown
    st.subheader("Per-Agent Breakdown")

    for agent_name, analyses in sorted(agent_analyses.items()):
        with st.expander(f"{agent_name} ({len(analyses)} runs)"):
            avg_deep = sum(a["sg_deepsearch_calls"] for a in analyses) / len(analyses)
            avg_keyword = sum(a["sg_keyword_calls"] for a in analyses) / len(analyses)
            avg_nls = sum(a["sg_nls_calls"] for a in analyses) / len(analyses)
            avg_local = sum(
                a["local_grep_calls"] + a["local_glob_calls"] for a in analyses
            ) / len(analyses)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Avg Deep Search", f"{avg_deep:.1f}")

            with col2:
                st.metric("Avg Keyword", f"{avg_keyword:.1f}")

            with col3:
                st.metric("Avg NLS", f"{avg_nls:.1f}")

            with col4:
                st.metric("Avg Local Tools", f"{avg_local:.1f}")


if __name__ == "__main__":
    show_deep_search_analytics()
