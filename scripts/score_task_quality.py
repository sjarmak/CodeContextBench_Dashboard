#!/usr/bin/env python3
"""
Task quality scoring CLI for benchmark tasks.

Scores individual tasks or entire benchmark adapters against HOW2BENCH
quality criteria including instruction clarity, ground truth validity,
and evaluation determinism.

Usage:
    # Score a single task
    python scripts/score_task_quality.py --task_dir path/to/task

    # Score all tasks in an adapter output directory
    python scripts/score_task_quality.py --adapter_dir path/to/adapter_output

    # Score with custom threshold
    python scripts/score_task_quality.py --adapter_dir path/to/output --threshold 0.8

    # Output as markdown
    python scripts/score_task_quality.py --adapter_dir path/to/output --format markdown
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.quality.task_quality_scorer import (
    TaskQualityReport,
    TaskQualityResult,
    TaskQualityScorer,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score benchmark tasks against quality criteria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Score a single task directory
    python scripts/score_task_quality.py --task_dir benchmarks/ainativebench/output/task-001

    # Score all tasks in an adapter output directory
    python scripts/score_task_quality.py --adapter_dir benchmarks/ainativebench/output

    # Use custom threshold and save as JSON
    python scripts/score_task_quality.py --adapter_dir output/ --threshold 0.8 --output report.json

    # Generate markdown report
    python scripts/score_task_quality.py --adapter_dir output/ --format markdown --output report.md
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--task_dir",
        type=Path,
        help="Path to a single task directory to score",
    )
    input_group.add_argument(
        "--adapter_dir",
        type=Path,
        help="Path to adapter output directory containing multiple tasks",
    )

    # Scoring options
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Score threshold for flagging tasks for review (default: 0.7)",
    )
    parser.add_argument(
        "--benchmark_name",
        type=str,
        default="",
        help="Name of the benchmark (defaults to directory name)",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (defaults to task_quality_report.json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "summary"],
        default="json",
        help="Output format (default: json)",
    )

    # Filtering options
    parser.add_argument(
        "--only_failing",
        action="store_true",
        help="Only show tasks that need review",
    )
    parser.add_argument(
        "--min_score",
        type=float,
        default=None,
        help="Only show tasks with score >= this value",
    )
    parser.add_argument(
        "--max_score",
        type=float,
        default=None,
        help="Only show tasks with score <= this value",
    )

    return parser.parse_args()


def format_single_result_summary(result: TaskQualityResult) -> str:
    """Format a single task result as a summary string."""
    status = "NEEDS REVIEW" if result.needs_review else "PASS"
    lines = [
        f"Task: {result.task_id}",
        f"Score: {result.score:.3f} ({status})",
        f"Directory: {result.task_directory}",
        "",
        "Criterion Breakdown:",
    ]

    for cs in result.criterion_scores:
        lines.append(f"  {cs.criterion.value}: {cs.score:.3f} (weight: {cs.weight:.2f})")
        if cs.details:
            for detail_key, detail_val in cs.details.items():
                lines.append(f"    - {detail_key}: {detail_val:.3f}")
        if cs.notes:
            lines.append(f"    Notes: {cs.notes}")

    return "\n".join(lines)


def format_report_summary(report: TaskQualityReport) -> str:
    """Format a report as a summary string."""
    lines = [
        f"Task Quality Report: {report.benchmark_name}",
        "=" * 50,
        f"Total Tasks: {report.total_tasks}",
        f"Mean Score: {report.mean_score:.3f}",
        f"Threshold: {report.threshold}",
        f"Tasks Needing Review: {report.tasks_needing_review} ({report.get_review_rate():.1f}%)",
        "",
        "Score Distribution:",
    ]

    for range_key, count in report.get_score_distribution().items():
        bar = "#" * count
        lines.append(f"  {range_key}: {count:3d} {bar}")

    lines.extend(["", "Criterion Averages:"])
    for criterion, avg in report.get_criterion_averages().items():
        lines.append(f"  {criterion}: {avg:.3f}")

    # List tasks needing review
    tasks_for_review = report.get_tasks_needing_review()
    if tasks_for_review:
        lines.extend(["", "Tasks Needing Review:"])
        for task in sorted(tasks_for_review, key=lambda t: t.score):
            failing = [
                cs.criterion.value
                for cs in task.get_failing_criteria(report.threshold)
            ]
            lines.append(f"  {task.task_id}: {task.score:.3f} - {', '.join(failing)}")

    return "\n".join(lines)


def filter_results(
    report: TaskQualityReport,
    only_failing: bool = False,
    min_score: float | None = None,
    max_score: float | None = None,
) -> TaskQualityReport:
    """Filter report results based on criteria."""
    filtered_results = report.results.copy()

    if only_failing:
        filtered_results = [r for r in filtered_results if r.needs_review]

    if min_score is not None:
        filtered_results = [r for r in filtered_results if r.score >= min_score]

    if max_score is not None:
        filtered_results = [r for r in filtered_results if r.score <= max_score]

    return TaskQualityReport(
        benchmark_name=report.benchmark_name,
        timestamp=report.timestamp,
        results=filtered_results,
        threshold=report.threshold,
        metadata={
            **report.metadata,
            "filtered": True,
            "original_total": report.total_tasks,
        },
    )


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Initialize scorer
    scorer = TaskQualityScorer(threshold=args.threshold)

    # Score task(s)
    if args.task_dir:
        if not args.task_dir.exists():
            print(f"Error: Task directory not found: {args.task_dir}", file=sys.stderr)
            return 1

        result = scorer.score_task(args.task_dir)

        # Output single result
        if args.format == "json":
            output = json.dumps(result.to_dict(), indent=2)
        elif args.format == "markdown":
            # Wrap single result in a mini-report for markdown
            report = TaskQualityReport(
                benchmark_name=args.benchmark_name or args.task_dir.parent.name,
                timestamp=result.timestamp,
                results=[result],
                threshold=args.threshold,
            )
            output = report.to_markdown()
        else:  # summary
            output = format_single_result_summary(result)

        if args.output:
            args.output.write_text(output)
            print(f"Report written to: {args.output}")
        else:
            print(output)

        # Return non-zero if task needs review
        return 1 if result.needs_review else 0

    else:  # adapter_dir
        if not args.adapter_dir.exists():
            print(f"Error: Adapter directory not found: {args.adapter_dir}", file=sys.stderr)
            return 1

        # Score all tasks in directory
        report = scorer.score_adapter_output(
            args.adapter_dir,
            benchmark_name=args.benchmark_name,
        )

        if report.total_tasks == 0:
            print(f"Warning: No tasks found in {args.adapter_dir}", file=sys.stderr)
            return 1

        # Apply filters if specified
        if args.only_failing or args.min_score is not None or args.max_score is not None:
            report = filter_results(
                report,
                only_failing=args.only_failing,
                min_score=args.min_score,
                max_score=args.max_score,
            )

        # Output report
        if args.format == "json":
            output = json.dumps(report.to_dict(), indent=2)
        elif args.format == "markdown":
            output = report.to_markdown()
        else:  # summary
            output = format_report_summary(report)

        # Determine output file
        output_path = args.output
        if output_path is None:
            if args.format == "json":
                output_path = args.adapter_dir / "task_quality_report.json"
            elif args.format == "markdown":
                output_path = args.adapter_dir / "task_quality_report.md"

        if output_path:
            output_path.write_text(output)
            print(f"Report written to: {output_path}")
        else:
            print(output)

        # Print summary to stderr if writing JSON to file
        if args.format == "json" and output_path:
            print(f"\nSummary:", file=sys.stderr)
            print(f"  Total tasks: {report.total_tasks}", file=sys.stderr)
            print(f"  Mean score: {report.mean_score:.3f}", file=sys.stderr)
            print(f"  Tasks needing review: {report.tasks_needing_review}", file=sys.stderr)

        # Return non-zero if any tasks need review
        return 1 if report.tasks_needing_review > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
