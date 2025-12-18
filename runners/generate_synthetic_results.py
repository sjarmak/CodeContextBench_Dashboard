#!/usr/bin/env python3
"""Generate synthetic benchmark results for testing the analysis pipeline.

Since Harbor CLI is broken (typer incompatibility), we use synthetic data
to test the end-to-end pipeline: execution → aggregation → analysis.

This allows validation of the analysis code without real task execution.

Usage:
    python runners/generate_synthetic_results.py --baseline-rate 0.35 --mcp-rate 0.48
"""

import json
import sys
import random
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta


def generate_task_result(
    task_id: str,
    agent_name: str,
    success: bool,
    duration_sec: float,
) -> Dict[str, Any]:
    """Generate synthetic result for a single task."""
    
    if success:
        # Successful tasks use more tokens
        input_tokens = random.randint(4000, 8000)
        output_tokens = random.randint(1500, 3500)
    else:
        # Failed tasks typically use fewer tokens
        input_tokens = random.randint(1000, 3000)
        output_tokens = random.randint(500, 1500)
    
    total_tokens = input_tokens + output_tokens
    
    # Cost calculation (Claude 3.5 Sonnet pricing)
    # Input: $3 per million tokens
    # Output: $15 per million tokens
    cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
    
    # Tool usage
    search_queries = random.randint(2, 8) if agent_name == "claude-mcp" else 0
    file_ops = random.randint(3, 12)
    git_ops = random.randint(1, 4)
    
    return {
        "task_id": task_id,
        "agent_name": agent_name,
        "benchmark": "github_mined",
        "success": success,
        "duration_sec": duration_sec,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
        "cost_usd": cost_usd,
        "tool_usage": {
            "search_queries": search_queries,
            "file_operations": file_ops,
            "git_operations": git_ops,
        },
        "error": None if success else "Task execution timeout or agent failure"
    }


def generate_benchmark_run(
    agent_name: str,
    n_tasks: int,
    success_rate: float,
    jobs_dir: Path,
) -> Path:
    """Generate synthetic benchmark run with N tasks.
    
    Args:
        agent_name: 'claude-baseline' or 'claude-mcp'
        n_tasks: Number of tasks to generate
        success_rate: Fraction of tasks that succeed (0.0-1.0)
        jobs_dir: Directory to write results
        
    Returns:
        Path to results.json file
    """
    
    # Create job directory
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = jobs_dir / f"{agent_name}-github_mined-{timestamp}"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating {agent_name} results ({n_tasks} tasks, {success_rate:.0%} success)...")
    
    # Generate task results
    results = []
    successful = 0
    
    for i in range(1, n_tasks + 1):
        task_id = f"sgt-{i:03d}"
        
        # Determine success based on rate
        is_success = random.random() < success_rate
        if is_success:
            successful += 1
        
        # Duration varies by success
        if is_success:
            duration_sec = random.uniform(120, 600)  # 2-10 minutes
        else:
            duration_sec = random.uniform(60, 300)   # 1-5 minutes (faster failure)
        
        result = generate_task_result(task_id, agent_name, is_success, duration_sec)
        results.append(result)
    
    # Aggregate
    total_cost = sum(r["cost_usd"] for r in results)
    total_tokens_input = sum(r["tokens"]["input"] for r in results)
    total_tokens_output = sum(r["tokens"]["output"] for r in results)
    avg_duration = sum(r["duration_sec"] for r in results) / len(results)
    
    aggregate = {
        "timestamp": datetime.now().isoformat(),
        "benchmark": "github_mined",
        "agent_name": agent_name,
        "job_dir": str(job_dir),
        "tasks_run": n_tasks,
        "tasks_successful": successful,
        "success_rate": successful / n_tasks if n_tasks > 0 else 0,
        "total_cost_usd": total_cost,
        "avg_cost_per_task": total_cost / n_tasks if n_tasks > 0 else 0,
        "avg_duration_sec": avg_duration,
        "total_tokens": {
            "input": total_tokens_input,
            "output": total_tokens_output,
            "total": total_tokens_input + total_tokens_output,
        },
        "task_results": results
    }
    
    # Write results.json
    result_file = job_dir / "results.json"
    result_file.write_text(json.dumps(aggregate, indent=2))
    
    print(f"  ✓ {job_dir.name}/results.json")
    print(f"    Success rate: {aggregate['success_rate']:.1%} ({successful}/{n_tasks})")
    print(f"    Avg cost: ${aggregate['avg_cost_per_task']:.3f}/task")
    
    return result_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic benchmark results for testing"
    )
    parser.add_argument(
        "--baseline-rate",
        type=float,
        default=0.35,
        help="Baseline agent success rate (default: 0.35 = 35%)"
    )
    parser.add_argument(
        "--mcp-rate",
        type=float,
        default=0.48,
        help="MCP agent success rate (default: 0.48 = 48%)"
    )
    parser.add_argument(
        "--n-tasks",
        type=int,
        default=10,
        help="Number of tasks per run (default: 10)"
    )
    parser.add_argument(
        "--jobs-dir",
        type=Path,
        default=Path("jobs"),
        help="Jobs directory (default: jobs/)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility"
    )
    
    args = parser.parse_args()
    
    if args.seed is not None:
        random.seed(args.seed)
    
    args.jobs_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("GENERATING SYNTHETIC BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Purpose: Test analysis pipeline (Harbor CLI broken)")
    print(f"Baseline success rate: {args.baseline_rate:.0%}")
    print(f"MCP success rate: {args.mcp_rate:.0%}")
    print(f"Tasks per run: {args.n_tasks}")
    print(f"Expected improvement: {(args.mcp_rate - args.baseline_rate):.0%}")
    
    # Generate baseline run
    baseline_file = generate_benchmark_run(
        "claude-baseline",
        args.n_tasks,
        args.baseline_rate,
        args.jobs_dir
    )
    
    # Generate MCP run
    mcp_file = generate_benchmark_run(
        "claude-mcp",
        args.n_tasks,
        args.mcp_rate,
        args.jobs_dir
    )
    
    print("\n" + "=" * 70)
    print("SYNTHETIC RESULTS GENERATED")
    print("=" * 70)
    print(f"Baseline: {baseline_file}")
    print(f"MCP:      {mcp_file}")
    print()
    print("Next steps:")
    print("  1. Verify results look reasonable:")
    print(f"     cat {baseline_file}")
    print("  2. Test aggregation pipeline:")
    print("     python3 runners/extract_nemo_traces.py --jobs-dir jobs/ --all --json")
    print("  3. Compare success rates (should show MCP > baseline)")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
