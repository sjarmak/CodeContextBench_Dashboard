"""
Experiment comparator for filesystem-based A/B experiment comparison.

Provides task alignment across two experiment directories, ensuring comparisons
only include tasks present in both runs. This is the foundation for the unified
experiment comparison pipeline with statistical rigor.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# Normalization rules per benchmark type.
# Each entry maps benchmark_type -> (min_raw, max_raw).
# Passthrough benchmarks use (0.0, 1.0).
BENCHMARK_NORMALIZATION: dict[str, tuple[float, float]] = {
    "locobench": (0.0, 1.0),
    "locobench_agent": (0.0, 1.0),
    "swebench": (0.0, 1.0),
    "swebench_pro": (0.0, 1.0),
    "big_code_mcp": (0.0, 1.0),
    "github_mined": (0.0, 1.0),
    "tac_mcp_value": (0.0, 1.0),
}

# Known benchmark directory name prefixes for type inference.
_BENCHMARK_DIR_NAMES = frozenset(BENCHMARK_NORMALIZATION.keys())


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


class RewardNormalizer:
    """Normalizes rewards to a 0-1 scale across benchmark types.

    Normalization rules are defined in BENCHMARK_NORMALIZATION. For benchmarks
    that already produce 0-1 rewards (LoCoBench, SWE-bench), this is a
    passthrough with clamping. For others, min-max normalization is applied.
    """

    def normalize(self, reward: float, benchmark_type: str) -> float:
        """Normalize a reward value to [0.0, 1.0].

        Args:
            reward: Raw reward value from the benchmark.
            benchmark_type: Benchmark type string (e.g., 'locobench', 'swebench_pro').

        Returns:
            Normalized reward clamped to [0.0, 1.0].

        Raises:
            ValueError: If benchmark_type is not recognized.
        """
        if benchmark_type not in BENCHMARK_NORMALIZATION:
            raise ValueError(
                f"Unknown benchmark type: '{benchmark_type}'. "
                f"Known types: {sorted(BENCHMARK_NORMALIZATION.keys())}"
            )

        raw_min, raw_max = BENCHMARK_NORMALIZATION[benchmark_type]

        if raw_max == raw_min:
            normalized = 0.0
        else:
            normalized = (reward - raw_min) / (raw_max - raw_min)

        return max(0.0, min(1.0, normalized))

    def infer_benchmark_type(self, task_path: Path) -> Optional[str]:
        """Infer benchmark type from a task directory path or its config.json.

        Checks config.json metadata first, then scans path components for
        known benchmark directory names.

        Args:
            task_path: Path to a task directory or benchmark path.

        Returns:
            Benchmark type string, or None if not inferrable.
        """
        # Try config.json first
        config_path = task_path / "config.json"
        if config_path.is_file():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                task_config = config.get("task") or {}
                config_task_path = task_config.get("path") or ""
                if config_task_path:
                    for part in Path(config_task_path).parts:
                        if part in _BENCHMARK_DIR_NAMES:
                            return part
            except (json.JSONDecodeError, TypeError):
                pass

        # Scan path components for known benchmark names
        for part in task_path.parts:
            if part in _BENCHMARK_DIR_NAMES:
                return part

        return None


@dataclass(frozen=True)
class BootstrapResult:
    """Result of pairwise bootstrap significance testing."""

    mean_delta: float
    ci_lower: float
    ci_upper: float
    p_value: float
    effect_size: float
    effect_interpretation: str
    n_resamples: int
    n_tasks: int


def _cohens_d(differences: np.ndarray) -> float:
    """Compute Cohen's d for paired differences.

    Args:
        differences: Array of paired differences (treatment - baseline).

    Returns:
        Cohen's d effect size (can be negative).
    """
    mean_diff = float(np.mean(differences))
    std_diff = float(np.std(differences, ddof=1)) if len(differences) > 1 else 0.0

    if std_diff == 0.0:
        if mean_diff == 0.0:
            return 0.0
        return float("inf") if mean_diff > 0 else float("-inf")

    return mean_diff / std_diff


def _interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d using standard thresholds.

    Args:
        d: Cohen's d value.

    Returns:
        One of: negligible, small, medium, large.
    """
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    if abs_d < 0.5:
        return "small"
    if abs_d < 0.8:
        return "medium"
    return "large"


def pairwise_bootstrap(
    baseline_rewards: list[float],
    treatment_rewards: list[float],
    n_resamples: int = 10000,
    confidence: float = 0.95,
    random_seed: Optional[int] = None,
) -> BootstrapResult:
    """Pairwise bootstrap significance test for paired reward differences.

    Resamples paired differences (not independent), preserving task pairing.

    Args:
        baseline_rewards: Reward values from baseline, ordered by task.
        treatment_rewards: Reward values from treatment, ordered by task.
        n_resamples: Number of bootstrap resamples.
        confidence: Confidence level for the interval (e.g. 0.95).
        random_seed: If provided, makes results deterministic.

    Returns:
        BootstrapResult with mean delta, CI, p-value, effect size.

    Raises:
        ValueError: If inputs are empty or have different lengths.
    """
    if len(baseline_rewards) != len(treatment_rewards):
        raise ValueError(
            f"Baseline and treatment must have same length, "
            f"got {len(baseline_rewards)} and {len(treatment_rewards)}"
        )
    if len(baseline_rewards) == 0:
        raise ValueError("Reward lists must contain at least one task")

    baseline_arr = np.array(baseline_rewards, dtype=np.float64)
    treatment_arr = np.array(treatment_rewards, dtype=np.float64)
    differences = treatment_arr - baseline_arr
    n_tasks = len(differences)

    mean_delta = float(np.mean(differences))
    effect_size_val = _cohens_d(differences)
    effect_interp = _interpret_effect_size(effect_size_val)

    rng = np.random.default_rng(random_seed)
    indices = rng.integers(0, n_tasks, size=(n_resamples, n_tasks))
    bootstrap_deltas = np.mean(differences[indices], axis=1)

    alpha = 1.0 - confidence
    ci_lower = float(np.percentile(bootstrap_deltas, 100 * alpha / 2))
    ci_upper = float(np.percentile(bootstrap_deltas, 100 * (1 - alpha / 2)))

    # p-value: proportion of bootstrap deltas on the opposite side of zero from the observed mean
    if mean_delta > 0:
        p_value = float(np.mean(bootstrap_deltas <= 0)) * 2
    elif mean_delta < 0:
        p_value = float(np.mean(bootstrap_deltas >= 0)) * 2
    else:
        p_value = 1.0

    p_value = min(p_value, 1.0)

    return BootstrapResult(
        mean_delta=mean_delta,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value=p_value,
        effect_size=abs(effect_size_val) if not math.isinf(effect_size_val) else abs(effect_size_val),
        effect_interpretation=effect_interp,
        n_resamples=n_resamples,
        n_tasks=n_tasks,
    )
