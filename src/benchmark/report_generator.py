"""
REPORT.md Generator

Generates human-readable markdown reports from evaluation_report.json.
Includes:
- Summary tables
- Agent comparisons
- Judge assessment highlights
- Tool usage breakdown
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


def generate_report_md(evaluation_report: Dict[str, Any], output_path: Path):
    """
    Generate REPORT.md from evaluation report.

    Args:
        evaluation_report: Loaded evaluation_report.json data
        output_path: Where to write REPORT.md
    """
    lines = []

    # Header
    lines.append(f"# Evaluation Report: {evaluation_report.get('experiment_id', 'N/A')}")
    lines.append("")
    lines.append(f"**Description:** {evaluation_report.get('experiment_description', 'N/A')}")
    lines.append(f"**Profile:** {evaluation_report.get('profile_name', 'N/A')}")
    lines.append(f"**Generated:** {evaluation_report.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary section
    summary = evaluation_report.get("summary", {})
    agents = summary.get("agents", {})

    lines.append("## Summary")
    lines.append("")
    lines.append(f"**Total Runs:** {summary.get('total_runs', 0)}")
    lines.append(f"**Agents Evaluated:** {len(agents)}")
    lines.append("")

    # Agent comparison table
    if agents:
        lines.append("### Agent Comparison")
        lines.append("")
        lines.append(
            "| Agent | Runs | Success Rate | Avg Tokens | Cost | Retrieval Quality | Code Quality |"
        )
        lines.append(
            "|-------|------|--------------|------------|------|-------------------|--------------|"
        )

        for agent_name, stats in sorted(agents.items()):
            total_runs = stats.get("total_runs", 0)
            success_rate = stats.get("success_rate", 0) * 100
            avg_tokens = stats.get("avg_tokens", 0)
            cost = stats.get("total_cost_usd", 0)

            judge_scores = stats.get("judge_scores", {})
            retrieval = judge_scores.get("retrieval_quality", {}).get("mean", 0)
            code = judge_scores.get("code_quality", {}).get("mean", 0)

            lines.append(
                f"| {agent_name} | {total_runs} | {success_rate:.1f}% | {avg_tokens:,.0f} | ${cost:.2f} | {retrieval:.2f}/5 | {code:.2f}/5 |"
            )

        lines.append("")

    # Benchmark metadata
    benchmark_metadata = evaluation_report.get("benchmark_metadata")
    if benchmark_metadata:
        lines.append("---")
        lines.append("")
        lines.append("## Benchmark Metadata")
        lines.append("")
        lines.append(f"**Benchmark ID:** {benchmark_metadata.get('benchmark_id', 'N/A')}")
        lines.append(f"**Description:** {benchmark_metadata.get('description', 'N/A')}")
        lines.append(
            f"**Pipeline Version:** {benchmark_metadata.get('pipeline_version', 'N/A')}"
        )
        lines.append(f"**Repo Commit:** `{benchmark_metadata.get('repo_commit', 'N/A')}`")
        lines.append("")

        # Datasets
        datasets = benchmark_metadata.get("datasets", [])
        if datasets:
            lines.append("**Datasets:**")
            for ds in datasets:
                path = Path(ds.get("path", "unknown")).name
                sha = ds.get("sha256", "N/A")[:16]
                lines.append(f"- `{path}` (SHA-256: `{sha}...`)")
            lines.append("")

    # Detailed agent runs
    agent_runs = evaluation_report.get("agent_runs", [])

    if agent_runs:
        lines.append("---")
        lines.append("")
        lines.append("## Detailed Results")
        lines.append("")

        # Group by agent
        by_agent: Dict[str, List] = {}
        for run in agent_runs:
            agent_name = run.get("agent_name", "unknown")
            if agent_name not in by_agent:
                by_agent[agent_name] = []
            by_agent[agent_name].append(run)

        for agent_name, runs in sorted(by_agent.items()):
            lines.append(f"### {agent_name}")
            lines.append("")

            for run in runs:
                task_name = run.get("task_name", "unknown")
                reward = run.get("reward", 0)
                success = "✅" if run.get("success", False) else "❌"

                lines.append(f"#### {success} {task_name}")
                lines.append("")

                # Metrics
                token_metrics = run.get("token_metrics", {})
                timing = run.get("timing_metrics", {})

                lines.append(f"**Reward:** {reward:.2f}")
                lines.append(
                    f"**Tokens:** {token_metrics.get('total_input_tokens', 0) + token_metrics.get('total_output_tokens', 0):,}"
                )
                lines.append(f"**Execution Time:** {timing.get('agent_execution_sec', 0):.1f}s")
                lines.append("")

                # Judge assessments
                assessments = run.get("judge_assessments", [])
                if assessments:
                    lines.append("**Judge Assessments:**")
                    for assessment in assessments:
                        dimension = assessment.get("dimension", "unknown").replace("_", " ").title()
                        score = assessment.get("score", 0)
                        reasoning = assessment.get("reasoning", "")

                        lines.append(f"- **{dimension}:** {score}/5")
                        lines.append(f"  - {reasoning}")

                    lines.append("")

                # Top tools
                tool_usage = run.get("tool_usage", [])
                if tool_usage:
                    top_tools = sorted(tool_usage, key=lambda x: x.get("call_count", 0), reverse=True)[
                        :5
                    ]
                    lines.append("**Top Tools:**")
                    for tool in top_tools:
                        tool_name = tool.get("tool_name", "unknown")
                        calls = tool.get("call_count", 0)
                        lines.append(f"- `{tool_name}`: {calls} calls")

                    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by CodeContextBench evaluation pipeline*")

    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
