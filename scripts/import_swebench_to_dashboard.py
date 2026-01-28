#!/usr/bin/env python3
"""
Import SWEBench evaluation results into the dashboard database.

This script:
1. Reads SWEBench evaluation results from external directories
2. Creates benchmark and run entries in the dashboard database
3. Creates task entries with metrics
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import init_database, BenchmarkRegistry, RunManager, TaskManager
from ingest.swebench_parser import SWEBenchParser


def parse_jsonl_transcript(transcript_path: Path) -> dict:
    """Parse JSONL transcript and extract tool usage metrics."""
    metrics = {
        "total_messages": 0,
        "assistant_messages": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cache_read_tokens": 0,
        "tool_calls": {},
    }
    
    if not transcript_path.exists():
        return metrics
    
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            metrics["total_messages"] += 1
            msg_type = record.get("type")
            
            if msg_type == "assistant":
                metrics["assistant_messages"] += 1
                message = record.get("message", {})
                
                # Extract token usage
                usage = message.get("usage", {})
                metrics["total_input_tokens"] += usage.get("input_tokens", 0)
                metrics["total_output_tokens"] += usage.get("output_tokens", 0)
                metrics["total_cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                
                # Extract tool calls
                content = message.get("content", [])
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_name = item.get("name", "unknown")
                        metrics["tool_calls"][tool_name] = metrics["tool_calls"].get(tool_name, 0) + 1
    
    return metrics


def import_swebench_results(evals_base: Path, dry_run: bool = False):
    """Import SWEBench results into dashboard database."""
    
    # Initialize database
    init_database()
    
    print(f"Scanning for evaluations in: {evals_base}")
    
    parser = SWEBenchParser()
    imported_count = 0
    
    # Find all job directories
    for job_dir in evals_base.iterdir():
        if not job_dir.is_dir() or job_dir.name.startswith("."):
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing job: {job_dir.name}")
        print(f"{'='*60}")
        
        # Determine MCP type from job name
        mcp_type = "deepsearch" if "deepsearch" in job_dir.name.lower() else "none"
        
        # Get or create benchmark entry
        benchmark_name = f"SWEBenchPro ({mcp_type})"
        benchmark = BenchmarkRegistry.get_by_name(benchmark_name)
        
        if not benchmark:
            print(f"  Creating benchmark: {benchmark_name}")
            if not dry_run:
                BenchmarkRegistry.add(
                    name=benchmark_name,
                    folder_name=job_dir.name,
                    adapter_type="swebench",
                    description=f"SWEBench Pro evaluation with MCP: {mcp_type}"
                )
                benchmark = BenchmarkRegistry.get_by_name(benchmark_name)
        
        # Create run entry
        run_id = f"swebench_{job_dir.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Process instances within job
        instances = []
        for item in job_dir.iterdir():
            if item.is_dir() and item.name.startswith("instance_"):
                instances.append(item)
        
        if not instances:
            print(f"  No instances found in {job_dir}")
            continue
        
        print(f"  Found {len(instances)} instances")
        
        # Create run
        if not dry_run and benchmark:
            RunManager.create(
                run_id=run_id,
                benchmark_id=benchmark["id"],
                run_type="evaluation",
                agents=["claude-code"],
                task_selection=None,
                concurrency=1,
                config={
                    "mcp_type": mcp_type,
                    "source": "swebench_vm_import",
                    "original_job": job_dir.name,
                },
                output_dir=str(job_dir)
            )
            RunManager.update_status(run_id, "completed")
        
        # Process each instance
        for instance_dir in instances:
            print(f"\n  Processing: {instance_dir.name}")
            
            try:
                swebench_result = parser.parse_instance_dir(instance_dir)
                harbor_result = swebench_result.harbor_result
                
                # Parse transcript for additional metrics
                transcript_path = instance_dir / "agent" / "claude-code.txt"
                transcript_metrics = parse_jsonl_transcript(transcript_path)
                
                # Calculate total tokens
                total_tokens = (
                    transcript_metrics["total_input_tokens"] + 
                    transcript_metrics["total_output_tokens"]
                )
                
                task_name = harbor_result.task_id
                agent_name = harbor_result.agent_name
                
                print(f"    Task: {task_name}")
                print(f"    Reward: {harbor_result.verifier_result.reward}")
                print(f"    MCP: {swebench_result.mcp_enabled}")
                print(f"    Tokens: {total_tokens:,}")
                
                if not dry_run:
                    # Create task entry
                    TaskManager.create(run_id, task_name, agent_name)
                    
                    # Update with results including tokens and execution time
                    TaskManager.update_status(
                        run_id=run_id,
                        task_name=task_name,
                        agent_name=agent_name,
                        status="completed",
                        reward=harbor_result.verifier_result.reward.get("reward", 0.0),
                        result_path=str(instance_dir / "result.json"),
                        trajectory_path=str(transcript_path),
                        total_tokens=total_tokens,
                        execution_time=swebench_result.agent_execution_duration,
                    )
                
                imported_count += 1
                
            except Exception as e:
                print(f"    ERROR: {e}")
                if not dry_run:
                    TaskManager.create(run_id, instance_dir.name, "claude-code")
                    TaskManager.update_status(
                        run_id=run_id,
                        task_name=instance_dir.name,
                        agent_name="claude-code",
                        status="failed",
                        error_message=str(e)
                    )
    
    print(f"\n{'='*60}")
    print(f"Import complete: {imported_count} tasks imported")
    if dry_run:
        print("(DRY RUN - no changes made)")
    print(f"{'='*60}")
    
    return imported_count


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Import SWEBench results to dashboard")
    parser.add_argument(
        "--evals-dir",
        type=Path,
        default=Path.home() / "evals" / "custom_agents" / "agents" / "claudecode" / "runs",
        help="Path to SWEBench evaluation results"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes"
    )
    
    args = parser.parse_args()
    
    if not args.evals_dir.exists():
        print(f"ERROR: Directory not found: {args.evals_dir}")
        return 1
    
    import_swebench_results(args.evals_dir, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
