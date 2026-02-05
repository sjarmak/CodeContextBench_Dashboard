"""
Comparison data loader for cross-config analysis.

Loads task_metrics.json files for all configs (baseline, sourcegraph_base,
sourcegraph_full) and joins on (benchmark, task_id) so comparison views
can display side-by-side metrics.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

_KNOWN_CONFIG_DIRS = ("baseline", "sourcegraph_base", "sourcegraph_full")

_SESSION_KEY = "comparison_data"


def _get_runs_dir() -> Path:
    """Resolve the external runs directory from env or default."""
    return Path(os.environ.get(
        "CCB_EXTERNAL_RUNS_DIR",
        os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs"),
    ))


def _extract_task_id(dir_name: str) -> str:
    """Extract clean task_id from directory name (strip hash suffix).

    Directory names look like: 'big-code-servo-001__jk4jiJS'
    We want: 'big-code-servo-001'
    """
    parts = dir_name.split("__")
    if len(parts) >= 2:
        return "__".join(parts[:-1])
    return dir_name


def _load_task_metrics(task_dir: Path) -> Optional[dict]:
    """Load task_metrics.json from a task directory.

    Returns None if file doesn't exist or fails to parse.
    """
    metrics_path = task_dir / "task_metrics.json"
    if not metrics_path.exists():
        return None
    try:
        return json.loads(metrics_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load %s: %s", metrics_path, e)
        return None


def _walk_config_tasks(config_dir: Path) -> dict[str, dict]:
    """Walk a config directory and collect task_metrics indexed by task_id.

    Structure: config_dir/<batch_timestamp>/<task_id__hash>/task_metrics.json
    """
    tasks: dict[str, dict] = {}
    if not config_dir.is_dir():
        return tasks

    for batch_dir in config_dir.iterdir():
        if not batch_dir.is_dir() or batch_dir.name.startswith("."):
            continue
        for task_dir in batch_dir.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith("."):
                continue
            metrics = _load_task_metrics(task_dir)
            if metrics is None:
                continue
            task_id = (metrics.get("task_id") or _extract_task_id(task_dir.name))
            tasks[task_id] = metrics

    return tasks


def _scan_run(run_path: Path) -> dict[str, dict[str, Optional[dict]]]:
    """Scan a single run directory for all configs.

    Returns dict: {task_id: {config_name: metrics_dict_or_none}}
    """
    joined: dict[str, dict[str, Optional[dict]]] = {}

    config_tasks: dict[str, dict[str, dict]] = {}
    for config_name in _KNOWN_CONFIG_DIRS:
        config_dir = run_path / config_name
        config_tasks[config_name] = _walk_config_tasks(config_dir)

    # Collect all task_ids across configs
    all_task_ids: set[str] = set()
    for tasks in config_tasks.values():
        all_task_ids.update(tasks.keys())

    # Join on task_id
    for task_id in sorted(all_task_ids):
        joined[task_id] = {
            config: config_tasks[config].get(task_id)
            for config in _KNOWN_CONFIG_DIRS
        }

    return joined


def load_comparison_data(
    runs_dir: Optional[Path] = None,
) -> dict[str, dict[str, Optional[dict]]]:
    """Load and join task_metrics across all configs for comparison.

    Walks runs/official/<run_name>/<config>/<batch>/<task>/task_metrics.json
    and joins on task_id.

    Args:
        runs_dir: Root runs directory. Defaults to CCB_EXTERNAL_RUNS_DIR
                  or ~/evals/custom_agents/agents/claudecode/runs.

    Returns:
        Dict mapping task_id to {config_name: metrics_dict_or_None}.
        Example: {'task-1': {'baseline': {...}, 'sourcegraph_base': None, ...}}
    """
    if runs_dir is None:
        runs_dir = _get_runs_dir()

    # Check session state cache
    if _SESSION_KEY in st.session_state:
        return st.session_state[_SESSION_KEY]

    merged: dict[str, dict[str, Optional[dict]]] = {}

    # Scan all subdirectories (official, experiment, etc.)
    if not runs_dir.exists():
        st.session_state[_SESSION_KEY] = merged
        return merged

    for folder in runs_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        for run_path in folder.iterdir():
            if not run_path.is_dir() or run_path.name.startswith("."):
                continue
            # Only scan runs that have at least one known config dir
            has_config = any(
                (run_path / config).is_dir() for config in _KNOWN_CONFIG_DIRS
            )
            if not has_config:
                continue

            run_data = _scan_run(run_path)
            for task_id, configs in run_data.items():
                if task_id in merged:
                    # Merge: fill in missing configs from additional runs
                    for config, metrics in configs.items():
                        if merged[task_id].get(config) is None and metrics is not None:
                            merged[task_id] = {
                                **merged[task_id],
                                config: metrics,
                            }
                else:
                    merged[task_id] = configs

    st.session_state[_SESSION_KEY] = merged
    logger.info("Loaded comparison data: %d tasks", len(merged))
    return merged


def invalidate_cache() -> None:
    """Remove cached comparison data from session state."""
    st.session_state.pop(_SESSION_KEY, None)
