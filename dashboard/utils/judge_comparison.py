"""
Comparative judge utilities for task-pair evaluation.

Matches tasks across baseline/variant runs, computes metric deltas,
and runs side-by-side LLM judge evaluation.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


BASELINE_MODES = {"baseline", "single"}
VARIANT_MODES = {"deepsearch", "sourcegraph_hybrid", "sourcegraph", "mcp"}


@dataclass(frozen=True)
class TaskPairMetrics:
    """Quantitative deltas between baseline and variant runs of a task."""

    task_name: str
    baseline_reward: float
    variant_reward: float
    reward_delta: float
    baseline_input_tokens: int
    variant_input_tokens: int
    token_delta: int
    baseline_duration: float | None
    variant_duration: float | None
    duration_delta: float | None
    baseline_mcp_calls: int
    variant_mcp_calls: int


@dataclass(frozen=True)
class TaskPairJudgeResult:
    """LLM judge scores for both sides of a task pair."""

    task_name: str
    dimensions: tuple[str, ...]
    baseline_scores: dict[str, float]
    variant_scores: dict[str, float]
    score_deltas: dict[str, float]
    baseline_reasoning: dict[str, str]
    variant_reasoning: dict[str, str]
    judge_model: str
    error: str | None = None


@dataclass(frozen=True)
class ComparativeReport:
    """Full comparative evaluation report."""

    benchmark: str
    timestamp: str
    judge_model: str
    dimensions: tuple[str, ...]
    pairs: tuple[TaskPairJudgeResult, ...]
    metrics: tuple[TaskPairMetrics, ...]
    summary: dict


def find_matched_pairs(
    task_index: dict[str, list[dict]],
    benchmark: str,
) -> list[tuple[str, dict, dict]]:
    """Find tasks that have both a baseline and variant run.

    Matching strategy:
    1. For each task, find baseline runs and variant runs.
    2. For each variant, prefer a baseline from the same experiment.
    3. Fall back to any baseline if no same-experiment match exists.

    Args:
        task_index: Mapping of task_name -> list of run dicts
            (from _build_task_index()[benchmark]).
        benchmark: Benchmark name (for logging context).

    Returns:
        List of (task_name, baseline_run, variant_run) tuples.
    """
    pairs: list[tuple[str, dict, dict]] = []

    for task_name, runs in task_index.items():
        baselines = [r for r in runs if r.get("mode_label") in BASELINE_MODES or r.get("mode") in BASELINE_MODES]
        variants = [r for r in runs if r.get("mode_label") in VARIANT_MODES or r.get("mode") in VARIANT_MODES]

        if not baselines or not variants:
            continue

        for variant in variants:
            # Prefer same-experiment baseline
            same_exp = [b for b in baselines if b["exp_name"] == variant["exp_name"]]
            baseline = same_exp[0] if same_exp else baselines[0]
            pairs.append((task_name, baseline, variant))
            break  # One pair per task

    return sorted(pairs, key=lambda p: p[0])


def compute_pair_metrics(
    task_name: str,
    baseline_run: dict,
    variant_run: dict,
) -> TaskPairMetrics:
    """Compute reward/token/duration/tool deltas between baseline and variant.

    Args:
        task_name: The task identifier.
        baseline_run: Run dict for the baseline.
        variant_run: Run dict for the variant.

    Returns:
        TaskPairMetrics with all computed deltas.
    """
    b_reward = baseline_run.get("reward", 0.0) or 0.0
    v_reward = variant_run.get("reward", 0.0) or 0.0

    b_tokens = baseline_run.get("input_tokens", 0) or 0
    v_tokens = variant_run.get("input_tokens", 0) or 0

    b_dur = baseline_run.get("duration")
    v_dur = variant_run.get("duration")
    dur_delta: float | None = None
    if b_dur is not None and v_dur is not None:
        dur_delta = v_dur - b_dur

    b_mcp = _count_mcp_calls(baseline_run)
    v_mcp = _count_mcp_calls(variant_run)

    return TaskPairMetrics(
        task_name=task_name,
        baseline_reward=b_reward,
        variant_reward=v_reward,
        reward_delta=v_reward - b_reward,
        baseline_input_tokens=b_tokens,
        variant_input_tokens=v_tokens,
        token_delta=v_tokens - b_tokens,
        baseline_duration=b_dur,
        variant_duration=v_dur,
        duration_delta=dur_delta,
        baseline_mcp_calls=b_mcp,
        variant_mcp_calls=v_mcp,
    )


def _count_mcp_calls(run: dict) -> int:
    """Count MCP tool calls from a run dict's tool_counts or mcp_tool_count."""
    if "mcp_tool_count" in run:
        return run["mcp_tool_count"] or 0
    tool_counts = run.get("tool_counts") or {}
    return sum(v for k, v in tool_counts.items() if k.startswith("mcp__"))


def evaluate_pair(
    task_name: str,
    baseline_run: dict,
    variant_run: dict,
    judge: Any,
    dimensions: list[str],
) -> TaskPairJudgeResult:
    """Run LLM judge on both sides of a task pair, compute score deltas.

    Args:
        task_name: The task identifier.
        baseline_run: Run dict for baseline (must have 'instance_dir').
        variant_run: Run dict for variant (must have 'instance_dir').
        judge: An EnhancedLLMJudge instance.
        dimensions: List of dimension names to evaluate.

    Returns:
        TaskPairJudgeResult with scores for both sides.
    """
    from dashboard.utils.judge_task_loader import build_judge_input, load_task_instance

    dim_mapping = {
        "code_quality": "code_quality",
        "correctness": "correctness",
        "completeness": "completeness",
        "retrieval_quality": "retrieval",
        "mcp_effectiveness": "mcp_effectiveness",
    }

    baseline_scores: dict[str, float] = {}
    variant_scores: dict[str, float] = {}
    baseline_reasoning: dict[str, str] = {}
    variant_reasoning: dict[str, str] = {}
    error: str | None = None

    try:
        b_data = load_task_instance(Path(baseline_run["instance_dir"]))
        v_data = load_task_instance(Path(variant_run["instance_dir"]))
        b_input = build_judge_input(b_data)
        v_input = build_judge_input(v_data)

        for dim in dimensions:
            enhanced_dim = dim_mapping.get(dim, dim)
            try:
                b_result = judge.evaluate(b_input, enhanced_dim)
                baseline_scores[dim] = b_result.score
                baseline_reasoning[dim] = b_result.reasoning
            except (ValueError, Exception) as e:
                baseline_scores[dim] = 0.0
                baseline_reasoning[dim] = f"Error: {e}"

            try:
                v_result = judge.evaluate(v_input, enhanced_dim)
                variant_scores[dim] = v_result.score
                variant_reasoning[dim] = v_result.reasoning
            except (ValueError, Exception) as e:
                variant_scores[dim] = 0.0
                variant_reasoning[dim] = f"Error: {e}"

    except Exception as e:
        error = str(e)

    score_deltas = {
        dim: variant_scores.get(dim, 0.0) - baseline_scores.get(dim, 0.0)
        for dim in dimensions
    }

    return TaskPairJudgeResult(
        task_name=task_name,
        dimensions=tuple(dimensions),
        baseline_scores=baseline_scores,
        variant_scores=variant_scores,
        score_deltas=score_deltas,
        baseline_reasoning=baseline_reasoning,
        variant_reasoning=variant_reasoning,
        judge_model=getattr(judge, "model", "unknown"),
        error=error,
    )


def build_comparative_report(
    benchmark: str,
    pair_results: list[TaskPairJudgeResult],
    pair_metrics: list[TaskPairMetrics],
    judge_model: str,
    dimensions: list[str],
) -> ComparativeReport:
    """Assemble a full comparative report with summary statistics.

    Computes mean deltas, win/tie/loss counts across all pairs.

    Args:
        benchmark: Benchmark suite name.
        pair_results: Judge results for each task pair.
        pair_metrics: Quantitative metrics for each pair.
        judge_model: Model used for judging.
        dimensions: Dimensions evaluated.

    Returns:
        ComparativeReport with summary aggregation.
    """
    # Compute reward summary from metrics
    reward_deltas = [m.reward_delta for m in pair_metrics]
    mean_reward_delta = sum(reward_deltas) / len(reward_deltas) if reward_deltas else 0.0

    # Win/tie/loss by reward
    variant_wins = sum(1 for d in reward_deltas if d > 0)
    ties = sum(1 for d in reward_deltas if d == 0)
    variant_losses = sum(1 for d in reward_deltas if d < 0)

    # Mean score deltas per dimension
    mean_score_deltas: dict[str, float] = {}
    for dim in dimensions:
        deltas = [r.score_deltas.get(dim, 0.0) for r in pair_results if not r.error]
        mean_score_deltas[dim] = sum(deltas) / len(deltas) if deltas else 0.0

    summary = {
        "mean_reward_delta": round(mean_reward_delta, 4),
        "mean_score_deltas": {k: round(v, 4) for k, v in mean_score_deltas.items()},
        "variant_wins": variant_wins,
        "ties": ties,
        "variant_losses": variant_losses,
        "total_pairs": len(pair_metrics),
        "judge_errors": sum(1 for r in pair_results if r.error),
    }

    return ComparativeReport(
        benchmark=benchmark,
        timestamp=datetime.now().isoformat(),
        judge_model=judge_model,
        dimensions=tuple(dimensions),
        pairs=tuple(pair_results),
        metrics=tuple(pair_metrics),
        summary=summary,
    )


def save_comparative_report(report: ComparativeReport, output_dir: Path) -> Path:
    """Save a comparative report to JSON.

    Args:
        report: The report to save.
        output_dir: Base directory for judge results (e.g., data/judge_results).

    Returns:
        Path to the saved JSON file.
    """
    comp_dir = output_dir / "comparative"
    comp_dir.mkdir(parents=True, exist_ok=True)

    safe_benchmark = report.benchmark.replace(" ", "_").replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_benchmark}_{ts}_comparative.json"
    filepath = comp_dir / filename

    data = {
        "type": "comparative",
        "benchmark": report.benchmark,
        "timestamp": report.timestamp,
        "judge_model": report.judge_model,
        "dimensions": list(report.dimensions),
        "total_pairs": len(report.pairs),
        "summary": report.summary,
        "pairs": [
            {
                "task_name": p.task_name,
                "dimensions": list(p.dimensions),
                "baseline_scores": p.baseline_scores,
                "variant_scores": p.variant_scores,
                "score_deltas": p.score_deltas,
                "baseline_reasoning": p.baseline_reasoning,
                "variant_reasoning": p.variant_reasoning,
                "judge_model": p.judge_model,
                "error": p.error,
            }
            for p in report.pairs
        ],
        "metrics": [
            {
                "task_name": m.task_name,
                "baseline_reward": m.baseline_reward,
                "variant_reward": m.variant_reward,
                "reward_delta": m.reward_delta,
                "baseline_input_tokens": m.baseline_input_tokens,
                "variant_input_tokens": m.variant_input_tokens,
                "token_delta": m.token_delta,
                "baseline_duration": m.baseline_duration,
                "variant_duration": m.variant_duration,
                "duration_delta": m.duration_delta,
                "baseline_mcp_calls": m.baseline_mcp_calls,
                "variant_mcp_calls": m.variant_mcp_calls,
            }
            for m in report.metrics
        ],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return filepath


def load_comparative_reports(output_dir: Path) -> list[dict]:
    """Load all saved comparative reports.

    Args:
        output_dir: Base directory for judge results.

    Returns:
        List of report dicts, newest first.
    """
    comp_dir = output_dir / "comparative"
    if not comp_dir.exists():
        return []

    reports: list[dict] = []
    for report_file in sorted(comp_dir.glob("*_comparative.json"), reverse=True):
        try:
            with open(report_file) as f:
                data = json.load(f)
                data["_file"] = report_file.name
                data["_path"] = str(report_file)
                reports.append(data)
        except (json.JSONDecodeError, OSError):
            pass

    return reports
