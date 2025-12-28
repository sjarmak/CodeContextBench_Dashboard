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

# MONKEYPATCH: Force Harbor to use a fixed registry URL globally
# This bypasses the broken remote registry even if Harbor ignores CLI flags
try:
    import harbor.registry.client
    FIXED_URL = "https://gist.githubusercontent.com/sjarmak/005160332f794266ae71c7b815cbef4a/raw/68bc000df990cf069007606603de599c8923fd13/registry.json"
    harbor.registry.client.RegistryClient.DEFAULT_REGISTRY_URL = FIXED_URL
    print(f"DEBUG: Harbor Registry monkeypatched to {FIXED_URL}")
except ImportError:
    pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.benchmark.run_orchestrator import get_orchestrator
from src.benchmark.database import RunManager

def main():
    parser = argparse.ArgumentParser(description="Run a benchmark evaluation")
    parser.add_argument("--run-id", required=True, help="Run ID to execute")
    parser.add_argument("--force-build", action="store_true", help="Force rebuild of Docker environment")
    args = parser.parse_args()

    print(f"Starting evaluation for Run ID: {args.run_id}", flush=True)
    
    try:
        # Mark run as running immediately in DB
        RunManager.update_status(args.run_id, "running")
        
        # We define a simple callback to show progress in terminal
        def progress_callback(completed, total, task_name, agent):
            print(f"[{completed}/{total}] Completed task: {task_name} with agent: {agent}", flush=True)

        orchestrator = get_orchestrator(args.run_id)
        
        # If force-build is requested, pass it through to the orchestrator logic
        # We store it in run_data for now so _run_evaluation can pick it up
        if args.force_build:
            orchestrator.run_data["force_build"] = True

        # The _run_evaluation method handles the loop
        orchestrator._run_evaluation(progress_callback=progress_callback)
        
        # Final check
        run_data = RunManager.get(args.run_id)
        print(f"Evaluation finished. Final status: {run_data['status']}", flush=True)
        return 0

    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user.", flush=True)
        RunManager.update_status(args.run_id, "stopped")
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Ensure failure is recorded
        RunManager.update_status(args.run_id, "failed", error=str(e))
        return 1

if __name__ == "__main__":
    sys.exit(main())
