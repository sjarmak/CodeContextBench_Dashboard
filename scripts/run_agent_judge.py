#!/usr/bin/env python3
"""
Agent-as-a-Judge CLI for batch evaluation of Harbor benchmark results.

Evaluates Harbor results against specified criteria using LLM-based judgment,
supporting both Anthropic (Claude) and OpenAI backends.

Usage:
    # Evaluate all results in a directory
    python scripts/run_agent_judge.py --results_dir ~/evals/my_run --criteria_file criteria.json

    # Use custom model and output location
    python scripts/run_agent_judge.py --results_dir ./results --model claude-opus-4-20250514 --output_dir ./judgments

    # Dry run to see what would be evaluated
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.yaml --dry_run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation.agent_judge import AgentJudge, HarborResult, JudgmentResult


@dataclass
class EvaluationSummary:
    """Summary statistics for batch evaluation."""

    total_tasks: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
    mean_overall_score: float = 0.0
    mean_confidence: float = 0.0
    score_distribution: dict[str, int] = field(default_factory=dict)
    criteria_satisfaction: dict[str, float] = field(default_factory=dict)
    model_used: str = ""
    evaluation_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_tasks": self.total_tasks,
            "successful_evaluations": self.successful_evaluations,
            "failed_evaluations": self.failed_evaluations,
            "mean_overall_score": self.mean_overall_score,
            "mean_confidence": self.mean_confidence,
            "score_distribution": self.score_distribution,
            "criteria_satisfaction": self.criteria_satisfaction,
            "model_used": self.model_used,
            "evaluation_timestamp": self.evaluation_timestamp,
        }


def load_criteria(criteria_path: Path) -> list[str]:
    """
    Load evaluation criteria from JSON or YAML file.

    Supports formats:
    - JSON array: ["criterion 1", "criterion 2"]
    - JSON object: {"criteria": ["criterion 1", "criterion 2"]}
    - YAML list or mapping with "criteria" key
    """
    if not criteria_path.exists():
        raise FileNotFoundError(f"Criteria file not found: {criteria_path}")

    content = criteria_path.read_text()
    suffix = criteria_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml

            data = yaml.safe_load(content)
        except ImportError as err:
            raise ImportError(
                "PyYAML required for YAML criteria files. Install with: pip install pyyaml"
            ) from err
    else:
        # Assume JSON
        data = json.loads(content)

    # Extract criteria list
    if isinstance(data, list):
        return [str(c) for c in data]
    elif isinstance(data, dict) and "criteria" in data:
        return [str(c) for c in data["criteria"]]
    else:
        raise ValueError(
            "Criteria file must be a JSON/YAML array or object with 'criteria' key"
        )


def find_harbor_results(results_dir: Path) -> list[tuple[str, Path]]:
    """
    Find all Harbor result files in directory.

    Looks for result.json files and extracts task IDs from directory structure.
    Returns list of (task_id, result_path) tuples.
    """
    results = []

    # Pattern 1: task_id/result.json
    for result_path in results_dir.rglob("result.json"):
        # Get task_id from parent directory name
        task_id = result_path.parent.name
        results.append((task_id, result_path))

    # Deduplicate by task_id, preferring shorter paths
    seen: dict[str, Path] = {}
    for task_id, result_path in results:
        if task_id not in seen or len(str(result_path)) < len(str(seen[task_id])):
            seen[task_id] = result_path

    return sorted(seen.items())


def load_harbor_result(task_id: str, result_path: Path) -> HarborResult | None:
    """Load and parse a Harbor result file into HarborResult."""
    try:
        with open(result_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Warning: Could not load {result_path}: {e}")
        return None

    # Extract task description from various possible locations
    task_description = ""

    # Try instruction.md in task directory
    task_dir = result_path.parent
    instruction_path = task_dir / "instruction.md"
    if instruction_path.exists():
        task_description = instruction_path.read_text()[:10000]

    # Try from result data itself
    if not task_description:
        task_description = data.get("task_description", "")
        if not task_description:
            task_description = data.get("task", {}).get("description", "")

    # Extract agent output from various possible locations
    agent_output = ""

    # Try trajectory.json
    trajectory_path = task_dir / "trajectory.json"
    if trajectory_path.exists():
        try:
            with open(trajectory_path) as f:
                trajectory = json.load(f)
            # Extract final agent response or all agent steps
            steps = trajectory.get("steps", [])
            agent_steps = [
                s.get("content", "") for s in steps if s.get("source") == "agent"
            ]
            agent_output = "\n\n---\n\n".join(
                str(s)[:5000] for s in agent_steps[-5:]
            )  # Last 5 agent steps
        except Exception:
            pass

    # Fallback to result data
    if not agent_output:
        agent_output = data.get("agent_output", "")
        if not agent_output:
            agent_output = str(data.get("verifier_result", {}))[:5000]

    # Extract ground truth if available
    ground_truth = None
    gt_path = task_dir / "ground_truth.json"
    if gt_path.exists():
        try:
            with open(gt_path) as f:
                gt_data = json.load(f)
            ground_truth = json.dumps(gt_data, indent=2)[:5000]
        except Exception:
            pass

    if not task_description and not agent_output:
        print(f"  Warning: No usable content found for {task_id}")
        return None

    return HarborResult(
        task_id=task_id,
        task_description=task_description or f"Task: {task_id}",
        agent_output=agent_output or "No agent output available",
        ground_truth=ground_truth,
        metadata={"source_path": str(result_path), "raw_result": data},
    )


def compute_summary(
    judgments: dict[str, JudgmentResult], model: str
) -> EvaluationSummary:
    """Compute aggregate statistics from evaluation results."""
    if not judgments:
        return EvaluationSummary(
            model_used=model, evaluation_timestamp=datetime.now().isoformat()
        )

    total = len(judgments)
    successful = sum(1 for j in judgments.values() if j.confidence > 0)
    failed = total - successful

    # Compute mean scores
    scores = [j.overall_score for j in judgments.values() if j.confidence > 0]
    confidences = [j.confidence for j in judgments.values() if j.confidence > 0]

    mean_score = sum(scores) / len(scores) if scores else 0.0
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Score distribution (buckets: 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0)
    distribution = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for score in scores:
        if score < 0.2:
            distribution["0.0-0.2"] += 1
        elif score < 0.4:
            distribution["0.2-0.4"] += 1
        elif score < 0.6:
            distribution["0.4-0.6"] += 1
        elif score < 0.8:
            distribution["0.6-0.8"] += 1
        else:
            distribution["0.8-1.0"] += 1

    # Criteria satisfaction rates
    criteria_counts: dict[str, list[float]] = {}
    for judgment in judgments.values():
        for crit_id, req_score in judgment.requirement_scores.items():
            if crit_id not in criteria_counts:
                criteria_counts[crit_id] = []
            criteria_counts[crit_id].append(1.0 if req_score.satisfied else 0.0)

    criteria_satisfaction = {
        crit_id: sum(vals) / len(vals) if vals else 0.0
        for crit_id, vals in criteria_counts.items()
    }

    return EvaluationSummary(
        total_tasks=total,
        successful_evaluations=successful,
        failed_evaluations=failed,
        mean_overall_score=mean_score,
        mean_confidence=mean_confidence,
        score_distribution=distribution,
        criteria_satisfaction=criteria_satisfaction,
        model_used=model,
        evaluation_timestamp=datetime.now().isoformat(),
    )


def print_progress(current: int, total: int) -> None:
    """Print progress indicator."""
    print(f"  Progress: {current}/{total} ({100 * current // total}%)", end="\r")


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Batch evaluate Harbor results using agent-as-a-judge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage with criteria file
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.json

    # Use Anthropic's Claude model (default)
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.json --model claude-sonnet-4-20250514

    # Use OpenAI's GPT-4
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.json --model gpt-4o

    # Custom output directory
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.json --output_dir ./judgments

    # Dry run to see what would be evaluated
    python scripts/run_agent_judge.py --results_dir ./results --criteria_file criteria.json --dry_run
""",
    )

    parser.add_argument(
        "--results_dir",
        type=Path,
        required=True,
        help="Directory containing Harbor result files (result.json)",
    )
    parser.add_argument(
        "--criteria_file",
        type=Path,
        required=True,
        help="Path to evaluation criteria file (JSON or YAML)",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=None,
        help="Output directory for judgment files (default: results_dir/judgments)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-20250514",
        help="Model to use for evaluation (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Show what would be evaluated without making LLM calls",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress information",
    )

    args = parser.parse_args()

    # Validate results directory
    if not args.results_dir.exists():
        print(f"ERROR: Results directory not found: {args.results_dir}")
        return 1

    if not args.results_dir.is_dir():
        print(f"ERROR: Not a directory: {args.results_dir}")
        return 1

    # Load criteria
    try:
        criteria = load_criteria(args.criteria_file)
        print(f"Loaded {len(criteria)} evaluation criteria from {args.criteria_file}")
    except Exception as e:
        print(f"ERROR: Failed to load criteria: {e}")
        return 1

    if args.verbose:
        for i, c in enumerate(criteria, 1):
            print(f"  {i}. {c[:80]}{'...' if len(c) > 80 else ''}")

    # Find Harbor results
    result_files = find_harbor_results(args.results_dir)
    print(f"Found {len(result_files)} Harbor result files")

    if not result_files:
        print("ERROR: No result.json files found in results directory")
        return 1

    # Setup output directory
    output_dir = args.output_dir or args.results_dir / "judgments"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Dry run - just show what would be evaluated
    if args.dry_run:
        print("\n=== DRY RUN ===")
        print(f"Would evaluate {len(result_files)} tasks:")
        for task_id, result_path in result_files:
            print(f"  - {task_id}: {result_path}")
        print(f"\nCriteria ({len(criteria)}):")
        for c in criteria:
            print(f"  - {c[:100]}")
        print(f"\nModel: {args.model}")
        print(f"Output: {output_dir}")
        return 0

    # Check for API key before starting
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    if not has_anthropic and not has_openai:
        print("ERROR: No API key found.")
        print("Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable.")
        return 1

    # Initialize judge
    try:
        judge = AgentJudge(model=args.model)
        print(f"Initialized AgentJudge with model: {args.model}")
    except Exception as e:
        print(f"ERROR: Failed to initialize AgentJudge: {e}")
        return 1

    # Evaluate each result
    print(f"\nEvaluating {len(result_files)} tasks...")
    judgments: dict[str, JudgmentResult] = {}

    for i, (task_id, result_path) in enumerate(result_files, 1):
        if args.verbose:
            print(f"\n[{i}/{len(result_files)}] Evaluating: {task_id}")
        else:
            print_progress(i, len(result_files))

        # Load Harbor result
        harbor_result = load_harbor_result(task_id, result_path)
        if harbor_result is None:
            print(f"\n  Skipping {task_id}: Could not load result")
            continue

        # Evaluate
        try:
            judgment = judge.evaluate_result(harbor_result, criteria)
            judgments[task_id] = judgment

            # Save individual judgment file
            judgment_path = output_dir / f"{task_id}_judgment.json"
            with open(judgment_path, "w") as f:
                json.dump(judgment.to_dict(), f, indent=2)

            if args.verbose:
                print(
                    f"  Score: {judgment.overall_score:.2f}, "
                    f"Confidence: {judgment.confidence:.2f}"
                )
        except Exception as e:
            print(f"\n  ERROR evaluating {task_id}: {e}")

    print()  # Clear progress line

    # Compute and save summary
    summary = compute_summary(judgments, args.model)
    summary_path = output_dir / "summary_report.json"
    with open(summary_path, "w") as f:
        json.dump(summary.to_dict(), f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total tasks:              {summary.total_tasks}")
    print(f"Successful evaluations:   {summary.successful_evaluations}")
    print(f"Failed evaluations:       {summary.failed_evaluations}")
    print(f"Mean overall score:       {summary.mean_overall_score:.3f}")
    print(f"Mean confidence:          {summary.mean_confidence:.3f}")
    print(f"Model used:               {summary.model_used}")
    print()

    # Score distribution
    print("Score Distribution:")
    for bucket, count in sorted(summary.score_distribution.items()):
        bar = "█" * count
        print(f"  {bucket}: {count:3d} {bar}")
    print()

    # Criteria satisfaction
    if summary.criteria_satisfaction:
        print("Criteria Satisfaction Rates:")
        for crit_id, rate in sorted(
            summary.criteria_satisfaction.items(), key=lambda x: x[1], reverse=True
        ):
            pct = 100 * rate
            bar = "█" * int(pct / 5)
            print(f"  {crit_id}: {pct:5.1f}% {bar}")
    print()

    print(f"Individual judgments saved to: {output_dir}/")
    print(f"Summary report saved to: {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
