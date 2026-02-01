#!/usr/bin/env python3
"""
CLI for running pre-flight validation on Harbor benchmark adapters.

Validates task directories against pre-flight checks before deployment.

Usage:
    python scripts/validate_adapter.py --adapter_dir path/to/adapter/output
    python scripts/validate_adapter.py --task_dir path/to/single/task
    python scripts/validate_adapter.py --adapter_dir path/to/adapter --output_dir reports/
    python scripts/validate_adapter.py --adapter_dir path/to/adapter --format json
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quality.preflight_validator import PreflightValidator, ValidationReport


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run pre-flight validation on Harbor benchmark adapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate all tasks in an adapter output directory
    python scripts/validate_adapter.py --adapter_dir benchmarks/ainativebench/output

    # Validate a single task directory
    python scripts/validate_adapter.py --task_dir benchmarks/ainativebench/output/task_001

    # Output JSON reports to a directory
    python scripts/validate_adapter.py --adapter_dir output/ --output_dir reports/ --format json

    # Generate markdown reports
    python scripts/validate_adapter.py --adapter_dir output/ --output_dir reports/ --format markdown
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--adapter_dir",
        type=Path,
        help="Path to adapter output directory containing task directories",
    )
    input_group.add_argument(
        "--task_dir",
        type=Path,
        help="Path to a single task directory to validate",
    )

    # Output options
    parser.add_argument(
        "--output_dir",
        type=Path,
        help="Directory to write validation reports (default: print to stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )

    # Behavior options
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any check fails (including warnings)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output final summary, suppress individual task details",
    )

    return parser.parse_args()


def print_summary_report(report: ValidationReport, quiet: bool = False) -> None:
    """Print a summary of a validation report."""
    status = "PASS" if report.overall_passed else "FAIL"
    status_color = "\033[92m" if report.overall_passed else "\033[91m"
    reset_color = "\033[0m"

    print(f"{status_color}[{status}]{reset_color} {report.task_id}")

    if not quiet:
        # Print critical failures
        failed_critical = report.get_failed_critical()
        if failed_critical:
            for check in failed_critical:
                print(f"  CRITICAL: {check.check_id} - {check.message}")
                if check.evidence:
                    print(f"            {check.evidence}")

        # Print warnings
        failed_warnings = report.get_failed_warnings()
        if failed_warnings:
            for check in failed_warnings:
                print(f"  WARNING:  {check.check_id} - {check.message}")


def save_json_report(report: ValidationReport, output_path: Path) -> None:
    """Save a validation report as JSON."""
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)


def save_markdown_report(report: ValidationReport, output_path: Path) -> None:
    """Save a validation report as markdown."""
    with open(output_path, "w") as f:
        f.write(report.to_markdown())


def generate_aggregate_summary(reports: list[ValidationReport]) -> dict[str, int | float]:
    """Generate aggregate statistics from multiple reports."""
    total_tasks = len(reports)
    passed_tasks = sum(1 for r in reports if r.overall_passed)
    failed_tasks = total_tasks - passed_tasks

    total_critical_checks = sum(r.critical_total for r in reports)
    passed_critical_checks = sum(r.critical_passed for r in reports)
    total_warning_checks = sum(r.warning_total for r in reports)
    passed_warning_checks = sum(r.warning_passed for r in reports)

    return {
        "total_tasks": total_tasks,
        "passed_tasks": passed_tasks,
        "failed_tasks": failed_tasks,
        "pass_rate": (passed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0,
        "total_critical_checks": total_critical_checks,
        "passed_critical_checks": passed_critical_checks,
        "critical_pass_rate": (
            passed_critical_checks / total_critical_checks * 100
            if total_critical_checks > 0
            else 0.0
        ),
        "total_warning_checks": total_warning_checks,
        "passed_warning_checks": passed_warning_checks,
        "warning_pass_rate": (
            passed_warning_checks / total_warning_checks * 100
            if total_warning_checks > 0
            else 0.0
        ),
    }


def print_aggregate_summary(summary: dict[str, int | float]) -> None:
    """Print aggregate summary statistics."""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Tasks:           {summary['passed_tasks']}/{summary['total_tasks']} passed "
          f"({summary['pass_rate']:.1f}%)")
    print(f"Critical Checks: {summary['passed_critical_checks']}/{summary['total_critical_checks']} passed "
          f"({summary['critical_pass_rate']:.1f}%)")
    print(f"Warning Checks:  {summary['passed_warning_checks']}/{summary['total_warning_checks']} passed "
          f"({summary['warning_pass_rate']:.1f}%)")
    print("=" * 60)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    validator = PreflightValidator()

    # Collect reports
    reports: list[ValidationReport] = []

    if args.task_dir:
        # Validate single task
        if not args.task_dir.exists():
            print(f"Error: Task directory not found: {args.task_dir}", file=sys.stderr)
            return 1
        reports.append(validator.validate_task_directory(args.task_dir))
    else:
        # Validate adapter directory
        if not args.adapter_dir.exists():
            print(f"Error: Adapter directory not found: {args.adapter_dir}", file=sys.stderr)
            return 1
        reports = validator.validate_adapter_directory(args.adapter_dir)

        if not reports:
            print(f"Warning: No task directories found in {args.adapter_dir}", file=sys.stderr)
            return 0

    # Create output directory if needed
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Process reports
    for report in reports:
        if args.format == "summary":
            print_summary_report(report, quiet=args.quiet)
        elif args.format == "json":
            if args.output_dir:
                output_path = args.output_dir / f"{report.task_id}_validation.json"
                save_json_report(report, output_path)
                if not args.quiet:
                    print(f"Wrote: {output_path}")
            else:
                print(json.dumps(report.to_dict(), indent=2))
        elif args.format == "markdown":
            if args.output_dir:
                output_path = args.output_dir / f"{report.task_id}_validation.md"
                save_markdown_report(report, output_path)
                if not args.quiet:
                    print(f"Wrote: {output_path}")
            else:
                print(report.to_markdown())

    # Print aggregate summary for multiple tasks
    if len(reports) > 1:
        summary = generate_aggregate_summary(reports)
        print_aggregate_summary(summary)

        # Save aggregate summary if output directory specified
        if args.output_dir:
            summary_path = args.output_dir / "validation_summary.json"
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
            if not args.quiet:
                print(f"Wrote summary: {summary_path}")

    # Determine exit code
    all_passed = all(r.overall_passed for r in reports)
    any_warnings = any(r.get_failed_warnings() for r in reports)

    if args.strict:
        # Strict mode: fail on any check failure
        if not all_passed or any_warnings:
            return 1
    else:
        # Normal mode: fail only on critical failures
        if not all_passed:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
