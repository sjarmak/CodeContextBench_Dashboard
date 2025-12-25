#!/usr/bin/env python3
"""
Post-Process Experiment Script

Orchestrates the complete post-run evaluation pipeline:
1. Extract metrics from Harbor results
2. Load benchmark manifest metadata
3. Run LLM judge evaluations (optional)
4. Generate evaluation_report.json
5. Generate REPORT.md

Usage:
    python scripts/postprocess_experiment.py <experiment_dir> [options]

Example:
    python scripts/postprocess_experiment.py jobs/2025-12-23__11-13-40 --judge --benchmark repoqa
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.metrics_extractor import extract_experiment_metrics
from benchmark.evaluation_schema import (
    ExperimentEvaluation,
    load_benchmark_manifest,
)
from benchmark.report_generator import generate_report_md

try:
    from benchmark.llm_judge import (
        LLMJudge,
        extract_tool_calls_from_trajectory,
        extract_code_changes_from_trajectory,
        load_task_description,
    )

    LLM_JUDGE_AVAILABLE = True
except ImportError:
    LLM_JUDGE_AVAILABLE = False
    print("Warning: anthropic package not installed. LLM judge evaluation disabled.")
    print("Install with: pip install anthropic")

import json


def postprocess_experiment(
    experiment_dir: Path,
    benchmark_id: Optional[str] = None,
    profile_name: Optional[str] = None,
    run_judge: bool = False,
    judge_model: str = "claude-haiku-4-5-20251001",
    output_dir: Optional[Path] = None,
):
    """
    Post-process an experiment directory.

    Args:
        experiment_dir: Path to experiment directory (e.g., jobs/2025-12-23__11-13-40/)
        benchmark_id: Benchmark ID for loading manifest (e.g., "repoqa")
        profile_name: Profile name if this was a profile run
        run_judge: Whether to run LLM judge evaluation
        judge_model: Model to use for judging
        output_dir: Where to write outputs (defaults to experiment_dir)
    """
    print(f"🔄 Post-processing experiment: {experiment_dir.name}")
    print()

    if not experiment_dir.exists():
        print(f"❌ Error: Experiment directory not found: {experiment_dir}")
        sys.exit(1)

    # Determine output directory
    if output_dir is None:
        output_dir = experiment_dir

    # Step 1: Extract metrics
    print("📊 Step 1: Extracting metrics from Harbor results...")
    agent_runs = extract_experiment_metrics(experiment_dir)

    if not agent_runs:
        print(f"⚠️  Warning: No agent runs found in {experiment_dir}")
        print("   Make sure the directory contains trial subdirectories with result.json files.")
        sys.exit(1)

    print(f"   ✓ Found {len(agent_runs)} agent runs")
    print()

    # Step 2: Load benchmark manifest
    benchmark_metadata = None
    if benchmark_id:
        print(f"📋 Step 2: Loading benchmark manifest for '{benchmark_id}'...")
        manifest_path = Path("benchmarks") / benchmark_id / "MANIFEST.json"

        if manifest_path.exists():
            benchmark_metadata = load_benchmark_manifest(manifest_path)
            print(f"   ✓ Loaded manifest from {manifest_path}")
        else:
            print(f"   ⚠️  Manifest not found: {manifest_path}")

        print()

    # Step 3: Run LLM judge (optional)
    if run_judge:
        if not LLM_JUDGE_AVAILABLE:
            print("❌ Error: LLM judge requested but anthropic package not installed")
            sys.exit(1)

        print(f"🤖 Step 3: Running LLM judge evaluation (model: {judge_model})...")
        judge = LLMJudge(model=judge_model)

        benchmarks_dir = Path("benchmarks")

        for i, run in enumerate(agent_runs, 1):
            print(f"   [{i}/{len(agent_runs)}] Judging {run.task_name}...", end=" ")

            # Load trajectory
            trajectory_path = Path(run.trajectory_path)
            if not trajectory_path.exists():
                print("⚠️  trajectory not found")
                continue

            with open(trajectory_path) as f:
                trajectory = json.load(f)

            # Load task description
            task_path = benchmarks_dir / benchmark_id / run.task_name
            if not task_path.exists():
                # Try to infer from trajectory
                task_path = Path(run.task_name)

            task_description = load_task_description(task_path) if task_path.exists() else "No description"

            # Extract tool calls and code changes
            tool_calls = extract_tool_calls_from_trajectory(trajectory)
            code_changes = extract_code_changes_from_trajectory(trajectory)

            # Evaluate
            retrieval_assessment = judge.evaluate_retrieval(task_description, tool_calls)
            code_assessment = judge.evaluate_code(task_description, code_changes, run.reward)

            run.judge_assessments = [retrieval_assessment, code_assessment]

            print(
                f"✓ (retrieval: {retrieval_assessment.score}/5, code: {code_assessment.score}/5)"
            )

        print()

    # Step 4: Generate evaluation report
    print("📄 Step 4: Generating evaluation_report.json...")

    evaluation = ExperimentEvaluation(
        experiment_id=experiment_dir.name,
        experiment_description=f"Experiment run on {experiment_dir.name}",
        profile_name=profile_name,
        benchmark_metadata=benchmark_metadata,
        agent_runs=agent_runs,
    )

    report_path = output_dir / "evaluation_report.json"
    evaluation.save(report_path)

    print(f"   ✓ Saved: {report_path}")
    print()

    # Step 5: Generate REPORT.md
    print("📝 Step 5: Generating REPORT.md...")

    md_path = output_dir / "REPORT.md"
    generate_report_md(evaluation.to_dict(), md_path)

    print(f"   ✓ Saved: {md_path}")
    print()

    # Summary
    print("✅ Post-processing complete!")
    print()
    print("📊 Summary:")

    summary = evaluation.summary
    agents = summary.get("agents", {})

    for agent_name, stats in sorted(agents.items()):
        success_rate = stats.get("success_rate", 0) * 100
        total_runs = stats.get("total_runs", 0)
        avg_tokens = stats.get("avg_tokens", 0)

        print(f"   {agent_name}:")
        print(f"      Runs: {total_runs}, Success Rate: {success_rate:.1f}%, Avg Tokens: {avg_tokens:,.0f}")

        if run_judge:
            judge_scores = stats.get("judge_scores", {})
            for dimension, scores in judge_scores.items():
                if isinstance(scores, dict):
                    mean = scores.get("mean", 0)
                    print(f"      {dimension.replace('_', ' ').title()}: {mean:.2f}/5")

    print()
    print(f"📁 Outputs:")
    print(f"   - {report_path}")
    print(f"   - {md_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Post-process experiment with metrics, manifest, and LLM judge"
    )

    parser.add_argument("experiment_dir", type=Path, help="Path to experiment directory")

    parser.add_argument(
        "--benchmark", "-b", help="Benchmark ID for loading manifest (e.g., repoqa, dibench)"
    )

    parser.add_argument(
        "--profile", "-p", help="Profile name if this was a profile run"
    )

    parser.add_argument(
        "--judge",
        action="store_true",
        help="Run LLM judge evaluation (requires ANTHROPIC_API_KEY)",
    )

    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Model for LLM judge (default: claude-haiku-4-5-20251001)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory (defaults to experiment_dir)",
    )

    args = parser.parse_args()

    postprocess_experiment(
        experiment_dir=args.experiment_dir,
        benchmark_id=args.benchmark,
        profile_name=args.profile,
        run_judge=args.judge,
        judge_model=args.judge_model,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
