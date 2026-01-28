#!/usr/bin/env python3
"""
Combine separate benchmark runs for comparison analysis.

This script merges SWE-bench Pro baseline and deepsearch runs that were
executed in separate directories into a unified comparison.

Usage:
    python scripts/combine_benchmark_runs.py \
        --baseline ~/evals/.../swebenchpro_run_baseline_* \
        --mcp ~/evals/.../swebenchpro_run_deepsearch_* \
        --output-dir analysis_output/swebenchpro_combined
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_analysis(analysis_dir: Path) -> dict:
    """Load analysis results from a directory."""
    results = {}

    manifest_path = analysis_dir / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            results["manifest"] = json.load(f)

    index_path = analysis_dir / "index.json"
    if index_path.exists():
        with open(index_path) as f:
            results["index"] = json.load(f)

    detailed_path = analysis_dir / "detailed_results.json"
    if detailed_path.exists():
        with open(detailed_path) as f:
            results["detailed"] = json.load(f)

    return results


def combine_runs(
    baseline_dir: Path,
    mcp_dir: Path,
    output_dir: Path,
    benchmark_name: str = "combined"
) -> dict:
    """Combine baseline and MCP run analyses into a unified comparison."""

    baseline = load_analysis(baseline_dir)
    mcp = load_analysis(mcp_dir)

    if not baseline or not mcp:
        print("Error: Could not load both baseline and MCP analyses")
        return {}

    # Extract summaries
    baseline_summary = None
    mcp_summary = None

    if "detailed" in baseline:
        for mode, data in baseline["detailed"].items():
            if "summary" in data:
                baseline_summary = data["summary"]
                baseline_tasks = data.get("tasks", [])
                break

    if "detailed" in mcp:
        for mode, data in mcp["detailed"].items():
            if "summary" in data:
                mcp_summary = data["summary"]
                mcp_tasks = data.get("tasks", [])
                break

    if not baseline_summary or not mcp_summary:
        print("Error: Could not extract summaries from analyses")
        return {}

    # Create combined manifest
    now = datetime.now(timezone.utc).isoformat()

    combined_manifest = {
        "schema_version": "1.0.0",
        "experiment_id": f"exp_{benchmark_name}_combined_{datetime.now().strftime('%Y-%m-%d')}",
        "created_at": now,
        "finished_at": now,
        "status": "completed",
        "config": {
            "source_dirs": [str(baseline_dir), str(mcp_dir)],
            "experiment_name": f"{benchmark_name}_combined",
            "description": f"Combined analysis of {benchmark_name} baseline vs MCP",
            "benchmarks": [baseline_summary.get("benchmark", "unknown")],
            "models": list({baseline_summary.get("model"), mcp_summary.get("model")} - {None}),
            "mcp_modes": ["baseline", "deepsearch_hybrid"],
            "seeds": [0],
            "tags": ["combined-analysis", benchmark_name],
        },
        "matrix_summary": {
            "total_runs": 2,
            "total_pairs": 1,
            "dimensions": {
                "benchmarks": 1,
                "models": 1,
                "mcp_modes": 2,
                "seeds": 1,
                "tasks": max(baseline_summary.get("total_tasks", 0),
                           mcp_summary.get("total_tasks", 0)),
            },
        },
        "runs": [
            {
                "run_id": baseline_summary.get("run_id", "baseline"),
                "status": "completed",
                "mcp_mode": "baseline",
                "total_tasks": baseline_summary.get("total_tasks", 0),
                "mean_reward": baseline_summary.get("mean_reward", 0.0),
            },
            {
                "run_id": mcp_summary.get("run_id", "mcp"),
                "status": "completed",
                "mcp_mode": "deepsearch_hybrid",
                "total_tasks": mcp_summary.get("total_tasks", 0),
                "mean_reward": mcp_summary.get("mean_reward", 0.0),
            },
        ],
        "pairs": [
            {
                "pair_id": "pair_baseline_vs_mcp",
                "baseline_run_id": baseline_summary.get("run_id", "baseline"),
                "mcp_run_id": mcp_summary.get("run_id", "mcp"),
                "status": "completed",
            }
        ],
    }

    # Create combined index
    baseline_mean = baseline_summary.get("mean_reward", 0.0)
    mcp_mean = mcp_summary.get("mean_reward", 0.0)
    improvement = 0.0
    if baseline_mean > 0:
        improvement = ((mcp_mean - baseline_mean) / baseline_mean) * 100

    combined_index = {
        "schema_version": "1.0.0",
        "experiment_id": combined_manifest["experiment_id"],
        "generated_at": now,
        "runs_by_mcp_mode": {
            "baseline": [baseline_summary.get("run_id", "baseline")],
            "deepsearch_hybrid": [mcp_summary.get("run_id", "mcp")],
        },
        "aggregate_stats": {
            "baseline": {
                "total_runs": 1,
                "mean_reward": baseline_mean,
                "total_tasks": baseline_summary.get("total_tasks", 0),
                "total_input_tokens": baseline_summary.get("total_input_tokens", 0),
                "total_output_tokens": baseline_summary.get("total_output_tokens", 0),
            },
            "mcp": {
                "total_runs": 1,
                "mean_reward": mcp_mean,
                "total_tasks": mcp_summary.get("total_tasks", 0),
                "total_input_tokens": mcp_summary.get("total_input_tokens", 0),
                "total_output_tokens": mcp_summary.get("total_output_tokens", 0),
            },
            "improvement_pct": improvement,
        },
    }

    # Create combined detailed results
    combined_detailed = {
        "baseline": {
            "summary": baseline_summary,
            "tasks": baseline_tasks if "baseline_tasks" in dir() else [],
        },
        "deepsearch_hybrid": {
            "summary": mcp_summary,
            "tasks": mcp_tasks if "mcp_tasks" in dir() else [],
        },
    }

    # Generate report
    report_lines = [
        f"# Combined Benchmark Analysis: {benchmark_name}",
        f"",
        f"Generated: {now}",
        f"",
        f"## Summary",
        f"",
        f"| MCP Mode | Tasks | Mean Reward | Input Tokens | Output Tokens |",
        f"|----------|-------|-------------|--------------|---------------|",
        f"| baseline | {baseline_summary.get('total_tasks', 0)} | "
        f"{baseline_mean:.4f} | "
        f"{baseline_summary.get('total_input_tokens', 0):,} | "
        f"{baseline_summary.get('total_output_tokens', 0):,} |",
        f"| deepsearch_hybrid | {mcp_summary.get('total_tasks', 0)} | "
        f"{mcp_mean:.4f} | "
        f"{mcp_summary.get('total_input_tokens', 0):,} | "
        f"{mcp_summary.get('total_output_tokens', 0):,} |",
        f"",
        f"## Comparison",
        f"",
        f"- **Mean Reward Delta**: {mcp_mean - baseline_mean:+.4f} ({improvement:+.1f}%)",
        f"- **Token Usage Delta**: "
        f"{mcp_summary.get('total_input_tokens', 0) - baseline_summary.get('total_input_tokens', 0):+,} input, "
        f"{mcp_summary.get('total_output_tokens', 0) - baseline_summary.get('total_output_tokens', 0):+,} output",
        f"",
    ]

    # Per-task comparison if tasks match
    baseline_by_task = {t.get("task_name"): t for t in baseline_tasks}
    mcp_by_task = {t.get("task_name"): t for t in mcp_tasks}

    common_tasks = set(baseline_by_task.keys()) & set(mcp_by_task.keys())
    if common_tasks:
        report_lines.extend([
            f"## Per-Task Comparison",
            f"",
            f"| Task | Baseline | MCP | Delta |",
            f"|------|----------|-----|-------|",
        ])

        for task_name in sorted(common_tasks):
            b = baseline_by_task[task_name]
            m = mcp_by_task[task_name]
            delta = m.get("reward", 0) - b.get("reward", 0)
            report_lines.append(
                f"| {task_name[:40]} | {b.get('reward', 0):.4f} | "
                f"{m.get('reward', 0):.4f} | {delta:+.4f} |"
            )

    report = "\n".join(report_lines)

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "manifest.json", "w") as f:
        json.dump(combined_manifest, f, indent=2)

    with open(output_dir / "index.json", "w") as f:
        json.dump(combined_index, f, indent=2)

    with open(output_dir / "detailed_results.json", "w") as f:
        json.dump(combined_detailed, f, indent=2)

    with open(output_dir / "REPORT.md", "w") as f:
        f.write(report)

    print(f"\nCombined analysis saved to: {output_dir}")
    print(f"\nResults:")
    print(f"  Baseline: {baseline_summary.get('total_tasks', 0)} tasks, "
          f"mean_reward={baseline_mean:.4f}")
    print(f"  MCP:      {mcp_summary.get('total_tasks', 0)} tasks, "
          f"mean_reward={mcp_mean:.4f}")
    print(f"  Delta:    {improvement:+.1f}%")

    return {
        "manifest": combined_manifest,
        "index": combined_index,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Combine separate benchmark runs for comparison"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to baseline analysis directory"
    )
    parser.add_argument(
        "--mcp",
        type=Path,
        required=True,
        help="Path to MCP analysis directory"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for combined analysis"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="combined",
        help="Benchmark name for the combined analysis"
    )

    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"Error: Baseline directory not found: {args.baseline}")
        sys.exit(1)

    if not args.mcp.exists():
        print(f"Error: MCP directory not found: {args.mcp}")
        sys.exit(1)

    combine_runs(args.baseline, args.mcp, args.output_dir, args.name)


if __name__ == "__main__":
    main()
