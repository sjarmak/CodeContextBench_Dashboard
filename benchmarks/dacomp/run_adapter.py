#!/usr/bin/env python3
"""
Script to run the DAComp adapter and convert instances to Harbor tasks.

Usage:
    python run_adapter.py --subset da \
        --dataset_path /path/to/dacomp-da.jsonl \
        --tasks_root /path/to/dacomp-da/tasks \
        --output_dir ./tasks \
        --limit 5

    python run_adapter.py --subset de \
        --tasks_root /path/to/dacomp-de/tasks \
        --output_dir ./tasks \
        --task_types impl evol \
        --limit 3
"""

import argparse
import logging
from pathlib import Path

from adapter import DACompDAAdapter, DACompDEAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert DAComp tasks to Harbor task directories"
    )
    parser.add_argument(
        "--subset",
        choices=["da", "de"],
        required=True,
        help="DAComp subset to convert: da (analysis) or de (engineering)",
    )
    parser.add_argument(
        "--dataset_path",
        type=Path,
        default=None,
        help="Path to DAComp-DA JSONL dataset file (required for subset=da)",
    )
    parser.add_argument(
        "--tasks_root",
        type=Path,
        required=True,
        help="Root directory containing DAComp task folders",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="Output directory for Harbor tasks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to generate (default: all)",
    )
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        default=None,
        help="Specific instance IDs to convert",
    )
    parser.add_argument(
        "--task_types",
        nargs="+",
        choices=["impl", "evol", "arch"],
        default=None,
        help="Filter DAComp-DE task types (impl, evol, arch)",
    )
    return parser.parse_args()


def _filter_ids(ids, instance_ids):
    if not instance_ids:
        return ids
    return [task_id for task_id in ids if task_id in instance_ids]


def main() -> None:
    args = _parse_args()

    if args.subset == "da":
        if not args.dataset_path:
            logger.error("--dataset_path is required for subset=da")
            return
        if not args.dataset_path.exists():
            logger.error(f"Dataset file not found: {args.dataset_path}")
            return
    
    if not args.tasks_root.exists():
        logger.error(f"Tasks root not found: {args.tasks_root}")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.subset == "da":
        logger.info("Initializing DAComp-DA adapter...")
        adapter = DACompDAAdapter(
            task_dir=args.output_dir,
            dataset_path=args.dataset_path,
            tasks_root=args.tasks_root,
        )
        task_ids = adapter.loader.all_ids()
    else:
        logger.info("Initializing DAComp-DE adapter...")
        adapter = DACompDEAdapter(
            task_dir=args.output_dir,
            tasks_root=args.tasks_root,
        )
        task_ids = adapter.loader.all_ids()
        if args.task_types:
            task_ids = [
                task_id for task_id in task_ids
                if adapter.loader.load(task_id).task_type in args.task_types
            ]

    task_ids = _filter_ids(task_ids, args.instance_ids)

    if args.limit:
        task_ids = task_ids[: args.limit]

    logger.info(f"Generating {len(task_ids)} Harbor tasks...")
    success_count = 0
    error_count = 0

    for i, task_id in enumerate(task_ids, 1):
        try:
            local_id = task_id
            logger.info(f"[{i}/{len(task_ids)}] Generating {task_id} -> {local_id}")
            adapter.generate_task(task_id, local_id)
            success_count += 1
        except Exception as exc:
            logger.error(f"[{i}/{len(task_ids)}] Failed {task_id}: {exc}")
            error_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("Task generation complete!")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info(f"  Output directory: {args.output_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
