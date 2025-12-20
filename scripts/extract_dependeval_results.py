#!/usr/bin/env python3
"""
Extract DependEval comparison results from Harbor job directories.

Harbor creates timestamped job directories (jobs/YYYY-MM-DD__HH-MM-SS/)
This script finds the latest baseline and MCP job runs and extracts comparison data.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import statistics


def find_latest_job_dirs():
    """Find the two most recent Harbor job directories (baseline, then MCP)."""
    jobs_dir = Path("jobs")
    job_dirs = sorted([
        d for d in jobs_dir.iterdir() 
        if d.is_dir() and d.name.startswith("2025-")
    ], reverse=True)
    
    if len(job_dirs) < 2:
        print(f"Error: Need at least 2 job directories, found {len(job_dirs)}")
        return None, None
    
    # Assume last 2 are baseline and MCP (in that order from script execution)
    baseline_dir = job_dirs[1]
    mcp_dir = job_dirs[0]
    
    return baseline_dir, mcp_dir


def extract_task_result(result_json_path: Path) -> Dict[str, Any]:
    """Extract reward and metadata from a result.json file."""
    try:
        with open(result_json_path, 'r') as f:
            result = json.load(f)
        
        task_name = result.get('task_name', 'unknown')
        
        # Harbor embeds reward in metrics
        metrics = result.get('metrics', {})
        reward = metrics.get('reward')
        
        # If not in metrics, check top level
        if reward is None:
            reward = result.get('reward')
        
        return {
            'task_name': task_name,
            'reward': reward,
            'trial_uri': result.get('trial_uri'),
            'success': reward is not None
        }
    except Exception as e:
        return {'error': str(e)}


def analyze_job_dir(job_dir: Path) -> Dict[str, Any]:
    """Extract all task results from a job directory."""
    results = {}
    
    # Find all trial directories (they have result.json)
    for trial_dir in job_dir.glob('*__*/'):
        result_path = trial_dir / 'result.json'
        if result_path.exists():
            task_result = extract_task_result(result_path)
            task_name = task_result.get('task_name', trial_dir.name)
            results[task_name] = task_result
    
    return results


def main():
    """Main entry point."""
    baseline_dir, mcp_dir = find_latest_job_dirs()
    
    if not baseline_dir or not mcp_dir:
        sys.exit(1)
    
    print("=" * 70)
    print("DependEval Baseline vs MCP Comparison Results")
    print("=" * 70)
    print(f"\nBaseline dir: {baseline_dir.name}")
    print(f"MCP dir:      {mcp_dir.name}")
    print()
    
    # Extract results
    baseline_results = analyze_job_dir(baseline_dir)
    mcp_results = analyze_job_dir(mcp_dir)
    
    # Display results
    print(f"{'Task':<45} {'Baseline':>10} {'MCP':>10} {'Δ':>10}")
    print("-" * 70)
    
    improvements = []
    
    # Match tasks
    all_tasks = set(baseline_results.keys()) | set(mcp_results.keys())
    for task_name in sorted(all_tasks):
        baseline = baseline_results.get(task_name, {}).get('reward')
        mcp = mcp_results.get(task_name, {}).get('reward')
        
        baseline_str = f"{baseline:.4f}" if baseline is not None else "N/A"
        mcp_str = f"{mcp:.4f}" if mcp is not None else "N/A"
        
        if baseline is not None and mcp is not None:
            delta = mcp - baseline
            delta_str = f"{delta:+.4f}"
            improvements.append(delta)
        else:
            delta_str = "N/A"
        
        print(f"{task_name:<45} {baseline_str:>10} {mcp_str:>10} {delta_str:>10}")
    
    print("-" * 70)
    
    # Summary statistics
    if improvements:
        avg_improvement = statistics.mean(improvements)
        median_improvement = statistics.median(improvements)
        max_improvement = max(improvements)
        min_improvement = min(improvements)
        
        print()
        print("Summary Statistics:")
        print(f"  Average improvement: {avg_improvement:+.4f}")
        print(f"  Median improvement:  {median_improvement:+.4f}")
        print(f"  Max improvement:     {max_improvement:+.4f}")
        print(f"  Min improvement:     {min_improvement:+.4f}")
        print(f"  Tasks evaluated:     {len(improvements)}")
        
        if avg_improvement > 0:
            print()
            print(f"✓ MCP improved performance by average {abs(avg_improvement)*100:.1f}%")
        elif avg_improvement < 0:
            print()
            print(f"✗ MCP decreased performance by average {abs(avg_improvement)*100:.1f}%")
        else:
            print()
            print("= MCP showed no measurable impact on average")
    
    print()


if __name__ == "__main__":
    main()
