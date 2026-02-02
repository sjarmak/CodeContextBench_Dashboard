"""
Statistical analysis step for the CCB pipeline.

Consumes experiment_metrics.json and produces analysis_results.json
with aggregate metrics per configuration, pairwise statistical tests,
per-benchmark breakdowns, and per-SDLC-phase analysis.

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

from scripts.ccb_pipeline.sdlc_mapping import get_benchmark_name, get_sdlc_phases

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


@dataclass(frozen=True)
class BenchmarkConfigMetrics:
    """Per-benchmark, per-config metrics."""

    benchmark: str
    config: str
    n_trials: int
    pass_rate: float
    mean_reward: float
    se_reward: float


@dataclass(frozen=True)
class BenchmarkSignificanceResult:
    """Significance test result for a benchmark between two configs."""

    benchmark: str
    config_a: str
    config_b: str
    metric: str
    test_name: str
    statistic: float
    p_value: float
    significant: bool
    mcp_improves: bool  # True if MCP config has better outcome


@dataclass(frozen=True)
class SDLCPhaseMetrics:
    """Per-SDLC-phase, per-config aggregated metrics."""

    sdlc_phase: str
    config: str
    n_trials: int
    pass_rate: float
    mean_reward: float
    mean_reward_delta: float | None  # delta vs BASELINE, None for BASELINE itself


@dataclass(frozen=True)
class EfficiencyMetrics:
    """Token consumption and timing efficiency metrics for a single config."""

    config: str
    n_trials: int
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    mean_input_tokens: float
    se_input_tokens: float
    mean_output_tokens: float
    se_output_tokens: float
    input_to_output_ratio: float | None  # None if output is 0
    median_wall_clock_seconds: float | None
    n_passing: int
    tokens_per_success: float | None  # total tokens / n_passing, None if 0 passing
    mcp_token_overhead: float | None  # delta vs BASELINE mean tokens, None for BASELINE


@dataclass(frozen=True)
class ToolUtilizationConfigMetrics:
    """Tool utilization metrics aggregated for a single config."""

    config: str
    n_trials: int
    mean_mcp_calls: float
    se_mcp_calls: float
    mean_deep_search_calls: float
    se_deep_search_calls: float
    mean_deep_search_vs_keyword_ratio: float
    mean_context_fill_rate: float
    se_context_fill_rate: float


@dataclass(frozen=True)
class ToolRewardCorrelation:
    """Correlation between MCP tool call count and task reward."""

    metric: str  # e.g. "mcp_calls_vs_reward"
    pearson_r: float
    p_value: float
    n_observations: int
    significant: bool  # p < 0.05


@dataclass(frozen=True)
class BenchmarkToolUsage:
    """Tool usage aggregated per benchmark, per config."""

    benchmark: str
    config: str
    n_trials: int
    mean_mcp_calls: float
    mean_deep_search_calls: float
    mean_total_tool_calls: float


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
# Efficiency analysis
# ---------------------------------------------------------------------------


def compute_efficiency_metrics(
    config_groups: dict[str, list[dict]],
) -> list[EfficiencyMetrics]:
    """Compute token consumption and timing efficiency metrics per config.

    Computes total tokens, input-to-output ratio, median wall-clock time,
    tokens-per-success, and MCP token overhead vs BASELINE.
    """
    # First pass: compute baseline mean total tokens for overhead calc
    baseline_mean_total: float | None = None
    if "BASELINE" in config_groups:
        bl_totals = [
            (t.get("input_tokens", 0) or 0)
            + (t.get("output_tokens", 0) or 0)
            for t in config_groups["BASELINE"]
        ]
        baseline_mean_total = _safe_mean([float(x) for x in bl_totals])

    results: list[EfficiencyMetrics] = []

    for config in sorted(config_groups.keys()):
        trials = config_groups[config]
        n = len(trials)

        input_vals = [t.get("input_tokens", 0) or 0 for t in trials]
        output_vals = [t.get("output_tokens", 0) or 0 for t in trials]
        cached_vals = [t.get("cached_tokens", 0) or 0 for t in trials]

        total_input = sum(input_vals)
        total_output = sum(output_vals)
        total_cached = sum(cached_vals)

        input_floats = [float(x) for x in input_vals]
        output_floats = [float(x) for x in output_vals]

        mean_input = _safe_mean(input_floats)
        mean_output = _safe_mean(output_floats)

        input_to_output: float | None = None
        if mean_output > 0:
            input_to_output = mean_input / mean_output

        durations = [
            t["duration_seconds"]
            for t in trials
            if t.get("duration_seconds") is not None
        ]
        median_wall = _safe_median(durations)

        n_passing = sum(1 for t in trials if t.get("pass_fail") == "pass")

        total_tokens = total_input + total_output
        tokens_per_success: float | None = None
        if n_passing > 0:
            tokens_per_success = total_tokens / n_passing

        mcp_overhead: float | None = None
        if config != "BASELINE" and baseline_mean_total is not None:
            mean_total = _safe_mean([float(i + o) for i, o in zip(input_vals, output_vals)])
            mcp_overhead = mean_total - baseline_mean_total

        results.append(
            EfficiencyMetrics(
                config=config,
                n_trials=n,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_cached_tokens=total_cached,
                mean_input_tokens=mean_input,
                se_input_tokens=_safe_se(input_floats),
                mean_output_tokens=mean_output,
                se_output_tokens=_safe_se(output_floats),
                input_to_output_ratio=input_to_output,
                median_wall_clock_seconds=median_wall,
                n_passing=n_passing,
                tokens_per_success=tokens_per_success,
                mcp_token_overhead=mcp_overhead,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Per-benchmark breakdown
# ---------------------------------------------------------------------------


def _get_trial_benchmark(trial: dict) -> str:
    """Extract benchmark name from a trial dict.

    Tries the 'benchmark' field first, then falls back to extracting
    from task_name using get_benchmark_name().
    """
    benchmark = trial.get("benchmark") or ""
    if benchmark and benchmark != "unknown":
        return benchmark
    task_name = trial.get("task_name") or ""
    return get_benchmark_name(task_name)


def _group_by_benchmark(trials: list[dict]) -> dict[str, list[dict]]:
    """Group trials by benchmark name."""
    groups: dict[str, list[dict]] = {}
    for trial in trials:
        benchmark = _get_trial_benchmark(trial)
        if benchmark not in groups:
            groups[benchmark] = []
        groups[benchmark].append(trial)
    return groups


def compute_per_benchmark_metrics(
    trials: list[dict],
) -> list[BenchmarkConfigMetrics]:
    """Compute per-benchmark, per-config metrics."""
    results: list[BenchmarkConfigMetrics] = []
    benchmark_groups = _group_by_benchmark(trials)

    for benchmark in sorted(benchmark_groups.keys()):
        config_groups = _group_by_config(benchmark_groups[benchmark])
        for config in sorted(config_groups.keys()):
            config_trials = config_groups[config]
            n = len(config_trials)
            rewards = [
                t["reward"] for t in config_trials if t.get("reward") is not None
            ]
            pass_count = sum(
                1 for t in config_trials if t.get("pass_fail") == "pass"
            )
            pass_rate = pass_count / n if n > 0 else 0.0

            results.append(
                BenchmarkConfigMetrics(
                    benchmark=benchmark,
                    config=config,
                    n_trials=n,
                    pass_rate=pass_rate,
                    mean_reward=_safe_mean(rewards),
                    se_reward=_safe_se(rewards),
                )
            )

    return results


def compute_per_benchmark_significance(
    trials: list[dict],
) -> list[BenchmarkSignificanceResult]:
    """Run pairwise significance tests per benchmark."""
    results: list[BenchmarkSignificanceResult] = []
    benchmark_groups = _group_by_benchmark(trials)

    for benchmark in sorted(benchmark_groups.keys()):
        config_groups = _group_by_config(benchmark_groups[benchmark])
        configs = sorted(config_groups.keys())

        for config_a, config_b in combinations(configs, 2):
            trials_a = config_groups[config_a]
            trials_b = config_groups[config_b]

            # Pass rate z-test
            n_a = len(trials_a)
            n_b = len(trials_b)
            pass_a = sum(1 for t in trials_a if t.get("pass_fail") == "pass")
            pass_b = sum(1 for t in trials_b if t.get("pass_fail") == "pass")

            if n_a > 0 and n_b > 0:
                z_stat, z_p = _proportion_z_test(pass_a, n_a, pass_b, n_b)
                rate_a = pass_a / n_a
                rate_b = pass_b / n_b
                mcp_improves = _is_mcp_improvement(
                    config_a, config_b, rate_a, rate_b
                )
                is_sig = bool(z_p < 0.05)
                results.append(
                    BenchmarkSignificanceResult(
                        benchmark=benchmark,
                        config_a=config_a,
                        config_b=config_b,
                        metric="pass_rate",
                        test_name="proportion_z_test",
                        statistic=float(z_stat),
                        p_value=float(z_p),
                        significant=is_sig,
                        mcp_improves=bool(mcp_improves and is_sig),
                    )
                )

            # Reward t-test
            rewards_a = [
                t["reward"] for t in trials_a if t.get("reward") is not None
            ]
            rewards_b = [
                t["reward"] for t in trials_b if t.get("reward") is not None
            ]

            if len(rewards_a) >= 2 and len(rewards_b) >= 2:
                stat, p_val = scipy.stats.ttest_ind(
                    rewards_a, rewards_b, equal_var=False
                )
                mean_a = _safe_mean(rewards_a)
                mean_b = _safe_mean(rewards_b)
                mcp_improves = _is_mcp_improvement(
                    config_a, config_b, mean_a, mean_b
                )
                is_sig = bool(float(p_val) < 0.05)
                results.append(
                    BenchmarkSignificanceResult(
                        benchmark=benchmark,
                        config_a=config_a,
                        config_b=config_b,
                        metric="reward",
                        test_name="welch_t_test",
                        statistic=float(stat),
                        p_value=float(p_val),
                        significant=is_sig,
                        mcp_improves=bool(mcp_improves and is_sig),
                    )
                )

    return results


def _is_mcp_improvement(
    config_a: str, config_b: str, value_a: float, value_b: float
) -> bool:
    """Determine if the MCP config shows improvement over BASELINE.

    When comparing two MCP configs, returns True if the 'higher' MCP
    config (MCP_FULL > MCP_BASE) has a better value.
    """
    mcp_order = {"BASELINE": 0, "MCP_BASE": 1, "MCP_FULL": 2}
    rank_a = mcp_order.get(config_a, 0)
    rank_b = mcp_order.get(config_b, 0)

    if rank_b > rank_a:
        # config_b is the more advanced MCP config
        return value_b > value_a
    # config_a is the more advanced MCP config
    return value_a > value_b


# ---------------------------------------------------------------------------
# Per-SDLC-phase breakdown
# ---------------------------------------------------------------------------


def compute_per_sdlc_phase_metrics(
    trials: list[dict],
) -> list[SDLCPhaseMetrics]:
    """Compute per-SDLC-phase, per-config aggregated metrics.

    A trial can belong to multiple SDLC phases (e.g. "Implementation" and "Testing").
    """
    # Build phase -> config -> trials mapping
    phase_config_trials: dict[str, dict[str, list[dict]]] = {}

    for trial in trials:
        benchmark = _get_trial_benchmark(trial)
        phases = get_sdlc_phases(benchmark)
        config = trial.get("agent_config", "UNKNOWN")

        for phase in phases:
            if phase not in phase_config_trials:
                phase_config_trials[phase] = {}
            if config not in phase_config_trials[phase]:
                phase_config_trials[phase][config] = []
            phase_config_trials[phase][config].append(trial)

    # Compute baseline mean reward per phase for delta calculation
    baseline_mean_by_phase: dict[str, float] = {}
    for phase, config_trials in phase_config_trials.items():
        if "BASELINE" in config_trials:
            bl_rewards = [
                t["reward"]
                for t in config_trials["BASELINE"]
                if t.get("reward") is not None
            ]
            baseline_mean_by_phase[phase] = _safe_mean(bl_rewards)

    results: list[SDLCPhaseMetrics] = []

    for phase in sorted(phase_config_trials.keys()):
        for config in sorted(phase_config_trials[phase].keys()):
            phase_trials = phase_config_trials[phase][config]
            n = len(phase_trials)
            rewards = [
                t["reward"] for t in phase_trials if t.get("reward") is not None
            ]
            pass_count = sum(
                1 for t in phase_trials if t.get("pass_fail") == "pass"
            )
            pass_rate = pass_count / n if n > 0 else 0.0
            mean_reward = _safe_mean(rewards)

            delta: float | None = None
            if config != "BASELINE" and phase in baseline_mean_by_phase:
                delta = mean_reward - baseline_mean_by_phase[phase]

            results.append(
                SDLCPhaseMetrics(
                    sdlc_phase=phase,
                    config=config,
                    n_trials=n,
                    pass_rate=pass_rate,
                    mean_reward=mean_reward,
                    mean_reward_delta=delta,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Tool utilization analysis
# ---------------------------------------------------------------------------


def _get_tool_util(trial: dict, field: str) -> float:
    """Safely extract a numeric field from a trial's tool_utilization dict."""
    util = trial.get("tool_utilization") or {}
    val = util.get(field, 0)
    if val is None:
        return 0.0
    return float(val)


def compute_tool_utilization_config_metrics(
    config_groups: dict[str, list[dict]],
) -> list[ToolUtilizationConfigMetrics]:
    """Compute per-config tool utilization metrics.

    Computes mean MCP calls, mean Deep Search calls, Deep Search vs keyword ratio,
    and context window fill rate per configuration.
    """
    results: list[ToolUtilizationConfigMetrics] = []

    for config in sorted(config_groups.keys()):
        trials = config_groups[config]
        n = len(trials)

        mcp_vals = [_get_tool_util(t, "mcp_calls") for t in trials]
        ds_vals = [_get_tool_util(t, "deep_search_calls") for t in trials]
        ratio_vals = [_get_tool_util(t, "deep_search_vs_keyword_ratio") for t in trials]
        fill_vals = [_get_tool_util(t, "context_fill_rate") for t in trials]

        results.append(
            ToolUtilizationConfigMetrics(
                config=config,
                n_trials=n,
                mean_mcp_calls=_safe_mean(mcp_vals),
                se_mcp_calls=_safe_se(mcp_vals),
                mean_deep_search_calls=_safe_mean(ds_vals),
                se_deep_search_calls=_safe_se(ds_vals),
                mean_deep_search_vs_keyword_ratio=_safe_mean(ratio_vals),
                mean_context_fill_rate=_safe_mean(fill_vals),
                se_context_fill_rate=_safe_se(fill_vals),
            )
        )

    return results


def compute_tool_reward_correlation(
    trials: list[dict],
) -> list[ToolRewardCorrelation]:
    """Compute Pearson correlation between MCP tool call count and task reward.

    Only includes trials with non-None reward and tool_utilization data.
    """
    # Filter to trials with both reward and tool utilization
    valid_pairs: list[tuple[float, float]] = []
    for trial in trials:
        reward = trial.get("reward")
        if reward is None:
            continue
        mcp_calls = _get_tool_util(trial, "mcp_calls")
        valid_pairs.append((mcp_calls, float(reward)))

    results: list[ToolRewardCorrelation] = []

    if len(valid_pairs) < 3:
        # Need at least 3 observations for meaningful correlation
        return results

    mcp_values = [p[0] for p in valid_pairs]
    reward_values = [p[1] for p in valid_pairs]

    # Check for zero variance (Pearson r is undefined)
    if len(set(mcp_values)) < 2 or len(set(reward_values)) < 2:
        return results

    r_stat, p_val = scipy.stats.pearsonr(mcp_values, reward_values)

    results.append(
        ToolRewardCorrelation(
            metric="mcp_calls_vs_reward",
            pearson_r=float(r_stat),
            p_value=float(p_val),
            n_observations=len(valid_pairs),
            significant=bool(float(p_val) < 0.05),
        )
    )

    return results


def compute_benchmark_tool_usage(
    trials: list[dict],
) -> list[BenchmarkToolUsage]:
    """Group tool usage by benchmark and config to identify where MCP is most/least used."""
    benchmark_groups = _group_by_benchmark(trials)
    results: list[BenchmarkToolUsage] = []

    for benchmark in sorted(benchmark_groups.keys()):
        config_groups = _group_by_config(benchmark_groups[benchmark])
        for config in sorted(config_groups.keys()):
            config_trials = config_groups[config]
            n = len(config_trials)

            mcp_vals = [_get_tool_util(t, "mcp_calls") for t in config_trials]
            ds_vals = [_get_tool_util(t, "deep_search_calls") for t in config_trials]
            total_vals = [_get_tool_util(t, "total_tool_calls") for t in config_trials]

            results.append(
                BenchmarkToolUsage(
                    benchmark=benchmark,
                    config=config,
                    n_trials=n,
                    mean_mcp_calls=_safe_mean(mcp_vals),
                    mean_deep_search_calls=_safe_mean(ds_vals),
                    mean_total_tool_calls=_safe_mean(total_vals),
                )
            )

    return results


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------


def analyze(categories: list[dict]) -> dict:
    """Run the full aggregate + pairwise + per-benchmark + per-SDLC + tool utilization analysis.

    Args:
        categories: The experiment_metrics.json structure (list of category dicts).

    Returns:
        Analysis results dict with aggregate_metrics, pairwise_tests,
        effect_sizes, per_benchmark, per_sdlc_phase, efficiency,
        tool_utilization, tool_reward_correlation, and benchmark_tool_usage sections.
    """
    all_trials = _flatten_trials(categories)

    if not all_trials:
        logger.warning("No trials found in input data")
        return {
            "aggregate_metrics": [],
            "pairwise_tests": [],
            "effect_sizes": [],
            "per_benchmark": [],
            "per_benchmark_significance": [],
            "per_sdlc_phase": [],
            "efficiency": [],
            "tool_utilization": [],
            "tool_reward_correlation": [],
            "benchmark_tool_usage": [],
        }

    config_groups = _group_by_config(all_trials)

    aggregate = compute_aggregate_metrics(config_groups)
    pairwise = compute_pairwise_tests(config_groups)
    effect_sizes = compute_effect_sizes(config_groups)
    per_benchmark = compute_per_benchmark_metrics(all_trials)
    per_benchmark_sig = compute_per_benchmark_significance(all_trials)
    per_sdlc = compute_per_sdlc_phase_metrics(all_trials)
    efficiency = compute_efficiency_metrics(config_groups)
    tool_util = compute_tool_utilization_config_metrics(config_groups)
    tool_corr = compute_tool_reward_correlation(all_trials)
    bench_tool = compute_benchmark_tool_usage(all_trials)

    return {
        "aggregate_metrics": [asdict(m) for m in aggregate],
        "pairwise_tests": [asdict(t) for t in pairwise],
        "effect_sizes": [asdict(e) for e in effect_sizes],
        "per_benchmark": [asdict(b) for b in per_benchmark],
        "per_benchmark_significance": [asdict(s) for s in per_benchmark_sig],
        "per_sdlc_phase": [asdict(p) for p in per_sdlc],
        "efficiency": [asdict(e) for e in efficiency],
        "tool_utilization": [asdict(u) for u in tool_util],
        "tool_reward_correlation": [asdict(c) for c in tool_corr],
        "benchmark_tool_usage": [asdict(b) for b in bench_tool],
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
    n_benchmarks = len(results["per_benchmark"])
    n_phases = len(results["per_sdlc_phase"])
    n_efficiency = len(results["efficiency"])
    n_tool_util = len(results["tool_utilization"])
    n_tool_corr = len(results["tool_reward_correlation"])
    n_bench_tool = len(results["benchmark_tool_usage"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "Analysis complete: %d configs, %d pairwise tests, %d effect sizes, "
        "%d benchmark entries, %d SDLC phase entries, %d efficiency entries, "
        "%d tool utilization entries, %d tool correlations, %d benchmark tool entries -> %s",
        n_agg,
        n_tests,
        n_effects,
        n_benchmarks,
        n_phases,
        n_efficiency,
        n_tool_util,
        n_tool_corr,
        n_bench_tool,
        output_path,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
