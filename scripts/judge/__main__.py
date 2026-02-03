"""CLI for batch judge evaluation.

Usage:
    python -m scripts.judge evaluate --mode direct --runs-dir ./runs --output results.json
    python -m scripts.judge compare --baseline-dir ./baseline --treatment-dirs ./mcp --output compare.json
    python -m scripts.judge report --input results.json --output summary.md
    python -m scripts.judge export --input results.json --format csv --output results.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.judge.backends.anthropic import AnthropicBackend, AnthropicBackendConfig
from src.judge.engine import JudgeConfig, JudgeError, UnifiedJudge
from src.judge.ensemble import EnsembleConfig, EnsembleJudge
from src.judge.experiment import (
    ExperimentDiff,
    JudgeExperiment,
    compare_experiments,
    list_experiments,
    load_experiment,
)
from src.judge.models import (
    DirectInput,
    EvaluationMode,
    JudgeVerdict,
    PairwiseInput,
    ReferenceInput,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_result_json(path: Path) -> dict[str, Any]:
    """Load a Harbor result.json file."""
    with open(path) as f:
        return json.load(f)


def _find_result_files(runs_dir: Path) -> list[Path]:
    """Recursively find all result.json files under a runs directory."""
    results = sorted(runs_dir.rglob("result.json"))
    return results


def _extract_task_id(result: dict[str, Any]) -> str:
    """Extract task ID from Harbor result.json."""
    task_name = result.get("task_name") or ""
    if task_name:
        return task_name
    task_id = result.get("task_id") or {}
    if isinstance(task_id, dict):
        return task_id.get("path", "") or task_id.get("name", "")
    return str(task_id)


def _extract_agent_output(result_dir: Path) -> str:
    """Extract agent output from a run directory.

    Looks for solution.md, then any .md in logs/agent/, then submission.
    """
    candidates = [
        result_dir / "logs" / "agent" / "solution.md",
        result_dir / "submission.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(errors="replace")

    agent_logs = result_dir / "logs" / "agent"
    if agent_logs.is_dir():
        md_files = sorted(agent_logs.glob("*.md"))
        if md_files:
            return md_files[0].read_text(errors="replace")

    return ""


def _extract_code_changes(result_dir: Path) -> str:
    """Extract code changes (patch/diff) from a run directory."""
    candidates = [
        result_dir / "submission.patch",
        result_dir / "submission.diff",
        result_dir / "patch.diff",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(errors="replace")
    return ""


def _load_oracle_data(task_id: str, oracle_dir: Path | None) -> dict[str, Any]:
    """Load oracle/ground truth data for a task if available."""
    if not oracle_dir or not oracle_dir.is_dir():
        return {}

    candidates = [
        oracle_dir / f"{task_id}.json",
        oracle_dir / task_id / "scenario.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                with open(candidate) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load oracle data from %s: %s", candidate, exc)
    return {}


def _build_direct_input(
    task_id: str,
    task_description: str,
    agent_output: str,
    code_changes: str,
) -> DirectInput:
    return DirectInput(
        task_id=task_id,
        task_description=task_description,
        evaluation_mode=EvaluationMode.DIRECT,
        agent_output=agent_output,
        code_changes=code_changes or None,
    )


def _build_reference_input(
    task_id: str,
    task_description: str,
    agent_output: str,
    oracle: dict[str, Any],
) -> ReferenceInput:
    ground_truth = oracle.get("ground_truth", "")
    if isinstance(ground_truth, dict):
        ground_truth = json.dumps(ground_truth)
    return ReferenceInput(
        task_id=task_id,
        task_description=task_description,
        evaluation_mode=EvaluationMode.REFERENCE_BASED,
        agent_output=agent_output,
        reference_answer=str(ground_truth),
        context_files=oracle.get("context_files", []),
        ground_truth=str(ground_truth) if ground_truth else None,
        evaluation_criteria=oracle.get("evaluation_criteria"),
    )


def _build_pairwise_input(
    task_id: str,
    task_description: str,
    outputs: dict[str, str],
) -> PairwiseInput:
    return PairwiseInput(
        task_id=task_id,
        task_description=task_description,
        evaluation_mode=EvaluationMode.PAIRWISE,
        outputs=outputs,
    )


def _create_backend(model: str) -> AnthropicBackend:
    """Create an Anthropic backend with the given model."""
    config = AnthropicBackendConfig(model=model)
    return AnthropicBackend(config=config)


def _create_backends_for_models(models: list[str]) -> list[AnthropicBackend]:
    """Create backends for each model ID."""
    return [_create_backend(m) for m in models]


def _verdict_to_dict(verdict: JudgeVerdict) -> dict[str, Any]:
    """Serialize a JudgeVerdict to a JSON-serializable dict."""
    data = asdict(verdict)
    if hasattr(verdict, "mode") and hasattr(verdict.mode, "value"):
        data["mode"] = verdict.mode.value
    scores_serialized: dict[str, Any] = {}
    for dim_name, dim_score in verdict.scores.items():
        scores_serialized[dim_name] = {
            "dimension": dim_score.dimension,
            "score": dim_score.score,
            "weight": dim_score.weight,
            "evidence": dim_score.evidence,
            "reasoning": dim_score.reasoning,
        }
    data["scores"] = scores_serialized
    comments_serialized = []
    for lc in verdict.line_comments:
        comments_serialized.append({
            "file_path": lc.file_path,
            "line_range": list(lc.line_range),
            "severity": lc.severity.value,
            "comment": lc.comment,
            "category": lc.category.value,
        })
    data["line_comments"] = comments_serialized
    return data


def _ensemble_verdict_to_dict(verdict: Any) -> dict[str, Any]:
    """Serialize an EnsembleVerdict to a JSON-serializable dict."""
    return {
        "consensus_score": verdict.consensus_score,
        "per_model_verdicts": [_verdict_to_dict(v) for v in verdict.per_model_verdicts],
        "vote_distribution": verdict.vote_distribution,
        "agreement_score": verdict.agreement_score,
        "confidence": verdict.confidence,
    }


async def _evaluate_single(
    judge: UnifiedJudge | EnsembleJudge,
    judge_input: DirectInput | ReferenceInput,
) -> dict[str, Any]:
    """Evaluate a single input and return serializable result."""
    from src.judge.ensemble import EnsembleJudge as EJ

    verdict = await judge.evaluate(judge_input)
    if isinstance(verdict, JudgeVerdict):
        return _verdict_to_dict(verdict)
    return _ensemble_verdict_to_dict(verdict)


async def _run_evaluate(args: argparse.Namespace) -> int:
    """Execute the evaluate subcommand."""
    try:
        from tqdm import tqdm
    except ImportError:
        def tqdm(iterable: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            return iterable

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_dir():
        logger.error("Runs directory does not exist: %s", runs_dir)
        return 1

    result_files = _find_result_files(runs_dir)
    if not result_files:
        logger.error("No result.json files found in %s", runs_dir)
        return 1

    logger.info("Found %d result files in %s", len(result_files), runs_dir)

    oracle_dir = Path(args.oracle_dir) if args.oracle_dir else None

    config = JudgeConfig(
        templates_dir=args.config if args.config else "",
    )

    models = [m.strip() for m in args.models.split(",")] if args.models else [_DEFAULT_MODEL]

    if args.ensemble and len(models) >= 2:
        backends = _create_backends_for_models(models)
        judges = [UnifiedJudge(backend=b, config=config) for b in backends]
        ensemble_config = EnsembleConfig(min_successful=min(2, len(judges)))
        judge: UnifiedJudge | EnsembleJudge = EnsembleJudge(
            judges=judges, config=ensemble_config
        )
    else:
        backend = _create_backend(models[0])
        judge = UnifiedJudge(backend=backend, config=config)

    mode = args.mode
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for result_file in tqdm(result_files, desc="Evaluating"):
        result_dir = result_file.parent
        try:
            result_data = _load_result_json(result_file)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append({"file": str(result_file), "error": str(exc)})
            continue

        task_id = _extract_task_id(result_data)
        task_desc = result_data.get("task_name", task_id)
        agent_output = _extract_agent_output(result_dir)

        try:
            if mode == "reference":
                oracle = _load_oracle_data(task_id, oracle_dir)
                if not oracle:
                    logger.warning("No oracle data for task %s, falling back to direct", task_id)
                    judge_input = _build_direct_input(
                        task_id, task_desc, agent_output, _extract_code_changes(result_dir)
                    )
                else:
                    judge_input = _build_reference_input(task_id, task_desc, agent_output, oracle)
            elif mode == "pairwise":
                logger.warning("Pairwise mode requires compare subcommand; skipping %s", task_id)
                continue
            else:
                judge_input = _build_direct_input(
                    task_id, task_desc, agent_output, _extract_code_changes(result_dir)
                )

            verdict_dict = await _evaluate_single(judge, judge_input)
            verdict_dict["task_id"] = task_id
            verdict_dict["source_file"] = str(result_file)
            results.append(verdict_dict)

        except (JudgeError, ValueError) as exc:
            errors.append({"task_id": task_id, "error": str(exc)})
            logger.warning("Evaluation failed for %s: %s", task_id, exc)

    output_data: dict[str, Any] = {
        "mode": mode,
        "runs_dir": str(runs_dir),
        "total_tasks": len(result_files),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(
        "Evaluation complete: %d/%d succeeded. Results written to %s",
        len(results), len(result_files), output_path,
    )
    return 0


async def _run_compare(args: argparse.Namespace) -> int:
    """Execute the compare subcommand."""
    try:
        from tqdm import tqdm
    except ImportError:
        def tqdm(iterable: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            return iterable

    baseline_dir = Path(args.baseline_dir)
    treatment_dirs = [Path(d) for d in args.treatment_dirs]

    for d in [baseline_dir, *treatment_dirs]:
        if not d.is_dir():
            logger.error("Directory does not exist: %s", d)
            return 1

    config = JudgeConfig(
        pairwise_method=args.method or "simultaneous",
        templates_dir=args.config if args.config else "",
    )

    models = [m.strip() for m in args.models.split(",")] if args.models else [_DEFAULT_MODEL]

    if args.ensemble and len(models) >= 2:
        backends = _create_backends_for_models(models)
        judges = [UnifiedJudge(backend=b, config=config) for b in backends]
        ensemble_config = EnsembleConfig(min_successful=min(2, len(judges)))
        judge: UnifiedJudge | EnsembleJudge = EnsembleJudge(
            judges=judges, config=ensemble_config
        )
    else:
        backend = _create_backend(models[0])
        judge = UnifiedJudge(backend=backend, config=config)

    condition_names = ["BASELINE"] + [d.name for d in treatment_dirs]
    baseline_results = _find_result_files(baseline_dir)

    task_map: dict[str, dict[str, Path]] = {}
    for rf in baseline_results:
        result_data = _load_result_json(rf)
        tid = _extract_task_id(result_data)
        task_map.setdefault(tid, {})["BASELINE"] = rf.parent

    for tdir in treatment_dirs:
        cname = tdir.name
        for rf in _find_result_files(tdir):
            result_data = _load_result_json(rf)
            tid = _extract_task_id(result_data)
            task_map.setdefault(tid, {})[cname] = rf.parent

    common_tasks = [
        tid for tid, conds in task_map.items()
        if len(conds) == len(condition_names)
    ]

    if not common_tasks:
        logger.error("No common tasks found across baseline and treatment directories")
        return 1

    logger.info(
        "Found %d common tasks across %d conditions",
        len(common_tasks), len(condition_names),
    )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for task_id in tqdm(common_tasks, desc="Comparing"):
        try:
            outputs: dict[str, str] = {}
            task_desc = task_id
            for cname, result_dir in task_map[task_id].items():
                outputs[cname] = _extract_agent_output(result_dir)

            judge_input = _build_pairwise_input(task_id, task_desc, outputs)
            verdict_dict = await _evaluate_single(judge, judge_input)
            verdict_dict["task_id"] = task_id
            results.append(verdict_dict)

        except (JudgeError, ValueError) as exc:
            errors.append({"task_id": task_id, "error": str(exc)})
            logger.warning("Comparison failed for %s: %s", task_id, exc)

    output_data: dict[str, Any] = {
        "mode": "pairwise",
        "method": args.method or "simultaneous",
        "conditions": condition_names,
        "common_tasks": len(common_tasks),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(
        "Comparison complete: %d/%d succeeded. Results written to %s",
        len(results), len(common_tasks), output_path,
    )
    return 0


def _run_report(args: argparse.Namespace) -> int:
    """Execute the report subcommand."""
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    with open(input_path) as f:
        data = json.load(f)

    mode = data.get("mode", "unknown")
    total = data.get("total_tasks", data.get("common_tasks", 0))
    successful = data.get("successful", 0)
    failed = data.get("failed", 0)
    results = data.get("results", [])

    lines: list[str] = []
    lines.append(f"# Judge Evaluation Report")
    lines.append("")
    lines.append(f"**Mode:** {mode}")
    lines.append(f"**Total tasks:** {total}")
    lines.append(f"**Successful:** {successful}")
    lines.append(f"**Failed:** {failed}")
    lines.append("")

    if results:
        scores = [r.get("overall_score", r.get("consensus_score", 0.0)) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        min_score = min(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0

        lines.append("## Score Summary")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Mean Score | {avg_score:.3f} |")
        lines.append(f"| Min Score | {min_score:.3f} |")
        lines.append(f"| Max Score | {max_score:.3f} |")
        lines.append(f"| Count | {len(scores)} |")
        lines.append("")

    if mode == "pairwise" and results:
        lines.append("## Pairwise Rankings")
        lines.append("")
        win_rate_agg: dict[str, list[float]] = {}
        for r in results:
            for cond, rate in r.get("win_rates", {}).items():
                win_rate_agg.setdefault(cond, []).append(rate)

        if win_rate_agg:
            lines.append("| Condition | Avg Win Rate |")
            lines.append("|-----------|-------------|")
            for cond, rates in sorted(win_rate_agg.items(), key=lambda x: -sum(x[1]) / len(x[1])):
                avg_rate = sum(rates) / len(rates)
                lines.append(f"| {cond} | {avg_rate:.3f} |")
            lines.append("")

    if results:
        lines.append("## Per-Task Results")
        lines.append("")
        lines.append("| Task ID | Score | Confidence |")
        lines.append("|---------|-------|------------|")
        for r in results:
            tid = r.get("task_id", "unknown")
            score = r.get("overall_score", r.get("consensus_score", 0.0))
            conf = r.get("confidence", 0.0)
            lines.append(f"| {tid} | {score:.3f} | {conf:.3f} |")
        lines.append("")

    errors = data.get("errors", [])
    if errors:
        lines.append("## Errors")
        lines.append("")
        for err in errors:
            tid = err.get("task_id", err.get("file", "unknown"))
            msg = err.get("error", "unknown error")
            lines.append(f"- **{tid}**: {msg}")
        lines.append("")

    report = "\n".join(lines)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    logger.info("Report written to %s", output_path)
    return 0


def _run_export(args: argparse.Namespace) -> int:
    """Execute the export subcommand."""
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    with open(input_path) as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        logger.warning("No results to export")
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = args.format
    if fmt == "json":
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
    elif fmt == "csv":
        rows: list[dict[str, Any]] = []
        for r in results:
            row: dict[str, Any] = {
                "task_id": r.get("task_id", ""),
                "overall_score": r.get("overall_score", r.get("consensus_score", "")),
                "confidence": r.get("confidence", ""),
                "reasoning": r.get("reasoning", ""),
                "mode": r.get("mode", ""),
                "model_id": r.get("model_id", ""),
            }
            scores = r.get("scores", {})
            for dim_name, dim_data in scores.items():
                if isinstance(dim_data, dict):
                    row[f"score_{dim_name}"] = dim_data.get("score", "")
                else:
                    row[f"score_{dim_name}"] = dim_data
            rows.append(row)

        if rows:
            fieldnames = list(rows[0].keys())
            for row in rows[1:]:
                for k in row:
                    if k not in fieldnames:
                        fieldnames.append(k)

            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
    else:
        logger.error("Unsupported format: %s (use json or csv)", fmt)
        return 1

    logger.info("Exported %d results to %s (%s)", len(results), output_path, fmt)
    return 0


def _run_experiment_list(args: argparse.Namespace) -> int:
    """Execute the experiment list subcommand."""
    base_dir = args.base_dir
    experiments = list_experiments(base_dir)

    if not experiments:
        logger.info("No experiments found in %s", base_dir or "eval_runs_v2/judge_experiments")
        return 0

    print(f"{'ID':<12} {'Timestamp':<28} {'Mode':<18} {'Models'}")
    print("-" * 80)
    for exp in experiments:
        models_str = ", ".join(exp.model_ids) if exp.model_ids else "none"
        print(f"{exp.experiment_id:<12} {exp.timestamp:<28} {exp.evaluation_mode:<18} {models_str}")

    print(f"\nTotal: {len(experiments)} experiments")
    return 0


def _run_experiment_compare(args: argparse.Namespace) -> int:
    """Execute the experiment compare subcommand."""
    base_dir = args.base_dir
    exp_id_a = args.exp_a
    exp_id_b = args.exp_b

    try:
        exp_a, results_a = load_experiment(exp_id_a, base_dir)
    except FileNotFoundError as exc:
        logger.error("Experiment A not found: %s", exc)
        return 1

    try:
        exp_b, results_b = load_experiment(exp_id_b, base_dir)
    except FileNotFoundError as exc:
        logger.error("Experiment B not found: %s", exc)
        return 1

    diff = compare_experiments(exp_a, results_a, exp_b, results_b)

    print(f"Comparing {exp_id_a} vs {exp_id_b}")
    print("=" * 60)

    print(f"\nModels A: {', '.join(diff.model_changes[0])}")
    print(f"Models B: {', '.join(diff.model_changes[1])}")

    if diff.config_changes:
        print("\nConfig Changes:")
        for key, (val_a, val_b) in diff.config_changes.items():
            print(f"  {key}: {val_a} -> {val_b}")
    else:
        print("\nConfig: identical")

    if diff.prompt_changes:
        print("\nPrompt Template Changes:")
        for key, (ver_a, ver_b) in diff.prompt_changes.items():
            print(f"  {key}: {ver_a} -> {ver_b}")
    else:
        print("\nPrompt Templates: identical")

    if diff.result_deltas:
        print("\nResult Deltas:")
        for key, val in diff.result_deltas.items():
            print(f"  {key}: {val:.4f}")
    else:
        print("\nResults: no scores to compare")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="judge",
        description="Unified LLM Judge CLI for batch evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # evaluate subcommand
    eval_parser = subparsers.add_parser(
        "evaluate",
        help="Run judge evaluation on a batch of results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    eval_parser.add_argument(
        "--mode",
        choices=["direct", "reference", "pairwise"],
        default="direct",
        help="Evaluation mode (default: direct)",
    )
    eval_parser.add_argument(
        "--runs-dir",
        required=True,
        help="Directory containing run results with result.json files",
    )
    eval_parser.add_argument(
        "--output",
        required=True,
        help="Output path for results JSON",
    )
    eval_parser.add_argument(
        "--config",
        default=None,
        help="Path to judge template directory",
    )
    eval_parser.add_argument(
        "--oracle-dir",
        default=None,
        help="Directory containing oracle/ground truth data (for reference mode)",
    )
    eval_parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Use ensemble evaluation with multiple models",
    )
    eval_parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated list of model IDs (default: claude-sonnet-4-20250514)",
    )

    # compare subcommand
    compare_parser = subparsers.add_parser(
        "compare",
        help="Pairwise comparison between baseline and treatment runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compare_parser.add_argument(
        "--baseline-dir",
        required=True,
        help="Directory containing baseline run results",
    )
    compare_parser.add_argument(
        "--treatment-dirs",
        nargs="+",
        required=True,
        help="One or more directories containing treatment run results",
    )
    compare_parser.add_argument(
        "--output",
        required=True,
        help="Output path for comparison results JSON",
    )
    compare_parser.add_argument(
        "--method",
        choices=["simultaneous", "round_robin"],
        default="simultaneous",
        help="Pairwise comparison method (default: simultaneous)",
    )
    compare_parser.add_argument(
        "--config",
        default=None,
        help="Path to judge template directory",
    )
    compare_parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Use ensemble evaluation with multiple models",
    )
    compare_parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated list of model IDs",
    )

    # report subcommand
    report_parser = subparsers.add_parser(
        "report",
        help="Generate markdown summary from results JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    report_parser.add_argument(
        "--input",
        required=True,
        help="Input results JSON file",
    )
    report_parser.add_argument(
        "--output",
        required=True,
        help="Output markdown file path",
    )

    # export subcommand
    export_parser = subparsers.add_parser(
        "export",
        help="Export results to JSON or CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    export_parser.add_argument(
        "--input",
        required=True,
        help="Input results JSON file",
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format (default: json)",
    )
    export_parser.add_argument(
        "--output",
        required=True,
        help="Output file path",
    )

    # experiment subcommand
    experiment_parser = subparsers.add_parser(
        "experiment",
        help="Manage judge experiments (list, compare)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    experiment_subparsers = experiment_parser.add_subparsers(
        dest="experiment_command",
        help="Experiment subcommands",
    )

    # experiment list
    exp_list_parser = experiment_subparsers.add_parser(
        "list",
        help="List all judge experiments",
    )
    exp_list_parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory for experiments (default: eval_runs_v2/judge_experiments)",
    )

    # experiment compare
    exp_compare_parser = experiment_subparsers.add_parser(
        "compare",
        help="Compare two judge experiments",
    )
    exp_compare_parser.add_argument(
        "exp_a",
        help="First experiment ID",
    )
    exp_compare_parser.add_argument(
        "exp_b",
        help="Second experiment ID",
    )
    exp_compare_parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory for experiments (default: eval_runs_v2/judge_experiments)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the judge CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    _setup_logging(args.verbose)

    if args.command == "evaluate":
        return asyncio.run(_run_evaluate(args))
    elif args.command == "compare":
        return asyncio.run(_run_compare(args))
    elif args.command == "report":
        return _run_report(args)
    elif args.command == "export":
        return _run_export(args)
    elif args.command == "experiment":
        if not hasattr(args, "experiment_command") or not args.experiment_command:
            parser.parse_args([args.command, "--help"])
            return 1
        if args.experiment_command == "list":
            return _run_experiment_list(args)
        elif args.experiment_command == "compare":
            return _run_experiment_compare(args)
        else:
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
