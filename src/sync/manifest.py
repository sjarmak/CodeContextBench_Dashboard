"""Sync manifest tracking what's been synced."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class SyncRecord:
    """Record of a single sync operation."""
    timestamp: str
    direction: str  # "push" or "pull"
    source: str
    destination: str
    files_synced: int
    bytes_synced: int
    status: str  # "success", "partial", "failed"
    error: Optional[str] = None


@dataclass
class SyncManifest:
    """Manifest tracking sync history and state."""
    last_push: Optional[str] = None
    last_pull: Optional[str] = None
    vm_host: str = ""
    vm_path: str = ""
    local_configs_path: str = ""
    local_results_path: str = ""
    history: list[SyncRecord] = field(default_factory=list)
    
    @classmethod
    def load(cls, path: Path) -> "SyncManifest":
        """Load manifest from file."""
        if not path.exists():
            return cls()
        
        with open(path) as f:
            data = json.load(f)
        
        history = [SyncRecord(**r) for r in data.pop("history", [])]
        return cls(**data, history=history)
    
    def save(self, path: Path) -> None:
        """Save manifest to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "last_push": self.last_push,
            "last_pull": self.last_pull,
            "vm_host": self.vm_host,
            "vm_path": self.vm_path,
            "local_configs_path": self.local_configs_path,
            "local_results_path": self.local_results_path,
            "history": [asdict(r) for r in self.history[-100:]],  # Keep last 100
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def record_sync(
        self,
        direction: str,
        source: str,
        destination: str,
        files_synced: int,
        bytes_synced: int,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Record a sync operation."""
        record = SyncRecord(
            timestamp=datetime.utcnow().isoformat(),
            direction=direction,
            source=source,
            destination=destination,
            files_synced=files_synced,
            bytes_synced=bytes_synced,
            status=status,
            error=error,
        )
        self.history.append(record)
        
        if direction == "push":
            self.last_push = record.timestamp
        else:
            self.last_pull = record.timestamp
