#!/usr/bin/env python3
"""
Filter CodeContextBench task mining results.

Applies eligibility criteria and validates task specifications.

Usage:
    python -m src.task_mining.filter_tasks \
      --input artifacts/mining_results.json \
      --output artifacts/filtered_tasks.json
    
    python -m src.task_mining.filter_tasks \
      --input artifacts/mining_results.json \
      --output artifacts/filtered_tasks.json \
      --per-repo 10  # Limit to 10 per repo
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

from src.task_mining.task_filter import TaskFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def filter_mining_results(
    mining_results: Dict[str, Any],
    per_repo_limit: int = None,
) -> Dict[str, Any]:
    """
    Filter mining results, applying CodeContextBench criteria.
    
    Args:
        mining_results: Output from mine_tasks.py
        per_repo_limit: Max tasks per repo (None = no limit)
    
    Returns:
        {
            "total_candidates": 100,
            "total_filtered": 42,
            "filter_rate": 0.42,
            "repositories": [
                {
                    "repo_key": "kubernetes",
                    "total_candidates": 30,
                    "filtered": 15,
                    "filter_rate": 0.50,
                    "tasks": [...]
                }
            ],
            "all_filtered_tasks": [...]
        }
    """
    results = {
        "total_candidates": 0,
        "total_filtered": 0,
        "filter_rate": 0,
        "repositories": [],
        "all_filtered_tasks": [],
    }
    
    for repo_result in mining_results.get("repositories", []):
        repo_key = repo_result.get("repo_key")
        candidates = repo_result.get("candidates", [])
        
        # Filter repo candidates
        filter_result = TaskFilter.filter_batch(candidates)
        
        passed_tasks = filter_result["passed_tasks"]
        
        # Apply per-repo limit
        if per_repo_limit:
            passed_tasks = passed_tasks[:per_repo_limit]
        
        results["repositories"].append({
            "repo_key": repo_key,
            "total_candidates": filter_result["total"],
            "filtered": len(passed_tasks),
            "filter_rate": filter_result["pass_rate"],
            "failures": [
                {
                    "task_id": f["task_id"],
                    "reasons": f["reasons"],
                }
                for f in filter_result["failed_tasks"][:5]  # Top 5 failures
            ],
            "tasks": passed_tasks,
        })
        
        results["total_candidates"] += filter_result["total"]
        results["total_filtered"] += len(passed_tasks)
        results["all_filtered_tasks"].extend(passed_tasks)
    
    results["filter_rate"] = (
        results["total_filtered"] / max(1, results["total_candidates"])
    )
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Filter CodeContextBench mining results"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Mining results file (from mine_tasks.py)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file for filtered tasks",
    )
    parser.add_argument(
        "--per-repo",
        type=int,
        default=None,
        help="Max tasks per repository (default: no limit)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    # Load mining results
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1
    
    logger.info(f"Loading mining results from: {input_path}")
    with open(input_path) as f:
        mining_results = json.load(f)
    
    # Filter
    logger.info("Filtering tasks...")
    filtered = filter_mining_results(mining_results, per_repo_limit=args.per_repo)
    
    # Report
    logger.info(f"Total candidates: {filtered['total_candidates']}")
    logger.info(f"Filtered (passed): {filtered['total_filtered']}")
    logger.info(f"Filter rate: {filtered['filter_rate']:.1%}")
    
    for repo in filtered["repositories"]:
        logger.info(
            f"  {repo['repo_key']}: "
            f"{repo['filtered']}/{repo['total_candidates']} "
            f"({repo['filter_rate']:.1%})"
        )
        
        if args.verbose and repo.get("failures"):
            for failure in repo["failures"][:3]:
                logger.info(f"    Rejection: {failure['task_id']}")
                for reason in failure["reasons"][:2]:
                    logger.info(f"      - {reason}")
    
    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(filtered, f, indent=2, default=str)
    
    logger.info(f"Filtered tasks written to: {output_path}")
    
    return 0 if filtered["total_filtered"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
