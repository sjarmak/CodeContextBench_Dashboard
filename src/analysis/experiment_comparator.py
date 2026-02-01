"""
Experiment comparator for filesystem-based A/B experiment comparison.

Provides task alignment across two experiment directories, ensuring comparisons
only include tasks present in both runs. This is the foundation for the unified
experiment comparison pipeline with statistical rigor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AlignmentResult:
    """Result of aligning tasks across two experiment directories."""

    common_tasks: list[str]
    baseline_only: list[str]
    treatment_only: list[str]
    total_baseline: int
    total_treatment: int


class TaskAligner:
    """Aligns tasks across two experiment directories for valid comparison.

    Scans baseline and treatment directories, resolves task IDs from
    config.json's task.path field (falling back to directory name), and
    returns the intersection plus exclusion lists.
    """

    def align(
        self,
        baseline_dir: Path,
        treatment_dir: Path,
    ) -> AlignmentResult:
        """Align tasks between baseline and treatment experiment directories.

        Args:
            baseline_dir: Path to baseline experiment run directory.
            treatment_dir: Path to treatment experiment run directory.

        Returns:
            AlignmentResult with common tasks, exclusions, and totals.
        """
        baseline_tasks = self._discover_tasks(baseline_dir)
        treatment_tasks = self._discover_tasks(treatment_dir)

        baseline_ids = set(baseline_tasks.keys())
        treatment_ids = set(treatment_tasks.keys())

        common = sorted(baseline_ids & treatment_ids)
        baseline_only = sorted(baseline_ids - treatment_ids)
        treatment_only = sorted(treatment_ids - baseline_ids)

        return AlignmentResult(
            common_tasks=common,
            baseline_only=baseline_only,
            treatment_only=treatment_only,
            total_baseline=len(baseline_ids),
            total_treatment=len(treatment_ids),
        )

    def _discover_tasks(self, experiment_dir: Path) -> dict[str, Path]:
        """Discover task IDs and their directories within an experiment dir.

        Args:
            experiment_dir: Root directory of an experiment run.

        Returns:
            Mapping of task_id -> task directory path.
        """
        tasks: dict[str, Path] = {}

        if not experiment_dir.is_dir():
            return tasks

        for entry in sorted(experiment_dir.iterdir()):
            if not entry.is_dir():
                continue

            # Skip hidden directories and common non-task dirs
            if entry.name.startswith("."):
                continue

            task_id = self._resolve_task_id(entry)
            tasks[task_id] = entry

        return tasks

    def _resolve_task_id(self, task_dir: Path) -> str:
        """Resolve the canonical task ID for a task directory.

        Reads config.json's task.path field when present, falling back
        to the directory name.

        Args:
            task_dir: Path to a single task result directory.

        Returns:
            Canonical task ID string.
        """
        config_path = task_dir / "config.json"

        if config_path.is_file():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)

                task_config = config.get("task") or {}
                task_path = task_config.get("path") or ""

                if task_path:
                    # Extract the final path segment as canonical task ID
                    return Path(task_path).name
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        # Fallback: use directory name, stripping any hash suffix
        # Trial dirs are often like "task-name__hashSuffix"
        dir_name = task_dir.name
        if "__" in dir_name:
            return dir_name.rsplit("__", 1)[0]
        return dir_name

    def load_result(self, task_dir: Path) -> dict:
        """Load and defensively parse a task's result.json.

        Args:
            task_dir: Path to a single task result directory.

        Returns:
            Parsed result dict with None-safe defaults.
        """
        result_path = task_dir / "result.json"

        if not result_path.is_file():
            return {}

        try:
            with open(result_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, TypeError):
            return {}

        if not isinstance(data, dict):
            return {}

        # Defensive None handling per CLAUDE.md pattern:
        # data.get("key") or default_value
        return {
            "task_name": (data.get("task_name") or ""),
            "started_at": (data.get("started_at") or ""),
            "finished_at": (data.get("finished_at") or ""),
            "agent_info": (data.get("agent_info") or {}),
            "agent_result": (data.get("agent_result") or {}),
            "verifier_result": (data.get("verifier_result") or {}),
            "exception_info": data.get("exception_info"),
        }

    def load_reward(self, task_dir: Path) -> Optional[float]:
        """Extract the primary reward from a task's result.json.

        Args:
            task_dir: Path to a single task result directory.

        Returns:
            Primary reward as float, or None if unavailable.
        """
        result = self.load_result(task_dir)
        verifier = result.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        reward = rewards.get("reward")

        if reward is not None:
            try:
                return float(reward)
            except (ValueError, TypeError):
                return None

        return None
