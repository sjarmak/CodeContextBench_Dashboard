#!/usr/bin/env python3
"""
CLI for running documentation compliance audits on benchmark directories.

Validates benchmarks against documentation requirements including
README.md presence and sections, DESIGN.md with task selection rationale,
and LICENSE compatibility with data source attribution.

Usage:
    python scripts/audit_benchmark.py --benchmark_dir benchmarks/ainativebench
    python scripts/audit_benchmark.py --benchmarks_dir benchmarks/ --output_dir reports/
    python scripts/audit_benchmark.py --benchmark_dir benchmarks/devai --format markdown
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quality.compliance_auditor import ComplianceAuditor, ComplianceReport


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run documentation compliance audit on benchmark directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Audit a single benchmark directory
    python scripts/audit_benchmark.py --benchmark_dir benchmarks/ainativebench

    # Audit all benchmarks in a parent directory
    python scripts/audit_benchmark.py --benchmarks_dir benchmarks/

    # Output JSON reports to a directory
    python scripts/audit_benchmark.py --benchmarks_dir benchmarks/ --output_dir reports/ --format json

    # Generate markdown reports
    python scripts/audit_benchmark.py --benchmark_dir benchmarks/devai --format markdown

    # Strict mode - fail on any non-passing check
    python scripts/audit_benchmark.py --benchmark_dir benchmarks/ainativebench --strict
        """,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--benchmark_dir",
        type=Path,
        help="Path to a single benchmark directory to audit",
    )
    input_group.add_argument(
        "--benchmarks_dir",
        type=Path,
        help="Path to parent directory containing multiple benchmark directories",
    )

    # Output options
    parser.add_argument(
        "--output_dir",
        type=Path,
        help="Directory to write audit reports (default: print to stdout)",
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
        help="Exit with non-zero status if any check fails (including important/recommended)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output final summary, suppress individual benchmark details",
    )

    return parser.parse_args()


def print_summary_report(report: ComplianceReport, quiet: bool = False) -> None:
    """Print a summary of a compliance report."""
    status = "PASS" if report.overall_passed else "FAIL"
    status_color = "\033[92m" if report.overall_passed else "\033[91m"
    reset_color = "\033[0m"

    print(f"{status_color}[{status}]{reset_color} {report.benchmark_name}")

    if not quiet:
        # Print critical failures
        failed_critical = report.get_failed_critical()
        if failed_critical:
            for check in failed_critical:
                print(f"  CRITICAL: {check.check_id} - {check.notes}")
                if check.evidence:
                    print(f"            {check.evidence}")

        # Print important failures
        failed_important = report.get_failed_important()
        if failed_important:
            for check in failed_important:
                print(f"  IMPORTANT: {check.check_id} - {check.notes}")


def save_json_report(report: ComplianceReport, output_path: Path) -> None:
    """Save a compliance report as JSON."""
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)


def save_markdown_report(report: ComplianceReport, output_path: Path) -> None:
    """Save a compliance report as markdown."""
    with open(output_path, "w") as f:
        f.write(report.to_markdown())


def print_aggregate_summary(summary: dict[str, int | float]) -> None:
    """Print aggregate summary statistics."""
    print("\n" + "=" * 60)
    print("COMPLIANCE AUDIT SUMMARY")
    print("=" * 60)
    print(
        f"Benchmarks:      {summary['passed_benchmarks']}/{summary['total_benchmarks']} passed "
        f"({summary['benchmark_pass_rate']:.1f}%)"
    )
    print(
        f"Critical Checks: {summary['passed_critical_checks']}/{summary['total_critical_checks']} passed "
        f"({summary['critical_pass_rate']:.1f}%)"
    )
    print(
        f"Important Checks: {summary['passed_important_checks']}/{summary['total_important_checks']} passed "
        f"({summary['important_pass_rate']:.1f}%)"
    )
    print(
        f"Recommended:     {summary['passed_recommended_checks']}/{summary['total_recommended_checks']} passed "
        f"({summary['recommended_pass_rate']:.1f}%)"
    )
    print("=" * 60)


def find_benchmark_directories(parent_dir: Path) -> list[Path]:
    """
    Find benchmark directories within a parent directory.

    A benchmark directory is identified by containing either:
    - adapter.py
    - README.md
    - tasks/ subdirectory
    """
    benchmark_dirs: list[Path] = []

    for item in parent_dir.iterdir():
        if not item.is_dir():
            continue
        # Skip hidden directories and common non-benchmark directories
        if item.name.startswith(".") or item.name in ["__pycache__", "node_modules"]:
            continue

        # Check if it looks like a benchmark directory
        has_adapter = (item / "adapter.py").exists()
        has_readme = (item / "README.md").exists()
        has_tasks = (item / "tasks").is_dir()

        if has_adapter or has_readme or has_tasks:
            benchmark_dirs.append(item)

    return sorted(benchmark_dirs)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    auditor = ComplianceAuditor()

    # Collect reports
    reports: list[ComplianceReport] = []

    if args.benchmark_dir:
        # Audit single benchmark
        if not args.benchmark_dir.exists():
            print(
                f"Error: Benchmark directory not found: {args.benchmark_dir}",
                file=sys.stderr,
            )
            return 1
        reports.append(auditor.audit_benchmark(args.benchmark_dir))
    else:
        # Audit all benchmarks in parent directory
        if not args.benchmarks_dir.exists():
            print(
                f"Error: Benchmarks directory not found: {args.benchmarks_dir}",
                file=sys.stderr,
            )
            return 1

        benchmark_dirs = find_benchmark_directories(args.benchmarks_dir)
        if not benchmark_dirs:
            print(
                f"Warning: No benchmark directories found in {args.benchmarks_dir}",
                file=sys.stderr,
            )
            return 0

        reports = auditor.audit_multiple_benchmarks(benchmark_dirs)

    # Create output directory if needed
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Process reports
    for report in reports:
        if args.format == "summary":
            print_summary_report(report, quiet=args.quiet)
        elif args.format == "json":
            if args.output_dir:
                output_path = args.output_dir / f"{report.benchmark_name}_compliance.json"
                save_json_report(report, output_path)
                if not args.quiet:
                    print(f"Wrote: {output_path}")
            else:
                print(json.dumps(report.to_dict(), indent=2))
        elif args.format == "markdown":
            if args.output_dir:
                output_path = args.output_dir / f"{report.benchmark_name}_compliance.md"
                save_markdown_report(report, output_path)
                if not args.quiet:
                    print(f"Wrote: {output_path}")
            else:
                print(report.to_markdown())

    # Print aggregate summary for multiple benchmarks
    if len(reports) > 1:
        summary = auditor.generate_aggregate_summary(reports)
        print_aggregate_summary(summary)

        # Save aggregate summary if output directory specified
        if args.output_dir:
            summary_path = args.output_dir / "compliance_summary.json"
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)
            if not args.quiet:
                print(f"Wrote summary: {summary_path}")

    # Determine exit code
    all_passed = all(r.overall_passed for r in reports)
    any_important_failed = any(r.get_failed_important() for r in reports)

    if args.strict:
        # Strict mode: fail on any check failure
        if not all_passed or any_important_failed:
            return 1
    else:
        # Normal mode: fail only on critical failures
        if not all_passed:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
