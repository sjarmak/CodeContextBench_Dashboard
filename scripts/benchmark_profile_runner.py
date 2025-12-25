#!/usr/bin/env python3
"""CLI entrypoint for CodeContextBench-fft benchmark profile runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.benchmark.lifecycle_pipeline import (  # type: ignore
    PipelineConfigError,
    load_pipeline_config,
)
from src.benchmark.profile_runner import (
    BenchmarkProfileRunner,
    ProfileConfigError,
    load_profile_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Launch Harbor job matrices defined in benchmark profile configs."
            " Profiles reference lifecycle manifests for provenance."
        )
    )
    parser.add_argument(
        "--pipeline-config",
        type=Path,
        default=Path("configs/benchmark_pipeline.yaml"),
        help="Benchmark lifecycle config (defines manifests + artifact paths)",
    )
    parser.add_argument(
        "--profile-config",
        type=Path,
        default=Path("configs/benchmark_profiles.yaml"),
        help="Benchmark profile registry",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        help="Optional list of profile IDs to run (defaults to all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print Harbor commands and provenance manifest locations without running",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pipeline_config = load_pipeline_config(args.pipeline_config)
        profile_config = load_profile_config(args.profile_config)
    except (PipelineConfigError, ProfileConfigError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[1]

    runner = BenchmarkProfileRunner(
        pipeline_config=pipeline_config,
        profile_config=profile_config,
        project_root=project_root,
        dry_run=args.dry_run,
    )

    try:
        run_dirs = runner.run(args.profiles)
    except ProfileConfigError as exc:
        print(f"Profile runner error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run complete. Outputs would be staged in:")
    else:
        print("Benchmark profiles complete. Outputs written to:")

    for profile_id, run_dir in run_dirs.items():
        print(f"  - {profile_id}: {run_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
