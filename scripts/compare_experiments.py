#!/usr/bin/env python3
"""CLI wrapper for the unified experiment comparison pipeline.

Usage:
    python scripts/compare_experiments.py <baseline_dir> <treatment_dir> [options]

Example:
    python scripts/compare_experiments.py \\
        ~/evals/runs/baseline \\
        ~/evals/runs/treatment \\
        --format both --output-dir ./reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path so src.analysis is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.analysis.experiment_comparator import ExperimentComparison


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a statistically rigorous comparison between two experiment directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/compare_experiments.py ./baseline ./treatment\n"
            "  python scripts/compare_experiments.py ./baseline ./treatment --format json\n"
            "  python scripts/compare_experiments.py ./baseline ./treatment --seed 42 --resamples 5000\n"
        ),
    )
    parser.add_argument("baseline_dir", type=Path, help="Path to baseline experiment directory")
    parser.add_argument("treatment_dir", type=Path, help="Path to treatment experiment directory")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory for output files (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--resamples",
        type=int,
        default=10000,
        help="Number of bootstrap resamples (default: 10000)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Confidence level for intervals (default: 0.95)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional)",
    )
    parser.add_argument(
        "--min-category-size",
        type=int,
        default=5,
        help="Minimum tasks per category for bootstrap (default: 5)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the experiment comparison CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    baseline_dir: Path = args.baseline_dir.resolve()
    treatment_dir: Path = args.treatment_dir.resolve()
    output_dir: Path = args.output_dir.resolve()

    if not baseline_dir.is_dir():
        print(f"Error: baseline directory does not exist: {baseline_dir}", file=sys.stderr)
        return 1

    if not treatment_dir.is_dir():
        print(f"Error: treatment directory does not exist: {treatment_dir}", file=sys.stderr)
        return 1

    try:
        comparator = ExperimentComparison(
            n_resamples=args.resamples,
            confidence=args.confidence,
            random_seed=args.seed,
            min_category_size=args.min_category_size,
        )
        report = comparator.compare(baseline_dir, treatment_dir)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Print summary to stdout.
    overall = report.overall_bootstrap
    alignment = report.alignment
    print(f"Comparison: {report.baseline_dir} vs {report.treatment_dir}")
    print(f"Common tasks: {len(alignment.common_tasks)}")
    print(
        f"Excluded: {len(alignment.baseline_only)} baseline-only, "
        f"{len(alignment.treatment_only)} treatment-only"
    )
    print(f"Mean delta: {overall.mean_delta:.4f}")
    print(f"95% CI: [{overall.ci_lower:.4f}, {overall.ci_upper:.4f}]")
    print(f"p-value: {overall.p_value:.4f}")
    print(f"Effect size (Cohen's d): {overall.effect_size:.4f} ({overall.effect_interpretation})")

    # Write output files.
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("markdown", "both"):
        md_path = output_dir / "comparison_report.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        print(f"\nMarkdown report: {md_path}")

    if args.format in ("json", "both"):
        json_path = output_dir / "comparison_report.json"
        report.save_json(json_path)
        print(f"JSON report: {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
