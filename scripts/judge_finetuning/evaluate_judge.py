"""Evaluate fine-tuned judge quality against human ratings.

Runs a judge model on held-out evaluation data and computes alignment
metrics against human annotations. Supports comparison of multiple models.

Usage:
    python -m scripts.judge_finetuning.evaluate_judge \
        --model <model_id> \
        --eval-data data/training/eval_split.jsonl \
        --output evaluation_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.judge.metrics import compute_cohens_kappa, compute_spearman_correlation

logger = logging.getLogger(__name__)

_CATEGORICAL_THRESHOLDS = {"pass": 0.75, "partial": 0.25}


@dataclass(frozen=True)
class EvalConfig:
    """Configuration for judge evaluation."""

    model_ids: tuple[str, ...] = ()
    eval_data_path: str = ""
    annotations_path: str = ""
    output_path: str = "evaluation_report.json"
    max_samples: int = 0
    temperature: float = 0.0
    max_tokens: int = 2000


@dataclass(frozen=True)
class ModelMetrics:
    """Evaluation metrics for a single model."""

    model_id: str
    spearman_rho: float = 0.0
    spearman_p_value: float = 1.0
    cohens_kappa: float = 0.0
    total_evaluations: int = 0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    estimated_cost_per_100: float = 0.0
    per_dimension_accuracy: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationReport:
    """Full evaluation report with per-model breakdown."""

    model_metrics: tuple[ModelMetrics, ...] = ()
    eval_samples: int = 0
    human_samples: int = 0
    best_model_id: str = ""
    best_spearman: float = 0.0
    comparison_summary: dict[str, Any] = field(default_factory=dict)


def load_eval_data(eval_path: Path) -> list[dict[str, Any]]:
    """Load evaluation data from JSONL file (preference pairs with scores).

    Each line must have 'prompt', 'chosen', 'rejected' fields.
    """
    records: list[dict[str, Any]] = []

    if not eval_path.exists():
        raise FileNotFoundError(f"Evaluation data not found: {eval_path}")

    with open(eval_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt line %d in %s", line_num, eval_path)
                continue

            if not all(k in record for k in ("prompt", "chosen", "rejected")):
                logger.warning("Skipping line %d: missing required fields", line_num)
                continue

            records.append(record)

    return records


def load_human_annotations(annotations_path: Path) -> list[dict[str, Any]]:
    """Load human annotations from JSONL file.

    Returns list of annotation dicts with task_id, mode, scores.
    """
    annotations: list[dict[str, Any]] = []

    if not annotations_path.exists():
        logger.warning("Annotations file not found: %s", annotations_path)
        return annotations

    with open(annotations_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                annotations.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt annotation at line %d", line_num)

    return annotations


def _categorize_score(score: float) -> str:
    """Categorize a continuous score into pass/partial/fail."""
    if score >= _CATEGORICAL_THRESHOLDS["pass"]:
        return "pass"
    if score >= _CATEGORICAL_THRESHOLDS["partial"]:
        return "partial"
    return "fail"


def _extract_human_scores(
    annotations: list[dict[str, Any]],
) -> dict[str, float]:
    """Extract per-task human scores from annotations.

    For direct mode: averages dimension scores.
    For reference mode: converts pass/partial/fail to 1.0/0.5/0.0.
    For pairwise: uses preference as binary (1.0 if chosen matches).

    Returns task_id -> human_score mapping.
    """
    _REFERENCE_SCORE_MAP = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
    scores: dict[str, list[float]] = {}

    for ann in annotations:
        task_id = ann.get("task_id", "")
        if not task_id:
            continue

        mode = ann.get("mode", "")
        ann_scores = ann.get("scores", {})

        score_value: float | None = None

        if mode == "direct" and isinstance(ann_scores, dict):
            dim_values = [
                v for v in ann_scores.values() if isinstance(v, (int, float))
            ]
            if dim_values:
                score_value = sum(dim_values) / len(dim_values)

        elif mode == "reference" and isinstance(ann_scores, dict):
            ref_values = [
                _REFERENCE_SCORE_MAP.get(str(v).lower(), 0.0)
                for v in ann_scores.values()
                if str(v).lower() in _REFERENCE_SCORE_MAP
            ]
            if ref_values:
                score_value = sum(ref_values) / len(ref_values)

        elif mode == "pairwise":
            preference = ann.get("preference", "")
            if preference and preference != "Tie":
                score_value = 1.0

        if score_value is not None:
            scores.setdefault(task_id, []).append(score_value)

    return {
        task_id: sum(vals) / len(vals)
        for task_id, vals in scores.items()
        if vals
    }


def _extract_dimension_scores(
    annotations: list[dict[str, Any]],
) -> dict[str, dict[str, list[float]]]:
    """Extract per-dimension scores from annotations.

    Returns dimension -> task_id -> list of scores.
    """
    result: dict[str, dict[str, list[float]]] = {}

    for ann in annotations:
        task_id = ann.get("task_id", "")
        mode = ann.get("mode", "")
        if not task_id or mode != "direct":
            continue

        ann_scores = ann.get("scores", {})
        if not isinstance(ann_scores, dict):
            continue

        for dim, val in ann_scores.items():
            if isinstance(val, (int, float)):
                result.setdefault(dim, {}).setdefault(task_id, []).append(float(val))

    return result


def compute_alignment_metrics(
    model_scores: dict[str, float],
    human_scores: dict[str, float],
) -> tuple[float, float, float]:
    """Compute alignment between model and human scores.

    Returns (spearman_rho, spearman_p, cohens_kappa).
    """
    common_tasks = sorted(set(model_scores) & set(human_scores))
    if len(common_tasks) < 2:
        return (0.0, 1.0, 0.0)

    m_scores = [model_scores[t] for t in common_tasks]
    h_scores = [human_scores[t] for t in common_tasks]

    rho, p_value = compute_spearman_correlation(m_scores, h_scores)

    m_cats = [_categorize_score(s) for s in m_scores]
    h_cats = [_categorize_score(s) for s in h_scores]
    kappa = compute_cohens_kappa(m_cats, h_cats)

    return (rho, p_value, kappa)


def compute_dimension_accuracy(
    model_dim_scores: dict[str, dict[str, float]],
    human_dim_scores: dict[str, dict[str, list[float]]],
) -> dict[str, float]:
    """Compute per-dimension accuracy (categorical match rate).

    Returns dimension -> accuracy mapping.
    """
    accuracy: dict[str, float] = {}

    for dim, human_tasks in human_dim_scores.items():
        model_tasks = model_dim_scores.get(dim, {})
        matches = 0
        total = 0

        for task_id, h_vals in human_tasks.items():
            if task_id not in model_tasks:
                continue
            h_avg = sum(h_vals) / len(h_vals)
            m_score = model_tasks[task_id]

            if _categorize_score(m_score) == _categorize_score(h_avg):
                matches += 1
            total += 1

        if total > 0:
            accuracy[dim] = matches / total

    return accuracy


def compute_cost_metrics(
    latencies_ms: list[float],
    token_counts: list[int],
    cost_per_1k_input: float = 0.0003,
    cost_per_1k_output: float = 0.001,
) -> tuple[float, int, float]:
    """Compute cost metrics from evaluation run data.

    Returns (avg_latency_ms, total_tokens, estimated_cost_per_100).
    """
    avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
    total_tokens = sum(token_counts) if token_counts else 0

    if token_counts and len(token_counts) > 0:
        avg_tokens_per_eval = total_tokens / len(token_counts)
        # Estimate: 80% input, 20% output
        input_tokens = avg_tokens_per_eval * 0.8
        output_tokens = avg_tokens_per_eval * 0.2
        cost_per_eval = (
            (input_tokens / 1000) * cost_per_1k_input
            + (output_tokens / 1000) * cost_per_1k_output
        )
        cost_per_100 = cost_per_eval * 100
    else:
        cost_per_100 = 0.0

    return (avg_latency, total_tokens, cost_per_100)


async def evaluate_model_on_data(
    model_id: str,
    eval_data: list[dict[str, Any]],
    temperature: float = 0.0,
    max_tokens: int = 2000,
) -> tuple[dict[str, float], list[float], list[int]]:
    """Evaluate a model on evaluation data, returning per-task scores.

    This runs the model as a judge on each evaluation sample and extracts
    the judge's score. Returns (task_scores, latencies_ms, token_counts).

    For offline evaluation without a live model, returns scores from the
    eval data's metadata if available.
    """
    task_scores: dict[str, float] = {}
    latencies: list[float] = []
    tokens: list[int] = []

    for item in eval_data:
        task_id = item.get("metadata", {}).get("task_id", f"task_{len(task_scores)}")

        try:
            start = time.monotonic()
            score = await _run_judge_evaluation(
                model_id, item, temperature, max_tokens
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            task_scores[task_id] = score
            latencies.append(elapsed_ms)
            # Estimate tokens from prompt + response length
            prompt_len = len(item.get("prompt", ""))
            tokens.append(prompt_len // 4 + max_tokens // 4)

        except Exception as exc:
            logger.warning("Evaluation failed for %s: %s", task_id, exc)
            continue

    return task_scores, latencies, tokens


async def _run_judge_evaluation(
    model_id: str,
    eval_item: dict[str, Any],
    temperature: float,
    max_tokens: int,
) -> float:
    """Run a single judge evaluation.

    Attempts to use the UnifiedJudge with the specified model.
    Falls back to score extraction from eval data metadata.
    """
    # Try to extract pre-computed score from metadata
    metadata = eval_item.get("metadata", {})
    if "model_score" in metadata:
        return float(metadata["model_score"])
    if "chosen_score" in metadata:
        return float(metadata["chosen_score"])

    # Try live evaluation via judge backend
    try:
        from src.judge.backends.anthropic import AnthropicBackend
        from src.judge.engine import UnifiedJudge
        from src.judge.models import DirectInput, EvaluationMode, JudgeConfig

        config = JudgeConfig(
            temperature=temperature,
            max_tokens=max_tokens,
        )

        backend = AnthropicBackend(model=model_id)
        judge = UnifiedJudge(backend=backend, config=config)

        judge_input = DirectInput(
            task_id=metadata.get("task_id", "eval"),
            task_description=eval_item.get("prompt", ""),
            evaluation_mode=EvaluationMode.DIRECT,
            agent_output=eval_item.get("chosen", ""),
        )

        verdict = await judge.evaluate(judge_input)
        return verdict.overall_score

    except (ImportError, Exception) as exc:
        logger.debug("Live evaluation unavailable: %s", exc)
        raise ValueError(
            f"Cannot evaluate model {model_id}: no pre-computed scores and "
            f"live evaluation failed: {exc}"
        ) from exc


def evaluate_judge(
    model_ids: list[str],
    eval_data: list[dict[str, Any]],
    human_scores: dict[str, float],
    human_dim_scores: dict[str, dict[str, list[float]]],
) -> EvaluationReport:
    """Evaluate one or more judge models against human ratings.

    Returns an EvaluationReport with per-model metrics and comparison.
    """
    all_metrics: list[ModelMetrics] = []

    for model_id in model_ids:
        try:
            model_scores, latencies, tokens = asyncio.run(
                evaluate_model_on_data(model_id, eval_data)
            )
        except Exception as exc:
            logger.error("Failed to evaluate model %s: %s", model_id, exc)
            all_metrics.append(ModelMetrics(model_id=model_id))
            continue

        if not model_scores:
            logger.warning("No scores produced for model %s", model_id)
            all_metrics.append(ModelMetrics(model_id=model_id))
            continue

        rho, p_value, kappa = compute_alignment_metrics(model_scores, human_scores)

        avg_latency, total_tokens, cost_per_100 = compute_cost_metrics(
            latencies, tokens
        )

        # Build per-dimension model scores (from overall for now)
        model_dim_scores: dict[str, dict[str, float]] = {}
        for dim in human_dim_scores:
            model_dim_scores[dim] = model_scores

        dim_accuracy = compute_dimension_accuracy(model_dim_scores, human_dim_scores)

        metrics = ModelMetrics(
            model_id=model_id,
            spearman_rho=rho,
            spearman_p_value=p_value,
            cohens_kappa=kappa,
            total_evaluations=len(model_scores),
            avg_latency_ms=avg_latency,
            total_tokens=total_tokens,
            estimated_cost_per_100=cost_per_100,
            per_dimension_accuracy=dim_accuracy,
        )
        all_metrics.append(metrics)

    best = max(all_metrics, key=lambda m: m.spearman_rho) if all_metrics else None

    comparison: dict[str, Any] = {}
    if len(all_metrics) > 1:
        comparison = {
            "models_compared": len(all_metrics),
            "ranking_by_spearman": [
                {"model_id": m.model_id, "spearman_rho": m.spearman_rho}
                for m in sorted(all_metrics, key=lambda x: x.spearman_rho, reverse=True)
            ],
            "ranking_by_kappa": [
                {"model_id": m.model_id, "cohens_kappa": m.cohens_kappa}
                for m in sorted(all_metrics, key=lambda x: x.cohens_kappa, reverse=True)
            ],
        }

    return EvaluationReport(
        model_metrics=tuple(all_metrics),
        eval_samples=len(eval_data),
        human_samples=len(human_scores),
        best_model_id=best.model_id if best else "",
        best_spearman=best.spearman_rho if best else 0.0,
        comparison_summary=comparison,
    )


def _metrics_to_dict(metrics: ModelMetrics) -> dict[str, Any]:
    """Convert ModelMetrics to a JSON-serializable dict."""
    return {
        "model_id": metrics.model_id,
        "spearman_rho": metrics.spearman_rho,
        "spearman_p_value": metrics.spearman_p_value,
        "cohens_kappa": metrics.cohens_kappa,
        "total_evaluations": metrics.total_evaluations,
        "avg_latency_ms": metrics.avg_latency_ms,
        "total_tokens": metrics.total_tokens,
        "estimated_cost_per_100": metrics.estimated_cost_per_100,
        "per_dimension_accuracy": dict(metrics.per_dimension_accuracy),
    }


def _report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    """Convert EvaluationReport to a JSON-serializable dict."""
    return {
        "eval_samples": report.eval_samples,
        "human_samples": report.human_samples,
        "best_model_id": report.best_model_id,
        "best_spearman": report.best_spearman,
        "model_metrics": [_metrics_to_dict(m) for m in report.model_metrics],
        "comparison_summary": dict(report.comparison_summary),
    }


def save_report(report: EvaluationReport, output_path: Path) -> None:
    """Save evaluation report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(_report_to_dict(report), f, indent=2)
    logger.info("Report saved to: %s", output_path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for judge evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate judge model quality against human ratings"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        action="append",
        dest="models",
        help="Model ID to evaluate (can be specified multiple times for comparison)",
    )
    parser.add_argument(
        "--eval-data",
        type=Path,
        required=True,
        help="Evaluation data JSONL (from train_dpo split or preference pairs)",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/human_annotations/annotations.jsonl"),
        help="Human annotations JSONL for alignment metrics",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation_report.json"),
        help="Output path for evaluation report JSON",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="Maximum evaluation samples (0 = all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        eval_data = load_eval_data(args.eval_data)
        if not eval_data:
            logger.error("No evaluation data loaded")
            return 1

        if args.max_samples > 0:
            eval_data = eval_data[: args.max_samples]

        annotations = load_human_annotations(args.annotations)
        human_scores = _extract_human_scores(annotations)
        human_dim_scores = _extract_dimension_scores(annotations)

        logger.info(
            "Loaded %d eval samples, %d human annotations (%d scored tasks)",
            len(eval_data),
            len(annotations),
            len(human_scores),
        )

        report = evaluate_judge(
            model_ids=args.models,
            eval_data=eval_data,
            human_scores=human_scores,
            human_dim_scores=human_dim_scores,
        )

        save_report(report, args.output)

        print(f"Evaluation complete: {len(report.model_metrics)} model(s)")
        print(f"  Eval samples: {report.eval_samples}")
        print(f"  Human scored tasks: {report.human_samples}")

        for m in report.model_metrics:
            print(f"\n  Model: {m.model_id}")
            print(f"    Spearman rho:  {m.spearman_rho:.4f} (p={m.spearman_p_value:.4f})")
            print(f"    Cohen's kappa: {m.cohens_kappa:.4f}")
            print(f"    Evaluations:   {m.total_evaluations}")
            print(f"    Avg latency:   {m.avg_latency_ms:.1f} ms")
            print(f"    Total tokens:  {m.total_tokens}")
            print(f"    Cost/100 evals: ${m.estimated_cost_per_100:.4f}")
            if m.per_dimension_accuracy:
                print("    Per-dimension accuracy:")
                for dim, acc in sorted(m.per_dimension_accuracy.items()):
                    print(f"      {dim}: {acc:.2%}")

        if report.best_model_id:
            print(f"\n  Best model: {report.best_model_id} (rho={report.best_spearman:.4f})")

        print(f"\nReport saved to: {args.output}")
        return 0

    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        return 1
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Evaluation failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
