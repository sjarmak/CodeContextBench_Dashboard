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


# Task-level report generation

def generate_task_report(
    run_id: str,
    task_name: str,
    agent_name: str,
    result_data: Dict,
    trajectory_data: Dict,
    judge_evaluation: Dict = None,
    task_metadata: Dict = None
) -> Dict[str, Any]:
    """
    Generate comprehensive evaluation report for a single task.

    Args:
        run_id: Evaluation run ID
        task_name: Task name
        agent_name: Agent name
        result_data: Result data from result.json
        trajectory_data: Trajectory data from trajectory.json
        judge_evaluation: Optional LLM judge evaluation data
        task_metadata: Optional task metadata (from task.toml)

    Returns:
        Report data dictionary
    """
    # Extract basic info
    reward = result_data.get("verifier_result", {}).get("rewards", {}).get("reward", 0.0)
    success = reward > 0.0

    # Token metrics
    agent_result = result_data.get("agent_result", {})
    token_metrics = {
        "total_input_tokens": agent_result.get("n_input_tokens", 0),
        "total_output_tokens": agent_result.get("n_output_tokens", 0),
        "total_cache_tokens": agent_result.get("n_cache_tokens", 0),
        "total_tokens": agent_result.get("n_input_tokens", 0) + agent_result.get("n_output_tokens", 0),
        "cost_usd": agent_result.get("cost_usd")
    }

    # Timing metrics
    started_at = result_data.get("started_at", "")
    finished_at = result_data.get("finished_at", "")

    # Calculate phase durations
    env_setup = result_data.get("environment_setup", {})
    agent_setup = result_data.get("agent_setup", {})
    agent_execution = result_data.get("agent_execution", {})
    verifier = result_data.get("verifier", {})

    def calculate_duration(phase_data):
        """Calculate duration from started_at and finished_at."""
        if phase_data.get("started_at") and phase_data.get("finished_at"):
            try:
                start = datetime.fromisoformat(phase_data["started_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(phase_data["finished_at"].replace("Z", "+00:00"))
                return (end - start).total_seconds()
            except:
                return 0.0
        return 0.0

    timing_metrics = {
        "environment_setup_sec": calculate_duration(env_setup),
        "agent_setup_sec": calculate_duration(agent_setup),
        "agent_execution_sec": calculate_duration(agent_execution),
        "verifier_sec": calculate_duration(verifier),
        "total_sec": calculate_duration({
            "started_at": started_at,
            "finished_at": finished_at
        }),
        "started_at": started_at,
        "finished_at": finished_at
    }

    # Tool usage summary
    tool_usage = extract_tool_usage(trajectory_data)

    # Code changes summary
    code_changes = extract_code_changes(trajectory_data)

    # Build report
    report = {
        "report_version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "run_id": run_id,
        "task_name": task_name,
        "agent_name": agent_name,
        "result": {
            "reward": reward,
            "success": success,
            "exception": result_data.get("exception_info")
        },
        "metrics": {
            "tokens": token_metrics,
            "timing": timing_metrics,
            "tool_usage": tool_usage,
            "code_changes": code_changes
        }
    }

    # Add task metadata if available
    if task_metadata:
        report["task_metadata"] = {
            "description": task_metadata.get("metadata", {}).get("description", ""),
            "difficulty": task_metadata.get("task", {}).get("difficulty", "unknown"),
            "language": task_metadata.get("task", {}).get("language", "unknown"),
            "category": task_metadata.get("task", {}).get("category", "unknown")
        }

    # Add judge evaluation if available
    if judge_evaluation:
        report["judge_evaluation"] = {
            "judge_model": judge_evaluation.get("judge_model", ""),
            "score": judge_evaluation.get("score", 0.0),
            "reasoning": judge_evaluation.get("reasoning", ""),
            "evaluation_data": judge_evaluation.get("evaluation_data", {})
        }

    return report


def extract_tool_usage(trajectory: Dict) -> Dict[str, int]:
    """Extract tool usage counts from trajectory."""
    tool_counts = {}

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name:
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # Also check old format
        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    if name:
                        tool_counts[name] = tool_counts.get(name, 0) + 1

    return tool_counts


def extract_code_changes(trajectory: Dict) -> Dict[str, Any]:
    """Extract code changes summary from trajectory."""
    edits = 0
    writes = 0
    files_modified = set()

    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")

        if tool_name:
            if "edit" in tool_name.lower():
                edits += 1
                raw_args = extra.get("raw_arguments", {})
                file_path = raw_args.get("file_path", "")
                if file_path:
                    files_modified.add(file_path)

            elif "write" in tool_name.lower():
                writes += 1
                raw_args = extra.get("raw_arguments", {})
                file_path = raw_args.get("file_path", "")
                if file_path:
                    files_modified.add(file_path)

        # Also check old format
        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "")
                    input_data = item.get("input", {})

                    if "edit" in name.lower():
                        edits += 1
                        file_path = input_data.get("file_path", "")
                        if file_path:
                            files_modified.add(file_path)

                    elif "write" in name.lower():
                        writes += 1
                        file_path = input_data.get("file_path", "")
                        if file_path:
                            files_modified.add(file_path)

    return {
        "total_edits": edits,
        "total_writes": writes,
        "files_modified": len(files_modified),
        "file_list": sorted(list(files_modified))
    }


def format_task_report_markdown(report: Dict) -> str:
    """Format task report as Markdown."""
    lines = []

    lines.append(f"# Task Report: {report['task_name']}")
    lines.append("")
    lines.append(f"**Generated:** {report['generated_at'][:19]}")
    lines.append(f"**Run ID:** {report['run_id']}")
    lines.append(f"**Agent:** {report['agent_name']}")
    lines.append("")

    # Task metadata
    if "task_metadata" in report:
        meta = report["task_metadata"]
        lines.append("## Task")
        lines.append(f"- **Description:** {meta.get('description', 'N/A')}")
        lines.append(f"- **Difficulty:** {meta.get('difficulty', 'N/A')}")
        lines.append(f"- **Language:** {meta.get('language', 'N/A')}")
        lines.append(f"- **Category:** {meta.get('category', 'N/A')}")
        lines.append("")

    # Result
    result = report["result"]
    lines.append("## Result")
    lines.append(f"- **Success:** {'Yes' if result['success'] else 'No'}")
    lines.append(f"- **Reward:** {result['reward']}")
    if result.get("exception"):
        lines.append(f"- **Exception:** {result['exception']}")
    lines.append("")

    # Metrics
    metrics = report["metrics"]

    # Tokens
    tokens = metrics["tokens"]
    lines.append("## Token Usage")
    lines.append(f"- **Total Tokens:** {tokens['total_tokens']:,}")
    lines.append(f"- **Input Tokens:** {tokens['total_input_tokens']:,}")
    lines.append(f"- **Output Tokens:** {tokens['total_output_tokens']:,}")
    lines.append(f"- **Cache Tokens:** {tokens['total_cache_tokens']:,}")
    if tokens.get("cost_usd"):
        lines.append(f"- **Cost:** ${tokens['cost_usd']:.4f}")
    lines.append("")

    # Timing
    timing = metrics["timing"]
    lines.append("## Timing")
    lines.append(f"- **Total Time:** {timing['total_sec']:.1f}s")
    lines.append(f"- **Environment Setup:** {timing['environment_setup_sec']:.1f}s")
    lines.append(f"- **Agent Setup:** {timing['agent_setup_sec']:.1f}s")
    lines.append(f"- **Agent Execution:** {timing['agent_execution_sec']:.1f}s")
    lines.append(f"- **Verifier:** {timing['verifier_sec']:.1f}s")
    lines.append("")

    # Tool usage
    tool_usage = metrics["tool_usage"]
    if tool_usage:
        lines.append("## Tool Usage")
        for tool_name, count in sorted(tool_usage.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{tool_name}:** {count}")
        lines.append("")

    # Code changes
    code_changes = metrics["code_changes"]
    lines.append("## Code Changes")
    lines.append(f"- **Total Edits:** {code_changes['total_edits']}")
    lines.append(f"- **Total Writes:** {code_changes['total_writes']}")
    lines.append(f"- **Files Modified:** {code_changes['files_modified']}")
    if code_changes.get("file_list"):
        lines.append("\n**Modified Files:**")
        for file_path in code_changes["file_list"]:
            lines.append(f"- `{file_path}`")
    lines.append("")

    # Judge evaluation
    if "judge_evaluation" in report:
        judge = report["judge_evaluation"]
        lines.append("## LLM Judge Evaluation")
        lines.append(f"- **Judge Model:** {judge['judge_model']}")
        lines.append(f"- **Score:** {judge['score']:.2f}/5")
        lines.append(f"- **Reasoning:** {judge['reasoning']}")

        eval_data = judge.get("evaluation_data", {})

        if eval_data.get("retrieval_quality"):
            ret = eval_data["retrieval_quality"]
            lines.append("\n### Retrieval Quality")
            lines.append(f"- **Score:** {ret.get('score', 0)}/5")
            lines.append(f"- **Reasoning:** {ret.get('reasoning', 'N/A')}")
            if ret.get("strengths"):
                lines.append("\n**Strengths:**")
                for strength in ret["strengths"]:
                    lines.append(f"- {strength}")
            if ret.get("weaknesses"):
                lines.append("\n**Weaknesses:**")
                for weakness in ret["weaknesses"]:
                    lines.append(f"- {weakness}")

        if eval_data.get("code_quality"):
            code = eval_data["code_quality"]
            lines.append("\n### Code Quality")
            lines.append(f"- **Score:** {code.get('score', 0)}/5")
            lines.append(f"- **Reasoning:** {code.get('reasoning', 'N/A')}")
            if code.get("strengths"):
                lines.append("\n**Strengths:**")
                for strength in code["strengths"]:
                    lines.append(f"- {strength}")
            if code.get("weaknesses"):
                lines.append("\n**Weaknesses:**")
                for weakness in code["weaknesses"]:
                    lines.append(f"- {weakness}")

        lines.append("")

    return "\n".join(lines)


def format_task_report_json(report: Dict) -> str:
    """Format task report as JSON."""
    import json
    return json.dumps(report, indent=2)


def format_task_report_csv_row(report: Dict) -> str:
    """Format task report as CSV row."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    result = report["result"]
    tokens = report["metrics"]["tokens"]
    timing = report["metrics"]["timing"]
    code_changes = report["metrics"]["code_changes"]

    judge_score = ""
    judge_model = ""
    if "judge_evaluation" in report:
        judge_score = report["judge_evaluation"].get("score", "")
        judge_model = report["judge_evaluation"].get("judge_model", "")

    writer.writerow([
        report["task_name"],
        report["agent_name"],
        result["success"],
        result["reward"],
        tokens["total_tokens"],
        tokens["total_input_tokens"],
        tokens["total_output_tokens"],
        tokens["total_cache_tokens"],
        timing["total_sec"],
        timing["agent_execution_sec"],
        code_changes["total_edits"],
        code_changes["total_writes"],
        code_changes["files_modified"],
        judge_score,
        judge_model
    ])

    return output.getvalue().strip()
