#!/usr/bin/env python3
"""
Initialize git repositories in LoCoBench task environments.

This script initializes git repos in task environment/project/ directories
so agents can use git commands during benchmark execution.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def extract_project_prefix(task_path: Path) -> str:
    """
    Extract project prefix from task directory name.

    Example:
        rust_web_social_expert_073_architectural_understanding_expert_01__ABC123
        -> rust_web_social_expert_073
    """
    task_name = task_path.name
    # Remove the task type suffix and hash
    # Format: {project_prefix}_{task_type}_{hash}
    parts = task_name.split("_")

    # Find where the task type starts (architectural, cross, bug)
    task_type_keywords = ["architectural", "cross", "bug"]
    for i, part in enumerate(parts):
        if part in task_type_keywords:
            # Project prefix is everything before the task type
            return "_".join(parts[:i])

    # Fallback: use task name without trailing hash (after __)
    if "__" in task_name:
        return task_name.split("__")[0].rsplit("_", 2)[0]

    raise ValueError(f"Could not extract project prefix from task name: {task_name}")


def init_git_repo(environment_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Initialize git repository in environment/project/ directory.

    Args:
        environment_path: Path to task environment directory (contains environment/project/)
        dry_run: If True, only print actions without executing them

    Returns:
        Tuple of (success: bool, message: str)
    """
    project_dir = environment_path / "environment" / "project"

    if not project_dir.exists():
        return False, f"Project directory does not exist: {project_dir}"

    git_dir = project_dir / ".git"

    # Step 1: Remove existing incomplete .git/ directory if present
    if git_dir.exists():
        if dry_run:
            print(f"[DRY RUN] Would remove existing .git directory: {git_dir}")
        else:
            print(f"Removing existing .git directory: {git_dir}")
            shutil.rmtree(git_dir)

    # Step 2: Extract project prefix for remote URL
    try:
        project_prefix = extract_project_prefix(environment_path)
        repo_name = f"locobench-{project_prefix}"
        remote_url = f"https://github.com/sg-benchmarks/{repo_name}.git"
    except ValueError as e:
        return False, str(e)

    if dry_run:
        print(f"[DRY RUN] Would initialize git in: {project_dir}")
        print(f"[DRY RUN] Would set remote to: {remote_url}")
        return True, f"DRY RUN: Would initialize git repo for {repo_name}"

    try:
        # Step 3: Run git init
        subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Initialized git repository in {project_dir}")

        # Step 4: Stage all files with git add .
        subprocess.run(
            ["git", "add", "."],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )

        # Step 5: Create commit
        commit_message = "Initial commit: full synthetic codebase"
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Created initial commit: '{commit_message}'")

        # Step 5b: Rename master branch to main
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )

        # Step 6: Configure remote origin
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"Configured remote origin: {remote_url}")

        # Step 7: Validate - git log shows commit
        log_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        if not log_result.stdout.strip():
            return False, "Validation failed: git log is empty"

        # Step 8: Validate - git ls-tree HEAD lists files
        tree_result = subprocess.run(
            ["git", "ls-tree", "-r", "HEAD"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True
        )
        file_count = len(tree_result.stdout.strip().split("\n"))
        if file_count == 0:
            return False, "Validation failed: git ls-tree HEAD shows no files"

        return True, f"Successfully initialized git repo with {file_count} files committed"

    except subprocess.CalledProcessError as e:
        return False, f"Git command failed: {e.stderr if e.stderr else str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize git repositories in LoCoBench task environments"
    )
    parser.add_argument(
        "environment_path",
        type=Path,
        help="Path to task environment directory (contains environment/project/)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing them"
    )

    args = parser.parse_args()

    environment_path = args.environment_path.resolve()

    if not environment_path.exists():
        print(f"Error: Environment path does not exist: {environment_path}", file=sys.stderr)
        return 1

    success, message = init_git_repo(environment_path, dry_run=args.dry_run)

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
