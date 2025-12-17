#!/usr/bin/env python3
"""
Mine CodeContextBench tasks from OSS repositories.

Usage:
    python -m src.task_mining.mine_tasks --repos firefox kubernetes --output artifacts/mining_results.json
    python -m src.task_mining.mine_tasks --repos all --days-back 180
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

from src.task_mining.github_client import GitHubClient
from src.task_mining.task_generator import TaskGenerator
from src.task_mining.repo_registry import RepositoryRegistry, REPO_REGISTRY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mine_repository(
    gh_client: GitHubClient,
    task_gen: TaskGenerator,
    repo_registry: RepositoryRegistry,
    repo_key: str,
    days_back: int = 365,
) -> Dict[str, Any]:
    """
    Mine tasks from a single repository.
    
    Returns:
        {
            "repo_key": "kubernetes",
            "status": "success" | "error",
            "error": "...",
            "candidates": [task dicts],
            "total": 10,
            "multi_file": 5,
            "verifiable": 3,
        }
    """
    repo = repo_registry.get_repo(repo_key)
    if not repo:
        return {
            "repo_key": repo_key,
            "status": "error",
            "error": f"Repository not found: {repo_key}",
            "candidates": [],
            "total": 0,
        }
    
    logger.info(f"Mining {repo_key} ({repo.github_url()})...")
    
    try:
        # Mine closed issues with linked PRs
        issues = gh_client.closed_issues_with_linked_prs(
            repo.github_graphql_query_repo(),
            days_back=days_back,
        )
        logger.info(f"  Found {len(issues)} closed issues with linked PRs")
        
        # Mine merged PRs
        prs = gh_client.merged_prs_with_tests(
            repo.github_graphql_query_repo(),
            days_back=days_back,
            min_files_changed=2,
        )
        logger.info(f"  Found {len(prs)} merged PRs (multi-file)")
        
        # Convert to task specs
        candidates = []
        task_counter = 1
        
        for pr in prs[:25]:  # Limit per repo
            task_id = f"sgt-{task_counter:03d}"
            task = task_gen.from_pr(
                pr,
                repo,
                task_id=task_id,
                pre_fix_rev="HEAD~1",  # Placeholder, needs git analysis
                ground_truth_rev=pr.merge_commit_sha or "HEAD",
            )
            if task:
                candidates.append(task.to_dict())
                task_counter += 1
        
        for issue in issues[:10]:  # Limit per repo
            if len(candidates) >= 50:  # Hard cap per repo
                break
            task_id = f"sgt-{task_counter:03d}"
            task = task_gen.from_issue(
                issue,
                repo,
                task_id=task_id,
                pre_fix_rev="HEAD~1",
                ground_truth_rev="HEAD",
            )
            if task:
                candidates.append(task.to_dict())
                task_counter += 1
        
        return {
            "repo_key": repo_key,
            "status": "success",
            "candidates_generated": len(candidates),
            "candidates": candidates,
        }
    
    except Exception as e:
        logger.error(f"Error mining {repo_key}: {e}")
        return {
            "repo_key": repo_key,
            "status": "error",
            "error": str(e),
            "candidates": [],
        }


def main():
    parser = argparse.ArgumentParser(description="Mine CodeContextBench tasks from OSS repos")
    parser.add_argument(
        "--repos",
        nargs="+",
        default=["firefox", "kubernetes", "pytorch", "vscode"],
        help="Repositories to mine (or 'all')",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="Mine issues/PRs from last N days",
    )
    parser.add_argument(
        "--output",
        default="artifacts/mining_results.json",
        help="Output file for mining results",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total candidates generated",
    )
    
    args = parser.parse_args()
    
    # Resolve repo list
    if args.repos == ["all"]:
        repos = list(REPO_REGISTRY.keys())
    else:
        repos = args.repos
    
    logger.info(f"Mining tasks from: {', '.join(repos)}")
    
    # Initialize clients
    gh_client = GitHubClient()
    task_gen = TaskGenerator(gh_client)
    repo_registry = RepositoryRegistry()
    
    # Mine each repo
    results = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "repos_mined": repos,
        "days_back": args.days_back,
        "repositories": [],
        "total_candidates": 0,
    }
    
    for repo_key in repos:
        repo_result = mine_repository(
            gh_client,
            task_gen,
            repo_registry,
            repo_key,
            days_back=args.days_back,
        )
        results["repositories"].append(repo_result)
        results["total_candidates"] += len(repo_result.get("candidates", []))
    
    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Mining complete. Generated {results['total_candidates']} candidates.")
    logger.info(f"Results written to: {output_path}")
    
    return 0 if results["total_candidates"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
