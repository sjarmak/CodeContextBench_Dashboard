#!/usr/bin/env python3
"""
Extract enterprise-informed metrics from Phase 3 trajectory data.

Based on ENTERPRISE_CODEBASES.md insights:
- 58% time on comprehension, 35% navigation, 19% external docs
- Context switching costs (23min recovery)
- Code search patterns and success rates
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Any

def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp."""
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

def extract_metrics(jsonl_path: Path) -> Dict[str, Any]:
    """Extract enterprise metrics from a trajectory JSONL file."""

    metrics = {
        'agent_type': 'unknown',
        'task_id': str(jsonl_path.parent.parent.name),
        'total_events': 0,
        'total_tokens': {'input': 0, 'output': 0},

        # Tool usage patterns
        'tool_calls': Counter(),
        'tool_call_timeline': [],

        # File access patterns
        'files_read': set(),
        'files_written': set(),
        'files_accessed': [],  # Timeline

        # Search patterns
        'search_queries': [],
        'mcp_searches': 0,

        # Navigation metrics
        'file_reads_count': 0,
        'file_edits_count': 0,
        'rereads': Counter(),  # Files read multiple times

        # Build/test cycles
        'test_runs': 0,
        'build_attempts': 0,

        # Time-based metrics
        'start_time': None,
        'end_time': None,
        'time_to_first_edit': None,
        'time_to_first_test': None,

        # Phases (comprehension vs implementation)
        'comprehension_actions': 0,
        'implementation_actions': 0,
        'navigation_actions': 0,
    }

    events = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    metrics['total_events'] = len(events)

    first_edit_recorded = False
    first_test_recorded = False

    for i, event in enumerate(events):
        timestamp = parse_timestamp(event['timestamp'])

        if metrics['start_time'] is None:
            metrics['start_time'] = timestamp
        metrics['end_time'] = timestamp

        # Extract token usage
        if event.get('type') == 'assistant' and 'message' in event:
            usage = event['message'].get('usage', {})
            metrics['total_tokens']['input'] += usage.get('input_tokens', 0)
            metrics['total_tokens']['input'] += usage.get('cache_read_input_tokens', 0)
            metrics['total_tokens']['output'] += usage.get('output_tokens', 0)

        # Extract tool calls
        if event.get('type') == 'assistant' and 'message' in event:
            content = event['message'].get('content', [])
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'tool_use':
                    tool_name = item.get('name')
                    if tool_name:
                        metrics['tool_calls'][tool_name] += 1
                        metrics['tool_call_timeline'].append({
                            'timestamp': timestamp,
                            'tool': tool_name,
                            'input': item.get('input', {})
                        })

                        # Categorize by phase
                        if tool_name in ['Read', 'Grep', 'Glob']:
                            metrics['navigation_actions'] += 1
                            metrics['comprehension_actions'] += 1
                        elif tool_name in ['Edit', 'Write']:
                            metrics['implementation_actions'] += 1
                            if not first_edit_recorded:
                                metrics['time_to_first_edit'] = (timestamp - metrics['start_time']).total_seconds()
                                first_edit_recorded = True
                        elif tool_name == 'Bash':
                            cmd = item.get('input', {}).get('command', '')
                            if 'test' in cmd.lower() or 'npm test' in cmd:
                                metrics['test_runs'] += 1
                                if not first_test_recorded:
                                    metrics['time_to_first_test'] = (timestamp - metrics['start_time']).total_seconds()
                                    first_test_recorded = True
                            elif 'build' in cmd.lower() or 'npm run' in cmd:
                                metrics['build_attempts'] += 1
                            elif 'grep' in cmd or 'find' in cmd:
                                metrics['navigation_actions'] += 1
                                metrics['comprehension_actions'] += 1

                        # Track file access
                        if tool_name == 'Read':
                            file_path = item.get('input', {}).get('file_path')
                            if file_path:
                                metrics['files_read'].add(file_path)
                                metrics['file_reads_count'] += 1
                                metrics['rereads'][file_path] += 1
                                metrics['files_accessed'].append({
                                    'timestamp': timestamp,
                                    'action': 'read',
                                    'file': file_path
                                })

                        elif tool_name in ['Edit', 'Write']:
                            file_path = item.get('input', {}).get('file_path')
                            if file_path:
                                metrics['files_written'].add(file_path)
                                metrics['file_edits_count'] += 1
                                metrics['files_accessed'].append({
                                    'timestamp': timestamp,
                                    'action': 'write',
                                    'file': file_path
                                })

                        # MCP tool detection
                        if tool_name and tool_name.startswith('sg_'):
                            metrics['mcp_searches'] += 1
                            metrics['search_queries'].append({
                                'timestamp': timestamp,
                                'tool': tool_name,
                                'query': item.get('input', {})
                            })

    # Calculate derived metrics
    if metrics['start_time'] and metrics['end_time']:
        metrics['total_duration'] = (metrics['end_time'] - metrics['start_time']).total_seconds()

    # Navigation efficiency
    if metrics['file_edits_count'] > 0:
        metrics['navigation_efficiency'] = metrics['file_reads_count'] / metrics['file_edits_count']
    else:
        metrics['navigation_efficiency'] = metrics['file_reads_count']

    # Reread ratio (comprehension indicator)
    total_rereads = sum(count - 1 for count in metrics['rereads'].values() if count > 1)
    metrics['reread_ratio'] = total_rereads / max(1, len(metrics['files_read']))

    # Time allocation (approximate)
    total_actions = (metrics['comprehension_actions'] +
                    metrics['implementation_actions'] +
                    metrics['navigation_actions'])
    if total_actions > 0:
        metrics['time_allocation'] = {
            'comprehension_pct': 100 * metrics['comprehension_actions'] / total_actions,
            'implementation_pct': 100 * metrics['implementation_actions'] / total_actions,
            'navigation_pct': 100 * metrics['navigation_actions'] / total_actions,
        }

    # Convert sets to counts for JSON serialization
    metrics['unique_files_read'] = len(metrics['files_read'])
    metrics['unique_files_written'] = len(metrics['files_written'])
    del metrics['files_read']
    del metrics['files_written']

    # Convert Counter to dict
    metrics['tool_calls'] = dict(metrics['tool_calls'])
    metrics['rereads'] = dict(metrics['rereads'])

    return metrics

def compare_agents(baseline_metrics: Dict, mcp_metrics: Dict) -> Dict[str, Any]:
    """Compare baseline vs MCP agent metrics."""

    comparison = {
        'task_id': baseline_metrics['task_id'],

        # Token usage comparison
        'tokens': {
            'baseline': baseline_metrics['total_tokens']['input'] + baseline_metrics['total_tokens']['output'],
            'mcp': mcp_metrics['total_tokens']['input'] + mcp_metrics['total_tokens']['output'],
            'delta': mcp_metrics['total_tokens']['input'] + mcp_metrics['total_tokens']['output'] -
                    (baseline_metrics['total_tokens']['input'] + baseline_metrics['total_tokens']['output']),
            'delta_pct': 100 * ((mcp_metrics['total_tokens']['input'] + mcp_metrics['total_tokens']['output']) /
                              max(1, baseline_metrics['total_tokens']['input'] + baseline_metrics['total_tokens']['output']) - 1)
        },

        # Navigation efficiency
        'navigation_efficiency': {
            'baseline': baseline_metrics['navigation_efficiency'],
            'mcp': mcp_metrics['navigation_efficiency'],
            'ratio': mcp_metrics['navigation_efficiency'] / max(0.1, baseline_metrics['navigation_efficiency'])
        },

        # File access
        'file_access': {
            'baseline_reads': baseline_metrics['file_reads_count'],
            'mcp_reads': mcp_metrics['file_reads_count'],
            'baseline_writes': baseline_metrics['file_edits_count'],
            'mcp_writes': mcp_metrics['file_edits_count'],
        },

        # MCP advantage
        'mcp_searches': mcp_metrics['mcp_searches'],

        # Time to first action
        'time_to_first_edit': {
            'baseline': baseline_metrics.get('time_to_first_edit'),
            'mcp': mcp_metrics.get('time_to_first_edit'),
        },

        # Time allocation comparison
        'time_allocation_baseline': baseline_metrics.get('time_allocation', {}),
        'time_allocation_mcp': mcp_metrics.get('time_allocation', {}),
    }

    return comparison

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_enterprise_metrics.py <trajectory_dir>")
        print("Example: extract_enterprise_metrics.py jobs/phase3-rerun-proper-20251220-1335")
        sys.exit(1)

    trajectory_dir = Path(sys.argv[1])

    # Find all task directories
    task_dirs = [d for d in trajectory_dir.iterdir() if d.is_dir() and d.name.startswith('big-code-')]

    print(f"Found {len(task_dirs)} tasks to analyze\n")

    all_comparisons = []

    for task_dir in sorted(task_dirs):
        print(f"\n{'='*80}")
        print(f"Task: {task_dir.name}")
        print(f"{'='*80}\n")

        # Find baseline and MCP trajectories
        baseline_jsonl = list(task_dir.glob('baseline/**/agent/sessions/**/*.jsonl'))
        mcp_jsonl = list(task_dir.glob('mcp/**/agent/sessions/**/*.jsonl'))

        # Filter for main session file (not agent-*.jsonl)
        baseline_jsonl = [f for f in baseline_jsonl if not f.stem.startswith('agent-')]
        mcp_jsonl = [f for f in mcp_jsonl if not f.stem.startswith('agent-')]

        if not baseline_jsonl or not mcp_jsonl:
            print(f"⚠️  Missing trajectories for {task_dir.name}")
            continue

        baseline_path = baseline_jsonl[0]
        mcp_path = mcp_jsonl[0]

        print(f"Baseline: {baseline_path.name} ({baseline_path.stat().st_size} bytes)")
        print(f"MCP:      {mcp_path.name} ({mcp_path.stat().st_size} bytes)\n")

        # Extract metrics
        baseline_metrics = extract_metrics(baseline_path)
        mcp_metrics = extract_metrics(mcp_path)

        # Compare
        comparison = compare_agents(baseline_metrics, mcp_metrics)
        all_comparisons.append(comparison)

        # Print summary
        print(f"📊 ENTERPRISE METRICS COMPARISON")
        print(f"\nTokens:")
        print(f"  Baseline: {comparison['tokens']['baseline']:,}")
        print(f"  MCP:      {comparison['tokens']['mcp']:,}")
        print(f"  Delta:    {comparison['tokens']['delta']:+,} ({comparison['tokens']['delta_pct']:+.1f}%)")

        print(f"\nNavigation Efficiency (reads/writes):")
        print(f"  Baseline: {comparison['navigation_efficiency']['baseline']:.2f}")
        print(f"  MCP:      {comparison['navigation_efficiency']['mcp']:.2f}")

        print(f"\nFile Access:")
        print(f"  Baseline: {comparison['file_access']['baseline_reads']} reads, {comparison['file_access']['baseline_writes']} writes")
        print(f"  MCP:      {comparison['file_access']['mcp_reads']} reads ({mcp_metrics['mcp_searches']} MCP searches), {comparison['file_access']['mcp_writes']} writes")

        if baseline_metrics.get('time_allocation'):
            print(f"\nTime Allocation (Baseline):")
            print(f"  Comprehension: {baseline_metrics['time_allocation']['comprehension_pct']:.1f}%")
            print(f"  Navigation:    {baseline_metrics['time_allocation']['navigation_pct']:.1f}%")
            print(f"  Implementation: {baseline_metrics['time_allocation']['implementation_pct']:.1f}%")

        if mcp_metrics.get('time_allocation'):
            print(f"\nTime Allocation (MCP):")
            print(f"  Comprehension: {mcp_metrics['time_allocation']['comprehension_pct']:.1f}%")
            print(f"  Navigation:    {mcp_metrics['time_allocation']['navigation_pct']:.1f}%")
            print(f"  Implementation: {mcp_metrics['time_allocation']['implementation_pct']:.1f}%")

        if comparison['time_to_first_edit']['baseline'] and comparison['time_to_first_edit']['mcp']:
            print(f"\nTime to First Edit:")
            print(f"  Baseline: {comparison['time_to_first_edit']['baseline']:.0f}s")
            print(f"  MCP:      {comparison['time_to_first_edit']['mcp']:.0f}s")

        # Save detailed metrics
        output_dir = Path('results/enterprise_metrics')
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / f"{task_dir.name}_baseline.json", 'w') as f:
            json.dump(baseline_metrics, f, indent=2, default=str)

        with open(output_dir / f"{task_dir.name}_mcp.json", 'w') as f:
            json.dump(mcp_metrics, f, indent=2, default=str)

        with open(output_dir / f"{task_dir.name}_comparison.json", 'w') as f:
            json.dump(comparison, f, indent=2, default=str)

    # Save aggregate comparison
    if all_comparisons:
        with open(Path('results/enterprise_metrics/all_tasks_comparison.json'), 'w') as f:
            json.dump(all_comparisons, f, indent=2, default=str)

        print(f"\n\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*80}\n")
        print(f"Analyzed {len(all_comparisons)} tasks")
        print(f"Results saved to: results/enterprise_metrics/")
        print(f"\nNext steps:")
        print(f"  1. Review individual task metrics: results/enterprise_metrics/*_comparison.json")
        print(f"  2. Aggregate analysis: results/enterprise_metrics/all_tasks_comparison.json")
        print(f"  3. Run visualization: python scripts/visualize_enterprise_metrics.py")

if __name__ == '__main__':
    main()
