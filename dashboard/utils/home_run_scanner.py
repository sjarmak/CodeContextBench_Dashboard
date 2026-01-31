"""
Home page run scanner - scans runs directory for grouped display.

Scans official/, experiment/, troubleshooting/ subdirectories plus
root-level legacy runs and returns RunSummary objects grouped by folder.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FOLDER_ORDER = ("official", "experiment", "troubleshooting", "uncategorized")

FOLDER_DESCRIPTIONS = {
    "official": "Production benchmark runs with pinned agent configurations",
    "experiment": "Comparing variants of agent profiles across benchmark tasks",
    "troubleshooting": "Debugging run issues",
    "uncategorized": "Legacy root-level runs",
}


@dataclass(frozen=True)
class RunSummary:
    """Summary of a single benchmark run for home page display."""

    name: str
    path: Path
    folder: str
    modes: tuple[str, ...]
    task_count: int
    agent_import_path: str
    model_name: str
    timestamp: str
    is_paired: bool


def _extract_agent_details(run_path: Path, modes: tuple[str, ...]) -> tuple[str, str]:
    """Extract agent import_path and model_name from the first task config.json."""
    for mode in modes:
        mode_dir = run_path / mode
        if not mode_dir.is_dir():
            continue
        for task_dir in sorted(mode_dir.iterdir()):
            config_path = task_dir / "config.json"
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                    agents = config.get("agents", [])
                    if agents:
                        first_agent = agents[0]
                        return (
                            first_agent.get("import_path", "unknown"),
                            first_agent.get("model_name", "unknown"),
                        )
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    logger.debug(f"Failed to parse {config_path}: {e}")
    return ("unknown", "unknown")


def _extract_timestamp(run_name: str, run_path: Path) -> str:
    """Extract timestamp from run directory name or fall back to mtime."""
    import re

    # Pattern: digits at end like _20260131_130446 or _2026-01-29_f334cd
    match = re.search(r'(\d{8}_\d{6})$', run_name)
    if match:
        raw = match.group(1)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[9:11]}:{raw[11:13]}:{raw[13:15]}"

    match = re.search(r'(\d{4}-\d{2}-\d{2})_', run_name)
    if match:
        return match.group(1)

    # Fall back to mtime
    try:
        from datetime import datetime
        mtime = run_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "unknown"


def _scan_single_run(run_path: Path, folder: str) -> Optional[RunSummary]:
    """Scan a single run directory and return a RunSummary."""
    if not run_path.is_dir() or run_path.name.startswith('.'):
        return None

    # Detect modes (subdirectories like baseline, deepsearch)
    modes = tuple(
        d.name for d in sorted(run_path.iterdir())
        if d.is_dir() and not d.name.startswith('.')
    )

    if not modes:
        return None

    # Count tasks across all modes
    task_count = 0
    for mode in modes:
        mode_dir = run_path / mode
        if mode_dir.is_dir():
            task_count += sum(
                1 for d in mode_dir.iterdir()
                if d.is_dir() and not d.name.startswith('.')
            )

    agent_import_path, model_name = _extract_agent_details(run_path, modes)
    timestamp = _extract_timestamp(run_path.name, run_path)

    return RunSummary(
        name=run_path.name,
        path=run_path,
        folder=folder,
        modes=modes,
        task_count=task_count,
        agent_import_path=agent_import_path,
        model_name=model_name,
        timestamp=timestamp,
        is_paired=len(modes) >= 2,
    )


def scan_runs_by_folder(runs_dir: Path) -> dict[str, list[RunSummary]]:
    """
    Scan runs directory and return runs grouped by folder.

    Checks official/, experiment/, troubleshooting/ subdirectories,
    then treats remaining root-level directories as uncategorized.

    Args:
        runs_dir: Path to the runs directory.

    Returns:
        Dict mapping folder name to list of RunSummary, sorted by timestamp desc.
    """
    result: dict[str, list[RunSummary]] = {f: [] for f in FOLDER_ORDER}

    if not runs_dir.exists():
        return result

    known_subdirs = {"official", "experiment", "troubleshooting"}

    for subdir_name in known_subdirs:
        subdir = runs_dir / subdir_name
        if not subdir.is_dir():
            continue
        for run_path in subdir.iterdir():
            summary = _scan_single_run(run_path, subdir_name)
            if summary is not None:
                result[subdir_name].append(summary)

    # Root-level legacy runs
    for run_path in runs_dir.iterdir():
        if run_path.name in known_subdirs or run_path.name.startswith('.'):
            continue
        summary = _scan_single_run(run_path, "uncategorized")
        if summary is not None:
            result["uncategorized"].append(summary)

    # Sort each group by timestamp descending
    for folder in result:
        result[folder] = sorted(result[folder], key=lambda r: r.timestamp, reverse=True)

    return result
