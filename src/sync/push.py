"""Push configurations to VM."""
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .manifest import SyncManifest


@dataclass
class PushResult:
    """Result of a push operation."""
    success: bool
    files_synced: int
    bytes_synced: int
    error: Optional[str] = None
    details: str = ""


def push_configs(
    local_configs_dir: Path,
    vm_host: str,
    vm_path: str,
    manifest: Optional[SyncManifest] = None,
    dry_run: bool = False,
) -> PushResult:
    """
    Push local configurations to VM using rsync.
    
    Args:
        local_configs_dir: Local directory with translated configs
        vm_host: VM hostname or SSH destination (e.g., "user@host")
        vm_path: Remote path on VM (e.g., "~/evals/configs")
        manifest: Optional manifest to record sync
        dry_run: If True, show what would be synced without syncing
        
    Returns:
        PushResult with sync status
    """
    if not local_configs_dir.exists():
        return PushResult(
            success=False,
            files_synced=0,
            bytes_synced=0,
            error=f"Local configs directory not found: {local_configs_dir}",
        )
    
    # Build rsync command
    cmd = [
        "rsync",
        "-avz",
        "--progress",
        "--delete",  # Remove files on remote that don't exist locally
    ]
    
    if dry_run:
        cmd.append("--dry-run")
    
    # Add source and destination
    source = str(local_configs_dir) + "/"
    destination = f"{vm_host}:{vm_path}"
    cmd.extend([source, destination])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return PushResult(
                success=False,
                files_synced=0,
                bytes_synced=0,
                error=result.stderr,
                details=result.stdout,
            )
        
        # Parse rsync output for stats
        files_synced, bytes_synced = _parse_rsync_output(result.stdout)
        
        push_result = PushResult(
            success=True,
            files_synced=files_synced,
            bytes_synced=bytes_synced,
            details=result.stdout,
        )
        
        # Record in manifest
        if manifest and not dry_run:
            manifest.record_sync(
                direction="push",
                source=str(local_configs_dir),
                destination=destination,
                files_synced=files_synced,
                bytes_synced=bytes_synced,
                status="success",
            )
        
        return push_result
        
    except subprocess.TimeoutExpired:
        return PushResult(
            success=False,
            files_synced=0,
            bytes_synced=0,
            error="Sync timed out after 5 minutes",
        )
    except Exception as e:
        return PushResult(
            success=False,
            files_synced=0,
            bytes_synced=0,
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
                # Parse "total size is X  speedup is Y"
                parts = line.split("is")
                if len(parts) >= 2:
                    size_str = parts[1].strip().split()[0].replace(",", "")
                    bytes_transferred = int(size_str)
            except (IndexError, ValueError):
                pass
    
    return files, bytes_transferred
