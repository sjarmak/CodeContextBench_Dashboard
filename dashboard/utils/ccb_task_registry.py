"""
CCB (CodeContextBench) task registry loader.

Loads enriched task metadata from the selected benchmark tasks JSON file,
providing SDLC phase, category, difficulty, language, MCP benefit score,
and repository information for each task.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

# Default path to the selected benchmark tasks registry
_DEFAULT_REGISTRY_PATH = Path(__file__).parent.parent.parent / "data" / "selected_benchmark_tasks.json"


@dataclass(frozen=True)
class CCBTaskMetadata:
    """Metadata for a single CCB benchmark task."""

    task_id: str
    benchmark: str
    sdlc_phase: str
    language: str
    category: str
    difficulty: str
    mcp_benefit_score: float
    repo: str


@st.cache_data
def load_ccb_task_registry(
    registry_path: Optional[str] = None,
) -> dict[str, CCBTaskMetadata]:
    """
    Load the CCB task registry from a JSON file.

    The JSON file is expected to be an array of objects with fields:
    task_id, benchmark, sdlc_phase, language, category, difficulty,
    mcp_benefit_score, repo.

    Args:
        registry_path: Optional override path. Defaults to data/selected_benchmark_tasks.json.

    Returns:
        Dict mapping task_id to CCBTaskMetadata. Empty dict if file missing.
    """
    path = Path(registry_path) if registry_path else _DEFAULT_REGISTRY_PATH

    if not path.exists():
        logger.debug(f"CCB task registry not found at {path}")
        return {}

    try:
        with open(path) as f:
            raw_tasks = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load CCB task registry from {path}: {e}")
        return {}

    # Handle both nested {"tasks": [...]} and flat list formats
    if isinstance(raw_tasks, dict):
        task_list = raw_tasks.get("tasks", [])
    elif isinstance(raw_tasks, list):
        task_list = raw_tasks
    else:
        logger.warning(f"CCB task registry at {path} has unexpected format")
        return {}

    registry: dict[str, CCBTaskMetadata] = {}

    for entry in task_list:
        if not isinstance(entry, dict):
            continue

        task_id = entry.get("task_id", "")
        if not task_id:
            continue

        metadata = CCBTaskMetadata(
            task_id=task_id,
            benchmark=entry.get("benchmark", ""),
            sdlc_phase=entry.get("sdlc_phase", ""),
            language=entry.get("language", ""),
            category=entry.get("category", ""),
            difficulty=entry.get("difficulty", ""),
            mcp_benefit_score=float(entry.get("mcp_benefit_score", 0.0)),
            repo=entry.get("repo", ""),
        )
        registry[task_id] = metadata

    logger.info(f"Loaded {len(registry)} tasks from CCB registry")
    return registry


def enrich_task_with_ccb_metadata(
    task_id: str, registry: dict[str, CCBTaskMetadata]
) -> Optional[CCBTaskMetadata]:
    """
    Look up CCB metadata for a given task ID.

    Args:
        task_id: The task identifier to look up.
        registry: The loaded CCB task registry.

    Returns:
        CCBTaskMetadata if found, None otherwise.
    """
    return registry.get(task_id)
