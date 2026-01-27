"""
Utility for detecting the benchmark set name from a run directory.

Derives the benchmark set name (LoCoBench, SWE-Bench Pro, etc.) from
a run's manifest.json config.benchmarks field, or falls back to
directory name pattern matching.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Mapping from manifest benchmark IDs to display names
BENCHMARK_ID_TO_NAME = {
    "locobench_agent": "LoCoBench",
    "locobench": "LoCoBench",
    "swebench_pro": "SWE-Bench Pro",
    "swebench-pro": "SWE-Bench Pro",
    "swebench_verified": "SWE-Bench Verified",
    "swebench-verified": "SWE-Bench Verified",
    "repoqa": "RepoQA",
    "dibench": "DIBench",
}

# Patterns for directory name matching (prefix -> display name)
DIRECTORY_PATTERNS = [
    (re.compile(r"^locobench", re.IGNORECASE), "LoCoBench"),
    (re.compile(r"^swebenchpro", re.IGNORECASE), "SWE-Bench Pro"),
    (re.compile(r"^swebench_pro", re.IGNORECASE), "SWE-Bench Pro"),
    (re.compile(r"^swebench[-_]?verified", re.IGNORECASE), "SWE-Bench Verified"),
    (re.compile(r"^repoqa", re.IGNORECASE), "RepoQA"),
    (re.compile(r"^dibench", re.IGNORECASE), "DIBench"),
]

UNKNOWN_BENCHMARK = "Unknown"


def detect_benchmark_set(run_dir: str | Path) -> str:
    """
    Detect the benchmark set name from a run directory.

    Detection strategy:
    1. Check manifest.json config.benchmarks field
    2. Fall back to directory name pattern matching

    Args:
        run_dir: Path to the run directory (str or Path)

    Returns:
        Display name of the benchmark set, or 'Unknown' if unrecognized
    """
    run_path = Path(run_dir)

    name = _detect_from_manifest(run_path)
    if name is not None:
        return name

    return _detect_from_directory_name(run_path.name)


def _detect_from_manifest(run_path: Path) -> Optional[str]:
    """
    Attempt to detect benchmark set from manifest.json.

    Looks for config.benchmarks array in manifest.json and maps
    the first recognized benchmark ID to a display name.

    Args:
        run_path: Path to the run directory

    Returns:
        Display name if found, None otherwise
    """
    manifest_path = run_path / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        benchmarks = manifest.get("config", {}).get("benchmarks", [])
        for benchmark_id in benchmarks:
            normalized = benchmark_id.lower().strip()
            if normalized in BENCHMARK_ID_TO_NAME:
                return BENCHMARK_ID_TO_NAME[normalized]

        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse manifest at {manifest_path}: {e}")
        return None


def _detect_from_directory_name(dir_name: str) -> str:
    """
    Detect benchmark set from directory name pattern.

    Matches directory name prefixes against known benchmark patterns.

    Args:
        dir_name: Name of the run directory (not full path)

    Returns:
        Display name if pattern matches, 'Unknown' otherwise
    """
    for pattern, name in DIRECTORY_PATTERNS:
        if pattern.search(dir_name):
            return name

    return UNKNOWN_BENCHMARK
