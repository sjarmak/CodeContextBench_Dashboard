#!/usr/bin/env python3
"""
Push LoCoBench project trees to GitHub sg-benchmarks organization.

This script pushes complete project trees from task environments to GitHub repos
so they can be indexed by Sourcegraph for MCP/Deep Search evaluation.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


def run_gh_command(args: list[str], check: bool = True) -> Tuple[bool, str, str]:
    """
    Run a gh CLI command.

    Args:
        args: Command arguments (excluding 'gh')
        check: If True, raise exception on non-zero exit

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return False, e.stdout or "", e.stderr or ""


def run_git_command(cwd: Path, args: list[str], check: bool = True) -> Tuple[bool, str, str]:
    """
    Run a git command in specified directory.

    Args:
        cwd: Working directory for the command
        args: Command arguments (excluding 'git')
        check: If True, raise exception on non-zero exit

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return False, e.stdout or "", e.stderr or ""


def check_gh_auth() -> bool:
    """Check if gh CLI is authenticated."""
    success, _, _ = run_gh_command(["auth", "status"], check=False)
    return success


def repo_exists(org: str, repo_name: str) -> bool:
    """Check if a GitHub repository exists."""
    success, _, _ = run_gh_command(
        ["repo", "view", f"{org}/{repo_name}"],
        check=False
    )
    return success


def get_repo_file_count(org: str, repo_name: str) -> Optional[int]:
    """
    Get the number of files in a GitHub repository using GitHub API.

    Args:
        org: GitHub organization name
        repo_name: Repository name

    Returns:
        Number of files in the repo, or None if unable to determine
    """
    try:
        # Use gh api to get the git tree
        success, stdout, _ = run_gh_command([
            "api",
            f"repos/{org}/{repo_name}/git/trees/HEAD?recursive=1",
            "--jq", ".tree | length"
        ], check=False)

        if success and stdout.strip().isdigit():
            return int(stdout.strip())
        return None
    except Exception:
        return None


def create_repo(org: str, repo_name: str, description: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Create a GitHub repository.

    Args:
        org: GitHub organization name
        repo_name: Repository name
        description: Repository description
        dry_run: If True, only print what would be done

    Returns:
        Tuple of (success: bool, message: str)
    """
    if dry_run:
        return True, f"[DRY RUN] Would create repo: {org}/{repo_name}"

    try:
        run_gh_command([
            "repo", "create", f"{org}/{repo_name}",
            "--public",
            "--description", description
        ])
        return True, f"Created repo: {org}/{repo_name}"
    except subprocess.CalledProcessError as e:
        return False, f"Failed to create repo: {e.stderr}"


def push_project_to_github(
    project_prefix: str,
    project_path: Path,
    org: str = "sg-benchmarks",
    dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Push a project directory to GitHub.

    Args:
        project_prefix: Project prefix (e.g., rust_web_social_expert_073)
        project_path: Path to the project directory (environment/project/)
        org: GitHub organization name
        dry_run: If True, only print what would be done

    Returns:
        Tuple of (success: bool, message: str)
    """
    repo_name = f"locobench-{project_prefix}"

    # Validate project path
    if not project_path.exists():
        return False, f"Project path does not exist: {project_path}"

    if not project_path.is_dir():
        return False, f"Project path is not a directory: {project_path}"

    # Count files in local project
    try:
        local_files = list(project_path.rglob("*"))
        local_file_count = sum(1 for f in local_files if f.is_file() and ".git" not in f.parts)
        print(f"Local project has {local_file_count} files")
    except Exception as e:
        return False, f"Failed to count local files: {e}"

    # Check if repo exists, create if not
    if repo_exists(org, repo_name):
        print(f"Repository {org}/{repo_name} already exists")
    else:
        print(f"Creating repository {org}/{repo_name}...")
        description = f"LoCoBench synthetic project: {project_prefix}"
        success, message = create_repo(org, repo_name, description, dry_run)
        if not success:
            return False, message
        print(message)

    if dry_run:
        return True, f"[DRY RUN] Would push {local_file_count} files to {org}/{repo_name}"

    # Check if .git exists in project directory
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return False, f"No .git directory found in {project_path}. Run init_git_repos.py first."

    # Set remote origin (remove existing if present)
    remote_url = f"https://github.com/{org}/{repo_name}.git"
    print(f"Configuring remote: {remote_url}")

    # Remove existing origin remote if it exists
    run_git_command(project_path, ["remote", "remove", "origin"], check=False)

    # Add new origin remote
    try:
        run_git_command(project_path, ["remote", "add", "origin", remote_url])
    except subprocess.CalledProcessError as e:
        return False, f"Failed to add remote: {e.stderr}"

    # Push to GitHub (force push to ensure we overwrite any existing content)
    print(f"Pushing to GitHub...")
    try:
        # Get current branch name
        success, current_branch, _ = run_git_command(project_path, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        if not success:
            # If we can't get branch, assume main
            current_branch = "main"
        else:
            current_branch = current_branch.strip()

        # Try pushing current branch
        success, stdout, stderr = run_git_command(
            project_path,
            ["push", "-u", "origin", current_branch, "--force"],
            check=False
        )

        if not success:
            # Try master branch if current branch failed
            success, stdout, stderr = run_git_command(
                project_path,
                ["push", "-u", "origin", "master", "--force"],
                check=False
            )

        if not success:
            # Try main branch as last resort
            success, stdout, stderr = run_git_command(
                project_path,
                ["push", "-u", "origin", "main", "--force"],
                check=False
            )

        if not success:
            return False, f"Failed to push to GitHub: {stderr}"

        print(f"Successfully pushed to {org}/{repo_name}")
    except Exception as e:
        return False, f"Failed to push: {str(e)}"

    # Validate: Check file count via GitHub API
    print(f"Validating push via GitHub API...")
    remote_file_count = get_repo_file_count(org, repo_name)

    if remote_file_count is None:
        return True, f"Warning: Could not validate file count via API, but push succeeded"

    print(f"Remote repository has {remote_file_count} files")

    # Check if remote has at least 70 files (per acceptance criteria)
    if remote_file_count < 70:
        return False, f"Validation failed: Remote has {remote_file_count} files, expected >= 70"

    return True, f"Successfully pushed and validated: {org}/{repo_name} ({remote_file_count} files)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Push LoCoBench project trees to GitHub sg-benchmarks organization"
    )
    parser.add_argument(
        "project_prefix",
        type=str,
        help="Project prefix (e.g., rust_web_social_expert_073)"
    )
    parser.add_argument(
        "project_path",
        type=Path,
        help="Path to project directory (environment/project/)"
    )
    parser.add_argument(
        "--org",
        type=str,
        default="sg-benchmarks",
        help="GitHub organization name (default: sg-benchmarks)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing them"
    )

    args = parser.parse_args()

    # Check prerequisites
    if not run_gh_command(["--version"], check=False)[0]:
        print("Error: gh CLI not found. Install with: brew install gh", file=sys.stderr)
        return 1

    if not check_gh_auth():
        print("Error: gh CLI not authenticated. Run: gh auth login", file=sys.stderr)
        return 1

    # Resolve project path
    project_path = args.project_path.resolve()

    success, message = push_project_to_github(
        args.project_prefix,
        project_path,
        args.org,
        args.dry_run
    )

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
