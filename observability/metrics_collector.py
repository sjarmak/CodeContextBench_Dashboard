#!/usr/bin/env python3
"""Collect and analyze metrics from Harbor benchmark executions.

Provides utility functions to gather execution metrics from Harbor logs
and produce standardized performance reports.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import defaultdict
import statistics


@dataclass
class ExecutionMetrics:
    """Metrics from a single task execution."""
    task_id: str
    agent: str
    benchmark: str
    success: bool
    reward: float
    duration_sec: float
    patch_size_bytes: int
    files_changed: int
    error_type: Optional[str]


class MetricsCollector:
    """Collect and aggregate execution metrics from manifests."""
    
    def __init__(self, jobs_dir: Path):
        """Initialize metrics collector.
        
        Args:
            jobs_dir: Root directory containing Harbor job outputs
        """
        self.jobs_dir = Path(jobs_dir)
    
    def load_manifests(self) -> List[Dict[str, Any]]:
        """Load all run_manifest.json files from jobs directory.
        
        Returns:
            List of loaded manifest dictionaries
        """
        manifests = []
        
        for manifest_file in self.jobs_dir.rglob('run_manifest.json'):
            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    manifests.append(manifest)
            except Exception as e:
                print(f"Warning: Failed to load {manifest_file}: {e}")
        
        return manifests
    
    def extract_metrics(self, manifests: List[Dict[str, Any]]) -> List[ExecutionMetrics]:
        """Extract structured metrics from manifests.
        
        Args:
            manifests: List of loaded manifests
            
        Returns:
            List of ExecutionMetrics objects
        """
        metrics = []
        
        for manifest in manifests:
            execution = manifest.get('execution', {})
            result = manifest.get('result', {})
            
            m = ExecutionMetrics(
                task_id=result.get('task_id', 'unknown'),
                agent=execution.get('agent', 'unknown'),
                benchmark=execution.get('benchmark', 'unknown'),
                success=result.get('success', False),
                reward=result.get('reward', 0.0),
                duration_sec=result.get('duration_sec', 0.0),
                patch_size_bytes=result.get('patch_size_bytes', 0),
                files_changed=result.get('files_changed', 0),
                error_type=result.get('error_type'),
            )
            metrics.append(m)
        
        return metrics
    
    def compute_summary_stats(self, metrics: List[ExecutionMetrics]) -> Dict[str, Any]:
        """Compute summary statistics across metrics.
        
        Args:
            metrics: List of execution metrics
            
        Returns:
            Dictionary with aggregated statistics
        """
        if not metrics:
            return {
                'total': 0,
                'successful': 0,
                'success_rate': 0.0,
                'avg_duration_sec': 0.0,
                'avg_patch_size_bytes': 0,
                'avg_files_changed': 0,
                'avg_reward': 0.0,
                'errors': {},
            }
        
        successful = [m for m in metrics if m.success]
        durations = [m.duration_sec for m in metrics]
        patch_sizes = [m.patch_size_bytes for m in metrics]
        files_changed_list = [m.files_changed for m in metrics]
        rewards = [m.reward for m in metrics]
        
        # Count errors
        error_counts = defaultdict(int)
        for m in metrics:
            if m.error_type:
                error_counts[m.error_type] += 1
        
        return {
            'total': len(metrics),
            'successful': len(successful),
            'success_rate': len(successful) / len(metrics) * 100 if metrics else 0.0,
            'avg_duration_sec': statistics.mean(durations) if durations else 0.0,
            'median_duration_sec': statistics.median(durations) if durations else 0.0,
            'avg_patch_size_bytes': statistics.mean(patch_sizes) if patch_sizes else 0,
            'avg_files_changed': statistics.mean(files_changed_list) if files_changed_list else 0,
            'avg_reward': statistics.mean(rewards) if rewards else 0.0,
            'max_reward': max(rewards) if rewards else 0.0,
            'errors': dict(error_counts),
        }
    
    def compute_per_agent_stats(self, metrics: List[ExecutionMetrics]) -> Dict[str, Dict[str, Any]]:
        """Compute statistics grouped by agent.
        
        Args:
            metrics: List of execution metrics
            
        Returns:
            Dictionary mapping agent name to its statistics
        """
        by_agent = defaultdict(list)
        
        for m in metrics:
            by_agent[m.agent].append(m)
        
        stats = {}
        for agent, agent_metrics in by_agent.items():
            stats[agent] = self.compute_summary_stats(agent_metrics)
        
        return stats
    
    def compute_per_benchmark_stats(self, metrics: List[ExecutionMetrics]) -> Dict[str, Dict[str, Any]]:
        """Compute statistics grouped by benchmark.
        
        Args:
            metrics: List of execution metrics
            
        Returns:
            Dictionary mapping benchmark name to its statistics
        """
        by_benchmark = defaultdict(list)
        
        for m in metrics:
            by_benchmark[m.benchmark].append(m)
        
        stats = {}
        for benchmark, bench_metrics in by_benchmark.items():
            stats[benchmark] = self.compute_summary_stats(bench_metrics)
        
        return stats
    
    def detect_regression(
        self,
        baseline_metrics: List[ExecutionMetrics],
        treatment_metrics: List[ExecutionMetrics],
        threshold_percent: float = 10.0
    ) -> Dict[str, Any]:
        """Detect performance regressions between baseline and treatment.
        
        Args:
            baseline_metrics: Metrics from baseline run
            treatment_metrics: Metrics from treatment run
            threshold_percent: Percentage threshold for regression detection
            
        Returns:
            Dictionary with regression analysis
        """
        baseline_stats = self.compute_summary_stats(baseline_metrics)
        treatment_stats = self.compute_summary_stats(treatment_metrics)
        
        regressions = []
        improvements = []
        
        # Check success rate
        baseline_sr = baseline_stats['success_rate']
        treatment_sr = treatment_stats['success_rate']
        sr_delta = treatment_sr - baseline_sr
        
        if sr_delta < -threshold_percent:
            regressions.append({
                'metric': 'success_rate',
                'baseline': baseline_sr,
                'treatment': treatment_sr,
                'delta_percent': sr_delta,
            })
        elif sr_delta > threshold_percent:
            improvements.append({
                'metric': 'success_rate',
                'baseline': baseline_sr,
                'treatment': treatment_sr,
                'delta_percent': sr_delta,
            })
        
        # Check duration
        baseline_dur = baseline_stats['avg_duration_sec']
        treatment_dur = treatment_stats['avg_duration_sec']
        if baseline_dur > 0:
            dur_delta = (treatment_dur - baseline_dur) / baseline_dur * 100
            
            if dur_delta > threshold_percent:  # Slower is bad
                regressions.append({
                    'metric': 'avg_duration_sec',
                    'baseline': baseline_dur,
                    'treatment': treatment_dur,
                    'delta_percent': dur_delta,
                })
            elif dur_delta < -threshold_percent:  # Faster is good
                improvements.append({
                    'metric': 'avg_duration_sec',
                    'baseline': baseline_dur,
                    'treatment': treatment_dur,
                    'delta_percent': dur_delta,
                })
        
        return {
            'regressions': regressions,
            'improvements': improvements,
            'baseline_stats': baseline_stats,
            'treatment_stats': treatment_stats,
        }
    
    def generate_report(self, metrics: List[ExecutionMetrics]) -> Dict[str, Any]:
        """Generate comprehensive metrics report.
        
        Args:
            metrics: List of execution metrics
            
        Returns:
            Complete report dictionary
        """
        overall_stats = self.compute_summary_stats(metrics)
        per_agent = self.compute_per_agent_stats(metrics)
        per_benchmark = self.compute_per_benchmark_stats(metrics)
        
        # Task consistency analysis
        task_consistency = {}
        tasks_by_name = defaultdict(list)
        for m in metrics:
            tasks_by_name[m.task_id].append(m.success)
        
        for task_id, outcomes in tasks_by_name.items():
            if len(outcomes) > 1:
                success_rate = sum(outcomes) / len(outcomes) * 100
                is_consistent = success_rate in (0, 100)
                task_consistency[task_id] = {
                    'runs': len(outcomes),
                    'success_rate': success_rate,
                    'consistent': is_consistent,
                }
        
        return {
            'overall': overall_stats,
            'per_agent': per_agent,
            'per_benchmark': per_benchmark,
            'task_consistency': task_consistency,
            'total_metrics': len(metrics),
        }
    
    def write_report(self, report: Dict[str, Any], output_path: Path) -> None:
        """Write metrics report to file.
        
        Args:
            report: Report dictionary from generate_report
            output_path: Path to write JSON report
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Metrics report written to: {output_path}")
    
    def print_report(self, report: Dict[str, Any]) -> None:
        """Print metrics report to stdout in human-readable format.
        
        Args:
            report: Report dictionary from generate_report
        """
        print("=" * 100)
        print("EXECUTION METRICS REPORT")
        print("=" * 100)
        print()
        
        # Overall statistics
        overall = report['overall']
        print("OVERALL STATISTICS")
        print("-" * 100)
        print(f"Total Executions:    {overall['total']}")
        print(f"Successful:          {overall['successful']}")
        print(f"Success Rate:        {overall['success_rate']:.1f}%")
        print(f"Avg Duration:        {overall['avg_duration_sec']:.2f}s")
        print(f"Median Duration:     {overall['median_duration_sec']:.2f}s")
        print(f"Avg Patch Size:      {overall['avg_patch_size_bytes']} bytes")
        print(f"Avg Files Changed:   {overall['avg_files_changed']:.1f}")
        print(f"Avg Reward:          {overall['avg_reward']:.3f}")
        print()
        
        # Per-agent breakdown
        if report['per_agent']:
            print("PER-AGENT STATISTICS")
            print("-" * 100)
            print(f"{'Agent':<30} {'Success':<12} {'Avg Time':<12} {'Avg Reward':<12}")
            print("-" * 100)
            
            for agent, stats in sorted(report['per_agent'].items()):
                print(f"{agent:<30} {stats['success_rate']:<11.1f}% {stats['avg_duration_sec']:<11.2f}s {stats['avg_reward']:<11.3f}")
            print()
        
        # Per-benchmark breakdown
        if report['per_benchmark']:
            print("PER-BENCHMARK STATISTICS")
            print("-" * 100)
            print(f"{'Benchmark':<30} {'Success':<12} {'Avg Time':<12} {'Avg Reward':<12}")
            print("-" * 100)
            
            for benchmark, stats in sorted(report['per_benchmark'].items()):
                print(f"{benchmark:<30} {stats['success_rate']:<11.1f}% {stats['avg_duration_sec']:<11.2f}s {stats['avg_reward']:<11.3f}")
            print()
        
        # Error summary
        if overall['errors']:
            print("ERROR SUMMARY")
            print("-" * 100)
            print(f"{'Error Type':<50} {'Count':<20}")
            print("-" * 100)
            
            for error_type, count in sorted(overall['errors'].items(), key=lambda x: -x[1]):
                print(f"{error_type:<50} {count:<20}")
            print()
        
        # Task consistency issues
        inconsistent_tasks = {k: v for k, v in report['task_consistency'].items() if not v['consistent']}
        if inconsistent_tasks:
            print("INCONSISTENT TASKS (varied success across runs)")
            print("-" * 100)
            print(f"{'Task':<50} {'Success Rate':<20} {'Runs':<10}")
            print("-" * 100)
            
            for task_id, data in sorted(inconsistent_tasks.items(), key=lambda x: x[1]['success_rate']):
                print(f"{task_id:<50} {data['success_rate']:<19.1f}% {data['runs']:<10}")
            print()
        
        print("=" * 100)
