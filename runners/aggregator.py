#!/usr/bin/env python3
"""Aggregate results from multiple benchmark runs into cross-benchmark reports.

Analyzes patterns across different benchmarks, agents, and configurations
to identify trends in agent performance.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any
from datetime import datetime


def load_results_from_jobs_dir(jobs_dir: str) -> List[Dict[str, Any]]:
    """Load all Harbor result.json files from a jobs directory tree.
    
    Args:
        jobs_dir: Root jobs directory containing timestamped run directories
        
    Returns:
        List of result dictionaries with run metadata
    """
    results = []
    jobs_path = Path(jobs_dir)
    
    if not jobs_path.exists():
        print(f"Warning: Jobs directory not found: {jobs_dir}", file=sys.stderr)
        return results
    
    # Find all result.json files (skip top-level aggregates)
    for result_file in jobs_path.rglob("result.json"):
        # Skip summary files at benchmark root
        if result_file.parent == jobs_path:
            continue
        
        try:
            with open(result_file) as f:
                data = json.load(f)
            
            # Extract agent and benchmark from directory path
            parts = result_file.parts
            run_dir = None
            for i, part in enumerate(parts):
                if 'jobs' in part:
                    if i + 1 < len(parts):
                        run_dir = parts[i + 1]
                    break
            
            task_name = data.get('task_name', data.get('task_id', 'unknown'))
            verifier_result = data.get('verifier_result', {})
            reward = verifier_result.get('rewards', {}).get('reward', 0)
            
            results.append({
                'run_dir': run_dir or 'unknown',
                'task_name': task_name,
                'success': reward > 0,
                'reward': reward,
                'agent_time': data.get('agent_execution', {}).get('duration_sec', 0),
                'error_type': data.get('exception_info', {}).get('type'),
                'patch_size': data.get('patch_info', {}).get('size_bytes', 0),
            })
        except Exception as e:
            print(f"Error reading {result_file}: {e}", file=sys.stderr)
    
    return results


def generate_aggregate_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate cross-benchmark aggregate statistics.
    
    Args:
        results: List of result dictionaries from all runs
        
    Returns:
        Aggregate report dictionary
    """
    if not results:
        return {
            'total_tasks': 0,
            'total_successful': 0,
            'overall_accuracy': 0.0,
            'by_run': {},
            'by_task': {},
            'errors': {},
        }
    
    # Group by run
    results_by_run = defaultdict(list)
    results_by_task = defaultdict(list)
    
    for result in results:
        results_by_run[result['run_dir']].append(result)
        results_by_task[result['task_name']].append(result)
    
    # Compute per-run statistics
    run_stats = {}
    for run_dir, run_results in results_by_run.items():
        total = len(run_results)
        successful = sum(1 for r in run_results if r['success'])
        accuracy = (successful / total * 100) if total else 0
        
        run_stats[run_dir] = {
            'total': total,
            'successful': successful,
            'accuracy': accuracy,
            'avg_time': sum(r['agent_time'] for r in run_results) / total if total else 0,
            'avg_patch_size': sum(r['patch_size'] for r in run_results) / total if total else 0,
        }
    
    # Compute per-task statistics
    task_stats = {}
    for task_name, task_results in results_by_task.items():
        successes = sum(1 for r in task_results if r['success'])
        task_stats[task_name] = {
            'total_runs': len(task_results),
            'successful_runs': successes,
            'success_rate': (successes / len(task_results) * 100) if task_results else 0,
            'avg_time': sum(r['agent_time'] for r in task_results) / len(task_results) if task_results else 0,
        }
    
    # Compute overall statistics
    total_tasks = len(results)
    total_successful = sum(1 for r in results if r['success'])
    overall_accuracy = (total_successful / total_tasks * 100) if total_tasks else 0
    
    # Aggregate errors
    error_counts = defaultdict(int)
    for result in results:
        if result.get('error_type'):
            error_counts[result['error_type']] += 1
    
    return {
        'timestamp': datetime.now().isoformat(),
        'total_tasks': total_tasks,
        'total_successful': total_successful,
        'overall_accuracy': overall_accuracy,
        'by_run': run_stats,
        'by_task': task_stats,
        'errors': dict(error_counts),
    }


def print_aggregate_report(report: Dict[str, Any]) -> None:
    """Print aggregated results in human-readable format.
    
    Args:
        report: Aggregate report dictionary
    """
    print("=" * 120)
    print("CROSS-BENCHMARK AGGREGATE REPORT")
    print("=" * 120)
    print()
    
    if report['total_tasks'] == 0:
        print("No results found")
        return
    
    print(f"Timestamp: {report['timestamp']}")
    print()
    
    # Overall statistics
    print("OVERALL STATISTICS")
    print("-" * 120)
    print(f"Total Tasks Run:    {report['total_tasks']}")
    print(f"Total Successful:   {report['total_successful']}")
    print(f"Overall Accuracy:   {report['overall_accuracy']:.1f}%")
    print()
    
    # Per-run breakdown
    if report['by_run']:
        print("RESULTS BY RUN")
        print("-" * 120)
        print(f"{'Run Directory':<50} {'Total':<10} {'Success':<10} {'Accuracy':<12} {'Avg Time':<12}")
        print("-" * 120)
        
        for run_dir, stats in sorted(report['by_run'].items()):
            print(f"{run_dir:<50} {stats['total']:<10} {stats['successful']:<10} "
                  f"{stats['accuracy']:<11.1f}% {stats['avg_time']:<11.2f}s")
        print()
    
    # Tasks with consistency issues
    task_consistency = []
    for task_name, stats in report['by_task'].items():
        if stats['total_runs'] > 1:
            success_rate = stats['success_rate']
            # Flag if success rate is 0-100 (inconsistent)
            if success_rate not in (0, 100):
                task_consistency.append((task_name, stats))
    
    if task_consistency:
        print("INCONSISTENT TASKS (varied success across runs)")
        print("-" * 120)
        print(f"{'Task Name':<60} {'Success Rate':<20} {'Runs':<10}")
        print("-" * 120)
        
        for task_name, stats in sorted(task_consistency, key=lambda x: x[1]['success_rate']):
            print(f"{task_name:<60} {stats['success_rate']:<19.1f}% {stats['total_runs']:<10}")
        print()
    
    # Error summary
    if report['errors']:
        print("ERROR SUMMARY")
        print("-" * 120)
        print(f"{'Error Type':<60} {'Count':<20}")
        print("-" * 120)
        
        for error_type, count in sorted(report['errors'].items(), key=lambda x: -x[1]):
            print(f"{error_type:<60} {count:<20}")
        print()
    
    print("=" * 120)


def main():
    """Entry point for result aggregation."""
    # Parse arguments
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Aggregate benchmark results across multiple runs'
    )
    parser.add_argument(
        '--runs',
        required=True,
        help='Directory containing Harbor job outputs'
    )
    parser.add_argument(
        '--output',
        default='cross-benchmark-report.json',
        help='Output file for JSON report (default: cross-benchmark-report.json)'
    )
    
    args = parser.parse_args()
    
    # Load results
    print(f"Loading results from {args.runs}...", file=sys.stderr)
    results = load_results_from_jobs_dir(args.runs)
    
    if not results:
        print("Error: No results found", file=sys.stderr)
        sys.exit(1)
    
    print(f"Loaded {len(results)} results", file=sys.stderr)
    
    # Generate report
    report = generate_aggregate_report(results)
    
    # Print human-readable report
    print_aggregate_report(report)
    
    # Save JSON report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nJSON report saved to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
