"""
End-to-end CCB analysis pipeline.

Chains extract -> judge -> analyze -> publish into a single command.

Usage:
    python -m scripts.ccb_pipeline --runs-dir <path> --output-dir output/ [--skip-judge] [--judge-template <path>]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from scripts.ccb_pipeline import analyze, extract, judge, publish

logger = logging.getLogger(__name__)

_STAGE_COUNT = 4


def _count_trials(metrics_path: Path) -> int:
    """Count total trials in an experiment_metrics.json file."""
    try:
        categories = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(categories, list):
        return 0
    return sum(
        len(exp.get("trials", []))
        for cat in categories
        for exp in cat.get("experiments", [])
    )


def _count_configs(metrics_path: Path) -> list[str]:
    """Return unique agent config values from experiment_metrics.json."""
    try:
        categories = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(categories, list):
        return []
    configs: set[str] = set()
    for cat in categories:
        for exp in cat.get("experiments", []):
            for trial in exp.get("trials", []):
                config = trial.get("agent_config")
                if config is not None:
                    configs.add(str(config))
    return sorted(configs)


def _count_artifacts(output_dir: Path) -> int:
    """Count generated artifact files in tables/ and figures/ subdirectories."""
    count = 0
    for subdir in ("tables", "figures"):
        artifact_dir = output_dir / subdir
        if artifact_dir.is_dir():
            count += sum(1 for f in artifact_dir.iterdir() if f.is_file())
    return count


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the end-to-end pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the full CCB analysis pipeline: extract -> judge -> analyze -> publish.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        required=True,
        help="Path to runs directory (contains official/, experiment/, troubleshooting/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Root output directory (default: output/)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip LLM judge evaluation stage",
    )
    parser.add_argument(
        "--judge-template",
        type=Path,
        default=None,
        help="Path to custom judge template JSON (overrides default rubric)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    runs_dir: Path = args.runs_dir
    output_dir: Path = args.output_dir
    metrics_path = output_dir / "experiment_metrics.json"
    analysis_path = output_dir / "analysis_results.json"

    if not runs_dir.is_dir():
        logger.error("Runs directory does not exist: %s", runs_dir)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Extract
    stage_num = 1
    print(
        f"Stage {stage_num}/{_STAGE_COUNT}: Extracting metrics...",
        file=sys.stderr,
    )
    rc = extract.main([
        "--runs-dir", str(runs_dir),
        "--output", str(metrics_path),
    ])
    if rc != 0:
        logger.error("Extract stage failed (exit code %d)", rc)
        return 1

    # Stage 2: Judge
    stage_num = 2
    if args.skip_judge:
        print(
            f"Stage {stage_num}/{_STAGE_COUNT}: Skipping judge (--skip-judge)...",
            file=sys.stderr,
        )
    else:
        print(
            f"Stage {stage_num}/{_STAGE_COUNT}: Running LLM judge...",
            file=sys.stderr,
        )
    judge_argv = [
        "--input", str(metrics_path),
        "--runs-dir", str(runs_dir),
    ]
    if args.skip_judge:
        judge_argv.append("--skip-judge")
    if args.judge_template is not None:
        judge_argv.extend(["--judge-template", str(args.judge_template)])
    rc = judge.main(judge_argv)
    if rc != 0:
        logger.error("Judge stage failed (exit code %d)", rc)
        return 1

    # Stage 3: Analyze
    stage_num = 3
    print(
        f"Stage {stage_num}/{_STAGE_COUNT}: Analyzing results...",
        file=sys.stderr,
    )
    rc = analyze.main([
        "--input", str(metrics_path),
        "--output", str(analysis_path),
    ])
    if rc != 0:
        logger.error("Analyze stage failed (exit code %d)", rc)
        return 1

    # Stage 4: Publish
    stage_num = 4
    print(
        f"Stage {stage_num}/{_STAGE_COUNT}: Publishing artifacts...",
        file=sys.stderr,
    )
    rc = publish.main([
        "--input", str(analysis_path),
        "--output-dir", str(output_dir),
    ])
    if rc != 0:
        logger.error("Publish stage failed (exit code %d)", rc)
        return 1

    # Summary
    total_trials = _count_trials(metrics_path)
    configs = _count_configs(metrics_path)
    total_artifacts = _count_artifacts(output_dir)

    print("\n--- Pipeline Complete ---", file=sys.stderr)
    print(f"Trials processed: {total_trials}", file=sys.stderr)
    print(f"Configs detected: {', '.join(configs) if configs else 'none'}", file=sys.stderr)
    print(f"Artifacts generated: {total_artifacts}", file=sys.stderr)
    print(f"Output directory: {output_dir}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
