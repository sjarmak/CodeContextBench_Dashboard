#!/usr/bin/env python3
"""Collect observability metrics from completed Harbor benchmark runs.

Usage:
    python runners/collect_observability.py --jobs-dir jobs/
    python runners/collect_observability.py --jobs-dir jobs/ --agent claude-baseline
    python runners/collect_observability.py --jobs-dir jobs/ --output metrics.json
    
This script:
1. Scans jobs directory for Harbor run outputs
2. Writes run_manifest.json for each task execution
3. Aggregates metrics across all runs
4. Generates JSON and human-readable reports
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from observability import ManifestWriter, MetricsCollector, ClaudeOutputParser


def collect_manifests(jobs_dir: Path, agent_filter: str = None) -> int:
    """Write run_manifest.json for all Harbor tasks in jobs directory.
    
    Args:
        jobs_dir: Root jobs directory containing Harbor outputs
        agent_filter: Optional agent name to filter by
        
    Returns:
        Number of manifests written
    """
    jobs_dir = Path(jobs_dir)
    if not jobs_dir.exists():
        print(f"Error: Jobs directory not found: {jobs_dir}")
        return 0
    
    manifests_written = 0
    
    # Find all task directories with result.json
    for result_file in jobs_dir.rglob('result.json'):
        task_dir = result_file.parent
        
        # Check if already has manifest
        manifest_file = task_dir / 'run_manifest.json'
        if manifest_file.exists():
            print(f"✓ Already has manifest: {manifest_file}")
            manifests_written += 1
            continue
        
        # Extract metadata from path
        # Expected: jobs/{run-id}/task-{id} or jobs/{agent}-{bench}-{time}/task-{id}
        parts = task_dir.relative_to(jobs_dir).parts
        
        # Parse run directory name
        run_dir = parts[0] if len(parts) > 0 else 'unknown'
        task_name = parts[1] if len(parts) > 1 else 'unknown'
        
        # Extract agent and benchmark from run directory
        run_parts = run_dir.split('-')
        if len(run_parts) >= 2:
            agent_name = run_parts[0]
            benchmark_name = run_parts[1]
        else:
            agent_name = 'unknown'
            benchmark_name = 'unknown'
        
        # Filter by agent if specified
        if agent_filter and agent_name != agent_filter:
            continue
        
        # Write manifest
        try:
            writer = ManifestWriter(task_dir)
            
            # Extract token usage from Claude output if available
            token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            
            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name=agent_name,
                benchmark_name=benchmark_name,
                input_tokens=token_usage.input_tokens,
                output_tokens=token_usage.output_tokens
            )
            print(f"✓ Wrote manifest: {manifest_path}")
            if token_usage.total_tokens > 0:
                print(f"  Token usage: {token_usage.input_tokens} input, {token_usage.output_tokens} output")
            manifests_written += 1
        except Exception as e:
            print(f"✗ Failed to write manifest for {task_dir}: {e}")
    
    return manifests_written


def generate_metrics_report(jobs_dir: Path, output_path: Path = None) -> None:
    """Generate metrics report from collected manifests.
    
    Args:
        jobs_dir: Jobs directory containing manifests
        output_path: Optional path to write JSON report (defaults to jobs_dir/metrics_report.json)
    """
    jobs_dir = Path(jobs_dir)
    output_path = output_path or jobs_dir / 'metrics_report.json'
    
    collector = MetricsCollector(jobs_dir)
    
    # Load all manifests
    print(f"Loading manifests from {jobs_dir}...")
    manifests = collector.load_manifests()
    
    if not manifests:
        print("Warning: No manifests found")
        return
    
    print(f"Loaded {len(manifests)} manifests")
    
    # Extract metrics
    metrics = collector.extract_metrics(manifests)
    
    # Generate report
    report = collector.generate_report(metrics)
    
    # Write JSON report
    collector.write_report(report, output_path)
    
    # Print human-readable report
    print()
    collector.print_report(report)


def compare_runs(jobs_dir: Path, baseline_pattern: str, treatment_pattern: str) -> None:
    """Compare baseline and treatment runs for regressions.
    
    Args:
        jobs_dir: Jobs directory
        baseline_pattern: Pattern to match baseline runs (e.g., 'baseline')
        treatment_pattern: Pattern to match treatment runs (e.g., 'treatment')
    """
    jobs_dir = Path(jobs_dir)
    collector = MetricsCollector(jobs_dir)
    
    # Load manifests
    manifests = collector.load_manifests()
    metrics = collector.extract_metrics(manifests)
    
    # Split by pattern
    baseline_metrics = [m for m in metrics if baseline_pattern in m.agent]
    treatment_metrics = [m for m in metrics if treatment_pattern in m.agent]
    
    if not baseline_metrics or not treatment_metrics:
        print("Error: Could not find baseline or treatment metrics")
        return
    
    print(f"Baseline metrics: {len(baseline_metrics)}")
    print(f"Treatment metrics: {len(treatment_metrics)}")
    print()
    
    # Detect regressions
    regression = collector.detect_regression(
        baseline_metrics,
        treatment_metrics,
        threshold_percent=10.0
    )
    
    print("=" * 80)
    print("REGRESSION ANALYSIS")
    print("=" * 80)
    print()
    
    # Print baseline stats
    baseline = regression['baseline_stats']
    print("BASELINE")
    print("-" * 80)
    print(f"Success Rate:      {baseline['success_rate']:.1f}%")
    print(f"Avg Duration:      {baseline['avg_duration_sec']:.2f}s")
    print(f"Avg Reward:        {baseline['avg_reward']:.3f}")
    print()
    
    # Print treatment stats
    treatment = regression['treatment_stats']
    print("TREATMENT")
    print("-" * 80)
    print(f"Success Rate:      {treatment['success_rate']:.1f}%")
    print(f"Avg Duration:      {treatment['avg_duration_sec']:.2f}s")
    print(f"Avg Reward:        {treatment['avg_reward']:.3f}")
    print()
    
    # Print regressions
    if regression['regressions']:
        print("REGRESSIONS (threshold: 10%)")
        print("-" * 80)
        for reg in regression['regressions']:
            print(f"{reg['metric']:<25} {reg['baseline']:>10.2f} → {reg['treatment']:>10.2f} "
                  f"({reg['delta_percent']:+.1f}%)")
        print()
    else:
        print("No regressions detected (within threshold)")
        print()
    
    # Print improvements
    if regression['improvements']:
        print("IMPROVEMENTS (threshold: 10%)")
        print("-" * 80)
        for imp in regression['improvements']:
            print(f"{imp['metric']:<25} {imp['baseline']:>10.2f} → {imp['treatment']:>10.2f} "
                  f"({imp['delta_percent']:+.1f}%)")
        print()
    else:
        print("No improvements detected")
        print()


def main():
    """Entry point for observability collection."""
    parser = argparse.ArgumentParser(
        description='Collect and analyze observability metrics from Harbor benchmark runs'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # collect command
    collect_parser = subparsers.add_parser('collect', help='Write manifests from results')
    collect_parser.add_argument('--jobs-dir', required=True, help='Jobs directory')
    collect_parser.add_argument('--agent', help='Optional: filter by agent name')
    
    # report command
    report_parser = subparsers.add_parser('report', help='Generate metrics report')
    report_parser.add_argument('--jobs-dir', required=True, help='Jobs directory')
    report_parser.add_argument('--output', help='Output file for JSON report')
    
    # compare command
    compare_parser = subparsers.add_parser('compare', help='Compare baseline vs treatment')
    compare_parser.add_argument('--jobs-dir', required=True, help='Jobs directory')
    compare_parser.add_argument('--baseline', default='baseline', help='Baseline pattern')
    compare_parser.add_argument('--treatment', default='treatment', help='Treatment pattern')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'collect':
            count = collect_manifests(args.jobs_dir, args.agent)
            print(f"\nWrote {count} manifests")
            
        elif args.command == 'report':
            generate_metrics_report(args.jobs_dir, Path(args.output) if args.output else None)
            
        elif args.command == 'compare':
            compare_runs(args.jobs_dir, args.baseline, args.treatment)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
