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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from scipy import stats


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


def extract_task_category(task_dir: Path) -> str:
    """Extract task category from config.json metadata or task directory path.

    Checks config.json for category metadata first, then infers from the
    task path components (e.g., 'architectural_understanding' from
    'benchmarks/locobench_agent/architectural_understanding/task-1').

    Args:
        task_dir: Path to a task result directory.

    Returns:
        Category string, or 'unknown' if not inferrable.
    """
    config_path = task_dir / "config.json"
    if config_path.is_file():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            task_config = config.get("task") or {}

            # Direct category field
            category = task_config.get("category") or ""
            if category:
                return category

            # Infer from task.path (e.g., "benchmarks/locobench_agent/arch_understanding/task-1")
            task_path_str = task_config.get("path") or ""
            if task_path_str:
                parts = Path(task_path_str).parts
                # Category is typically the segment after the benchmark name
                for i, part in enumerate(parts):
                    if part in _BENCHMARK_DIR_NAMES and i + 1 < len(parts):
                        return parts[i + 1]
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: scan directory ancestors for category-like names
    return "unknown"


@dataclass(frozen=True)
class CategoryBreakdown:
    """Per-category comparison result."""

    category: str
    n_tasks: int
    baseline_mean: float
    treatment_mean: float
    mean_delta: float
    bootstrap: Optional[BootstrapResult]


def compute_category_breakdown(
    aligned_results: list[dict],
    categories: dict[str, str],
    n_resamples: int = 10000,
    confidence: float = 0.95,
    random_seed: Optional[int] = None,
    min_category_size: int = 5,
) -> list[CategoryBreakdown]:
    """Compute per-category breakdown with optional bootstrap testing.

    Args:
        aligned_results: List of dicts with keys 'task_id', 'baseline_reward', 'treatment_reward'.
        categories: Mapping of task_id -> category string.
        n_resamples: Number of bootstrap resamples.
        confidence: Confidence level for bootstrap CI.
        random_seed: Optional seed for reproducibility.
        min_category_size: Minimum tasks for bootstrap testing.

    Returns:
        List of CategoryBreakdown sorted by absolute mean_delta descending,
        with an 'all' pseudo-category included.
    """
    if not aligned_results:
        return []

    # Group tasks by category
    groups: dict[str, list[dict]] = {}
    for item in aligned_results:
        task_id = item["task_id"]
        cat = categories.get(task_id) or "unknown"
        if cat not in groups:
            groups[cat] = []
        groups[cat] = [*groups[cat], item]

    breakdowns: list[CategoryBreakdown] = []

    # Per-category breakdowns
    for cat, items in groups.items():
        breakdown = _build_category_breakdown(
            category=cat,
            items=items,
            n_resamples=n_resamples,
            confidence=confidence,
            random_seed=random_seed,
            min_category_size=min_category_size,
        )
        breakdowns.append(breakdown)

    # 'all' pseudo-category aggregate
    all_breakdown = _build_category_breakdown(
        category="all",
        items=aligned_results,
        n_resamples=n_resamples,
        confidence=confidence,
        random_seed=random_seed,
        min_category_size=min_category_size,
    )
    breakdowns.append(all_breakdown)

    # Sort by absolute mean_delta descending
    return sorted(breakdowns, key=lambda b: abs(b.mean_delta), reverse=True)


def _build_category_breakdown(
    category: str,
    items: list[dict],
    n_resamples: int,
    confidence: float,
    random_seed: Optional[int],
    min_category_size: int,
) -> CategoryBreakdown:
    """Build a single CategoryBreakdown from a list of aligned result dicts."""
    baseline_rewards = [item["baseline_reward"] for item in items]
    treatment_rewards = [item["treatment_reward"] for item in items]
    n_tasks = len(items)

    baseline_mean = sum(baseline_rewards) / n_tasks
    treatment_mean = sum(treatment_rewards) / n_tasks
    mean_delta = treatment_mean - baseline_mean

    bootstrap_result: Optional[BootstrapResult] = None
    if n_tasks >= min_category_size:
        bootstrap_result = pairwise_bootstrap(
            baseline_rewards=baseline_rewards,
            treatment_rewards=treatment_rewards,
            n_resamples=n_resamples,
            confidence=confidence,
            random_seed=random_seed,
        )

    return CategoryBreakdown(
        category=category,
        n_tasks=n_tasks,
        baseline_mean=baseline_mean,
        treatment_mean=treatment_mean,
        mean_delta=mean_delta,
        bootstrap=bootstrap_result,
    )


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


@dataclass(frozen=True)
class ToolCorrelation:
    """Result of tool usage correlation analysis."""

    spearman_rho: float
    spearman_p_value: float
    n_tasks: int
    interpretation: str
    per_task: list[dict]


def _interpret_correlation(rho: float) -> str:
    """Interpret Spearman rho using standard thresholds.

    Args:
        rho: Spearman rank correlation coefficient.

    Returns:
        One of: strong positive, moderate positive, weak/no correlation,
        moderate negative, strong negative.
    """
    if rho > 0.5:
        return "strong positive"
    if rho > 0.3:
        return "moderate positive"
    if rho >= -0.3:
        return "weak/no correlation"
    if rho >= -0.5:
        return "moderate negative"
    return "strong negative"


def _extract_tool_call_count(result_data: dict) -> Optional[int]:
    """Extract tool call count from a result.json dict.

    Checks agent_info for tool call counts, then falls back to
    agent_result metadata.

    Args:
        result_data: Parsed result.json dict (already None-safe from load_result).

    Returns:
        Total tool call count, or None if not available.
    """
    agent_info = result_data.get("agent_info") or {}

    # Check common tool call count locations
    tool_calls = agent_info.get("tool_calls")
    if tool_calls is not None:
        try:
            return int(tool_calls)
        except (ValueError, TypeError):
            pass

    # Check for tool usage summary dict
    tool_usage = agent_info.get("tool_usage") or {}
    if tool_usage and isinstance(tool_usage, dict):
        total = sum(
            int(v) for v in tool_usage.values()
            if v is not None
        )
        if total > 0:
            return total

    # Check agent_result for tool call metadata
    agent_result = result_data.get("agent_result") or {}
    n_tool_calls = agent_result.get("n_tool_calls")
    if n_tool_calls is not None:
        try:
            return int(n_tool_calls)
        except (ValueError, TypeError):
            pass

    return None


def compute_tool_correlation(
    treatment_results: list[dict],
    reward_deltas: dict[str, float],
) -> Optional[ToolCorrelation]:
    """Compute Spearman rank correlation between tool call counts and reward deltas.

    Args:
        treatment_results: List of dicts with keys 'task_id' and 'result_data'
            (parsed result.json from treatment run).
        reward_deltas: Mapping of task_id -> reward delta (treatment - baseline).

    Returns:
        ToolCorrelation with Spearman rho, p-value, and per-task data,
        or None if treatment run has no tool call data or fewer than 3 tasks
        have tool data.
    """
    per_task: list[dict] = []

    for item in treatment_results:
        task_id = item["task_id"]
        result_data = item.get("result_data") or {}
        tool_count = _extract_tool_call_count(result_data)

        if tool_count is not None and task_id in reward_deltas:
            per_task = [
                *per_task,
                {
                    "task_id": task_id,
                    "tool_calls": tool_count,
                    "reward_delta": reward_deltas[task_id],
                },
            ]

    if len(per_task) < 3:
        return None

    tool_counts = [t["tool_calls"] for t in per_task]
    deltas = [t["reward_delta"] for t in per_task]

    # Check for zero variance — spearmanr returns NaN when all values are identical
    if len(set(tool_counts)) < 2 or len(set(deltas)) < 2:
        return ToolCorrelation(
            spearman_rho=0.0,
            spearman_p_value=1.0,
            n_tasks=len(per_task),
            interpretation="weak/no correlation",
            per_task=per_task,
        )

    result = stats.spearmanr(tool_counts, deltas)
    rho = float(result.statistic)
    p_val = float(result.pvalue)

    return ToolCorrelation(
        spearman_rho=rho,
        spearman_p_value=p_val,
        n_tasks=len(per_task),
        interpretation=_interpret_correlation(rho),
        per_task=per_task,
    )


@dataclass(frozen=True)
class ComparisonReport:
    """Full comparison report from the ExperimentComparison pipeline."""

    baseline_dir: str
    treatment_dir: str
    alignment: AlignmentResult
    overall_bootstrap: BootstrapResult
    category_breakdown: list[CategoryBreakdown]
    tool_correlation: Optional[ToolCorrelation]
    generated_at: str
    config: dict

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict.

        Converts all dataclass fields, Path objects, and numpy types to
        JSON-serializable Python primitives.

        Returns:
            Dict safe for json.dumps().
        """
        def _bootstrap_to_dict(b: BootstrapResult) -> dict:
            return {
                "mean_delta": b.mean_delta,
                "ci_lower": b.ci_lower,
                "ci_upper": b.ci_upper,
                "p_value": b.p_value,
                "effect_size": b.effect_size,
                "effect_interpretation": b.effect_interpretation,
                "n_resamples": b.n_resamples,
                "n_tasks": b.n_tasks,
            }

        def _category_to_dict(c: CategoryBreakdown) -> dict:
            return {
                "category": c.category,
                "n_tasks": c.n_tasks,
                "baseline_mean": c.baseline_mean,
                "treatment_mean": c.treatment_mean,
                "mean_delta": c.mean_delta,
                "bootstrap": _bootstrap_to_dict(c.bootstrap) if c.bootstrap else None,
            }

        def _tool_corr_to_dict(tc: ToolCorrelation) -> dict:
            return {
                "spearman_rho": tc.spearman_rho,
                "spearman_p_value": tc.spearman_p_value,
                "n_tasks": tc.n_tasks,
                "interpretation": tc.interpretation,
                "per_task": list(tc.per_task),
            }

        return {
            "version": "1.0.0",
            "generated_at": self.generated_at,
            "config": self.config,
            "metadata": {
                "baseline_dir": self.baseline_dir,
                "treatment_dir": self.treatment_dir,
            },
            "alignment": {
                "common_tasks": list(self.alignment.common_tasks),
                "baseline_only": list(self.alignment.baseline_only),
                "treatment_only": list(self.alignment.treatment_only),
                "total_baseline": self.alignment.total_baseline,
                "total_treatment": self.alignment.total_treatment,
            },
            "overall": _bootstrap_to_dict(self.overall_bootstrap),
            "categories": [_category_to_dict(c) for c in self.category_breakdown],
            "tool_correlation": (
                _tool_corr_to_dict(self.tool_correlation)
                if self.tool_correlation
                else None
            ),
        }

    def to_markdown(self) -> str:
        """Render as a Markdown report.

        Returns:
            Complete Markdown document string.
        """
        lines: list[str] = []
        a = self.alignment
        ob = self.overall_bootstrap

        # --- Summary ---
        lines.append("# Experiment Comparison Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Baseline:** {self.baseline_dir}")
        lines.append(f"- **Treatment:** {self.treatment_dir}")
        lines.append(f"- **Date:** {self.generated_at}")
        lines.append(
            f"- **Common tasks:** {len(a.common_tasks)}"
        )
        lines.append(
            f"- **Excluded tasks:** "
            f"{len(a.baseline_only)} baseline-only, "
            f"{len(a.treatment_only)} treatment-only"
        )
        lines.append("")

        # --- Overall Result ---
        lines.append("## Overall Result")
        lines.append("")
        sig_marker = _significance_marker(ob.p_value)
        lines.append(
            f"- **Mean delta:** {ob.mean_delta:.4f} "
            f"(95% CI: [{ob.ci_lower:.4f}, {ob.ci_upper:.4f}])"
        )
        lines.append(f"- **p-value:** {ob.p_value:.4f}{sig_marker}")
        lines.append(
            f"- **Effect size (Cohen's d):** {ob.effect_size:.4f} "
            f"({ob.effect_interpretation})"
        )
        significant = "Yes" if ob.p_value < 0.05 else "No"
        lines.append(f"- **Significant at alpha=0.05:** {significant}")
        lines.append("")

        # --- Per-Category Breakdown ---
        lines.append("## Per-Category Breakdown")
        lines.append("")
        lines.append(
            "| Category | N | Baseline Mean | Treatment Mean "
            "| Delta | 95% CI | Significant? |"
        )
        lines.append(
            "|----------|---|---------------|----------------"
            "|-------|--------|--------------|"
        )
        for cat in self.category_breakdown:
            if cat.bootstrap:
                ci_str = f"[{cat.bootstrap.ci_lower:.4f}, {cat.bootstrap.ci_upper:.4f}]"
                sig_str = (
                    "Yes" + _significance_marker(cat.bootstrap.p_value)
                    if cat.bootstrap.p_value < 0.05
                    else "No"
                )
            else:
                ci_str = "N/A"
                sig_str = "N/A"
            lines.append(
                f"| {cat.category} | {cat.n_tasks} "
                f"| {cat.baseline_mean:.4f} | {cat.treatment_mean:.4f} "
                f"| {cat.mean_delta:.4f} | {ci_str} | {sig_str} |"
            )
        lines.append("")

        # --- Tool Usage Correlation ---
        lines.append("## Tool Usage Correlation")
        lines.append("")
        if self.tool_correlation:
            tc = self.tool_correlation
            lines.append(f"- **Spearman rho:** {tc.spearman_rho:.4f}")
            lines.append(f"- **p-value:** {tc.spearman_p_value:.4f}")
            lines.append(f"- **Interpretation:** {tc.interpretation}")
            lines.append(f"- **Tasks with tool data:** {tc.n_tasks}")
            lines.append("")
            lines.append("*See JSON output for per-task scatter plot data.*")
        else:
            lines.append("No tool usage data available for correlation analysis.")
        lines.append("")

        # --- Excluded Tasks ---
        lines.append("## Excluded Tasks")
        lines.append("")
        lines.append(
            _format_excluded_list("Baseline-only", a.baseline_only)
        )
        lines.append(
            _format_excluded_list("Treatment-only", a.treatment_only)
        )

        return "\n".join(lines)


def _significance_marker(p_value: float) -> str:
    """Return asterisk significance markers for a p-value."""
    if p_value < 0.001:
        return " ***"
    if p_value < 0.01:
        return " **"
    if p_value < 0.05:
        return " *"
    return ""


def _format_excluded_list(label: str, task_ids: list[str]) -> str:
    """Format a list of excluded task IDs, collapsing if > 10."""
    if not task_ids:
        return f"**{label}:** None"

    if len(task_ids) <= 10:
        items = ", ".join(task_ids)
        return f"**{label}:** {items}"

    # Collapse long lists
    items = ", ".join(task_ids[:10])
    return (
        f"<details>\n<summary><b>{label}:</b> "
        f"{len(task_ids)} tasks</summary>\n\n"
        f"{items}, ... and {len(task_ids) - 10} more\n\n"
        f"</details>"
    )


class ExperimentComparison:
    """Orchestrator that combines all comparison pipeline stages.

    Runs task alignment, reward normalization, bootstrap testing,
    per-category breakdown, and tool correlation in one call.
    """

    def __init__(
        self,
        n_resamples: int = 10000,
        confidence: float = 0.95,
        random_seed: Optional[int] = None,
        min_category_size: int = 5,
    ) -> None:
        self._n_resamples = n_resamples
        self._confidence = confidence
        self._random_seed = random_seed
        self._min_category_size = min_category_size
        self._aligner = TaskAligner()
        self._normalizer = RewardNormalizer()

    def compare(
        self,
        baseline_dir: Path,
        treatment_dir: Path,
    ) -> ComparisonReport:
        """Run the full comparison pipeline.

        Args:
            baseline_dir: Path to baseline experiment run directory.
            treatment_dir: Path to treatment experiment run directory.

        Returns:
            ComparisonReport with all analysis results.

        Raises:
            ValueError: If alignment produces 0 common tasks.
        """
        # Step 1: Task alignment
        alignment = self._aligner.align(baseline_dir, treatment_dir)

        if not alignment.common_tasks:
            raise ValueError(
                "No common tasks between baseline and treatment directories. "
                f"Baseline has {alignment.total_baseline} tasks, "
                f"treatment has {alignment.total_treatment} tasks, "
                "but none overlap."
            )

        # Step 2: Load rewards and build aligned result list
        baseline_tasks = self._aligner._discover_tasks(baseline_dir)
        treatment_tasks = self._aligner._discover_tasks(treatment_dir)

        aligned_results: list[dict] = []
        baseline_rewards: list[float] = []
        treatment_rewards: list[float] = []
        categories: dict[str, str] = {}
        treatment_result_data: list[dict] = []
        reward_deltas: dict[str, float] = {}

        for task_id in alignment.common_tasks:
            b_dir = baseline_tasks[task_id]
            t_dir = treatment_tasks[task_id]

            b_reward = self._aligner.load_reward(b_dir)
            t_reward = self._aligner.load_reward(t_dir)

            # Skip tasks with missing reward data
            if b_reward is None or t_reward is None:
                continue

            # Normalize rewards
            b_type = self._normalizer.infer_benchmark_type(b_dir)
            if b_type:
                b_reward = self._normalizer.normalize(b_reward, b_type)
                t_reward = self._normalizer.normalize(t_reward, b_type)

            aligned_results = [
                *aligned_results,
                {
                    "task_id": task_id,
                    "baseline_reward": b_reward,
                    "treatment_reward": t_reward,
                },
            ]
            baseline_rewards = [*baseline_rewards, b_reward]
            treatment_rewards = [*treatment_rewards, t_reward]

            # Category for breakdown
            categories[task_id] = extract_task_category(t_dir)

            # Treatment result data for tool correlation
            t_result = self._aligner.load_result(t_dir)
            treatment_result_data = [
                *treatment_result_data,
                {"task_id": task_id, "result_data": t_result},
            ]

            reward_deltas[task_id] = t_reward - b_reward

        if not aligned_results:
            raise ValueError(
                "No tasks with valid reward data in both baseline and treatment. "
                f"{len(alignment.common_tasks)} common tasks found but "
                "all had missing reward values."
            )

        # Step 3: Overall bootstrap
        overall_bootstrap = pairwise_bootstrap(
            baseline_rewards=baseline_rewards,
            treatment_rewards=treatment_rewards,
            n_resamples=self._n_resamples,
            confidence=self._confidence,
            random_seed=self._random_seed,
        )

        # Step 4: Per-category breakdown
        category_breakdown = compute_category_breakdown(
            aligned_results=aligned_results,
            categories=categories,
            n_resamples=self._n_resamples,
            confidence=self._confidence,
            random_seed=self._random_seed,
            min_category_size=self._min_category_size,
        )

        # Step 5: Tool usage correlation
        tool_correlation = compute_tool_correlation(
            treatment_results=treatment_result_data,
            reward_deltas=reward_deltas,
        )

        return ComparisonReport(
            baseline_dir=str(baseline_dir),
            treatment_dir=str(treatment_dir),
            alignment=alignment,
            overall_bootstrap=overall_bootstrap,
            category_breakdown=category_breakdown,
            tool_correlation=tool_correlation,
            generated_at=datetime.now(timezone.utc).isoformat(),
            config={
                "n_resamples": self._n_resamples,
                "confidence": self._confidence,
                "random_seed": self._random_seed,
                "min_category_size": self._min_category_size,
            },
        )
