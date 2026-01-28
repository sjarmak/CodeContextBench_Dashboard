#!/usr/bin/env python3
"""
Analyze benchmark runs from ~/evals/ and generate v2 manifests.

This script processes completed Harbor benchmark runs that were executed outside
the v2 CLI framework, extracting metrics and generating proper v2-format manifests.

Usage:
    python scripts/analyze_evals_v2.py --evals-dir ~/evals/custom_agents/agents/claudecode
    python scripts/analyze_evals_v2.py --run locobench_50_tasks_20260124_225159
    python scripts/analyze_evals_v2.py --run swebenchpro_run_baseline_opus_nodebb_seed0_ce2dc3
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TaskResult:
    """Individual task result from Harbor."""
    task_name: str
    trial_name: str
    reward: float
    model: str
    agent_name: str

    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    agent_execution_seconds: float = 0.0
    verifier_seconds: float = 0.0

    # Token usage
    input_tokens: int = 0
    cache_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None

    # Source info
    source: str = ""
    mcp_mode: str = "baseline"

    raw_result: dict = field(default_factory=dict)


@dataclass
class RunSummary:
    """Summary metrics for a benchmark run."""
    run_id: str
    benchmark: str
    mcp_mode: str
    model: str

    total_tasks: int = 0
    mean_reward: float = 0.0
    min_reward: float = 0.0
    max_reward: float = 0.0

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_tokens: int = 0
    total_cost_usd: float = 0.0

    # Timing
    total_duration_seconds: float = 0.0
    mean_agent_execution_seconds: float = 0.0

    # Task breakdown
    tasks: list[TaskResult] = field(default_factory=list)

    # Status
    started_at: str = ""
    finished_at: str = ""


def parse_harbor_result(result_path: Path) -> TaskResult | None:
    """Parse a Harbor result.json file."""
    try:
        with open(result_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Warning: Could not parse {result_path}: {e}")
        return None

    # Extract reward
    verifier_result = data.get("verifier_result") or {}
    rewards = verifier_result.get("rewards") or {}
    reward = rewards.get("reward", 0.0)

    # Extract model info
    agent_info = data.get("agent_info") or {}
    model_info = agent_info.get("model_info") or {}
    config = data.get("config") or {}
    agent_config = config.get("agent") or {}
    model = model_info.get("name") or agent_config.get("model_name") or "unknown"

    # Extract timing
    timing = {}
    for key in ["started_at", "finished_at"]:
        timing[key] = data.get(key, "")

    agent_exec = data.get("agent_execution") or {}
    verifier = data.get("verifier") or {}

    agent_exec_seconds = 0.0
    verifier_seconds = 0.0

    if agent_exec.get("started_at") and agent_exec.get("finished_at"):
        try:
            start = datetime.fromisoformat(agent_exec["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(agent_exec["finished_at"].replace("Z", "+00:00"))
            agent_exec_seconds = (end - start).total_seconds()
        except ValueError:
            pass

    if verifier.get("started_at") and verifier.get("finished_at"):
        try:
            start = datetime.fromisoformat(verifier["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(verifier["finished_at"].replace("Z", "+00:00"))
            verifier_seconds = (end - start).total_seconds()
        except ValueError:
            pass

    total_duration = 0.0
    if timing.get("started_at") and timing.get("finished_at"):
        try:
            start = datetime.fromisoformat(timing["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(timing["finished_at"].replace("Z", "+00:00"))
            total_duration = (end - start).total_seconds()
        except ValueError:
            pass

    # Extract token usage
    agent_result = data.get("agent_result") or {}

    # Determine MCP mode from path or config
    mcp_mode = "baseline"
    if "deepsearch" in str(result_path).lower() or "hybrid" in str(result_path).lower():
        mcp_mode = "deepsearch_hybrid"

    # Check for .mcp.json in the same directory
    mcp_config_path = result_path.parent / "agent" / ".mcp.json"
    if mcp_config_path.exists():
        mcp_mode = "deepsearch_hybrid"

    return TaskResult(
        task_name=data.get("task_name", "unknown"),
        trial_name=data.get("trial_name", result_path.parent.name),
        reward=float(reward) if reward is not None else 0.0,
        model=model,
        agent_name=agent_info.get("name", "claude-code"),
        started_at=timing.get("started_at", ""),
        finished_at=timing.get("finished_at", ""),
        duration_seconds=total_duration,
        agent_execution_seconds=agent_exec_seconds,
        verifier_seconds=verifier_seconds,
        input_tokens=agent_result.get("n_input_tokens") or 0,
        cache_tokens=agent_result.get("n_cache_tokens") or 0,
        output_tokens=agent_result.get("n_output_tokens") or 0,
        cost_usd=agent_result.get("cost_usd"),
        source=data.get("source", ""),
        mcp_mode=mcp_mode,
        raw_result=data,
    )


def discover_runs(jobs_dir: Path) -> list[Path]:
    """Discover all benchmark run directories."""
    runs = []

    for item in jobs_dir.iterdir():
        if not item.is_dir():
            continue

        # Skip hidden directories
        if item.name.startswith("."):
            continue

        # Check if it contains result.json files
        result_files = list(item.glob("**/result.json"))
        if result_files:
            runs.append(item)

    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def analyze_run(run_dir: Path) -> dict[str, RunSummary]:
    """Analyze a benchmark run directory and return summaries by MCP mode."""
    print(f"\nAnalyzing: {run_dir.name}")

    summaries: dict[str, RunSummary] = {}

    # Find all result.json files
    result_files = list(run_dir.glob("**/result.json"))

    # Skip top-level result.json (run summary, not task result)
    task_results = [f for f in result_files if f.parent != run_dir]

    print(f"  Found {len(task_results)} task results")

    # Detect benchmark type
    benchmark = "unknown"
    if "locobench" in run_dir.name.lower():
        benchmark = "locobench_agent"
    elif "swebench" in run_dir.name.lower():
        benchmark = "swebench_pro"

    # Group by MCP mode
    results_by_mode: dict[str, list[TaskResult]] = {}

    for result_file in task_results:
        task_result = parse_harbor_result(result_file)
        if task_result is None:
            continue

        mode = task_result.mcp_mode
        if mode not in results_by_mode:
            results_by_mode[mode] = []
        results_by_mode[mode].append(task_result)

    # Build summaries for each mode
    for mode, tasks in results_by_mode.items():
        if not tasks:
            continue

        rewards = [t.reward for t in tasks]

        summary = RunSummary(
            run_id=f"{run_dir.name}_{mode}",
            benchmark=benchmark,
            mcp_mode=mode,
            model=tasks[0].model if tasks else "unknown",
            total_tasks=len(tasks),
            mean_reward=sum(rewards) / len(rewards) if rewards else 0.0,
            min_reward=min(rewards) if rewards else 0.0,
            max_reward=max(rewards) if rewards else 0.0,
            total_input_tokens=sum(t.input_tokens for t in tasks),
            total_output_tokens=sum(t.output_tokens for t in tasks),
            total_cache_tokens=sum(t.cache_tokens for t in tasks),
            total_cost_usd=sum(t.cost_usd or 0 for t in tasks),
            total_duration_seconds=sum(t.duration_seconds for t in tasks),
            mean_agent_execution_seconds=(
                sum(t.agent_execution_seconds for t in tasks) / len(tasks)
                if tasks else 0.0
            ),
            tasks=tasks,
        )

        # Set timing bounds
        start_times = [t.started_at for t in tasks if t.started_at]
        end_times = [t.finished_at for t in tasks if t.finished_at]

        if start_times:
            summary.started_at = min(start_times)
        if end_times:
            summary.finished_at = max(end_times)

        summaries[mode] = summary

        print(f"  {mode}: {summary.total_tasks} tasks, mean_reward={summary.mean_reward:.4f}")

    return summaries


def generate_manifest(
    summaries: dict[str, RunSummary],
    run_dir: Path,
    output_dir: Path | None = None
) -> dict:
    """Generate a v2-format manifest from run summaries."""

    if not summaries:
        return {}

    # Get any summary for common fields
    sample = next(iter(summaries.values()))

    experiment_id = f"exp_{run_dir.name[:20]}_{datetime.utcnow().strftime('%Y-%m-%d')}"

    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": experiment_id,
        "created_at": sample.started_at or datetime.utcnow().isoformat() + "Z",
        "finished_at": sample.finished_at or datetime.utcnow().isoformat() + "Z",
        "status": "completed",
        "config": {
            "source_dir": str(run_dir),
            "experiment_name": run_dir.name,
            "description": f"Retroactive analysis of {run_dir.name}",
            "benchmarks": [sample.benchmark],
            "models": list(set(s.model for s in summaries.values())),
            "mcp_modes": list(summaries.keys()),
            "seeds": [0],
            "tags": ["retroactive-analysis", sample.benchmark],
        },
        "matrix_summary": {
            "total_runs": len(summaries),
            "total_pairs": 1 if len(summaries) == 2 else 0,
            "dimensions": {
                "benchmarks": 1,
                "models": len(set(s.model for s in summaries.values())),
                "mcp_modes": len(summaries),
                "seeds": 1,
                "tasks": max(s.total_tasks for s in summaries.values()),
            },
        },
        "runs": [
            {
                "run_id": s.run_id,
                "status": "completed",
                "mcp_mode": s.mcp_mode,
                "total_tasks": s.total_tasks,
                "mean_reward": s.mean_reward,
            }
            for s in summaries.values()
        ],
    }

    # Build pairs if we have baseline and MCP
    if "baseline" in summaries and len(summaries) > 1:
        mcp_modes = [m for m in summaries.keys() if m != "baseline"]
        manifest["pairs"] = [
            {
                "pair_id": f"pair_{mode}",
                "baseline_run_id": summaries["baseline"].run_id,
                "mcp_run_id": summaries[mode].run_id,
                "status": "completed",
            }
            for mode in mcp_modes
        ]
    else:
        manifest["pairs"] = []

    return manifest


def generate_index(
    summaries: dict[str, RunSummary],
    manifest: dict
) -> dict:
    """Generate a v2-format index from run summaries."""

    runs_by_mode: dict[str, list[str]] = {}
    runs_by_model: dict[str, list[str]] = {}
    runs_by_task: dict[str, list[str]] = {}

    for mode, summary in summaries.items():
        runs_by_mode[mode] = [summary.run_id]

        if summary.model not in runs_by_model:
            runs_by_model[summary.model] = []
        runs_by_model[summary.model].append(summary.run_id)

        for task in summary.tasks:
            if task.task_name not in runs_by_task:
                runs_by_task[task.task_name] = []
            runs_by_task[task.task_name].append(summary.run_id)

    # Compute aggregate stats
    baseline_mean = summaries.get("baseline", RunSummary("", "", "", "")).mean_reward
    mcp_modes = [m for m in summaries.keys() if m != "baseline"]
    mcp_mean = (
        sum(summaries[m].mean_reward for m in mcp_modes) / len(mcp_modes)
        if mcp_modes else 0.0
    )

    improvement = 0.0
    if baseline_mean > 0:
        improvement = ((mcp_mean - baseline_mean) / baseline_mean) * 100

    return {
        "schema_version": "1.0.0",
        "experiment_id": manifest.get("experiment_id", ""),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "runs_by_mcp_mode": runs_by_mode,
        "runs_by_model": runs_by_model,
        "runs_by_task": runs_by_task,
        "pairs_by_task": {},  # Would need paired task analysis
        "aggregate_stats": {
            "baseline": {
                "total_runs": 1 if "baseline" in summaries else 0,
                "mean_reward": baseline_mean,
                "total_tasks": summaries.get("baseline", RunSummary("", "", "", "")).total_tasks,
            },
            "mcp": {
                "total_runs": len(mcp_modes),
                "mean_reward": mcp_mean,
                "total_tasks": sum(summaries[m].total_tasks for m in mcp_modes) if mcp_modes else 0,
            },
            "improvement_pct": improvement,
        },
    }


def generate_report(summaries: dict[str, RunSummary], run_dir: Path) -> str:
    """Generate a markdown report for the run."""

    lines = [
        f"# Benchmark Analysis: {run_dir.name}",
        f"",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"",
    ]

    # Summary table
    lines.extend([
        "## Summary",
        "",
        "| MCP Mode | Tasks | Mean Reward | Min | Max | Input Tokens | Output Tokens |",
        "|----------|-------|-------------|-----|-----|--------------|---------------|",
    ])

    for mode, s in sorted(summaries.items()):
        lines.append(
            f"| {mode} | {s.total_tasks} | {s.mean_reward:.4f} | "
            f"{s.min_reward:.4f} | {s.max_reward:.4f} | "
            f"{s.total_input_tokens:,} | {s.total_output_tokens:,} |"
        )

    # Comparison
    if "baseline" in summaries and len(summaries) > 1:
        baseline = summaries["baseline"]
        lines.extend([
            "",
            "## MCP vs Baseline Comparison",
            "",
        ])

        for mode, s in summaries.items():
            if mode == "baseline":
                continue

            delta = s.mean_reward - baseline.mean_reward
            pct = (delta / baseline.mean_reward * 100) if baseline.mean_reward > 0 else 0

            lines.extend([
                f"### {mode}",
                f"- Mean Reward Delta: {delta:+.4f} ({pct:+.1f}%)",
                f"- Token Usage Delta: {s.total_input_tokens - baseline.total_input_tokens:+,} input, "
                f"{s.total_output_tokens - baseline.total_output_tokens:+,} output",
                "",
            ])

    # Per-task details
    lines.extend([
        "## Per-Task Results",
        "",
    ])

    for mode, s in sorted(summaries.items()):
        lines.extend([
            f"### {mode}",
            "",
            "| Task | Reward | Duration (s) | Input Tokens |",
            "|------|--------|--------------|--------------|",
        ])

        for task in sorted(s.tasks, key=lambda t: t.reward, reverse=True)[:20]:
            lines.append(
                f"| {task.task_name[:50]} | {task.reward:.4f} | "
                f"{task.agent_execution_seconds:.1f} | {task.input_tokens:,} |"
            )

        if len(s.tasks) > 20:
            lines.append(f"| ... and {len(s.tasks) - 20} more tasks | | | |")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze benchmark runs and generate v2 manifests"
    )
    parser.add_argument(
        "--evals-dir",
        type=Path,
        default=Path.home() / "evals" / "custom_agents" / "agents" / "claudecode",
        help="Base evals directory"
    )
    parser.add_argument(
        "--run",
        type=str,
        help="Specific run directory name to analyze"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("analysis_output"),
        help="Output directory for manifests and reports"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available runs"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of markdown"
    )

    args = parser.parse_args()

    runs_dir = args.evals_dir / "runs"

    if not runs_dir.exists():
        print(f"Error: Runs directory not found: {runs_dir}")
        sys.exit(1)

    # Discover runs
    runs = discover_runs(runs_dir)

    if args.list:
        print(f"Available runs in {runs_dir}:\n")
        for run in runs:
            result_count = len(list(run.glob("**/result.json")))
            print(f"  {run.name} ({result_count} results)")
        sys.exit(0)

    # Filter to specific run if requested
    if args.run:
        runs = [r for r in runs if args.run in r.name]
        if not runs:
            print(f"Error: No runs found matching '{args.run}'")
            sys.exit(1)

    # Analyze runs
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for run_dir in runs:
        summaries = analyze_run(run_dir)

        if not summaries:
            continue

        # Generate manifest
        manifest = generate_manifest(summaries, run_dir)
        index = generate_index(summaries, manifest)
        report = generate_report(summaries, run_dir)

        # Save outputs
        run_output_dir = args.output_dir / run_dir.name
        run_output_dir.mkdir(parents=True, exist_ok=True)

        with open(run_output_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        with open(run_output_dir / "index.json", "w") as f:
            json.dump(index, f, indent=2)

        with open(run_output_dir / "REPORT.md", "w") as f:
            f.write(report)

        # Also save detailed per-task results
        detailed = {
            mode: {
                "summary": {
                    "run_id": s.run_id,
                    "benchmark": s.benchmark,
                    "mcp_mode": s.mcp_mode,
                    "model": s.model,
                    "total_tasks": s.total_tasks,
                    "mean_reward": s.mean_reward,
                    "total_input_tokens": s.total_input_tokens,
                    "total_output_tokens": s.total_output_tokens,
                },
                "tasks": [
                    {
                        "task_name": t.task_name,
                        "reward": t.reward,
                        "input_tokens": t.input_tokens,
                        "output_tokens": t.output_tokens,
                        "duration_seconds": t.duration_seconds,
                        "agent_execution_seconds": t.agent_execution_seconds,
                    }
                    for t in s.tasks
                ],
            }
            for mode, s in summaries.items()
        }

        with open(run_output_dir / "detailed_results.json", "w") as f:
            json.dump(detailed, f, indent=2)

        all_results[run_dir.name] = {
            "manifest": manifest,
            "index": index,
        }

        print(f"  Output saved to: {run_output_dir}")

    # Print final summary
    if args.json:
        print(json.dumps(all_results, indent=2))
    else:
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)

        for run_name, data in all_results.items():
            stats = data["index"].get("aggregate_stats", {})
            baseline = stats.get("baseline", {})
            mcp = stats.get("mcp", {})

            print(f"\n{run_name}:")
            print(f"  Baseline: {baseline.get('total_tasks', 0)} tasks, "
                  f"mean_reward={baseline.get('mean_reward', 0):.4f}")
            print(f"  MCP:      {mcp.get('total_tasks', 0)} tasks, "
                  f"mean_reward={mcp.get('mean_reward', 0):.4f}")
            print(f"  Delta:    {stats.get('improvement_pct', 0):+.1f}%")


if __name__ == "__main__":
    main()
