"""Simple metrics collection from Harbor runs.

Replaces NeMo-Agent-Toolkit complexity. Collects:
- Execution time and status
- Patch statistics (files modified, lines changed)
- Test pass/fail results
- Tool usage (if available in logs)
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class ExecutionMetrics:
    """Metrics from a single agent run on a task."""
    
    agent_name: str
    task_id: str
    timestamp: str
    status: str  # "success", "failure", "timeout"
    elapsed_seconds: float
    patch_file: Optional[Path] = None
    patch_stats: Optional[Dict[str, Any]] = None
    test_passed: Optional[bool] = None
    test_output: Optional[str] = None
    error_message: Optional[str] = None
    tool_calls: int = 0
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self), default=str, indent=2)
    
    def save(self, output_path: Path) -> None:
        """Save metrics to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(self.to_json())


@dataclass
class PatchStatistics:
    """Statistics about a git diff patch."""
    
    files_modified: int
    files_created: int
    files_deleted: int
    lines_added: int
    lines_deleted: int
    lines_changed: int
    
    @classmethod
    def from_diff_stat(cls, stat_file: Path) -> "PatchStatistics":
        """Parse git diff --stat output.
        
        Args:
            stat_file: Path to patch.stat file from 'git diff --stat'
            
        Returns:
            PatchStatistics object
        """
        if not stat_file.exists():
            return cls(0, 0, 0, 0, 0, 0)
        
        files_modified = 0
        lines_added = 0
        lines_deleted = 0
        
        with open(stat_file, 'r') as f:
            for line in f:
                if ' | ' not in line:
                    continue
                
                parts = line.split('|')
                if len(parts) >= 2:
                    files_modified += 1
                    
                    # Extract +/- from right side
                    stat_part = parts[1].strip()
                    # Format: "123 +++++++++++" or "123 -----------" or "123 ++++------"
                    plus_count = stat_part.count('+')
                    minus_count = stat_part.count('-')
                    lines_added += plus_count
                    lines_deleted += minus_count
        
        return cls(
            files_modified=files_modified,
            files_created=0,  # Would need diff --name-status to get this
            files_deleted=0,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            lines_changed=lines_added + lines_deleted,
        )
    
    def to_dict(self) -> dict:
        return asdict(self)


def collect_metrics(
    agent_name: str,
    task_id: str,
    logs_dir: Path,
    status: str = "unknown",
    elapsed_seconds: float = 0.0,
) -> ExecutionMetrics:
    """Collect metrics from a completed Harbor run.
    
    Args:
        agent_name: Name of the agent (e.g., "claude-baseline")
        task_id: Task identifier
        logs_dir: Path to /logs/agent/ directory
        status: Execution status ("success", "failure", "timeout")
        elapsed_seconds: How long the task took
        
    Returns:
        ExecutionMetrics object with collected data
    """
    
    metrics = ExecutionMetrics(
        agent_name=agent_name,
        task_id=task_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        status=status,
        elapsed_seconds=elapsed_seconds,
    )
    
    # Try to load patch statistics
    patch_stat_file = logs_dir / "patch.stat"
    if patch_stat_file.exists():
        patch_stats = PatchStatistics.from_diff_stat(patch_stat_file)
        metrics.patch_stats = asdict(patch_stats)
    
    # Try to load patch file
    patch_file = logs_dir / "patch.diff"
    if patch_file.exists():
        metrics.patch_file = patch_file
    
    # Try to load test output
    test_output_file = logs_dir / "test_output.txt"
    if test_output_file.exists():
        with open(test_output_file, 'r') as f:
            metrics.test_output = f.read()
        # Simple heuristic: test passed if file contains "PASSED" or exit code was 0
        metrics.test_passed = "PASSED" in metrics.test_output or "passed" in metrics.test_output.lower()
    
    return metrics
