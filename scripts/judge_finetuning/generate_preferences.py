"""Generate DPO preference pairs from human annotations and judge results.

Converts pairwise preferences, direct scoring comparisons, and reference-based
ratings into (prompt, chosen, rejected) training pairs for DPO fine-tuning.

Usage:
    python -m scripts.judge_finetuning.generate_preferences \
        --annotations-dir data/human_annotations/ \
        --judge-dir eval_runs_v2/judge_experiments/ \
        --output data/training/preference_pairs.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REFERENCE_RATING_ORDER = {"pass": 2, "partial": 1, "fail": 0}
_DIRECT_SCORE_THRESHOLD = 0.5


@dataclass(frozen=True)
class PreferencePair:
    """A single DPO preference pair for fine-tuning."""

    prompt: str
    chosen: str
    rejected: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationReport:
    """Summary of preference pair generation results."""

    total_pairs: int
    from_human_pairwise: int
    from_human_direct: int
    from_human_reference: int
    from_judge: int
    skipped_annotations: int
    skipped_judge_results: int


def load_annotations(annotations_dir: Path) -> list[dict[str, Any]]:
    """Load human annotations from JSONL file(s) in annotations directory."""
    annotations: list[dict[str, Any]] = []
    annotations_file = annotations_dir / "annotations.jsonl"

    if not annotations_file.exists():
        logger.warning("Annotations file not found: %s", annotations_file)
        return annotations

    try:
        with open(annotations_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    annotations.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(
                        "Skipping corrupt annotation at line %d", line_num
                    )
    except OSError as exc:
        logger.warning("Failed to read annotations: %s", exc)

    return annotations


def load_judge_results(
    judge_dir: Path,
) -> list[dict[str, Any]]:
    """Load judge experiment results, returning flat list of per-task results.

    Each result dict includes 'experiment_id' for provenance tracking.
    """
    all_results: list[dict[str, Any]] = []

    if not judge_dir.is_dir():
        logger.warning("Judge experiments directory not found: %s", judge_dir)
        return all_results

    for exp_dir in sorted(judge_dir.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
            continue

        results_path = exp_dir / "results.json"
        if not results_path.exists():
            continue

        try:
            with open(results_path) as f:
                data = json.load(f)

            experiment_id = exp_dir.name.removeprefix("exp_")

            for result in data.get("results", []):
                result_with_exp = {**result, "experiment_id": experiment_id}
                all_results.append(result_with_exp)

        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load experiment %s: %s", exp_dir.name, exc
            )

    return all_results


def _build_prompt_from_task(
    task_id: str,
    task_description: str,
    evaluation_criteria: str = "",
    reference_answer: str = "",
) -> str:
    """Build a prompt string from task metadata."""
    parts = [f"Task: {task_description or task_id}"]
    if evaluation_criteria:
        parts.append(f"\nEvaluation Criteria: {evaluation_criteria}")
    if reference_answer:
        truncated = reference_answer[:5000]
        parts.append(f"\nReference Answer: {truncated}")
    return "\n".join(parts)


def pairs_from_pairwise_annotations(
    annotations: list[dict[str, Any]],
    task_outputs: dict[str, dict[str, str]],
    task_descriptions: dict[str, str],
) -> tuple[list[PreferencePair], int]:
    """Generate preference pairs from pairwise human annotations.

    For each pairwise annotation with a non-tie preference, the preferred
    output becomes 'chosen' and the other becomes 'rejected'. Ties are skipped.

    Returns (pairs, skipped_count).
    """
    pairs: list[PreferencePair] = []
    skipped = 0

    for ann in annotations:
        if ann.get("mode") != "pairwise":
            continue

        task_id = ann.get("task_id", "")
        preference = ann.get("preference", "")
        conditions = ann.get("scores", {}).get("conditions", [])

        if not task_id or not preference or preference == "Tie":
            skipped += 1
            continue

        outputs = task_outputs.get(task_id, {})
        if preference not in outputs:
            skipped += 1
            continue

        rejected_conditions = [c for c in conditions if c != preference and c in outputs]
        if not rejected_conditions:
            skipped += 1
            continue

        prompt = _build_prompt_from_task(
            task_id, task_descriptions.get(task_id, task_id)
        )
        chosen_text = outputs[preference]

        for rejected_cond in rejected_conditions:
            pairs.append(
                PreferencePair(
                    prompt=prompt,
                    chosen=chosen_text,
                    rejected=outputs[rejected_cond],
                    metadata={
                        "task_id": task_id,
                        "annotator": ann.get("annotator_id", ""),
                        "source": "human_pairwise",
                        "preference": preference,
                        "rejected_condition": rejected_cond,
                        "reasoning": ann.get("reasoning", ""),
                    },
                )
            )

    return pairs, skipped


def pairs_from_direct_annotations(
    annotations: list[dict[str, Any]],
    task_outputs: dict[str, dict[str, str]],
    task_descriptions: dict[str, str],
) -> tuple[list[PreferencePair], int]:
    """Generate preference pairs from direct scoring annotations.

    Groups annotations by task_id. When a task has at least 2 annotated outputs,
    pairs the higher-scored output (chosen) with the lower-scored one (rejected).
    Score is the mean across all dimensions.

    Returns (pairs, skipped_count).
    """
    pairs: list[PreferencePair] = []
    skipped = 0

    by_task: dict[str, list[dict[str, Any]]] = {}
    for ann in annotations:
        if ann.get("mode") != "direct":
            continue
        task_id = ann.get("task_id", "")
        if not task_id:
            skipped += 1
            continue
        by_task.setdefault(task_id, []).append(ann)

    for task_id, task_anns in by_task.items():
        outputs = task_outputs.get(task_id, {})
        if len(outputs) < 2:
            skipped += len(task_anns)
            continue

        scored_outputs: list[tuple[str, float, str]] = []
        for condition, output_text in outputs.items():
            condition_anns = [
                a for a in task_anns
                if a.get("scores") and isinstance(a["scores"], dict)
            ]
            if not condition_anns:
                continue

            total_score = 0.0
            count = 0
            for a in condition_anns:
                scores = a["scores"]
                dim_scores = [
                    v for v in scores.values()
                    if isinstance(v, (int, float))
                ]
                if dim_scores:
                    total_score += sum(dim_scores) / len(dim_scores)
                    count += 1

            if count > 0:
                avg_score = total_score / count
                scored_outputs.append((condition, avg_score, output_text))

        if len(scored_outputs) < 2:
            skipped += len(task_anns)
            continue

        scored_outputs.sort(key=lambda x: x[1], reverse=True)

        prompt = _build_prompt_from_task(
            task_id, task_descriptions.get(task_id, task_id)
        )

        best_cond, best_score, best_text = scored_outputs[0]
        for cond, score, text in scored_outputs[1:]:
            if best_score - score >= _DIRECT_SCORE_THRESHOLD:
                pairs.append(
                    PreferencePair(
                        prompt=prompt,
                        chosen=best_text,
                        rejected=text,
                        metadata={
                            "task_id": task_id,
                            "source": "human_direct",
                            "chosen_condition": best_cond,
                            "rejected_condition": cond,
                            "chosen_score": best_score,
                            "rejected_score": score,
                        },
                    )
                )

    return pairs, skipped


def pairs_from_reference_annotations(
    annotations: list[dict[str, Any]],
    task_outputs: dict[str, dict[str, str]],
    task_descriptions: dict[str, str],
    task_references: dict[str, str],
) -> tuple[list[PreferencePair], int]:
    """Generate preference pairs from reference-based annotations.

    Groups annotations by task_id. Outputs with higher reference ratings
    (pass > partial > fail) are chosen over lower-rated ones.

    Returns (pairs, skipped_count).
    """
    pairs: list[PreferencePair] = []
    skipped = 0

    by_task: dict[str, list[dict[str, Any]]] = {}
    for ann in annotations:
        if ann.get("mode") != "reference":
            continue
        task_id = ann.get("task_id", "")
        if not task_id:
            skipped += 1
            continue
        by_task.setdefault(task_id, []).append(ann)

    for task_id, task_anns in by_task.items():
        outputs = task_outputs.get(task_id, {})
        if len(outputs) < 2:
            skipped += len(task_anns)
            continue

        scored_outputs: list[tuple[str, float, str]] = []
        for condition, output_text in outputs.items():
            condition_anns = [
                a for a in task_anns
                if a.get("scores") and isinstance(a["scores"], dict)
            ]
            if not condition_anns:
                continue

            total_score = 0.0
            count = 0
            for a in condition_anns:
                scores = a["scores"]
                dim_values = [
                    _REFERENCE_RATING_ORDER.get(str(v).lower(), 0)
                    for v in scores.values()
                    if str(v).lower() in _REFERENCE_RATING_ORDER
                ]
                if dim_values:
                    total_score += sum(dim_values) / len(dim_values)
                    count += 1

            if count > 0:
                avg_score = total_score / count
                scored_outputs.append((condition, avg_score, output_text))

        if len(scored_outputs) < 2:
            skipped += len(task_anns)
            continue

        scored_outputs.sort(key=lambda x: x[1], reverse=True)

        reference = task_references.get(task_id, "")
        prompt = _build_prompt_from_task(
            task_id,
            task_descriptions.get(task_id, task_id),
            reference_answer=reference,
        )

        best_cond, best_score, best_text = scored_outputs[0]
        for cond, score, text in scored_outputs[1:]:
            if best_score > score:
                pairs.append(
                    PreferencePair(
                        prompt=prompt,
                        chosen=best_text,
                        rejected=text,
                        metadata={
                            "task_id": task_id,
                            "source": "human_reference",
                            "chosen_condition": best_cond,
                            "rejected_condition": cond,
                            "chosen_score": best_score,
                            "rejected_score": score,
                        },
                    )
                )

    return pairs, skipped


def pairs_from_judge_results(
    results: list[dict[str, Any]],
) -> tuple[list[PreferencePair], int]:
    """Generate preference pairs from judge evaluation results.

    Groups results by task_id. When multiple conditions/outputs exist for the
    same task, pairs the higher-scored output (chosen) with lower-scored (rejected).

    Returns (pairs, skipped_count).
    """
    pairs: list[PreferencePair] = []
    skipped = 0

    by_task: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        task_id = result.get("task_id", "")
        if not task_id:
            skipped += 1
            continue
        by_task.setdefault(task_id, []).append(result)

    for task_id, task_results in by_task.items():
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for r in task_results:
            score = r.get("overall_score", r.get("consensus_score"))
            agent_output = r.get("agent_output", "")
            if score is not None and agent_output:
                scored.append((float(score), agent_output, r))

        if len(scored) < 2:
            skipped += len(task_results)
            continue

        scored.sort(key=lambda x: x[0], reverse=True)

        best_score, best_output, best_result = scored[0]
        task_desc = best_result.get("task_description", task_id)
        reference = best_result.get("reference_answer", "")
        criteria = best_result.get("evaluation_criteria", "")

        prompt = _build_prompt_from_task(
            task_id, task_desc,
            evaluation_criteria=criteria,
            reference_answer=reference,
        )

        for score, output, result in scored[1:]:
            if best_score - score >= 0.1:
                pairs.append(
                    PreferencePair(
                        prompt=prompt,
                        chosen=best_output,
                        rejected=output,
                        metadata={
                            "task_id": task_id,
                            "source": "judge",
                            "chosen_score": best_score,
                            "rejected_score": score,
                            "model_id": result.get("model_id", ""),
                            "experiment_id": result.get("experiment_id", ""),
                        },
                    )
                )

    return pairs, skipped


def _build_task_index(
    annotations: list[dict[str, Any]],
    judge_results: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, str],
    dict[str, str],
]:
    """Build task output, description, and reference indexes from all sources.

    Returns (task_outputs, task_descriptions, task_references).
    task_outputs: task_id -> {condition_name: output_text}
    """
    task_outputs: dict[str, dict[str, str]] = {}
    task_descriptions: dict[str, str] = {}
    task_references: dict[str, str] = {}

    for result in judge_results:
        task_id = result.get("task_id", "")
        if not task_id:
            continue

        agent_output = result.get("agent_output", "")
        if agent_output:
            condition = result.get("condition", result.get("experiment_id", "default"))
            task_outputs.setdefault(task_id, {})[condition] = agent_output

        desc = result.get("task_description", "")
        if desc and task_id not in task_descriptions:
            task_descriptions[task_id] = desc

        ref = result.get("reference_answer", "")
        if ref and task_id not in task_references:
            task_references[task_id] = ref

        criteria = result.get("evaluation_criteria", "")
        if criteria and task_id not in task_descriptions:
            task_descriptions[task_id] = f"{desc}\n\nCriteria: {criteria}" if desc else criteria

    return task_outputs, task_descriptions, task_references


def generate_preference_pairs(
    annotations_dir: Path,
    judge_dir: Path,
) -> tuple[list[PreferencePair], GenerationReport]:
    """Generate all preference pairs from annotations and judge results.

    Returns (pairs, report).
    """
    annotations = load_annotations(annotations_dir)
    judge_results = load_judge_results(judge_dir)

    task_outputs, task_descriptions, task_references = _build_task_index(
        annotations, judge_results
    )

    pairwise_pairs, pairwise_skipped = pairs_from_pairwise_annotations(
        annotations, task_outputs, task_descriptions
    )

    direct_pairs, direct_skipped = pairs_from_direct_annotations(
        annotations, task_outputs, task_descriptions
    )

    reference_pairs, reference_skipped = pairs_from_reference_annotations(
        annotations, task_outputs, task_descriptions, task_references
    )

    judge_pairs, judge_skipped = pairs_from_judge_results(judge_results)

    all_pairs = pairwise_pairs + direct_pairs + reference_pairs + judge_pairs

    report = GenerationReport(
        total_pairs=len(all_pairs),
        from_human_pairwise=len(pairwise_pairs),
        from_human_direct=len(direct_pairs),
        from_human_reference=len(reference_pairs),
        from_judge=len(judge_pairs),
        skipped_annotations=pairwise_skipped + direct_skipped + reference_skipped,
        skipped_judge_results=judge_skipped,
    )

    return all_pairs, report


def serialize_pair(pair: PreferencePair) -> dict[str, Any]:
    """Serialize a PreferencePair to a JSON-compatible dict."""
    return {
        "prompt": pair.prompt,
        "chosen": pair.chosen,
        "rejected": pair.rejected,
        "metadata": dict(pair.metadata),
    }


def write_pairs_jsonl(pairs: list[PreferencePair], output_path: Path) -> None:
    """Write preference pairs to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for pair in pairs:
            f.write(json.dumps(serialize_pair(pair), default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for preference pair generation."""
    parser = argparse.ArgumentParser(
        description="Generate DPO preference pairs from annotations and judge results"
    )
    parser.add_argument(
        "--annotations-dir",
        type=Path,
        default=Path("data/human_annotations"),
        help="Directory containing annotations.jsonl",
    )
    parser.add_argument(
        "--judge-dir",
        type=Path,
        default=Path("eval_runs_v2/judge_experiments"),
        help="Directory containing judge experiment results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training/preference_pairs.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    pairs, report = generate_preference_pairs(args.annotations_dir, args.judge_dir)

    if not pairs:
        logger.warning("No preference pairs generated.")
        print("No preference pairs generated.")
        print(f"  Skipped annotations: {report.skipped_annotations}")
        print(f"  Skipped judge results: {report.skipped_judge_results}")
        return 1

    write_pairs_jsonl(pairs, args.output)

    print(f"Generated {report.total_pairs} preference pairs:")
    print(f"  Human pairwise: {report.from_human_pairwise}")
    print(f"  Human direct:   {report.from_human_direct}")
    print(f"  Human reference: {report.from_human_reference}")
    print(f"  Judge results:  {report.from_judge}")
    print(f"  Skipped annotations: {report.skipped_annotations}")
    print(f"  Skipped judge results: {report.skipped_judge_results}")
    print(f"Output written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
