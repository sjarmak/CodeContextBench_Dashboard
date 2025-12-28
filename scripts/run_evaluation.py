#!/usr/bin/env python3
"""
CLI Evaluation Runner

Runs a single benchmark evaluation with selected agents and tasks.
Usage:
    python scripts/run_evaluation.py --run-id <run_id>
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.benchmark.run_orchestrator import get_orchestrator
from src.benchmark.database import RunManager

def main():
    parser = argparse.ArgumentParser(description="Run a benchmark evaluation")
    parser.add_argument("--run-id", required=True, help="Run ID to execute")
    parser.add_argument("--force-build", action="store_true", help="Force rebuild of Docker environment")
    args = parser.parse_args()

    print(f"Starting evaluation for Run ID: {args.run_id}")
    
    try:
        # Mark run as running immediately in DB
        RunManager.update_status(args.run_id, "running")
        
        # We define a simple callback to show progress in terminal
        def progress_callback(completed, total, task_name, agent):
            print(f"[{completed}/{total}] Completed task: {task_name} with agent: {agent}")

        orchestrator = get_orchestrator(args.run_id)
        
        # If force-build is requested, pass it through to the orchestrator logic
        # We store it in run_data for now so _run_evaluation can pick it up
        if args.force_build:
            orchestrator.run_data["force_build"] = True

        # The _run_evaluation method handles the loop
        orchestrator._run_evaluation(progress_callback=progress_callback)
        
        # Final check
        run_data = RunManager.get(args.run_id)
        print(f"Evaluation finished. Final status: {run_data['status']}")
        return 0

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        # Ensure failure is recorded
        RunManager.update_status(args.run_id, "failed", error=str(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
