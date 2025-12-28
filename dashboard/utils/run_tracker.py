"""
Persistent run tracker for background processes.

Stores information about running profile/benchmark jobs so they can be
monitored across dashboard sessions.
"""
import json
import psutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


class RunTracker:
    """Track background runs persistently."""

    def __init__(self, tracker_dir: Path = None):
        """Initialize tracker with a directory for storing run metadata."""
        if tracker_dir is None:
            tracker_dir = Path.cwd() / ".dashboard_runs"

        self.tracker_dir = Path(tracker_dir)
        self.tracker_dir.mkdir(exist_ok=True, parents=True)

    def register_run(
        self,
        run_id: str,
        run_type: str,  # "profile", "trial", "benchmark"
        pid: int,
        command: str,
        profile_name: str = None,
        benchmark_name: str = None,
        agent_name: str = None,
        **kwargs
    ) -> Dict:
        """Register a new background run."""
        run_info = {
            "run_id": run_id,
            "run_type": run_type,
            "pid": pid,
            "command": command,
            "profile_name": profile_name,
            "benchmark_name": benchmark_name,
            "agent_name": agent_name,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "output_file": str(self.tracker_dir / f"{run_id}.log"),
            **kwargs
        }

        # Write to tracker file
        tracker_file = self.tracker_dir / f"{run_id}.json"
        with open(tracker_file, "w") as f:
            json.dump(run_info, f, indent=2)

        return run_info

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get information about a specific run."""
        tracker_file = self.tracker_dir / f"{run_id}.json"

        if not tracker_file.exists():
            return None

        with open(tracker_file) as f:
            run_info = json.load(f)

        # Update status based on process
        run_info["status"] = self._check_process_status(run_info["pid"])

        return run_info

    def list_runs(self, status: str = None) -> List[Dict]:
        """List all tracked runs, optionally filtered by status."""
        runs = []

        for tracker_file in self.tracker_dir.glob("*.json"):
            try:
                with open(tracker_file) as f:
                    run_info = json.load(f)

                # Update status
                run_info["status"] = self._check_process_status(run_info["pid"])

                # Filter by status if specified
                if status is None or run_info["status"] == status:
                    runs.append(run_info)

            except Exception as e:
                print(f"Error reading {tracker_file}: {e}")

        # Sort by start time (newest first)
        runs.sort(key=lambda x: x.get("start_time", ""), reverse=True)

        return runs

    def update_run(self, run_id: str, **updates):
        """Update run metadata."""
        tracker_file = self.tracker_dir / f"{run_id}.json"

        if not tracker_file.exists():
            return False

        with open(tracker_file) as f:
            run_info = json.load(f)

        run_info.update(updates)

        with open(tracker_file, "w") as f:
            json.dump(run_info, f, indent=2)

        return True

    def remove_run(self, run_id: str):
        """Remove a run from tracking."""
        tracker_file = self.tracker_dir / f"{run_id}.json"
        log_file = self.tracker_dir / f"{run_id}.log"

        if tracker_file.exists():
            tracker_file.unlink()

        if log_file.exists():
            log_file.unlink()

    def cleanup_completed(self, keep_recent: int = 10):
        """Remove completed runs, keeping only the most recent N."""
        completed_runs = self.list_runs(status="completed")

        # Keep only the most recent N
        for run in completed_runs[keep_recent:]:
            self.remove_run(run["run_id"])

    def _check_process_status(self, pid: int) -> str:
        """Check if a process is still running."""
        try:
            process = psutil.Process(pid)
            if process.is_running():
                return "running"
            else:
                return "completed"
        except psutil.NoSuchProcess:
            return "completed"
        except psutil.AccessDenied:
            return "unknown"

    def get_process_output(self, run_id: str, tail_lines: int = 100) -> str:
        """Get output from a running process."""
        log_file = self.tracker_dir / f"{run_id}.log"

        if not log_file.exists():
            return ""

        try:
            with open(log_file) as f:
                lines = f.readlines()

            # Return last N lines
            if tail_lines and len(lines) > tail_lines:
                return "".join(lines[-tail_lines:])
            else:
                return "".join(lines)

        except Exception as e:
            return f"Error reading log: {e}"

    def terminate_run(self, run_id: str) -> bool:
        """Terminate a running process."""
        run_info = self.get_run(run_id)

        if not run_info or run_info["status"] != "running":
            return False

        try:
            process = psutil.Process(run_info["pid"])
            process.terminate()
            self.update_run(run_id, status="terminated")
            return True
        except Exception as e:
            print(f"Error terminating process: {e}")
            return False
