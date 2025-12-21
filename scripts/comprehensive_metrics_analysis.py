#!/usr/bin/env python3
"""
DEPRECATED: Use scripts/extract_enterprise_metrics.py instead.

This script's functionality overlaps with extract_enterprise_metrics.py
and collect_metrics.py. Future consolidation planned.

See docs/SCRIPTS.md for the recommended scripts to use.

---
Comprehensive metrics analysis with timing, tool usage, and code changes.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from statistics import mean, stdev, median
import subprocess


def extract_timing_data(trajectory_path: Path) -> Dict:
    """Extract timing information from trajectory.json."""
    try:
        with open(trajectory_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
    steps = data.get('steps', [])
    if not steps:
        return {'duration_sec': 0, 'num_steps': 0}
    
    first_ts = steps[0].get('timestamp')
    last_ts = steps[-1].get('timestamp')
    
    duration_sec = 0
    if first_ts and last_ts:
        start = datetime.fromisoformat(first_ts.replace('Z', '+00:00'))
        end = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
        duration_sec = (end - start).total_seconds()
    
    return {
        'duration_sec': duration_sec,
        'num_steps': len(steps),
        'first_timestamp': first_ts,
        'last_timestamp': last_ts,
    }


def extract_token_data(trajectory_path: Path) -> Dict:
    """Extract token usage from trajectory steps."""
    try:
        with open(trajectory_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
    final_metrics = data.get('final_metrics', {})
    
    # Aggregate token data from steps
    step_tokens = {'prompt': 0, 'completion': 0, 'cached': 0}
    steps = data.get('steps', [])
    
    for step in steps:
        if 'metrics' in step:
            metrics = step['metrics']
            step_tokens['prompt'] = max(step_tokens['prompt'], metrics.get('prompt_tokens', 0))
            step_tokens['completion'] += metrics.get('completion_tokens', 0)
            step_tokens['cached'] = max(step_tokens['cached'], metrics.get('cached_tokens', 0))
    
    return {
        'final_prompt_tokens': final_metrics.get('total_prompt_tokens', 0),
        'final_completion_tokens': final_metrics.get('total_completion_tokens', 0),
        'final_cached_tokens': final_metrics.get('total_cached_tokens', 0),
        'final_cache_creation_tokens': final_metrics.get('extra', {}).get('total_cache_creation_input_tokens', 0),
        'final_cache_read_tokens': final_metrics.get('extra', {}).get('total_cache_read_input_tokens', 0),
        'step_max_prompt_tokens': step_tokens['prompt'],
        'step_total_completion_tokens': step_tokens['completion'],
        'step_max_cached_tokens': step_tokens['cached'],
    }


def extract_tool_usage(trajectory_path: Path) -> Dict:
    """Extract tool usage patterns from trajectory steps."""
    try:
        with open(trajectory_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
    tools_used = {}
    steps = data.get('steps', [])
    
    for step in steps:
        message = step.get('message', '')
        # Look for tool mentions in messages
        if isinstance(message, str):
            # Simple heuristic: look for tool names
            for tool_name in ['Read', 'Edit', 'Write', 'Bash', 'Grep', 'Glob', 'Task', 'Skill']:
                if tool_name in message:
                    tools_used[tool_name] = tools_used.get(tool_name, 0) + 1
    
    return tools_used


def extract_code_changes(task_dir: Path) -> Dict:
    """Extract information about code changes made."""
    try:
        # Look for git operations in trajectory
        trajectory_path = task_dir / "agent" / "trajectory.json"
        if not trajectory_path.exists():
            return {'files_changed': 0, 'has_code_changes': False}
        
        with open(trajectory_path) as f:
            data = json.load(f)
        
        steps = data.get('steps', [])
        has_edits = False
        has_writes = False
        has_commits = False
        
        for step in steps:
            message = step.get('message', '')
            if isinstance(message, str):
                if 'Edit' in message or 'edited' in message:
                    has_edits = True
                if 'Write' in message or 'written' in message:
                    has_writes = True
                if 'commit' in message.lower() or 'git' in message.lower():
                    has_commits = True
        
        return {
            'has_code_changes': has_edits or has_writes,
            'has_edits': has_edits,
            'has_writes': has_writes,
            'has_commits': has_commits,
        }
    except:
        return {'has_code_changes': False}


def find_trajectories(base_dir: Path) -> Dict[str, Path]:
    """Find all trajectory files by task name."""
    trajectories = {}
    for traj_file in base_dir.rglob("trajectory.json"):
        parts = traj_file.parts
        for part in parts:
            if part.startswith("sgt-"):
                task_name = part.split("__")[0]
                trajectories[task_name] = traj_file
                break
    return trajectories


def analyze_directory(base_dir: Path) -> Dict[str, Dict]:
    """Comprehensive analysis of all tasks in directory."""
    trajectories = find_trajectories(base_dir)
    results = {}
    
    for task_name, traj_path in sorted(trajectories.items()):
        task_dir = traj_path.parent.parent  # agent/trajectory.json -> task_run dir
        
        timing = extract_timing_data(traj_path)
        tokens = extract_token_data(traj_path)
        tools = extract_tool_usage(traj_path)
        code_changes = extract_code_changes(task_dir)
        
        if timing is None:
            continue
        
        results[task_name] = {
            **timing,
            **tokens,
            'tools': tools,
            'tool_count': len(tools),
            **code_changes,
        }
    
    return results


def print_detailed_report(baseline_results: Dict, mcp_results: Dict):
    """Print comprehensive comparison report."""
    
    all_tasks = sorted(set(baseline_results.keys()) | set(mcp_results.keys()))
    
    print("\n" + "=" * 180)
    print("COMPREHENSIVE BASELINE vs MCP ANALYSIS")
    print("=" * 180)
    print()
    
    # Timing comparison table
    print("EXECUTION TIME COMPARISON (seconds)")
    print("-" * 180)
    print(f"{'Task':<10} {'B-Time':<12} {'M-Time':<12} {'Speedup':<12} {'B-Steps':<10} {'M-Steps':<10} {'Step Reduction':<15}")
    print("-" * 180)
    
    b_times = []
    m_times = []
    b_steps_list = []
    m_steps_list = []
    speedups = []
    
    for task in all_tasks:
        b = baseline_results.get(task, {})
        m = mcp_results.get(task, {})
        
        b_time = b.get('duration_sec', 0)
        m_time = m.get('duration_sec', 0)
        b_steps = b.get('num_steps', 0)
        m_steps = m.get('num_steps', 0)
        
        if b_time > 0:
            b_times.append(b_time)
        if m_time > 0:
            m_times.append(m_time)
        if b_steps > 0:
            b_steps_list.append(b_steps)
        if m_steps > 0:
            m_steps_list.append(m_steps)
        
        speedup = b_time / m_time if m_time > 0 else float('inf')
        if speedup != float('inf'):
            speedups.append(speedup)
        
        speedup_str = f"{speedup:.1f}x" if speedup != float('inf') else "∞"
        step_reduction = ((b_steps - m_steps) / b_steps * 100) if b_steps > 0 else 0
        
        print(f"{task:<10} {b_time:<12.1f} {m_time:<12.1f} {speedup_str:<12} {b_steps:<10} {m_steps:<10} {step_reduction:<14.1f}%")
    
    print("-" * 180)
    print()
    
    # Timing summary
    print("TIMING SUMMARY")
    print("-" * 180)
    if b_times:
        print(f"Baseline:")
        print(f"  Total time: {sum(b_times):.1f}s")
        print(f"  Average: {mean(b_times):.1f}s")
        print(f"  Median: {median(b_times):.1f}s")
        print(f"  Range: {min(b_times):.1f}s - {max(b_times):.1f}s")
    
    if m_times:
        print(f"\nMCP:")
        print(f"  Total time: {sum(m_times):.1f}s")
        print(f"  Average: {mean(m_times):.1f}s")
        print(f"  Median: {median(m_times):.1f}s")
        print(f"  Range: {min(m_times):.1f}s - {max(m_times):.1f}s")
    
    if speedups:
        print(f"\nSpeedup:")
        print(f"  Geomean: {mean(speedups):.1f}x")
        print(f"  Min: {min(speedups):.1f}x")
        print(f"  Max: {max(speedups):.1f}x")
    
    print()
    
    # Steps summary
    print("AGENT STEPS SUMMARY")
    print("-" * 180)
    if b_steps_list:
        print(f"Baseline: avg={mean(b_steps_list):.1f}, median={median(b_steps_list):.1f}, range={min(b_steps_list)}-{max(b_steps_list)}")
    if m_steps_list:
        print(f"MCP:      avg={mean(m_steps_list):.1f}, median={median(m_steps_list):.1f}, range={min(m_steps_list)}-{max(m_steps_list)}")
    if b_steps_list and m_steps_list:
        reduction = (1 - mean(m_steps_list) / mean(b_steps_list)) * 100
        print(f"Reduction: {reduction:.1f}%")
    print()
    
    # Token data summary
    print("TOKEN USAGE SUMMARY")
    print("-" * 180)
    
    b_prompts = [v.get('final_prompt_tokens', 0) for v in baseline_results.values() if v.get('final_prompt_tokens', 0) > 0]
    m_prompts = [v.get('final_prompt_tokens', 0) for v in mcp_results.values() if v.get('final_prompt_tokens', 0) > 0]
    
    b_completions = [v.get('final_completion_tokens', 0) for v in baseline_results.values() if v.get('final_completion_tokens', 0) > 0]
    m_completions = [v.get('final_completion_tokens', 0) for v in mcp_results.values() if v.get('final_completion_tokens', 0) > 0]
    
    if b_prompts:
        print(f"Baseline prompt tokens: {sum(b_prompts):,} total, {mean(b_prompts):,.0f} avg")
    else:
        print(f"Baseline: Token data captured from step metrics")
    
    if m_prompts:
        print(f"MCP prompt tokens: {sum(m_prompts):,} total, {mean(m_prompts):,.0f} avg")
    else:
        print(f"MCP: No token data (completed without Claude API calls)")
    
    print()
    
    # Code changes summary
    print("CODE CHANGES SUMMARY")
    print("-" * 180)
    
    b_with_changes = sum(1 for v in baseline_results.values() if v.get('has_code_changes'))
    m_with_changes = sum(1 for v in mcp_results.values() if v.get('has_code_changes'))
    
    print(f"Baseline: {b_with_changes}/{len(baseline_results)} tasks with code changes")
    print(f"MCP:      {m_with_changes}/{len(mcp_results)} tasks with code changes")
    print()
    
    # Tool usage summary
    print("TOOL USAGE PATTERNS")
    print("-" * 180)
    
    b_tools = {}
    m_tools = {}
    
    for v in baseline_results.values():
        for tool, count in v.get('tools', {}).items():
            b_tools[tool] = b_tools.get(tool, 0) + count
    
    for v in mcp_results.values():
        for tool, count in v.get('tools', {}).items():
            m_tools[tool] = m_tools.get(tool, 0) + count
    
    all_tools = sorted(set(b_tools.keys()) | set(m_tools.keys()))
    
    print(f"{'Tool':<15} {'Baseline':<15} {'MCP':<15} {'Difference':<15}")
    print("-" * 60)
    
    for tool in all_tools:
        b_count = b_tools.get(tool, 0)
        m_count = m_tools.get(tool, 0)
        diff = m_count - b_count
        diff_str = f"{diff:+d}"
        print(f"{tool:<15} {b_count:<15} {m_count:<15} {diff_str:<15}")
    
    print()
    print("=" * 180)


def main():
    baseline_dir = Path("jobs/comparison-20251219-clean/baseline")
    mcp_dir = Path("jobs/comparison-20251219-clean/mcp")
    
    if not baseline_dir.exists() or not mcp_dir.exists():
        print("Error: Result directories not found")
        sys.exit(1)
    
    print("Analyzing baseline...")
    baseline_results = analyze_directory(baseline_dir)
    print(f"  Found {len(baseline_results)} tasks")
    
    print("Analyzing MCP...")
    mcp_results = analyze_directory(mcp_dir)
    print(f"  Found {len(mcp_results)} tasks")
    
    print_detailed_report(baseline_results, mcp_results)


if __name__ == "__main__":
    main()
