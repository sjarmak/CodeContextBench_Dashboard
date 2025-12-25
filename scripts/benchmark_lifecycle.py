#!/usr/bin/env python3
"""CLI entrypoint for the benchmark lifecycle pipeline (CodeContextBench-cu8)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.benchmark.lifecycle_pipeline import (
    BenchmarkLifecyclePipeline,
    PipelineConfigError,
    load_pipeline_config,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Chain benchmark creation, adapter refresh, Harbor validation, "
            "and manifest emission into a reproducible workflow"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/benchmark_pipeline.yaml"),
        help="Path to lifecycle pipeline YAML config",
    )
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        help="Optional benchmark IDs to run (defaults to all defined benchmarks)",
    )
    parser.add_argument(
        "--logs-root",
        type=Path,
        default=None,
        help="Override directory for pipeline logs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands and manifest destinations without executing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_pipeline_config(args.config)
    except PipelineConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[1]

    pipeline = BenchmarkLifecyclePipeline(
        config=config,
        project_root=project_root,
        logs_root=args.logs_root,
        dry_run=args.dry_run,
    )

    try:
        manifests = pipeline.run(args.benchmarks)
    except PipelineConfigError as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run complete. Manifests would be written to:")
    else:
        print("Benchmark lifecycle complete. Manifests written to:")

    for benchmark_id, manifest_path in manifests.items():
        print(f"  - {benchmark_id}: {manifest_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
