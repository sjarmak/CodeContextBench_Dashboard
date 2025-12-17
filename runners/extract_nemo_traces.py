#!/usr/bin/env python3
"""Batch extract NeMo-Agent-Toolkit traces and generate manifests.

This runner processes Harbor job directories, extracts NeMo execution traces,
and generates run_manifest.json files with structured metrics.

Usage:
    python runners/extract_nemo_traces.py --jobs-dir jobs/ --agent claude-baseline
    python runners/extract_nemo_traces.py --jobs-dir jobs/ --all
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from observability import (
    NeMoTraceParser,
    ManifestWriter,
    ClaudeOutputParser,
)


class NeMoTraceExtractor:
    """Extract and process NeMo traces from job directories."""
    
    def __init__(self, jobs_dir: Path):
        """Initialize extractor.
        
        Args:
            jobs_dir: Root directory containing Harbor job outputs
        """
        self.jobs_dir = Path(jobs_dir)
    
    def find_job_dirs(self, agent_filter: str = None) -> List[Path]:
        """Find all Harbor job directories.
        
        Args:
            agent_filter: Optional agent name to filter by (e.g., 'claude-baseline')
            
        Returns:
            List of job directory paths
        """
        job_dirs = []
        
        for item in self.jobs_dir.iterdir():
            if not item.is_dir():
                continue
            
            # Match Harbor job naming pattern: <agent>-<benchmark>-<date>
            if agent_filter:
                if not item.name.startswith(agent_filter):
                    continue
            
            # Check if it contains task subdirectories
            task_dirs = list(item.glob('task-*'))
            if task_dirs:
                job_dirs.append(item)
        
        return sorted(job_dirs)
    
    def process_job(
        self,
        job_dir: Path,
        harness_name: str = 'harbor-v1',
        model: str = 'claude-haiku-4-5'
    ) -> Dict[str, Any]:
        """Process a single Harbor job directory.
        
        Extracts NeMo traces or falls back to Claude output parsing.
        
        Args:
            job_dir: Path to job directory
            harness_name: Benchmark harness name
            model: Model name for cost calculation
            
        Returns:
            Summary of processed tasks
        """
        summary = {
            'job_dir': str(job_dir),
            'job_name': job_dir.name,
            'tasks_processed': 0,
            'traces_found': 0,
            'manifests_written': 0,
            'fallback_to_logs': 0,
            'errors': 0,
            'task_summaries': [],
        }
        
        # Find task directories
        task_dirs = sorted(job_dir.glob('task-*'))
        
        if not task_dirs:
            return summary
        
        # Parse agent and benchmark from job name
        # Expected format: <agent>-<benchmark>-<date>
        name_parts = job_dir.name.rsplit('-', 2)
        agent_name = name_parts[0] if len(name_parts) >= 2 else 'unknown'
        benchmark_name = name_parts[1] if len(name_parts) >= 2 else 'unknown'
        
        for task_dir in task_dirs:
            task_name = task_dir.name
            
            try:
                # Try to extract NeMo trace
                trace = NeMoTraceParser.extract_from_task_execution(task_dir)
                
                if trace:
                    summary['traces_found'] += 1
                    input_tokens = trace.total_input_tokens
                    output_tokens = trace.total_output_tokens
                else:
                    # Fallback: extract from Claude logs
                    summary['fallback_to_logs'] += 1
                    token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
                    input_tokens = token_usage.input_tokens
                    output_tokens = token_usage.output_tokens
                
                # Write manifest
                writer = ManifestWriter(task_dir, model=model)
                manifest_path = writer.write_manifest(
                    harness_name=harness_name,
                    agent_name=agent_name,
                    benchmark_name=benchmark_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    nemo_trace=trace
                )
                
                summary['manifests_written'] += 1
                summary['task_summaries'].append({
                    'task': task_name,
                    'manifest': str(manifest_path),
                    'has_nemo_trace': trace is not None,
                    'tokens': {
                        'input': input_tokens,
                        'output': output_tokens,
                        'total': input_tokens + output_tokens,
                    },
                    'cost_usd': writer.calculate_cost(input_tokens, output_tokens),
                })
                
            except Exception as e:
                summary['errors'] += 1
                summary['task_summaries'].append({
                    'task': task_name,
                    'error': str(e),
                })
                continue
        
        summary['tasks_processed'] = len(task_dirs)
        return summary
    
    def process_all_jobs(
        self,
        agent_filter: str = None,
        harness_name: str = 'harbor-v1',
        model: str = 'claude-haiku-4-5'
    ) -> Dict[str, Any]:
        """Process all Harbor jobs, optionally filtered by agent.
        
        Args:
            agent_filter: Optional agent name filter
            harness_name: Benchmark harness name
            model: Model name for cost calculation
            
        Returns:
            Aggregated summary across all jobs
        """
        job_dirs = self.find_job_dirs(agent_filter)
        
        if not job_dirs:
            print(f"No job directories found in {self.jobs_dir}")
            return {
                'timestamp': datetime.now().isoformat(),
                'jobs_processed': 0,
                'total_tasks': 0,
                'total_manifests_written': 0,
                'total_traces_found': 0,
                'total_cost_usd': 0.0,
                'job_summaries': [],
            }
        
        aggregate = {
            'timestamp': datetime.now().isoformat(),
            'jobs_dir': str(self.jobs_dir),
            'agent_filter': agent_filter,
            'jobs_processed': len(job_dirs),
            'total_tasks': 0,
            'total_manifests_written': 0,
            'total_traces_found': 0,
            'total_cost_usd': 0.0,
            'total_tokens': {'input': 0, 'output': 0},
            'job_summaries': [],
        }
        
        for job_dir in job_dirs:
            summary = self.process_job(job_dir, harness_name, model)
            aggregate['job_summaries'].append(summary)
            
            # Aggregate metrics
            aggregate['total_tasks'] += summary['tasks_processed']
            aggregate['total_manifests_written'] += summary['manifests_written']
            aggregate['total_traces_found'] += summary['traces_found']
            
            for task_summary in summary['task_summaries']:
                if 'tokens' in task_summary:
                    aggregate['total_tokens']['input'] += task_summary['tokens']['input']
                    aggregate['total_tokens']['output'] += task_summary['tokens']['output']
                    aggregate['total_cost_usd'] += task_summary['cost_usd']
        
        return aggregate
    
    def print_summary(self, aggregate: Dict[str, Any]) -> None:
        """Print human-readable summary.
        
        Args:
            aggregate: Aggregated summary from process_all_jobs
        """
        print("=" * 100)
        print("NeMo TRACE EXTRACTION SUMMARY")
        print("=" * 100)
        print()
        
        print(f"Timestamp:           {aggregate.get('timestamp', 'N/A')}")
        print(f"Jobs Directory:      {aggregate.get('jobs_dir', 'N/A')}")
        if aggregate.get('agent_filter'):
            print(f"Agent Filter:        {aggregate['agent_filter']}")
        print()
        
        print("AGGREGATE METRICS")
        print("-" * 100)
        print(f"Jobs Processed:      {aggregate['jobs_processed']}")
        print(f"Total Tasks:         {aggregate['total_tasks']}")
        print(f"Manifests Written:   {aggregate['total_manifests_written']}")
        print(f"NeMo Traces Found:   {aggregate['total_traces_found']}")
        print(f"Input Tokens:        {aggregate['total_tokens']['input']:,}")
        print(f"Output Tokens:       {aggregate['total_tokens']['output']:,}")
        print(f"Total Tokens:        {aggregate['total_tokens']['input'] + aggregate['total_tokens']['output']:,}")
        print(f"Total Cost (USD):    ${aggregate['total_cost_usd']:.6f}")
        print()
        
        # Per-job summary
        if aggregate['job_summaries']:
            print("PER-JOB SUMMARY")
            print("-" * 100)
            print(f"{'Job':<50} {'Tasks':<10} {'Manifests':<12} {'Traces':<10} {'Errors':<10}")
            print("-" * 100)
            
            for job in aggregate['job_summaries']:
                print(f"{job['job_name']:<50} {job['tasks_processed']:<10} {job['manifests_written']:<12} {job['traces_found']:<10} {job['errors']:<10}")
            print()
        
        print("=" * 100)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Extract NeMo traces and generate manifests from Harbor jobs'
    )
    parser.add_argument(
        '--jobs-dir',
        type=Path,
        default=Path('jobs'),
        help='Root directory containing Harbor job outputs (default: jobs/)'
    )
    parser.add_argument(
        '--agent',
        type=str,
        help='Filter by agent name (e.g., claude-baseline)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all jobs (default if no agent filter)'
    )
    parser.add_argument(
        '--harness',
        type=str,
        default='harbor-v1',
        help='Harness name for manifests (default: harbor-v1)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='claude-haiku-4-5',
        help='Model name for cost calculation (default: claude-haiku-4-5)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Write summary JSON to file'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    extractor = NeMoTraceExtractor(args.jobs_dir)
    
    # Determine what to process
    agent_filter = args.agent if args.agent else None
    
    # Process jobs
    aggregate = extractor.process_all_jobs(
        agent_filter=agent_filter,
        harness_name=args.harness,
        model=args.model
    )
    
    # Output results
    if args.json:
        print(json.dumps(aggregate, indent=2))
    else:
        extractor.print_summary(aggregate)
    
    # Write to file if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(aggregate, f, indent=2)
        print(f"\nSummary written to: {args.output}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
