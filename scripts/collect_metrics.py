#!/usr/bin/env python3
"""
CLI tool for collecting enterprise metrics from trajectory files.

Usage:
    # Single trajectory
    python scripts/collect_metrics.py trajectory.jsonl

    # Directory of trajectories
    python scripts/collect_metrics.py jobs/phase3-rerun-proper-20251220-1335

    # With output directory
    python scripts/collect_metrics.py trajectory.jsonl --output results/metrics

    # Compare baseline vs MCP
    python scripts/collect_metrics.py --compare \\
        jobs/*/baseline/**/*.jsonl \\
        jobs/*/mcp/**/*.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics import EnterpriseMetricsCollector

def collect_single(jsonl_path: Path, output_dir: Path, task_metadata: dict = None) -> dict:
    """Collect metrics from a single trajectory file."""
    print(f"Processing: {jsonl_path.name}")

    collector = EnterpriseMetricsCollector()
    metrics = collector.process_trajectory(jsonl_path, task_metadata)

    # Save to output
    output_file = output_dir / f"{jsonl_path.stem}_metrics.json"
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"  ✅ Saved to: {output_file}")
    return metrics

def print_summary(metrics: dict):
    """Print a summary of metrics."""
    print(f"\n📊 METRICS SUMMARY: {metrics['metadata']['task_id']}")
    print(f"  Agent type: {metrics['metadata']['agent_type']}")
    print(f"  Duration: {metrics['execution']['total_duration']:.0f}s")
    print(f"  Events: {metrics['execution']['total_events']}")
    print(f"\n  Tokens: {metrics['tokens']['total']:,}")
    print(f"    Input:  {metrics['tokens']['total_input']:,}")
    print(f"    Output: {metrics['tokens']['total_output']:,}")
    print(f"\n  Time Allocation:")
    print(f"    Comprehension: {metrics['time_allocation']['comprehension_pct']:.1f}% (target: 58%)")
    print(f"    Navigation:    {metrics['time_allocation']['navigation_pct']:.1f}% (target: 35%)")
    print(f"    Implementation: {metrics['time_allocation']['implementation_pct']:.1f}%")
    print(f"    Gap: {metrics['time_allocation']['baseline_comparison']['comprehension_gap']:+.1f} points")
    print(f"\n  Navigation:")
    print(f"    Reads:  {metrics['navigation']['file_reads']}")
    print(f"    Writes: {metrics['navigation']['file_writes']}")
    print(f"    Efficiency: {metrics['navigation']['navigation_efficiency']:.2f} reads/write")
    print(f"    Rereads: {len([f for f, c in metrics['navigation']['rereads'].items() if c > 1])} files")
    print(f"\n  Tools:")
    print(f"    MCP searches: {metrics['tool_usage']['mcp_searches']}")
    print(f"    Test runs: {metrics['build_test']['test_runs']}")
    print(f"    Build attempts: {metrics['build_test']['build_attempts']}")
    print(f"\n  Context Switching:")
    print(f"    File switches: {metrics['context_switching']['file_switches']}")
    print(f"    Rapid switches: {metrics['context_switching']['rapid_switches']}")
    print(f"    Thrashing: {'⚠️  Yes' if metrics['context_switching']['thrashing_detected'] else 'No'}")

def compare_agents(baseline_metrics: dict, mcp_metrics: dict):
    """Compare baseline vs MCP metrics."""
    print(f"\n\n{'='*80}")
    print(f"BASELINE vs MCP COMPARISON")
    print(f"{'='*80}\n")

    print(f"Task: {baseline_metrics['metadata']['task_id']}\n")

    # Tokens
    baseline_tokens = baseline_metrics['tokens']['total']
    mcp_tokens = mcp_metrics['tokens']['total']
    delta = mcp_tokens - baseline_tokens
    delta_pct = 100 * delta / baseline_tokens

    print(f"Tokens:")
    print(f"  Baseline: {baseline_tokens:,}")
    print(f"  MCP:      {mcp_tokens:,}")
    print(f"  Delta:    {delta:+,} ({delta_pct:+.1f}%)\n")

    # Time allocation
    print(f"Time Allocation:")
    print(f"  Comprehension:")
    print(f"    Baseline: {baseline_metrics['time_allocation']['comprehension_pct']:.1f}%")
    print(f"    MCP:      {mcp_metrics['time_allocation']['comprehension_pct']:.1f}%")
    print(f"  Navigation:")
    print(f"    Baseline: {baseline_metrics['time_allocation']['navigation_pct']:.1f}%")
    print(f"    MCP:      {mcp_metrics['time_allocation']['navigation_pct']:.1f}%")
    print(f"  Implementation:")
    print(f"    Baseline: {baseline_metrics['time_allocation']['implementation_pct']:.1f}%")
    print(f"    MCP:      {mcp_metrics['time_allocation']['implementation_pct']:.1f}%\n")

    # Navigation
    print(f"Navigation Efficiency:")
    print(f"  Baseline: {baseline_metrics['navigation']['navigation_efficiency']:.2f} reads/write")
    print(f"  MCP:      {mcp_metrics['navigation']['navigation_efficiency']:.2f} reads/write\n")

    # MCP advantage
    print(f"MCP Advantage:")
    print(f"  Searches: {mcp_metrics['tool_usage']['mcp_searches']} (baseline: {baseline_metrics['tool_usage']['mcp_searches']})")
    print(f"  Tools detected: {', '.join(mcp_metrics['tool_usage']['mcp_tools_detected']) if mcp_metrics['tool_usage']['mcp_tools_detected'] else 'None'}\n")

    # Quality indicators
    print(f"Enterprise Alignment:")
    baseline_gap = abs(baseline_metrics['time_allocation']['baseline_comparison']['comprehension_gap'])
    mcp_gap = abs(mcp_metrics['time_allocation']['baseline_comparison']['comprehension_gap'])

    if mcp_gap < baseline_gap:
        print(f"  ✅ MCP closer to research baseline ({mcp_gap:.1f} vs {baseline_gap:.1f} point gap)")
    else:
        print(f"  ⚠️  Baseline closer to research baseline ({baseline_gap:.1f} vs {mcp_gap:.1f} point gap)")

def main():
    parser = argparse.ArgumentParser(description='Collect enterprise metrics from trajectories')
    parser.add_argument('paths', nargs='+', help='Trajectory file(s) or directory')
    parser.add_argument('--output', '-o', default='results/enterprise_metrics_v2',
                       help='Output directory for metrics JSON files')
    parser.add_argument('--compare', action='store_true',
                       help='Compare first two trajectories as baseline vs MCP')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Print detailed summaries')

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {output_dir}\n")

    # Collect all trajectory files
    trajectory_files: List[Path] = []
    for path_str in args.paths:
        path = Path(path_str)
        if path.is_file() and path.suffix == '.jsonl':
            trajectory_files.append(path)
        elif path.is_dir():
            # Find all .jsonl files that look like session files
            found = list(path.rglob('*.jsonl'))
            # Filter out agent-*.jsonl files (internal Harbor files)
            found = [f for f in found if not f.stem.startswith('agent-')]
            trajectory_files.extend(found)

    if not trajectory_files:
        print(f"❌ No trajectory files found")
        return 1

    print(f"Found {len(trajectory_files)} trajectory files\n")

    # Collect metrics
    all_metrics = []
    for traj_file in trajectory_files:
        try:
            # Infer metadata from path
            task_id = 'unknown'
            agent_type = 'unknown'

            # Try to extract from path: .../task_id/agent_type/.../file.jsonl
            parts = traj_file.parts
            if 'baseline' in parts:
                agent_type = 'baseline'
            elif 'mcp' in parts:
                agent_type = 'mcp'

            for part in parts:
                if part.startswith('big-code-'):
                    task_id = part
                    break

            metadata = {
                'task_id': task_id,
                'agent_type': agent_type
            }

            metrics = collect_single(traj_file, output_dir, metadata)
            all_metrics.append(metrics)

            if args.verbose:
                print_summary(metrics)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

    # Comparison mode
    if args.compare and len(all_metrics) >= 2:
        compare_agents(all_metrics[0], all_metrics[1])

    # Save aggregate
    aggregate_file = output_dir / 'all_metrics.json'
    with open(aggregate_file, 'w') as f:
        json.dump(all_metrics, f, indent=2)

    print(f"\n\n✅ Complete! Processed {len(all_metrics)} trajectories")
    print(f"📁 Metrics saved to: {output_dir}")
    print(f"📊 Aggregate file: {aggregate_file}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
