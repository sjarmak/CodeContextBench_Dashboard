#!/usr/bin/env python3
"""Compare Harbor benchmark results between baseline and treatment runs.

Generates summary statistics and task-by-task comparison reports
for evaluating agent performance across different configurations.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple


def load_harbor_results(jobs_dir: str) -> List[Dict[str, Any]]:
    """Load all result.json files from a Harbor jobs directory.
    
    Args:
        jobs_dir: Path to Harbor jobs directory
        
    Returns:
        List of result dictionaries from Harbor executions
    """
    results = []
    jobs_path = Path(jobs_dir)
    
    if not jobs_path.exists():
        print(f"Warning: Jobs directory not found: {jobs_dir}", file=sys.stderr)
        return results
    
    for result_file in jobs_path.rglob("result.json"):
        # Skip top-level summary result.json files
        if result_file.parent == jobs_path or result_file.parent.name.startswith("2025-"):
            if result_file.parent.parent == jobs_path:
                continue
        
        try:
            with open(result_file) as f:
                data = json.load(f)
            
            task_name = data.get('task_name', data.get('task_id', 'unknown'))
            if not task_name:
                continue
            
            # Extract verification result
            verifier_result = data.get('verifier_result', {})
            rewards = verifier_result.get('rewards', {})
            reward = rewards.get('reward', 0)
            
            # Extract timing info
            agent_exec = data.get('agent_execution', {})
            agent_time = agent_exec.get('duration_sec', 0)
            
            # Extract error info
            exception = data.get('exception_info', {})
            error_type = exception.get('type') if exception else None
            error_message = exception.get('message') if exception else None
            
            # Extract patch info
            patch_info = data.get('patch_info', {})
            patch_size = patch_info.get('size_bytes', 0)
            files_changed = patch_info.get('files_changed', 0)
            
            results.append({
                'task_name': task_name,
                'trial_name': data.get('trial_name', 'unknown'),
                'success': reward > 0,
                'reward': reward,
                'agent_time': agent_time,
                'error_type': error_type,
                'error_message': error_message,
                'patch_size': patch_size,
                'files_changed': files_changed,
            })
        except Exception as e:
            print(f"Error reading {result_file}: {e}", file=sys.stderr)
    
    return results


def compute_summary_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute summary statistics for a result set.
    
    Args:
        results: List of result dictionaries
        
    Returns:
        Dictionary with summary statistics
    """
    if not results:
        return {
            'total': 0,
            'successful': 0,
            'accuracy': 0.0,
            'avg_time': 0.0,
            'avg_patch_size': 0.0,
            'errors': {}
        }
    
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    accuracy = (successful / total * 100) if total else 0.0
    avg_time = sum(r['agent_time'] for r in results) / total if total else 0.0
    avg_patch_size = sum(r['patch_size'] for r in results) / total if total else 0.0
    
    # Count errors
    error_counts = defaultdict(int)
    for r in results:
        if r['error_type']:
            error_counts[r['error_type']] += 1
    
    return {
        'total': total,
        'successful': successful,
        'accuracy': accuracy,
        'avg_time': avg_time,
        'avg_patch_size': avg_patch_size,
        'errors': dict(error_counts),
    }


def compare_results(baseline_dir: str, treatment_dir: str) -> None:
    """Generate comparison report between baseline and treatment runs.
    
    Args:
        baseline_dir: Path to baseline Harbor jobs directory
        treatment_dir: Path to treatment Harbor jobs directory
    """
    baseline = load_harbor_results(baseline_dir)
    treatment = load_harbor_results(treatment_dir)
    
    if not baseline or not treatment:
        print("Error: No results found in one or both directories", file=sys.stderr)
        sys.exit(1)
    
    # Compute statistics
    baseline_stats = compute_summary_stats(baseline)
    treatment_stats = compute_summary_stats(treatment)
    
    # Create task mappings
    baseline_map = {r['task_name']: r for r in baseline}
    treatment_map = {r['task_name']: r for r in treatment}
    all_tasks = sorted(set(baseline_map.keys()) | set(treatment_map.keys()))
    
    # Print header
    print("=" * 110)
    print("CODCONTEXTBENCH COMPARISON REPORT")
    print("=" * 110)
    print()
    print(f"Baseline:  {baseline_dir}")
    print(f"Treatment: {treatment_dir}")
    print()
    
    # Print summary statistics
    print("SUMMARY STATISTICS")
    print("-" * 110)
    print()
    print(f"{'Metric':<40} {'Baseline':<25} {'Treatment':<25} {'Delta':<20}")
    print("-" * 110)
    
    print(f"{'Total Tasks':<40} {baseline_stats['total']:<25} {treatment_stats['total']:<25} "
          f"{treatment_stats['total'] - baseline_stats['total']:+<20}")
    
    print(f"{'Successful Tasks':<40} {baseline_stats['successful']:<25} {treatment_stats['successful']:<25} "
          f"{treatment_stats['successful'] - baseline_stats['successful']:+<20}")
    
    print(f"{'Accuracy':<40} {baseline_stats['accuracy']:<24.1f}% {treatment_stats['accuracy']:<24.1f}% "
          f"{treatment_stats['accuracy'] - baseline_stats['accuracy']:+.1f}%")
    
    print(f"{'Avg Agent Time (sec)':<40} {baseline_stats['avg_time']:<25.2f} {treatment_stats['avg_time']:<25.2f} "
          f"{treatment_stats['avg_time'] - baseline_stats['avg_time']:+.2f}")
    
    print(f"{'Avg Patch Size (bytes)':<40} {baseline_stats['avg_patch_size']:<25.0f} "
          f"{treatment_stats['avg_patch_size']:<25.0f} "
          f"{treatment_stats['avg_patch_size'] - baseline_stats['avg_patch_size']:+.0f}")
    
    print()
    
    # Print error breakdown
    print("ERROR BREAKDOWN")
    print("-" * 110)
    all_error_types = sorted(
        set(baseline_stats['errors'].keys()) | set(treatment_stats['errors'].keys())
    )
    
    if all_error_types:
        print(f"{'Error Type':<40} {'Baseline':<25} {'Treatment':<25}")
        print("-" * 110)
        for error_type in all_error_types:
            baseline_count = baseline_stats['errors'].get(error_type, 0)
            treatment_count = treatment_stats['errors'].get(error_type, 0)
            print(f"{error_type:<40} {baseline_count:<25} {treatment_count:<25}")
    else:
        print("No errors in either run")
    
    print()
    
    # Print task-by-task differences
    print("TASK-BY-TASK DIFFERENCES")
    print("-" * 110)
    print()
    
    differences = []
    for task in all_tasks:
        b = baseline_map.get(task)
        t = treatment_map.get(task)
        
        if not b or not t:
            differences.append((task, b, t, "MISSING"))
        elif b['success'] != t['success']:
            differences.append((task, b, t, "OUTCOME_CHANGE"))
        elif abs(b['agent_time'] - t['agent_time']) > 1.0:  # >1s time difference
            differences.append((task, b, t, "TIME_CHANGE"))
    
    if differences:
        print(f"Found {len(differences)} tasks with differences:")
        print()
        print(f"{'Task':<50} {'Baseline':<15} {'Treatment':<15} {'Reason':<20}")
        print("-" * 110)
        
        for task, b, t, reason in differences:
            if reason == "MISSING":
                status = "MISSING in " + ("treatment" if not t else "baseline")
                print(f"{task:<50} {'':<15} {'':<15} {status:<20}")
            elif reason == "OUTCOME_CHANGE":
                b_status = "✓ PASS" if b['success'] else "✗ FAIL"
                t_status = "✓ PASS" if t['success'] else "✗ FAIL"
                print(f"{task:<50} {b_status:<15} {t_status:<15} {reason:<20}")
            elif reason == "TIME_CHANGE":
                b_time = f"{b['agent_time']:.2f}s"
                t_time = f"{t['agent_time']:.2f}s"
                print(f"{task:<50} {b_time:<15} {t_time:<15} {reason:<20}")
    else:
        print("All tasks had identical outcomes in both runs")
    
    print()
    print("=" * 110)


def main():
    """Entry point for result comparison."""
    if len(sys.argv) < 3:
        print("Usage: compare_results.py <baseline-dir> <treatment-dir>")
        print()
        print("Compares Harbor benchmark results between baseline and treatment runs.")
        print()
        print("Example:")
        print("  python3 compare_results.py jobs/claude-baseline-20251217-161000 jobs/claude-mcp-20251217-161500")
        sys.exit(1)
    
    baseline_dir = sys.argv[1]
    treatment_dir = sys.argv[2]
    
    compare_results(baseline_dir, treatment_dir)


if __name__ == "__main__":
    main()
