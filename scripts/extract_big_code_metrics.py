#!/usr/bin/env python3
"""Extract metrics from big code MCP comparison trajectories."""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple
import statistics


def extract_metrics(traj_path: Path) -> Dict[str, Any]:
    """Extract key metrics from a trajectory file."""
    with open(traj_path) as f:
        traj = json.load(f)
    
    final_metrics = traj.get("final_metrics", {})
    return {
        "prompt_tokens": final_metrics.get("total_prompt_tokens", 0),
        "completion_tokens": final_metrics.get("total_completion_tokens", 0),
        "total_tokens": final_metrics.get("total_prompt_tokens", 0) + final_metrics.get("total_completion_tokens", 0),
        "steps": len(traj.get("steps", [])),
        "success": "error" not in str(traj).lower(),
    }


def find_task_trajectories(base_dir: Path) -> Dict[str, Dict[str, Path]]:
    """Find all trajectory files organized by task and agent type."""
    tasks = {}
    
    for traj_file in base_dir.rglob("trajectory.json"):
        parts = traj_file.parts
        
        # Find task name (big-code-*)
        task_name = None
        for part in parts:
            if part.startswith("big-code-"):
                task_name = part
                break
        
        if not task_name:
            continue
        
        # Determine agent type (baseline or mcp)
        agent_type = None
        if "baseline" in str(traj_file):
            agent_type = "baseline"
        elif "mcp" in str(traj_file):
            agent_type = "mcp"
        
        if not agent_type:
            continue
        
        if task_name not in tasks:
            tasks[task_name] = {}
        
        tasks[task_name][agent_type] = traj_file
    
    return tasks


def format_tokens(tokens: int) -> str:
    """Format token count for display."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    else:
        return str(tokens)


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_big_code_metrics.py <comparison_dir>")
        sys.exit(1)
    
    base_dir = Path(sys.argv[1])
    if not base_dir.exists():
        print(f"ERROR: Directory not found: {base_dir}")
        sys.exit(1)
    
    # Find all trajectories
    tasks = find_task_trajectories(base_dir)
    
    if not tasks:
        print("ERROR: No trajectory files found")
        sys.exit(1)
    
    # Extract metrics for each task
    results = {}
    for task_name in sorted(tasks.keys()):
        task_data = tasks[task_name]
        
        if "baseline" not in task_data or "mcp" not in task_data:
            print(f"⚠ {task_name}: Missing baseline or MCP trajectory")
            continue
        
        baseline_metrics = extract_metrics(task_data["baseline"])
        mcp_metrics = extract_metrics(task_data["mcp"])
        
        results[task_name] = {
            "baseline": baseline_metrics,
            "mcp": mcp_metrics,
        }
    
    # Display results
    print("=" * 120)
    print("BIG CODE MCP COMPARISON RESULTS")
    print("=" * 120)
    print()
    
    # Summary table
    print(f"{'Task':<25} {'Baseline Tokens':<20} {'MCP Tokens':<20} {'Δ Tokens':<15} {'Δ %':<10}")
    print("-" * 120)
    
    for task_name in sorted(results.keys()):
        baseline = results[task_name]["baseline"]
        mcp = results[task_name]["mcp"]
        
        baseline_total = baseline["total_tokens"]
        mcp_total = mcp["total_tokens"]
        delta = mcp_total - baseline_total
        delta_pct = (delta / baseline_total * 100) if baseline_total > 0 else 0
        
        print(
            f"{task_name:<25} "
            f"{format_tokens(baseline_total):<20} "
            f"{format_tokens(mcp_total):<20} "
            f"{format_tokens(delta):<15} "
            f"{delta_pct:+.1f}%"
        )
    
    print()
    print("=" * 120)
    print("DETAILED METRICS")
    print("=" * 120)
    print()
    
    for task_name in sorted(results.keys()):
        baseline = results[task_name]["baseline"]
        mcp = results[task_name]["mcp"]
        
        print(f"Task: {task_name}")
        print(f"  Baseline:")
        print(f"    Prompt tokens:     {format_tokens(baseline['prompt_tokens'])}")
        print(f"    Completion tokens: {format_tokens(baseline['completion_tokens'])}")
        print(f"    Total tokens:      {format_tokens(baseline['total_tokens'])}")
        print(f"    Steps:             {baseline['steps']}")
        
        print(f"  MCP:")
        print(f"    Prompt tokens:     {format_tokens(mcp['prompt_tokens'])}")
        print(f"    Completion tokens: {format_tokens(mcp['completion_tokens'])}")
        print(f"    Total tokens:      {format_tokens(mcp['total_tokens'])}")
        print(f"    Steps:             {mcp['steps']}")
        
        delta_tokens = mcp["total_tokens"] - baseline["total_tokens"]
        delta_pct = (delta_tokens / baseline["total_tokens"] * 100) if baseline["total_tokens"] > 0 else 0
        delta_steps = mcp["steps"] - baseline["steps"]
        
        print(f"  Difference:")
        print(f"    Tokens: {format_tokens(delta_tokens)} ({delta_pct:+.1f}%)")
        print(f"    Steps:  {delta_steps:+d}")
        print()
    
    # Aggregate stats
    print("=" * 120)
    print("AGGREGATE STATISTICS")
    print("=" * 120)
    print()
    
    all_baseline_tokens = [results[t]["baseline"]["total_tokens"] for t in results]
    all_mcp_tokens = [results[t]["mcp"]["total_tokens"] for t in results]
    
    total_baseline = sum(all_baseline_tokens)
    total_mcp = sum(all_mcp_tokens)
    total_delta = total_mcp - total_baseline
    total_pct = (total_delta / total_baseline * 100) if total_baseline > 0 else 0
    
    print(f"Total baseline tokens:  {format_tokens(total_baseline)}")
    print(f"Total MCP tokens:       {format_tokens(total_mcp)}")
    print(f"Overall difference:     {format_tokens(total_delta)} ({total_pct:+.1f}%)")
    print()
    
    avg_baseline = statistics.mean(all_baseline_tokens)
    avg_mcp = statistics.mean(all_mcp_tokens)
    
    print(f"Average baseline tokens: {format_tokens(int(avg_baseline))}")
    print(f"Average MCP tokens:      {format_tokens(int(avg_mcp))}")
    print()
    
    # Compare to Trevor's findings
    print("=" * 120)
    print("COMPARISON TO TREVOR'S RESEARCH")
    print("=" * 120)
    print()
    print("Trevor's findings (from TREVOR_RESEARCH_DEC2025.md):")
    print("  - VS Code diagnostics: MCP required for full pipeline understanding")
    print("  - Kubernetes taint: MCP found all evaluation points across 1.4GB codebase")
    print("  - Servo scrollend: MCP located all scroll handlers across modules")
    print("  - TensorRT quantization: MCP comprehensive across Python/C++ boundary")
    print()
    print("Expected outcomes:")
    print("  - MCP may use more tokens (broader searches)")
    print("  - But should find more correct locations and fewer missed integration points")
    print()


if __name__ == "__main__":
    main()
