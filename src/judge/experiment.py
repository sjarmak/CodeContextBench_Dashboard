"""Experiment tracking for judge evaluations.

Provides persistence and comparison of judge evaluation runs with full
provenance tracking including config hashes, prompt template versions,
and model IDs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("eval_runs_v2/judge_experiments")


@dataclass(frozen=True)
class JudgeExperiment:
    """Metadata for a judge evaluation experiment run."""

    experiment_id: str
    timestamp: str
    judge_config: dict[str, Any]
    prompt_template_versions: dict[str, str]
    model_ids: list[str]
    evaluation_mode: str
    input_data_hash: str
    results_path: str


def _compute_data_hash(data: Any) -> str:
    """Compute a stable SHA-256 hash of input data."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _compute_config_hash(config: dict[str, Any]) -> str:
    """Compute a hash of the judge config for provenance."""
    return _compute_data_hash(config)


def _serialize_experiment(experiment: JudgeExperiment) -> dict[str, Any]:
    """Convert a JudgeExperiment to a JSON-serializable dict."""
    return {
        "experiment_id": experiment.experiment_id,
        "timestamp": experiment.timestamp,
        "judge_config": experiment.judge_config,
        "prompt_template_versions": experiment.prompt_template_versions,
        "model_ids": experiment.model_ids,
        "evaluation_mode": experiment.evaluation_mode,
        "input_data_hash": experiment.input_data_hash,
        "results_path": experiment.results_path,
    }


def _deserialize_experiment(data: dict[str, Any]) -> JudgeExperiment:
    """Reconstruct a JudgeExperiment from a dict."""
    return JudgeExperiment(
        experiment_id=data["experiment_id"],
        timestamp=data["timestamp"],
        judge_config=data.get("judge_config") or {},
        prompt_template_versions=data.get("prompt_template_versions") or {},
        model_ids=data.get("model_ids") or [],
        evaluation_mode=data.get("evaluation_mode", "unknown"),
        input_data_hash=data.get("input_data_hash", ""),
        results_path=data.get("results_path", ""),
    )


def create_experiment(
    judge_config: dict[str, Any],
    prompt_template_versions: dict[str, str],
    model_ids: list[str],
    evaluation_mode: str,
    input_data: Any = None,
    results_path: str = "",
) -> JudgeExperiment:
    """Create a new JudgeExperiment with a unique ID and timestamp."""
    exp_id = str(uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    input_hash = _compute_data_hash(input_data) if input_data else ""

    return JudgeExperiment(
        experiment_id=exp_id,
        timestamp=timestamp,
        judge_config=judge_config,
        prompt_template_versions=prompt_template_versions,
        model_ids=list(model_ids),
        evaluation_mode=evaluation_mode,
        input_data_hash=input_hash,
        results_path=results_path,
    )


def _generate_summary(
    experiment: JudgeExperiment,
    results: dict[str, Any],
    bias_report: dict[str, Any] | None = None,
) -> str:
    """Generate a markdown summary for the experiment."""
    lines: list[str] = []
    lines.append(f"# Experiment {experiment.experiment_id}")
    lines.append("")
    lines.append(f"**Timestamp:** {experiment.timestamp}")
    lines.append(f"**Mode:** {experiment.evaluation_mode}")
    lines.append(f"**Models:** {', '.join(experiment.model_ids)}")
    lines.append(f"**Input Hash:** {experiment.input_data_hash}")
    lines.append("")

    lines.append("## Config")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(experiment.judge_config, indent=2, default=str))
    lines.append("```")
    lines.append("")

    result_list = results.get("results", [])
    if result_list:
        scores = [
            r.get("overall_score", r.get("consensus_score", 0.0))
            for r in result_list
        ]
        avg = sum(scores) / len(scores) if scores else 0.0
        lines.append("## Results Summary")
        lines.append("")
        lines.append(f"- **Tasks evaluated:** {len(result_list)}")
        lines.append(f"- **Mean score:** {avg:.3f}")
        if scores:
            lines.append(f"- **Min score:** {min(scores):.3f}")
            lines.append(f"- **Max score:** {max(scores):.3f}")
        lines.append("")

    if bias_report:
        lines.append("## Bias Report")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(bias_report, indent=2, default=str))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def save_experiment(
    experiment: JudgeExperiment,
    results: dict[str, Any],
    output_dir: str | Path | None = None,
    bias_report: dict[str, Any] | None = None,
) -> Path:
    """Save an experiment and its results to disk.

    Creates directory structure:
        {output_dir}/exp_{id}/
            config.json
            results.json
            summary.md
            bias_report.json (if provided)

    Returns the experiment directory path.
    """
    base = Path(output_dir) if output_dir else _DEFAULT_BASE_DIR
    exp_dir = base / f"exp_{experiment.experiment_id}"
    exp_dir.mkdir(parents=True, exist_ok=True)

    config_path = exp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(_serialize_experiment(experiment), f, indent=2, default=str)

    results_path = exp_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    summary_path = exp_dir / "summary.md"
    summary = _generate_summary(experiment, results, bias_report)
    with open(summary_path, "w") as f:
        f.write(summary)

    if bias_report is not None:
        bias_path = exp_dir / "bias_report.json"
        with open(bias_path, "w") as f:
            json.dump(bias_report, f, indent=2, default=str)

    logger.info("Saved experiment %s to %s", experiment.experiment_id, exp_dir)
    return exp_dir


def load_experiment(
    experiment_id: str,
    base_dir: str | Path | None = None,
) -> tuple[JudgeExperiment, dict[str, Any]]:
    """Load an experiment and its results from disk.

    Returns (experiment, results) tuple.
    Raises FileNotFoundError if experiment directory doesn't exist.
    """
    base = Path(base_dir) if base_dir else _DEFAULT_BASE_DIR
    exp_dir = base / f"exp_{experiment_id}"

    if not exp_dir.is_dir():
        raise FileNotFoundError(f"Experiment directory not found: {exp_dir}")

    config_path = exp_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config_data = json.load(f)

    experiment = _deserialize_experiment(config_data)

    results_path = exp_dir / "results.json"
    results: dict[str, Any] = {}
    if results_path.exists():
        with open(results_path) as f:
            results = json.load(f)

    return experiment, results


def list_experiments(
    base_dir: str | Path | None = None,
) -> list[JudgeExperiment]:
    """List all experiments sorted by timestamp (newest first).

    Returns list of JudgeExperiment objects.
    """
    base = Path(base_dir) if base_dir else _DEFAULT_BASE_DIR

    if not base.is_dir():
        return []

    experiments: list[JudgeExperiment] = []
    for exp_dir in sorted(base.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
            continue

        config_path = exp_dir / "config.json"
        if not config_path.exists():
            logger.warning("Skipping %s: no config.json", exp_dir)
            continue

        try:
            with open(config_path) as f:
                config_data = json.load(f)
            experiments.append(_deserialize_experiment(config_data))
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            logger.warning("Failed to load experiment from %s: %s", exp_dir, exc)

    experiments.sort(key=lambda e: e.timestamp, reverse=True)
    return experiments


@dataclass(frozen=True)
class ExperimentDiff:
    """Diff between two experiments."""

    config_changes: dict[str, tuple[Any, Any]]
    prompt_changes: dict[str, tuple[str, str]]
    model_changes: tuple[list[str], list[str]]
    result_deltas: dict[str, float]


def compare_experiments(
    exp_a: JudgeExperiment,
    results_a: dict[str, Any],
    exp_b: JudgeExperiment,
    results_b: dict[str, Any],
) -> ExperimentDiff:
    """Compare two experiments and return their differences.

    Returns an ExperimentDiff with config, prompt, model, and result changes.
    """
    config_changes: dict[str, tuple[Any, Any]] = {}
    all_keys = set(exp_a.judge_config.keys()) | set(exp_b.judge_config.keys())
    for key in sorted(all_keys):
        val_a = exp_a.judge_config.get(key)
        val_b = exp_b.judge_config.get(key)
        if val_a != val_b:
            config_changes[key] = (val_a, val_b)

    prompt_changes: dict[str, tuple[str, str]] = {}
    all_prompts = set(exp_a.prompt_template_versions.keys()) | set(
        exp_b.prompt_template_versions.keys()
    )
    for key in sorted(all_prompts):
        ver_a = exp_a.prompt_template_versions.get(key, "")
        ver_b = exp_b.prompt_template_versions.get(key, "")
        if ver_a != ver_b:
            prompt_changes[key] = (ver_a, ver_b)

    model_changes = (list(exp_a.model_ids), list(exp_b.model_ids))

    result_deltas: dict[str, float] = {}

    scores_a = _extract_task_scores(results_a)
    scores_b = _extract_task_scores(results_b)

    all_scores_a = list(scores_a.values())
    all_scores_b = list(scores_b.values())

    if all_scores_a:
        result_deltas["mean_score_a"] = sum(all_scores_a) / len(all_scores_a)
    if all_scores_b:
        result_deltas["mean_score_b"] = sum(all_scores_b) / len(all_scores_b)
    if all_scores_a and all_scores_b:
        result_deltas["mean_delta"] = result_deltas["mean_score_b"] - result_deltas["mean_score_a"]

    common_tasks = set(scores_a.keys()) & set(scores_b.keys())
    if common_tasks:
        common_deltas = [scores_b[t] - scores_a[t] for t in common_tasks]
        result_deltas["common_task_count"] = float(len(common_tasks))
        result_deltas["common_mean_delta"] = sum(common_deltas) / len(common_deltas)

    return ExperimentDiff(
        config_changes=config_changes,
        prompt_changes=prompt_changes,
        model_changes=model_changes,
        result_deltas=result_deltas,
    )


def _extract_task_scores(results: dict[str, Any]) -> dict[str, float]:
    """Extract task_id -> score mapping from results data."""
    scores: dict[str, float] = {}
    for r in results.get("results", []):
        task_id = r.get("task_id", "")
        score = r.get("overall_score", r.get("consensus_score"))
        if task_id and score is not None:
            scores[task_id] = float(score)
    return scores
