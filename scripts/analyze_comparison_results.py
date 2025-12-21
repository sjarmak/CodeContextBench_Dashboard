#!/usr/bin/env python3
"""
DEPRECATED: Use runners/compare_results.py instead.

This script is hardcoded for 10 tasks. The canonical comparison script is
runners/compare_results.py which handles arbitrary task counts.

See docs/SCRIPTS.md for the recommended scripts to use.

---
Analyze 10-task comparison results between baseline and MCP agents.
Extracts metrics from Harbor result.json files and generates comparison table.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime


def load_result_json(path: Path) -> Dict:
    """Load a Harbor result.json file"""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def extract_metrics(result_dir: Path) -> Dict[str, List[Dict]]:
    """Extract metrics from all trial results in a directory"""
    metrics = []
    
    # Find all result.json files (one per trial)
    for result_file in sorted(result_dir.glob("*/result.json")):
        result = load_result_json(result_file)
        if not result:
            continue
        
        # Extract key metrics
        task_name = result.get("task_name", "unknown")
        reward = result.get("verifier_result", {}).get("rewards", {}).get("reward", None)
        tokens_in = result.get("agent_result", {}).get("n_input_tokens", 0)
        tokens_out = result.get("agent_result", {}).get("n_output_tokens", 0)
        
        # Extract timing
        agent_exec = result.get("agent_execution", {})
        start = agent_exec.get("started_at")
        end = agent_exec.get("finished_at")
        duration_sec = None
        if start and end:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            duration_sec = (end_dt - start_dt).total_seconds()
        
        metrics.append({
            "task": task_name,
            "reward": reward,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_sec": duration_sec,
        })
    
    return {"metrics": metrics}


def compare_results(baseline_dir: Path, mcp_dir: Path) -> None:
    """Compare results from baseline and MCP runs"""
    
    baseline_data = extract_metrics(baseline_dir)
    mcp_data = extract_metrics(mcp_dir)
    
    baseline_metrics = baseline_data.get("metrics", [])
    mcp_metrics = mcp_data.get("metrics", [])
    
    # Create lookup dicts
    baseline_map = {m["task"]: m for m in baseline_metrics}
    mcp_map = {m["task"]: m for m in mcp_metrics}
    
    # Get all unique tasks
    all_tasks = sorted(set(baseline_map.keys()) | set(mcp_map.keys()))
    
    print("\n" + "=" * 100)
    print("10-TASK COMPARISON: BASELINE vs MCP")
    print("=" * 100)
    print()
    print(f"{'Task':<10} {'Baseline':<12} {'MCP':<12} {'Improvement':<15} {'B-Tokens':<12} {'M-Tokens':<12}")
    print(f"{'':10} {'Reward':<12} {'Reward':<12} {'Diff':<15} {'In/Out':<12} {'In/Out':<12}")
    print("-" * 100)
    
    baseline_passes = 0
    mcp_passes = 0
    improvements = []
    regressions = []
    
    for task in all_tasks:
        b = baseline_map.get(task, {})
        m = mcp_map.get(task, {})
        
        b_reward = b.get("reward")
        m_reward = m.get("reward")
        
        # Count passes
        if b_reward == 1.0:
            baseline_passes += 1
        if m_reward == 1.0:
            mcp_passes += 1
        
        # Detect improvement/regression
        if b_reward == 0.0 and m_reward == 1.0:
            improvements.append(task)
            diff_str = "✓ MCP FIXED"
        elif b_reward == 1.0 and m_reward == 0.0:
            regressions.append(task)
            diff_str = "✗ MCP BROKE"
        elif b_reward == m_reward:
            diff_str = "="
        else:
            diff_str = f"{m_reward - b_reward:+.1f}" if m_reward and b_reward else "?"
        
        b_tokens = f"{b.get('tokens_in', 0)}/{b.get('tokens_out', 0)}" if b else "N/A"
        m_tokens = f"{m.get('tokens_in', 0)}/{m.get('tokens_out', 0)}" if m else "N/A"
        
        b_reward_str = f"{b_reward:.1f}" if b_reward is not None else "N/A"
        m_reward_str = f"{m_reward:.1f}" if m_reward is not None else "N/A"
        
        print(f"{task:<10} {b_reward_str:<12} {m_reward_str:<12} {diff_str:<15} {b_tokens:<12} {m_tokens:<12}")
    
    print("-" * 100)
    print()
    
    # Summary statistics
    print(f"BASELINE: {baseline_passes}/{len(all_tasks)} passed ({100*baseline_passes/len(all_tasks):.0f}%)")
    print(f"MCP:      {mcp_passes}/{len(all_tasks)} passed ({100*mcp_passes/len(all_tasks):.0f}%)")
    print()
    
    if improvements:
        print(f"✓ MCP improvements (+{len(improvements)} tasks): {', '.join(improvements)}")
    if regressions:
        print(f"✗ MCP regressions (-{len(regressions)} tasks): {', '.join(regressions)}")
    
    if not improvements and not regressions:
        print("No improvements or regressions detected")
    
    print()
    print("=" * 100)


def main():
    """Main entry point"""
    baseline_dir = Path("jobs/baseline-10task-20251219")
    mcp_dir = Path("jobs/mcp-10task-20251219")
    
    if not baseline_dir.exists():
        print(f"Error: {baseline_dir} not found")
        print("Run: bash scripts/run_10task_comparison.sh")
        sys.exit(1)
    
    if not mcp_dir.exists():
        print(f"Error: {mcp_dir} not found")
        print("Run: bash scripts/run_10task_comparison.sh")
        sys.exit(1)
    
    compare_results(baseline_dir, mcp_dir)


if __name__ == "__main__":
    main()
