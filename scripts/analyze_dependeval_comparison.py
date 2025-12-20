#!/usr/bin/env python3
"""
Analyze DependEval baseline vs MCP comparison results.

Compares performance metrics between baseline (no MCP) and MCP-enabled agents
on DependEval tasks.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import statistics


def load_reward_file(file_path: Path) -> float | None:
    """Load reward score from file."""
    try:
        with open(file_path, 'r') as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def extract_token_usage(log_path: Path) -> Dict[str, int]:
    """Extract token usage from task log."""
    tokens = {"input": 0, "output": 0}
    if not log_path.exists():
        return tokens
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
            # Look for token counts in the log
            # This is a simplified extraction - adjust based on actual log format
            if "input_tokens" in content:
                # Parse as needed
                pass
    except:
        pass
    
    return tokens


def analyze_comparison(job_dir: Path):
    """Analyze baseline vs MCP comparison."""
    baseline_dir = job_dir / "baseline"
    mcp_dir = job_dir / "mcp"
    
    if not baseline_dir.exists() or not mcp_dir.exists():
        print(f"Error: Expected {baseline_dir} and {mcp_dir}")
        sys.exit(1)
    
    # Collect results
    baseline_results = {}
    mcp_results = {}
    
    # Find all tasks
    for task_dir in sorted(baseline_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        
        task_name = task_dir.name
        
        # Load baseline reward
        baseline_reward = load_reward_file(task_dir / "reward.txt")
        mcp_reward = load_reward_file(mcp_dir / task_name / "reward.txt")
        
        if baseline_reward is not None or mcp_reward is not None:
            baseline_results[task_name] = baseline_reward
            mcp_results[task_name] = mcp_reward
    
    # Display results
    print("="*70)
    print("DependEval Baseline vs MCP Comparison Results")
    print("="*70)
    print("")
    print(f"{'Task':<45} {'Baseline':>10} {'MCP':>10} {'Δ':>10}")
    print("-"*70)
    
    improvements = []
    
    for task_name in sorted(baseline_results.keys()):
        baseline = baseline_results[task_name]
        mcp = mcp_results[task_name]
        
        baseline_str = f"{baseline:.4f}" if baseline is not None else "N/A"
        mcp_str = f"{mcp:.4f}" if mcp is not None else "N/A"
        
        if baseline is not None and mcp is not None:
            delta = mcp - baseline
            delta_str = f"{delta:+.4f}"
            improvements.append(delta)
        else:
            delta_str = "N/A"
        
        print(f"{task_name:<45} {baseline_str:>10} {mcp_str:>10} {delta_str:>10}")
    
    print("-"*70)
    
    # Summary statistics
    if improvements:
        avg_improvement = statistics.mean(improvements)
        median_improvement = statistics.median(improvements)
        max_improvement = max(improvements)
        min_improvement = min(improvements)
        
        print("")
        print("Summary Statistics:")
        print(f"  Average improvement: {avg_improvement:+.4f}")
        print(f"  Median improvement:  {median_improvement:+.4f}")
        print(f"  Max improvement:     {max_improvement:+.4f}")
        print(f"  Min improvement:     {min_improvement:+.4f}")
        print(f"  Tasks evaluated:     {len(improvements)}")
        
        if avg_improvement > 0:
            print("")
            print(f"✓ MCP improved performance by average {abs(avg_improvement)*100:.1f}%")
        elif avg_improvement < 0:
            print("")
            print(f"✗ MCP decreased performance by average {abs(avg_improvement)*100:.1f}%")
        else:
            print("")
            print("= MCP showed no measurable impact on average")
    
    print("")
    print(f"Results directory: {job_dir}")
    print("")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_dependeval_comparison.py <job_dir>")
        sys.exit(1)
    
    job_dir = Path(sys.argv[1])
    if not job_dir.exists():
        print(f"Error: Directory not found: {job_dir}")
        sys.exit(1)
    
    analyze_comparison(job_dir)


if __name__ == "__main__":
    main()
