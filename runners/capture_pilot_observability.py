#!/usr/bin/env python3
"""Capture observability metrics from baseline and MCP pilot runs.

Usage:
    python runners/capture_pilot_observability.py --baseline jobs/harbor-baseline-full
    python runners/capture_pilot_observability.py --mcp jobs/harbor-mcp-final
    python runners/capture_pilot_observability.py --all
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from observability import ManifestWriter, ClaudeOutputParser


def process_pilot_run(job_dir: Path, pilot_name: str) -> Dict[str, Any]:
    """Process a single pilot job directory and capture observability metrics.
    
    Args:
        job_dir: Path to Harbor job results directory
        pilot_name: Name of the pilot (e.g., "baseline-001", "mcp-001")
        
    Returns:
        Aggregate observability report
    """
    
    # Find all task directories
    task_dirs = sorted(job_dir.glob('sgt-*_*'))
    
    if not task_dirs:
        print(f"No task directories found in {job_dir}")
        return {
            'pilot': pilot_name,
            'job_dir': str(job_dir),
            'tasks_processed': 0,
            'metrics': {},
        }
    
    aggregate = {
        'pilot': pilot_name,
        'job_dir': str(job_dir),
        'tasks_processed': len(task_dirs),
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'total_cost_usd': 0.0,
        'tasks': [],
    }
    
    for task_dir in task_dirs:
        task_name = task_dir.name
        
        try:
            # Extract token usage from Claude logs
            token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)
            input_tokens = token_usage.input_tokens
            output_tokens = token_usage.output_tokens
            
            # Write manifest
            writer = ManifestWriter(task_dir, model='claude-haiku-4-5')
            manifest_path = writer.write_manifest(
                harness_name='harbor-v1',
                agent_name=pilot_name.split('-')[0],  # baseline or mcp
                benchmark_name='github_mined',
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            
            # Calculate cost
            cost_usd = writer.calculate_cost(input_tokens, output_tokens)
            
            # Check reward
            reward_file = task_dir / 'reward.txt'
            reward = 0.0
            if reward_file.exists():
                try:
                    reward = float(reward_file.read_text().strip())
                except:
                    pass
            
            task_record = {
                'task': task_name,
                'manifest': str(manifest_path),
                'reward': reward,
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'total': input_tokens + output_tokens,
                },
                'cost_usd': cost_usd,
            }
            
            aggregate['tasks'].append(task_record)
            aggregate['total_input_tokens'] += input_tokens
            aggregate['total_output_tokens'] += output_tokens
            aggregate['total_cost_usd'] += cost_usd
            
            print(f"  {task_name}: {input_tokens + output_tokens} tokens, reward={reward}, cost=${cost_usd:.6f}")
            
        except Exception as e:
            print(f"  {task_name}: ERROR - {e}")
            continue
    
    return aggregate


def main():
    parser = argparse.ArgumentParser(
        description='Capture observability metrics from pilot runs'
    )
    parser.add_argument(
        '--baseline',
        type=Path,
        help='Baseline job directory (e.g., jobs/harbor-baseline-full)'
    )
    parser.add_argument(
        '--mcp',
        type=Path,
        help='MCP job directory (e.g., jobs/harbor-mcp-final)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process both baseline and MCP if they exist'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('artifacts/pilot-observability.json'),
        help='Output file for combined report'
    )
    
    args = parser.parse_args()
    
    results = {}
    
    # Process baseline
    if args.baseline or args.all:
        baseline_dir = args.baseline or Path('jobs/harbor-baseline-full')
        if baseline_dir.exists():
            # Find latest run
            run_dirs = sorted(baseline_dir.glob('*'))[-1:]
            if run_dirs:
                print(f"\nProcessing baseline: {run_dirs[0]}")
                results['baseline'] = process_pilot_run(run_dirs[0], 'baseline')
    
    # Process MCP
    if args.mcp or args.all:
        mcp_dir = args.mcp or Path('jobs/harbor-mcp-final')
        if mcp_dir.exists():
            # Find latest run
            run_dirs = sorted(mcp_dir.glob('*'))[-1:]
            if run_dirs:
                print(f"\nProcessing MCP: {run_dirs[0]}")
                results['mcp'] = process_pilot_run(run_dirs[0], 'mcp')
    
    # Print summary
    print("\n" + "="*80)
    print("OBSERVABILITY SUMMARY")
    print("="*80)
    
    for pilot_name, data in results.items():
        print(f"\n{pilot_name.upper()}")
        print(f"  Tasks: {data['tasks_processed']}")
        print(f"  Total Tokens: {data['total_input_tokens'] + data['total_output_tokens']:,}")
        print(f"  Total Cost: ${data['total_cost_usd']:.6f}")
        
        rewards = [t['reward'] for t in data['tasks']]
        if rewards:
            success_count = sum(1 for r in rewards if r > 0)
            print(f"  Success Rate: {success_count}/{len(rewards)} ({100*success_count/len(rewards):.1f}%)")
    
    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to: {args.output}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
