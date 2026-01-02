"""Pull results from VM."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .manifest import SyncManifest


@dataclass
class PullResult:
    """Result of a pull operation."""
    success: bool
    files_synced: int
    bytes_synced: int
    experiments_found: list[str]
    error: Optional[str] = None
    details: str = ""


def pull_results(
    vm_host: str,
    vm_jobs_path: str,
    local_results_dir: Path,
    experiment_id: Optional[str] = None,
    manifest: Optional[SyncManifest] = None,
    dry_run: bool = False,
    exclude_patterns: Optional[list[str]] = None,
) -> PullResult:
    """
    Pull job results from VM using rsync.
    
    Args:
        vm_host: VM hostname or SSH destination
        vm_jobs_path: Remote jobs directory (e.g., "~/evals/custom_agents/agents/claudecode/jobs")
        local_results_dir: Local directory to store results
        experiment_id: Optional specific experiment to pull (pulls all if None)
        manifest: Optional manifest to record sync
        dry_run: If True, show what would be synced
        exclude_patterns: Patterns to exclude (e.g., ["**/-testbed/**"])
        
    Returns:
        PullResult with sync status
    """
    local_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Default exclusions for large/unnecessary files
    if exclude_patterns is None:
        exclude_patterns = [
            "**/-testbed/**",
            "**/agent/sessions/**",
            "**/*.tar.gz",
            "**/*.tar",
        ]
    
    # Build rsync command
    cmd = [
        "rsync",
        "-avz",
        "--progress",
    ]
    
    # Add exclusions
    for pattern in exclude_patterns:
        cmd.extend(["--exclude", pattern])
    
    if dry_run:
        cmd.append("--dry-run")
    
    # Build source path
    if experiment_id:
        source = f"{vm_host}:{vm_jobs_path}/{experiment_id}/"
        local_dest = local_results_dir / experiment_id
        local_dest.mkdir(parents=True, exist_ok=True)
        destination = str(local_dest) + "/"
    else:
        source = f"{vm_host}:{vm_jobs_path}/"
        destination = str(local_results_dir) + "/"
    
    cmd.extend([source, destination])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for potentially large syncs
        )
        
        if result.returncode != 0:
            return PullResult(
                success=False,
                files_synced=0,
                bytes_synced=0,
                experiments_found=[],
                error=result.stderr,
                details=result.stdout,
            )
        
        # Parse rsync output
        files_synced, bytes_synced = _parse_rsync_output(result.stdout)
        
        # Find experiments in results
        experiments = _find_experiments(local_results_dir)
        
        pull_result = PullResult(
            success=True,
            files_synced=files_synced,
            bytes_synced=bytes_synced,
            experiments_found=experiments,
            details=result.stdout,
        )
        
        # Record in manifest
        if manifest and not dry_run:
            manifest.record_sync(
                direction="pull",
                source=source,
                destination=str(local_results_dir),
                files_synced=files_synced,
                bytes_synced=bytes_synced,
                status="success",
            )
        
        return pull_result
        
    except subprocess.TimeoutExpired:
        return PullResult(
            success=False,
            files_synced=0,
            bytes_synced=0,
            experiments_found=[],
            error="Sync timed out after 10 minutes",
        )
    except Exception as e:
        return PullResult(
            success=False,
            files_synced=0,
            bytes_synced=0,
            experiments_found=[],
            error=str(e),
        )


def _parse_rsync_output(output: str) -> tuple[int, int]:
    """Parse rsync output to extract file count and bytes."""
    files = 0
    bytes_transferred = 0
    
    for line in output.split("\n"):
        if "files transferred" in line.lower():
            try:
                files = int(line.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
        elif "total size" in line.lower():
            try:
                parts = line.split("is")
                if len(parts) >= 2:
                    size_str = parts[1].strip().split()[0].replace(",", "")
                    bytes_transferred = int(size_str)
            except (IndexError, ValueError):
                pass
    
    return files, bytes_transferred


def _find_experiments(results_dir: Path) -> list[str]:
    """Find experiment directories in results."""
    experiments = []
    
    if not results_dir.exists():
        return experiments
    
    for item in results_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            # Check if it looks like an experiment directory
            # (has subdirectories that look like job outputs)
            experiments.append(item.name)
    
    return sorted(experiments)
