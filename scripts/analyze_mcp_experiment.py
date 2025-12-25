#!/usr/bin/env python3
"""
Analyze MCP Experiment Results

Generates a comprehensive report from experiment data including:
- Reward summary per agent/task
- Deep Search usage analysis
- LLM judge scores
- Overall recommendations

Usage:
    python scripts/analyze_mcp_experiment.py <experiment_dir>
"""

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.benchmark.provenance import build_provenance_section, load_profile_metadata

def count_tool_usage(trajectory_path: Path) -> dict:
    """Count tool usage from trajectory file."""
    counts = defaultdict(int)

    if not trajectory_path.exists():
        return counts

    try:
        with open(trajectory_path) as f:
            trajectory = json.load(f)
    except Exception:
        return counts

    # New format: extra.tool_use_name
    for step in trajectory.get("steps", []):
        extra = step.get("extra", {})
        tool_name = extra.get("tool_use_name", "")
        if tool_name:
            counts[tool_name] += 1

    # Old format: content list
    for step in trajectory.get("steps", []):
        if step.get("role") != "assistant":
            continue

        content = step.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "unknown")
                    counts[name] += 1

    return dict(counts)


def detect_experiment_format(experiment_dir: Path) -> str:
    """Detect if this is single-task or multi-task format."""
    agent_names = {"strategic", "aggressive", "baseline"}
    subdirs = {d.name for d in experiment_dir.iterdir() if d.is_dir()}

    if subdirs & agent_names:
        return "single-task"

    for subdir in experiment_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith("big-code-"):
            return "multi-task"

    return "unknown"


def find_task_from_path(path: Path) -> str:
    """Extract task name from a path."""
    for part in path.parts:
        if "big-code-" in part:
            if "__" in part:
                return part.split("__")[0]
            return part
    return "unknown-task"


def extract_timing(result_path: Path) -> float:
    """Extract timing from result file."""
    if not result_path.exists():
        return 0.0

    try:
        with open(result_path) as f:
            result = json.load(f)

        started = result.get("started_at", "")
        finished = result.get("finished_at", "")

        if started and finished:
            # Parse ISO format timestamps
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
            return (end_dt - start_dt).total_seconds()
    except Exception:
        pass

    return 0.0


def extract_reward(result_path: Path) -> float:
    """Extract reward from result file."""
    if not result_path.exists():
        return 0.0

    try:
        with open(result_path) as f:
            result = json.load(f)

        stats = result.get("stats", {}).get("evals", {})
        for eval_data in stats.values():
            metrics = eval_data.get("metrics", [])
            if metrics:
                return metrics[0].get("mean", 0.0)
    except Exception:
        pass

    return 0.0


def analyze_experiment(experiment_dir: Path) -> dict:
    """Analyze all results in experiment directory."""
    analysis = {
        "tasks": {},
        "agents": defaultdict(
            lambda: {
                "total_reward": 0,
                "count": 0,
                "times": [],
                "deep_search_calls": [],
            }
        ),
        "overall": {},
    }

    exp_format = detect_experiment_format(experiment_dir)

    if exp_format == "single-task":
        # Agent directories at top level
        for agent_dir in sorted(experiment_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("."):
                continue

            agent_name = agent_dir.name
            if agent_name not in {"strategic", "aggressive", "baseline"}:
                continue

            # Find result and trajectory files
            result_files = list(agent_dir.rglob("result.json"))
            trajectory_files = list(agent_dir.rglob("trajectory.json"))

            if not result_files:
                continue

            task_name = (
                find_task_from_path(trajectory_files[0])
                if trajectory_files
                else "unknown-task"
            )

            if task_name not in analysis["tasks"]:
                analysis["tasks"][task_name] = {}

            reward = extract_reward(result_files[0])
            timing = extract_timing(result_files[0])
            tool_counts = (
                count_tool_usage(trajectory_files[0]) if trajectory_files else {}
            )

            # Count Deep Search specifically
            deep_search_count = sum(
                v
                for k, v in tool_counts.items()
                if "sg_deepsearch" in k.lower() or "deepsearch" in k.lower()
            )

            analysis["tasks"][task_name][agent_name] = {
                "reward": reward,
                "time_seconds": timing,
                "time_formatted": f"{int(timing // 60)}:{int(timing % 60):02d}",
                "deep_search_calls": deep_search_count,
                "tool_counts": tool_counts,
            }

            # Aggregate by agent
            analysis["agents"][agent_name]["total_reward"] += reward
            analysis["agents"][agent_name]["count"] += 1
            analysis["agents"][agent_name]["times"].append(timing)
            analysis["agents"][agent_name]["deep_search_calls"].append(
                deep_search_count
            )
    else:
        # Multi-task format: task directories with agent subdirectories
        for task_dir in sorted(experiment_dir.iterdir()):
            if not task_dir.is_dir() or not task_dir.name.startswith("big-code-"):
                continue

            task_name = task_dir.name
            analysis["tasks"][task_name] = {}

            for agent_dir in sorted(task_dir.iterdir()):
                if not agent_dir.is_dir():
                    continue

                agent_name = agent_dir.name

                # Find result and trajectory files
                result_files = list(agent_dir.rglob("result.json"))
                trajectory_files = list(agent_dir.rglob("trajectory.json"))

                reward = extract_reward(result_files[0]) if result_files else 0.0
                timing = extract_timing(result_files[0]) if result_files else 0.0
                tool_counts = (
                    count_tool_usage(trajectory_files[0]) if trajectory_files else {}
                )

                # Count Deep Search specifically
                deep_search_count = sum(
                    v
                    for k, v in tool_counts.items()
                    if "sg_deepsearch" in k.lower() or "deepsearch" in k.lower()
                )

                analysis["tasks"][task_name][agent_name] = {
                    "reward": reward,
                    "time_seconds": timing,
                    "time_formatted": f"{int(timing // 60)}:{int(timing % 60):02d}",
                    "deep_search_calls": deep_search_count,
                    "tool_counts": tool_counts,
                }

                # Aggregate by agent
                analysis["agents"][agent_name]["total_reward"] += reward
                analysis["agents"][agent_name]["count"] += 1
                analysis["agents"][agent_name]["times"].append(timing)
                analysis["agents"][agent_name]["deep_search_calls"].append(
                    deep_search_count
                )

    # Calculate overall stats
    for agent_name, data in analysis["agents"].items():
        if data["count"] > 0:
            data["avg_reward"] = data["total_reward"] / data["count"]
            data["avg_time"] = (
                sum(data["times"]) / len(data["times"]) if data["times"] else 0
            )
            data["avg_deep_search"] = (
                sum(data["deep_search_calls"]) / len(data["deep_search_calls"])
                if data["deep_search_calls"]
                else 0
            )

    return analysis


def load_judge_results(experiment_dir: Path) -> dict:
    """Load LLM judge results if available."""
    judge_path = experiment_dir / "llm_judge_results.json"
    if judge_path.exists():
        with open(judge_path) as f:
            return json.load(f)
    return {}


def generate_report(
    experiment_dir: Path,
    analysis: dict,
    judge_results: dict,
    profile_metadata: dict | None = None,
) -> str:
    """Generate markdown report including provenance details."""
    lines = [
        "# MCP Experiment Full Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Experiment Directory:** `{experiment_dir}`",
        "",
        "## Executive Summary",
        "",
    ]

    # Calculate winner
    agents = dict(analysis["agents"])
    if agents:
        best_agent = max(
            agents.items(),
            key=lambda x: (
                x[1].get("avg_reward", 0),
                -x[1].get("avg_time", float("inf")),
            ),
        )
        fastest_agent = min(
            agents.items(), key=lambda x: x[1].get("avg_time", float("inf"))
        )

        lines.extend(
            [
                f"- **Best Overall Agent:** {best_agent[0]} (avg reward: {best_agent[1].get('avg_reward', 0):.2f})",
                f"- **Fastest Agent:** {fastest_agent[0]} (avg time: {fastest_agent[1].get('avg_time', 0):.0f}s)",
                "",
            ]
        )

    # Results table
    lines.extend(
        [
            "## Results by Task",
            "",
            "| Task | Agent | Reward | Time | Deep Search | Retrieval | Code |",
            "|------|-------|--------|------|-------------|-----------|------|",
        ]
    )

    for task_name, task_data in sorted(analysis["tasks"].items()):
        for agent_name, agent_data in sorted(task_data.items()):
            reward = agent_data.get("reward", 0)
            time_fmt = agent_data.get("time_formatted", "N/A")
            ds_calls = agent_data.get("deep_search_calls", 0)

            # Get judge scores if available
            r_score = "-"
            c_score = "-"
            if task_name in judge_results and agent_name in judge_results[task_name]:
                jr = judge_results[task_name][agent_name]
                if "retrieval" in jr:
                    r_score = f"{jr['retrieval'].get('score', 0)}/5"
                if "code" in jr:
                    c_score = f"{jr['code'].get('score', 0)}/5"

            reward_icon = "✅" if reward >= 1.0 else "❌" if reward == 0 else "⚠️"
            lines.append(
                f"| {task_name} | {agent_name} | {reward_icon} {reward:.1f} | {time_fmt} | {ds_calls} | {r_score} | {c_score} |"
            )

    # Agent comparison
    lines.extend(
        [
            "",
            "## Agent Comparison (Aggregated)",
            "",
            "| Agent | Avg Reward | Avg Time | Avg Deep Search | Success Rate |",
            "|-------|------------|----------|-----------------|--------------|",
        ]
    )

    for agent_name, data in sorted(agents.items()):
        avg_reward = data.get("avg_reward", 0)
        avg_time = data.get("avg_time", 0)
        avg_ds = data.get("avg_deep_search", 0)
        success_rate = (data.get("total_reward", 0) / data.get("count", 1)) * 100

        time_fmt = f"{int(avg_time // 60)}:{int(avg_time % 60):02d}"
        lines.append(
            f"| {agent_name} | {avg_reward:.2f} | {time_fmt} | {avg_ds:.1f} | {success_rate:.0f}% |"
        )

    # Key insights
    lines.extend(
        [
            "",
            "## Key Insights",
            "",
        ]
    )

    # Compare MCP vs baseline
    if "baseline" in agents and "aggressive" in agents:
        baseline_time = agents["baseline"].get("avg_time", 0)
        aggressive_time = agents["aggressive"].get("avg_time", 0)

        if baseline_time > 0 and aggressive_time > 0:
            speedup = ((baseline_time - aggressive_time) / baseline_time) * 100
            lines.append(
                f"1. **MCP Speedup:** Aggressive Deep Search is {speedup:.0f}% faster than baseline"
            )

    if "strategic" in agents and "aggressive" in agents:
        strat_ds = agents["strategic"].get("avg_deep_search", 0)
        aggr_ds = agents["aggressive"].get("avg_deep_search", 0)
        lines.append(
            f"2. **Deep Search Usage:** Strategic uses {strat_ds:.1f} calls vs Aggressive's {aggr_ds:.1f} calls"
        )

    # LLM Judge insights
    if judge_results:
        avg_retrieval = []
        avg_code = []
        for task_data in judge_results.values():
            for agent_data in task_data.values():
                if "retrieval" in agent_data:
                    avg_retrieval.append(agent_data["retrieval"].get("score", 0))
                if "code" in agent_data:
                    avg_code.append(agent_data["code"].get("score", 0))

        if avg_retrieval:
            lines.append(
                f"3. **Avg Retrieval Quality:** {sum(avg_retrieval) / len(avg_retrieval):.1f}/5"
            )
        if avg_code:
            lines.append(
                f"4. **Avg Code Quality:** {sum(avg_code) / len(avg_code):.1f}/5"
            )

    # Recommendations
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "Based on this experiment:",
            "",
        ]
    )

    if agents.get("aggressive", {}).get("avg_time", float("inf")) < agents.get(
        "strategic", {}
    ).get("avg_time", float("inf")):
        lines.append("- **Use aggressive Deep Search** for large codebases (>1M lines)")
        lines.append(
            "- The overhead of extra searches is offset by faster context gathering"
        )
    else:
        lines.append("- **Use strategic Deep Search** for balanced performance")
        lines.append("- Fewer targeted searches may be more efficient")

    provenance_lines = build_provenance_section(profile_metadata or {})
    if provenance_lines:
        lines.extend(provenance_lines)

    lines.extend(
        [
            "",
            "---",
            f"*Report generated by analyze_mcp_experiment.py*",
        ]
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze MCP Experiment Results")
    parser.add_argument("experiment_dir", help="Path to experiment directory")
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    if not experiment_dir.exists():
        print(f"ERROR: Experiment directory not found: {experiment_dir}")
        return 1

    print(f"Analyzing: {experiment_dir}")

    # Run analysis
    analysis = analyze_experiment(experiment_dir)
    judge_results = load_judge_results(experiment_dir)
    profile_metadata = load_profile_metadata(experiment_dir)
    if profile_metadata:
        analysis["profile_metadata"] = profile_metadata

    # Generate report
    report = generate_report(experiment_dir, analysis, judge_results, profile_metadata)

    # Save report
    report_path = experiment_dir / "REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\n✓ Report saved to {report_path}")

    # Also print to stdout
    print("\n" + "=" * 60)
    print(report)

    # Save raw analysis
    analysis_path = experiment_dir / "analysis.json"
    with open(analysis_path, "w") as f:
        # Convert defaultdict to dict for JSON serialization
        analysis["agents"] = dict(analysis["agents"])
        json.dump(analysis, f, indent=2)

    print(f"\n✓ Raw analysis saved to {analysis_path}")

    return 0


if __name__ == "__main__":
    exit(main())
