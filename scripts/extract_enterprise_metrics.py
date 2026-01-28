#!/usr/bin/env python3
"""Extract enterprise metrics from trajectory files for baseline vs MCP comparison."""

import json
import os
from pathlib import Path
from collections import defaultdict
import sys

def extract_metrics_from_trajectory(trajectory_path):
    """Extract relevant metrics from a trajectory file."""
    with open(trajectory_path) as f:
        data = json.load(f)
    
    metrics = {
        'total_steps': len(data.get('steps', [])),
        'tool_calls': defaultdict(int),
        'file_reads': 0,
        'grep_searches': 0,
        'glob_searches': 0,
        'bash_commands': 0,
        'mcp_deep_search': 0,
        'mcp_keyword_search': 0,
        'mcp_other': 0,
        'total_prompt_tokens': 0,
        'total_completion_tokens': 0,
        'files_mentioned': set(),
    }
    
    for step in data.get('steps', []):
        # Count tokens
        if 'metrics' in step:
            metrics['total_prompt_tokens'] += step['metrics'].get('prompt_tokens', 0)
            metrics['total_completion_tokens'] += step['metrics'].get('completion_tokens', 0)
        
        # Count tool calls
        if 'tool_calls' in step:
            for call in step['tool_calls']:
                func_name = call.get('function_name', 'unknown')
                metrics['tool_calls'][func_name] += 1
                
                # Categorize tool calls
                if 'read' in func_name.lower() or func_name == 'Read':
                    metrics['file_reads'] += 1
                elif 'grep' in func_name.lower() or func_name == 'Grep':
                    metrics['grep_searches'] += 1
                elif 'glob' in func_name.lower() or func_name == 'Glob':
                    metrics['glob_searches'] += 1
                elif 'bash' in func_name.lower():
                    metrics['bash_commands'] += 1
                elif 'deepsearch' in func_name.lower() or 'deep_search' in func_name.lower():
                    metrics['mcp_deep_search'] += 1
                elif 'sg_' in func_name.lower() or 'mcp_' in func_name.lower() or 'sourcegraph' in func_name.lower():
                    if 'keyword' in func_name.lower() or 'search' in func_name.lower():
                        metrics['mcp_keyword_search'] += 1
                    else:
                        metrics['mcp_other'] += 1
        
        # Look for file paths in messages
        message = step.get('message', '')
        if isinstance(message, str):
            # Simple heuristic: look for paths
            for word in message.split():
                if '/' in word and ('.' in word or word.startswith('/')):
                    metrics['files_mentioned'].add(word[:100])  # Truncate long paths
    
    metrics['files_mentioned'] = len(metrics['files_mentioned'])
    metrics['tool_calls'] = dict(metrics['tool_calls'])
    return metrics


def analyze_runs(base_path, label):
    """Analyze all runs in a directory."""
    all_metrics = []
    
    for root, dirs, files in os.walk(base_path):
        if 'trajectory.json' in files:
            traj_path = Path(root) / 'trajectory.json'
            try:
                metrics = extract_metrics_from_trajectory(traj_path)
                task_name = root.split('/')[-2] if '__' in root.split('/')[-1] else root.split('/')[-1]
                metrics['task'] = task_name
                metrics['path'] = str(traj_path)
                all_metrics.append(metrics)
            except Exception as e:
                print(f"Error processing {traj_path}: {e}", file=sys.stderr)
    
    return all_metrics


def compute_summary(metrics_list):
    """Compute summary statistics."""
    if not metrics_list:
        return {}
    
    total_tasks = len(metrics_list)
    summary = {
        'total_tasks': total_tasks,
        'avg_steps': sum(m['total_steps'] for m in metrics_list) / total_tasks,
        'avg_file_reads': sum(m['file_reads'] for m in metrics_list) / total_tasks,
        'avg_grep_searches': sum(m['grep_searches'] for m in metrics_list) / total_tasks,
        'avg_glob_searches': sum(m['glob_searches'] for m in metrics_list) / total_tasks,
        'avg_bash_commands': sum(m['bash_commands'] for m in metrics_list) / total_tasks,
        'avg_mcp_deep_search': sum(m['mcp_deep_search'] for m in metrics_list) / total_tasks,
        'avg_mcp_keyword_search': sum(m['mcp_keyword_search'] for m in metrics_list) / total_tasks,
        'total_prompt_tokens': sum(m['total_prompt_tokens'] for m in metrics_list),
        'total_completion_tokens': sum(m['total_completion_tokens'] for m in metrics_list),
        'avg_files_mentioned': sum(m['files_mentioned'] for m in metrics_list) / total_tasks,
    }
    return summary


def main():
    baseline_path = Path("runs/baseline-10task-20251219")
    mcp_path = Path("runs/mcp-10task-20251219")
    
    print("Extracting enterprise metrics from trajectories...\n")
    
    baseline_metrics = analyze_runs(baseline_path, "baseline")
    mcp_metrics = analyze_runs(mcp_path, "mcp")
    
    baseline_summary = compute_summary(baseline_metrics)
    mcp_summary = compute_summary(mcp_metrics)
    
    print("=" * 60)
    print("ENTERPRISE METRICS COMPARISON")
    print("=" * 60)
    print()
    
    print(f"{'Metric':<30} {'Baseline':>15} {'MCP':>15} {'Ratio':>10}")
    print("-" * 70)
    
    metrics_to_compare = [
        ('Tasks analyzed', 'total_tasks'),
        ('Avg steps per task', 'avg_steps'),
        ('Avg file reads', 'avg_file_reads'),
        ('Avg grep searches', 'avg_grep_searches'),
        ('Avg glob searches', 'avg_glob_searches'),
        ('Avg bash commands', 'avg_bash_commands'),
        ('Avg MCP Deep Search', 'avg_mcp_deep_search'),
        ('Avg MCP Keyword Search', 'avg_mcp_keyword_search'),
        ('Total prompt tokens', 'total_prompt_tokens'),
        ('Total completion tokens', 'total_completion_tokens'),
        ('Avg files mentioned', 'avg_files_mentioned'),
    ]
    
    for label, key in metrics_to_compare:
        b_val = baseline_summary.get(key, 0)
        m_val = mcp_summary.get(key, 0)
        ratio = m_val / b_val if b_val > 0 else float('inf')
        
        if isinstance(b_val, float):
            print(f"{label:<30} {b_val:>15.1f} {m_val:>15.1f} {ratio:>10.2f}x")
        else:
            print(f"{label:<30} {b_val:>15,} {m_val:>15,} {ratio:>10.2f}x")
    
    print()
    print("=" * 60)
    print("TOOL USAGE BREAKDOWN")
    print("=" * 60)
    
    # Aggregate tool calls
    baseline_tools = defaultdict(int)
    mcp_tools = defaultdict(int)
    
    for m in baseline_metrics:
        for tool, count in m['tool_calls'].items():
            baseline_tools[tool] += count
    
    for m in mcp_metrics:
        for tool, count in m['tool_calls'].items():
            mcp_tools[tool] += count
    
    all_tools = set(baseline_tools.keys()) | set(mcp_tools.keys())
    
    print(f"\n{'Tool':<40} {'Baseline':>10} {'MCP':>10}")
    print("-" * 60)
    for tool in sorted(all_tools):
        print(f"{tool:<40} {baseline_tools[tool]:>10} {mcp_tools[tool]:>10}")
    
    # Save detailed results
    output = {
        'baseline': {
            'summary': baseline_summary,
            'tasks': baseline_metrics
        },
        'mcp': {
            'summary': mcp_summary,
            'tasks': mcp_metrics
        }
    }
    
    output_path = Path("artifacts/enterprise_metrics_comparison.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
