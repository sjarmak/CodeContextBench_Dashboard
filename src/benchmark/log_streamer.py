"""
Log Streamer

Simple log tailing for monitoring evaluation runs.
"""

from pathlib import Path
from typing import Optional, List
import time


class LogStreamer:
    """Stream logs from a file."""

    def __init__(self, log_file: Path):
        """
        Initialize log streamer.

        Args:
            log_file: Path to log file
        """
        self.log_file = log_file
        self.position = 0

    def get_new_lines(self) -> List[str]:
        """
        Get new lines since last read.

        Returns:
            List of new log lines
        """
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.position)
                lines = f.readlines()
                self.position = f.tell()
                return lines
        except Exception:
            return []

    def get_all_lines(self) -> List[str]:
        """
        Get all lines from the log file.

        Returns:
            List of all log lines
        """
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, 'r') as f:
                return f.readlines()
        except Exception:
            return []

    def tail(self, num_lines: int = 100) -> List[str]:
        """
        Get last N lines from log file.

        Args:
            num_lines: Number of lines to return

        Returns:
            Last N lines
        """
        all_lines = self.get_all_lines()
        return all_lines[-num_lines:] if all_lines else []


def get_run_logs(run_id: str, job_dir: Optional[Path] = None) -> List[str]:
    """
    Get logs for a run.

    Args:
        run_id: Run identifier
        job_dir: Optional job directory path

    Returns:
        List of log lines
    """
    if job_dir is None:
        job_dir = Path(f"runs/{run_id}")

    if not job_dir.exists():
        return ["No logs directory found"]

    # Look for log files
    log_files = list(job_dir.rglob("*.log"))

    if not log_files:
        return ["No log files found"]

    # Combine all logs
    all_logs = []
    for log_file in sorted(log_files):
        all_logs.append(f"\n=== {log_file.name} ===\n")
        streamer = LogStreamer(log_file)
        all_logs.extend(streamer.get_all_lines())

    return all_logs
