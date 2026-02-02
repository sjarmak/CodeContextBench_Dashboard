"""
Statistical analysis step for the CCB pipeline.

Consumes experiment_metrics.json and produces analysis_results.json
with aggregate metrics per configuration and pairwise statistical tests.

Usage:
    python -m scripts.ccb_pipeline.analyze --input experiment_metrics.json --output analysis_results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

import scipy.stats

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures (frozen / immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigAggregateMetrics:
    """Aggregate metrics for a single agent configuration."""

    config: str
    n_trials: int
    mean_reward: float
    se_reward: float
    pass_rate: float
    se_pass_rate: float
    median_duration_seconds: float | None
    mean_input_tokens: float
    mean_output_tokens: float


@dataclass(frozen=True)
class PairwiseTestResult:
    """Result of a pairwise statistical test between two configurations."""

    config_a: str
    config_b: str
    metric: str
    test_name: str
    statistic: float
    p_value: float
    significant: bool  # p < 0.05


@dataclass(frozen=True)
class EffectSizeResult:
    """Cohen's d effect size for a pairwise comparison."""

    config_a: str
    config_b: str
    metric: str
    cohens_d: float
    interpretation: str  # negligible / small / medium / large


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _flatten_trials(categories: list[dict]) -> list[dict]:
    """Flatten nested categories/experiments/trials into a flat list of trial dicts."""
    trials: list[dict] = []
    for category in categories:
        for experiment in category.get("experiments", []):
            for trial in experiment.get("trials", []):
                trials.append(trial)
    return trials


def _group_by_config(trials: list[dict]) -> dict[str, list[dict]]:
    """Group trials by agent_config value."""
    groups: dict[str, list[dict]] = {}
    for trial in trials:
        config = trial.get("agent_config", "UNKNOWN")
        if config not in groups:
            groups[config] = []
        groups[config].append(trial)
    return groups


def _safe_mean(values: list[float]) -> float:
    """Compute mean, returning 0.0 for empty lists."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_se(values: list[float]) -> float:
    """Compute standard error of the mean."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance / n)


def _safe_median(values: list[float]) -> float | None:
    """Compute median, returning None for empty lists."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return sorted_vals[mid]


def _se_proportion(p: float, n: int) -> float:
    """Standard error for a proportion."""
    if n < 1:
        return 0.0
    return math.sqrt(p * (1.0 - p) / n)


def _cohens_d(values_a: list[float], values_b: list[float]) -> float:
    """Compute Cohen's d effect size between two groups."""
    n_a = len(values_a)
    n_b = len(values_b)
    if n_a < 2 or n_b < 2:
        return 0.0

    mean_a = sum(values_a) / n_a
    mean_b = sum(values_b) / n_b

    var_a = sum((x - mean_a) ** 2 for x in values_a) / (n_a - 1)
    var_b = sum((x - mean_b) ** 2 for x in values_b) / (n_b - 1)

    # Pooled standard deviation
    pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
    pooled_sd = math.sqrt(pooled_var)

    if pooled_sd == 0.0:
        return 0.0

    return (mean_a - mean_b) / pooled_sd


def _interpret_cohens_d(d: float) -> str:
    """Interpret Cohen's d magnitude."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    if abs_d < 0.5:
        return "small"
    if abs_d < 0.8:
        return "medium"
    return "large"


def _proportion_z_test(
    successes_a: int, n_a: int, successes_b: int, n_b: int
) -> tuple[float, float]:
    """Two-proportion z-test.

    Returns (z_statistic, p_value).
    """
    if n_a == 0 or n_b == 0:
        return (0.0, 1.0)

    p_a = successes_a / n_a
    p_b = successes_b / n_b

    # Pooled proportion
    p_pool = (successes_a + successes_b) / (n_a + n_b)

    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n_a + 1.0 / n_b))
    if se == 0.0:
        return (0.0, 1.0)

    z = (p_a - p_b) / se
    p_value = 2.0 * (1.0 - scipy.stats.norm.cdf(abs(z)))
    return (z, p_value)


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def compute_aggregate_metrics(
    config_groups: dict[str, list[dict]],
) -> list[ConfigAggregateMetrics]:
    """Compute per-configuration aggregate metrics."""
    results: list[ConfigAggregateMetrics] = []

    for config, trials in sorted(config_groups.items()):
        rewards = [t["reward"] for t in trials if t.get("reward") is not None]
        pass_count = sum(1 for t in trials if t.get("pass_fail") == "pass")
        n = len(trials)
        pass_rate = pass_count / n if n > 0 else 0.0

        durations = [
            t["duration_seconds"]
            for t in trials
            if t.get("duration_seconds") is not None
        ]
        input_tokens = [t.get("input_tokens", 0) or 0 for t in trials]
        output_tokens = [t.get("output_tokens", 0) or 0 for t in trials]

        results.append(
            ConfigAggregateMetrics(
                config=config,
                n_trials=n,
                mean_reward=_safe_mean(rewards),
                se_reward=_safe_se(rewards),
                pass_rate=pass_rate,
                se_pass_rate=_se_proportion(pass_rate, n),
                median_duration_seconds=_safe_median(durations),
                mean_input_tokens=_safe_mean([float(x) for x in input_tokens]),
                mean_output_tokens=_safe_mean([float(x) for x in output_tokens]),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Pairwise tests
# ---------------------------------------------------------------------------


def compute_pairwise_tests(
    config_groups: dict[str, list[dict]],
) -> list[PairwiseTestResult]:
    """Run pairwise statistical tests for all config pairs."""
    results: list[PairwiseTestResult] = []
    configs = sorted(config_groups.keys())

    for config_a, config_b in combinations(configs, 2):
        trials_a = config_groups[config_a]
        trials_b = config_groups[config_b]

        # Reward t-test
        rewards_a = [t["reward"] for t in trials_a if t.get("reward") is not None]
        rewards_b = [t["reward"] for t in trials_b if t.get("reward") is not None]

        if len(rewards_a) >= 2 and len(rewards_b) >= 2:
            stat, p_val = scipy.stats.ttest_ind(rewards_a, rewards_b, equal_var=False)
            results.append(
                PairwiseTestResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="reward",
                    test_name="welch_t_test",
                    statistic=float(stat),
                    p_value=float(p_val),
                    significant=float(p_val) < 0.05,
                )
            )

        # Pass rate proportion z-test
        n_a = len(trials_a)
        n_b = len(trials_b)
        pass_a = sum(1 for t in trials_a if t.get("pass_fail") == "pass")
        pass_b = sum(1 for t in trials_b if t.get("pass_fail") == "pass")

        if n_a > 0 and n_b > 0:
            z_stat, z_p = _proportion_z_test(pass_a, n_a, pass_b, n_b)
            results.append(
                PairwiseTestResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="pass_rate",
                    test_name="proportion_z_test",
                    statistic=z_stat,
                    p_value=z_p,
                    significant=z_p < 0.05,
                )
            )

        # Duration t-test
        dur_a = [
            t["duration_seconds"]
            for t in trials_a
            if t.get("duration_seconds") is not None
        ]
        dur_b = [
            t["duration_seconds"]
            for t in trials_b
            if t.get("duration_seconds") is not None
        ]

        if len(dur_a) >= 2 and len(dur_b) >= 2:
            stat, p_val = scipy.stats.ttest_ind(dur_a, dur_b, equal_var=False)
            results.append(
                PairwiseTestResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="duration",
                    test_name="welch_t_test",
                    statistic=float(stat),
                    p_value=float(p_val),
                    significant=float(p_val) < 0.05,
                )
            )

        # Input tokens t-test
        itok_a = [float(t.get("input_tokens", 0) or 0) for t in trials_a]
        itok_b = [float(t.get("input_tokens", 0) or 0) for t in trials_b]

        if len(itok_a) >= 2 and len(itok_b) >= 2:
            stat, p_val = scipy.stats.ttest_ind(itok_a, itok_b, equal_var=False)
            results.append(
                PairwiseTestResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="input_tokens",
                    test_name="welch_t_test",
                    statistic=float(stat),
                    p_value=float(p_val),
                    significant=float(p_val) < 0.05,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------


def compute_effect_sizes(
    config_groups: dict[str, list[dict]],
) -> list[EffectSizeResult]:
    """Compute Cohen's d effect sizes for all config pairs and continuous metrics."""
    results: list[EffectSizeResult] = []
    configs = sorted(config_groups.keys())

    for config_a, config_b in combinations(configs, 2):
        trials_a = config_groups[config_a]
        trials_b = config_groups[config_b]

        # Reward
        rewards_a = [t["reward"] for t in trials_a if t.get("reward") is not None]
        rewards_b = [t["reward"] for t in trials_b if t.get("reward") is not None]

        if len(rewards_a) >= 2 and len(rewards_b) >= 2:
            d = _cohens_d(rewards_a, rewards_b)
            results.append(
                EffectSizeResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="reward",
                    cohens_d=d,
                    interpretation=_interpret_cohens_d(d),
                )
            )

        # Duration
        dur_a = [
            t["duration_seconds"]
            for t in trials_a
            if t.get("duration_seconds") is not None
        ]
        dur_b = [
            t["duration_seconds"]
            for t in trials_b
            if t.get("duration_seconds") is not None
        ]

        if len(dur_a) >= 2 and len(dur_b) >= 2:
            d = _cohens_d(dur_a, dur_b)
            results.append(
                EffectSizeResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="duration",
                    cohens_d=d,
                    interpretation=_interpret_cohens_d(d),
                )
            )

        # Input tokens
        itok_a = [float(t.get("input_tokens", 0) or 0) for t in trials_a]
        itok_b = [float(t.get("input_tokens", 0) or 0) for t in trials_b]

        if len(itok_a) >= 2 and len(itok_b) >= 2:
            d = _cohens_d(itok_a, itok_b)
            results.append(
                EffectSizeResult(
                    config_a=config_a,
                    config_b=config_b,
                    metric="input_tokens",
                    cohens_d=d,
                    interpretation=_interpret_cohens_d(d),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------


def analyze(categories: list[dict]) -> dict:
    """Run the full aggregate + pairwise analysis.

    Args:
        categories: The experiment_metrics.json structure (list of category dicts).

    Returns:
        Analysis results dict with aggregate_metrics, pairwise_tests, effect_sizes.
    """
    all_trials = _flatten_trials(categories)

    if not all_trials:
        logger.warning("No trials found in input data")
        return {
            "aggregate_metrics": [],
            "pairwise_tests": [],
            "effect_sizes": [],
        }

    config_groups = _group_by_config(all_trials)

    aggregate = compute_aggregate_metrics(config_groups)
    pairwise = compute_pairwise_tests(config_groups)
    effect_sizes = compute_effect_sizes(config_groups)

    return {
        "aggregate_metrics": [asdict(m) for m in aggregate],
        "pairwise_tests": [asdict(t) for t in pairwise],
        "effect_sizes": [asdict(e) for e in effect_sizes],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the analysis step."""
    parser = argparse.ArgumentParser(
        description="Compute aggregate metrics and pairwise statistical tests.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/experiment_metrics.json"),
        help="Path to experiment_metrics.json (default: output/experiment_metrics.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/analysis_results.json"),
        help="Output path for analysis_results.json (default: output/analysis_results.json)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    input_path: Path = args.input
    output_path: Path = args.output

    if not input_path.is_file():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    try:
        categories = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read input file: %s", exc)
        return 1

    if not isinstance(categories, list):
        logger.error("Input must be a JSON array of category objects")
        return 1

    logger.info("Analyzing metrics from: %s", input_path)
    results = analyze(categories)

    # Summary
    n_agg = len(results["aggregate_metrics"])
    n_tests = len(results["pairwise_tests"])
    n_effects = len(results["effect_sizes"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Analysis complete: %d configs, %d pairwise tests, %d effect sizes -> %s",
        n_agg,
        n_tests,
        n_effects,
        output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
