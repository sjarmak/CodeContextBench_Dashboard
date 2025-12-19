#!/usr/bin/env python3
"""
Regenerate task definitions from JSON mining output.

Updates existing task directories with:
1. Real commit SHAs (pre_fix_rev, ground_truth_rev)
2. Updated task.toml with commit information
3. Dockerfile with proper git checkout

Usage:
    python -m src.task_mining.regenerate_tasks \\
        --mining-output artifacts/mining_results.json \\
        --tasks-dir benchmarks/github_mined_pilot
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_mining_results(mining_output: Path) -> Dict[str, Any]:
    """Load mining results from JSON file"""
    with open(mining_output, "r") as f:
        return json.load(f)


def update_task_toml(
    task_dir: Path,
    task_data: Dict[str, Any],
) -> None:
    """Update task.toml with commit information"""
    task_toml_path = task_dir / "task.toml"
    
    if not task_toml_path.exists():
        logger.warning(f"No task.toml found in {task_dir}")
        return
    
    # Read existing TOML
    with open(task_toml_path, "r") as f:
        content = f.read()
    
    # Add commit info to [task] section if not present
    if "pre_fix_rev" not in content:
        # Insert after language line
        pre_fix_rev = task_data.get("pre_fix_rev", "HEAD~1")
        ground_truth_rev = task_data.get("ground_truth_rev", "HEAD")
        
        insert_text = f'pre_fix_rev = "{pre_fix_rev}"\nground_truth_rev = "{ground_truth_rev}"\n'
        
        # Find position after 'language' line
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if line.startswith("language"):
                insert_idx = i + 1
                break
        
        if insert_idx:
            lines.insert(insert_idx, insert_text.rstrip())
            content = "\n".join(lines)
            
            with open(task_toml_path, "w") as f:
                f.write(content)
            
            logger.info(f"Updated {task_toml_path} with commit SHAs")


def update_dockerfile(
    task_dir: Path,
    task_data: Dict[str, Any],
    repo_config: Dict[str, Any],
) -> None:
    """Update Dockerfile to checkout pre_fix_rev"""
    dockerfile_path = task_dir / "environment" / "Dockerfile"
    
    if not dockerfile_path.exists():
        logger.warning(f"No Dockerfile found in {dockerfile_path}")
        return
    
    with open(dockerfile_path, "r") as f:
        content = f.read()
    
    repo_url = repo_config.get("repo_url", "")
    pre_fix_rev = task_data.get("pre_fix_rev", "HEAD~1")
    
    if not repo_url:
        logger.warning(f"No repo_url for {task_data.get('id')}")
        return
    
    # Replace git checkout line with pre_fix_rev
    old_checkout = 'git checkout main'
    new_checkout = f'git checkout {pre_fix_rev}'
    
    if old_checkout in content:
        content = content.replace(old_checkout, new_checkout)
        
        with open(dockerfile_path, "w") as f:
            f.write(content)
        
        logger.info(f"Updated {dockerfile_path} to checkout {pre_fix_rev}")
    else:
        logger.debug(f"No 'git checkout main' found in {dockerfile_path}")


def regenerate_tasks(
    mining_output: Path,
    tasks_dir: Path,
    repo_registry: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Regenerate task definitions from mining output"""
    
    if not mining_output.exists():
        logger.error(f"Mining output not found: {mining_output}")
        return
    
    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        return
    
    # Load mining results
    results = load_mining_results(mining_output)
    
    # Build repo registry if not provided
    if repo_registry is None:
        from .repo_registry import REPO_REGISTRY
        repo_registry = {k: v.__dict__ for k, v in REPO_REGISTRY.items()}
    
    # Process each repository's tasks
    total_updated = 0
    
    for repo_result in results.get("repositories", []):
        repo_key = repo_result.get("repo_key")
        repo_config = repo_registry.get(repo_key)
        
        if not repo_config:
            logger.warning(f"No repo config for {repo_key}")
            continue
        
        for task_data in repo_result.get("candidates", []):
            task_id = task_data.get("id")
            task_dir = tasks_dir / task_id
            
            if not task_dir.exists():
                logger.debug(f"Task directory not found: {task_dir}")
                continue
            
            # Update task.toml and Dockerfile
            update_task_toml(task_dir, task_data)
            update_dockerfile(task_dir, task_data, repo_config)
            total_updated += 1
    
    logger.info(f"Regenerated {total_updated} task definitions")


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate task definitions from mining output"
    )
    parser.add_argument(
        "--mining-output",
        type=Path,
        default="artifacts/mining_results.json",
        help="Path to mining output JSON",
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default="benchmarks/github_mined_pilot",
        help="Path to tasks directory",
    )
    
    args = parser.parse_args()
    
    regenerate_tasks(args.mining_output, args.tasks_dir)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
