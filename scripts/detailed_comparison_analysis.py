#!/usr/bin/env python3
"""
Comprehensive comparison analysis of baseline vs MCP agents.

Extracts rich metrics from trajectory.json files including:
- Task completion (reward)
- Token usage (prompt, completion, cached, cache creation/read)
- Execution time and steps
- Cost analysis
- Cache efficiency
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from statistics import mean, stdev


def find_trajectory_files(base_dir: Path) -> Dict[str, Path]:
    """Find all trajectory.json files and map by task name."""
    trajectories = {}
    for trajectory_file in base_dir.rglob("trajectory.json"):
        # Extract task name from path: .../sgt-001__xxx/agent/trajectory.json
        parts = trajectory_file.parts
        for i, part in enumerate(parts):
            if part.startswith("sgt-"):
                task_name = part.split("__")[0]
                trajectories[task_name] = trajectory_file
                break
    return trajectories


def extract_trajectory_metrics(trajectory_path: Path) -> Dict:
    """Extract metrics from a trajectory.json file."""
    try:
        with open(trajectory_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    
    final_metrics = data.get('final_metrics', {})
    
    return {
        'prompt_tokens': final_metrics.get('total_prompt_tokens', 0),
        'completion_tokens': final_metrics.get('total_completion_tokens', 0),
        'cached_tokens': final_metrics.get('total_cached_tokens', 0),
        'cache_creation_tokens': final_metrics.get('extra', {}).get('total_cache_creation_input_tokens', 0),
        'cache_read_tokens': final_metrics.get('extra', {}).get('total_cache_read_input_tokens', 0),
        'steps': final_metrics.get('total_steps', 0),
        'agent': data.get('agent', {}).get('name', 'unknown'),
        'model': data.get('agent', {}).get('model_name', 'unknown'),
    }


def extract_task_result(batch_dir: Path, task_name: str) -> Optional[float]:
    """Extract task reward from the batch result.json."""
    result_file = batch_dir / "result.json"
    
    if not result_file.exists():
        return None
    
    try:
        with open(result_file) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return None
    
    # Extract from stats -> evals
    stats = data.get('stats', {})
    evals = stats.get('evals', {})
    
    for eval_key, eval_data in evals.items():
        reward_stats = eval_data.get('reward_stats', {}).get('reward', {})
        for reward_val, task_list in reward_stats.items():
            for task_id in task_list:
                if task_id.startswith(task_name + "__"):
                    return float(reward_val)
    
    return None


def analyze_directory(base_dir: Path) -> Dict[str, Dict]:
    """Analyze all tasks in a directory."""
    trajectories = find_trajectory_files(base_dir)
    results = {}
    
    # Find all batch directories
    batch_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("2025")]
    
    for task_name, traj_path in sorted(trajectories.items()):
        metrics = extract_trajectory_metrics(traj_path)
        
        if metrics is None:
            continue
        
        # Find reward from the batch directory containing this trajectory
        batch_dir = traj_path.parent.parent.parent  # trajectory -> agent -> task_run -> batch
        reward = extract_task_result(batch_dir, task_name)
        
        metrics['reward'] = reward
        results[task_name] = metrics
    
    return results


def calculate_token_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculate estimated cost in USD for Claude Haiku (prices as of Dec 2024)."""
    # Haiku: $0.80 per 1M prompt tokens, $4.00 per 1M completion tokens
    prompt_cost = (prompt_tokens / 1_000_000) * 0.80
    completion_cost = (completion_tokens / 1_000_000) * 4.00
    return prompt_cost + completion_cost


def print_detailed_comparison(baseline_results: Dict, mcp_results: Dict) -> None:
    """Print comprehensive comparison report."""
    
    all_tasks = sorted(set(baseline_results.keys()) | set(mcp_results.keys()))
    
    print("\n" + "=" * 150)
    print("DETAILED BASELINE vs MCP COMPARISON")
    print("=" * 150)
    print()
    
    # Task-by-task comparison
    print(f"{'Task':<10} {'Pass':<6} {'B-Prompt':<12} {'M-Prompt':<12} {'B-Comp':<10} {'M-Comp':<10} {'B-Cache':<12} {'M-Cache':<12} {'B-Steps':<8} {'M-Steps':<8}")
    print("-" * 150)
    
    b_pass = 0
    m_pass = 0
    
    for task in all_tasks:
        b = baseline_results.get(task, {})
        m = mcp_results.get(task, {})
        
        b_reward = b.get('reward')
        m_reward = m.get('reward')
        
        status = "✓" if (b_reward == 1.0 and m_reward == 1.0) else "✗"
        if b_reward == 1.0:
            b_pass += 1
        if m_reward == 1.0:
            m_pass += 1
        
        b_prompt = f"{b.get('prompt_tokens', 0):,}" if b else "N/A"
        m_prompt = f"{m.get('prompt_tokens', 0):,}" if m else "N/A"
        
        b_comp = f"{b.get('completion_tokens', 0):,}" if b else "N/A"
        m_comp = f"{m.get('completion_tokens', 0):,}" if m else "N/A"
        
        b_cache = f"{b.get('cached_tokens', 0):,}" if b else "N/A"
        m_cache = f"{m.get('cached_tokens', 0):,}" if m else "N/A"
        
        b_steps = b.get('steps', 0)
        m_steps = m.get('steps', 0)
        
        print(f"{task:<10} {status:<6} {b_prompt:<12} {m_prompt:<12} {b_comp:<10} {m_comp:<10} {b_cache:<12} {m_cache:<12} {b_steps:<8} {m_steps:<8}")
    
    print("-" * 150)
    print()
    
    # Summary statistics
    print("SUMMARY STATISTICS")
    print("-" * 150)
    print()
    
    print(f"Pass Rate:")
    print(f"  Baseline: {b_pass}/{len(all_tasks)} ({100*b_pass/len(all_tasks):.1f}%)")
    print(f"  MCP:      {m_pass}/{len(all_tasks)} ({100*m_pass/len(all_tasks):.1f}%)")
    print()
    
    # Token statistics
    b_prompts = [v.get('prompt_tokens', 0) for v in baseline_results.values() if v.get('prompt_tokens', 0) > 0]
    m_prompts = [v.get('prompt_tokens', 0) for v in mcp_results.values() if v.get('prompt_tokens', 0) > 0]
    
    b_comps = [v.get('completion_tokens', 0) for v in baseline_results.values() if v.get('completion_tokens', 0) > 0]
    m_comps = [v.get('completion_tokens', 0) for v in mcp_results.values() if v.get('completion_tokens', 0) > 0]
    
    b_caches = [v.get('cached_tokens', 0) for v in baseline_results.values() if v.get('cached_tokens', 0) > 0]
    m_caches = [v.get('cached_tokens', 0) for v in mcp_results.values() if v.get('cached_tokens', 0) > 0]
    
    print(f"Prompt Tokens (avg):")
    if b_prompts:
        print(f"  Baseline: {mean(b_prompts):,.0f}")
    else:
        print(f"  Baseline: N/A (no token data captured)")
    if m_prompts:
        print(f"  MCP:      {mean(m_prompts):,.0f}")
        if b_prompts:
            print(f"  Difference: {mean(m_prompts) - mean(b_prompts):+,.0f} ({100*(mean(m_prompts) - mean(b_prompts))/mean(b_prompts):+.1f}%)")
    else:
        print(f"  MCP:      N/A (token data not captured - may indicate immediate success)")
    print()
    
    print(f"Completion Tokens (avg):")
    if b_comps:
        print(f"  Baseline: {mean(b_comps):,.0f}")
    else:
        print(f"  Baseline: N/A (no token data captured)")
    if m_comps:
        print(f"  MCP:      {mean(m_comps):,.0f}")
        if b_comps:
            print(f"  Difference: {mean(m_comps) - mean(b_comps):+,.0f} ({100*(mean(m_comps) - mean(b_comps))/mean(b_comps):+.1f}%)")
    else:
        print(f"  MCP:      N/A (token data not captured)")
    print()
    
    print(f"Cached Tokens (avg):")
    if b_caches:
        print(f"  Baseline: {mean(b_caches):,.0f}")
    else:
        print(f"  Baseline: N/A (no cache data)")
    if m_caches:
        print(f"  MCP:      {mean(m_caches):,.0f}")
        print(f"  Difference: {mean(m_caches) - mean(b_caches):+,.0f}")
    else:
        print(f"  MCP:      N/A (no cache data)")
    print()
    
    # Cache efficiency for MCP
    total_cache_reads = sum(v.get('cache_read_tokens', 0) for v in mcp_results.values())
    total_cache_creates = sum(v.get('cache_creation_tokens', 0) for v in mcp_results.values())
    
    print(f"MCP Cache Efficiency:")
    print(f"  Total cache read tokens: {total_cache_reads:,}")
    print(f"  Total cache creation tokens: {total_cache_creates:,}")
    if total_cache_reads > 0:
        efficiency = total_cache_reads / (total_cache_reads + total_cache_creates) if (total_cache_reads + total_cache_creates) > 0 else 0
        print(f"  Cache hit rate: {efficiency*100:.1f}%")
    print()
    
    # Cost analysis
    b_costs = [calculate_token_cost(v.get('prompt_tokens', 0), v.get('completion_tokens', 0), v.get('model', '')) 
               for v in baseline_results.values() if v.get('prompt_tokens', 0) > 0 or v.get('completion_tokens', 0) > 0]
    m_costs = [calculate_token_cost(v.get('prompt_tokens', 0), v.get('completion_tokens', 0), v.get('model', '')) 
               for v in mcp_results.values() if v.get('prompt_tokens', 0) > 0 or v.get('completion_tokens', 0) > 0]
    
    print(f"Estimated Cost (Claude Haiku prices):")
    if b_costs:
        print(f"  Baseline (total): ${sum(b_costs):.2f}")
        print(f"  Baseline (avg):   ${mean(b_costs):.4f}")
    else:
        print(f"  Baseline: N/A (no token data)")
    if m_costs:
        print(f"  MCP (total):      ${sum(m_costs):.2f}")
        print(f"  MCP (avg):        ${mean(m_costs):.4f}")
        if b_costs:
            print(f"  Difference:       ${sum(m_costs) - sum(b_costs):+.2f}")
    else:
        print(f"  MCP: N/A (token data not captured)")
    print()
    
    # Step analysis
    b_steps = [v.get('steps', 0) for v in baseline_results.values() if v.get('steps', 0) > 0]
    m_steps = [v.get('steps', 0) for v in mcp_results.values() if v.get('steps', 0) > 0]
    
    print(f"Agent Steps (avg):")
    if b_steps:
        print(f"  Baseline: {mean(b_steps):.1f}")
    else:
        print(f"  Baseline: N/A")
    if m_steps:
        print(f"  MCP:      {mean(m_steps):.1f}")
        print(f"  Difference: {mean(m_steps) - mean(b_steps) if b_steps else 0:+.1f} steps ({100*(mean(m_steps) - mean(b_steps))/mean(b_steps) if b_steps and mean(b_steps) > 0 else 0:+.1f}%)")
    else:
        print(f"  MCP: N/A")
    print()
    
    print("=" * 150)


def main():
    baseline_dir = Path("jobs/comparison-20251219-clean/baseline")
    mcp_dir = Path("jobs/comparison-20251219-clean/mcp")
    
    if not baseline_dir.exists():
        print(f"Error: {baseline_dir} not found")
        sys.exit(1)
    
    if not mcp_dir.exists():
        print(f"Error: {mcp_dir} not found")
        sys.exit(1)
    
    print("Analyzing baseline results...")
    baseline_results = analyze_directory(baseline_dir)
    print(f"  Found {len(baseline_results)} tasks")
    
    print("Analyzing MCP results...")
    mcp_results = analyze_directory(mcp_dir)
    print(f"  Found {len(mcp_results)} tasks")
    
    print_detailed_comparison(baseline_results, mcp_results)


if __name__ == "__main__":
    main()
