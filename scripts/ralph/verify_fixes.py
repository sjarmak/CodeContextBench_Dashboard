#!/usr/bin/env python3
"""
Automated verification script for LoCoBench data integrity fixes.

Verifies that all fixes from US-001 through US-006 were applied correctly:
1. All 50 tasks have >= 70 files in environment/project/
2. All 50 tasks have working git repos (git log, git ls-tree HEAD)
3. 15 broken GitHub repos now have >= 70 files (via GitHub API)
4. Agent code has CLAUDE.md template with repo name support
5. Adapter code has instruction.md conditional Deep Search logic
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import json
import re

# Task base path
TASKS_BASE = Path("/home/stephanie_jarmak/CodeContextBench/benchmarks/locobench_agent/tasks")

# Agent code path
AGENT_CODE = Path("/home/stephanie_jarmak/evals/custom_agents/agents/claudecode/agents/claude_baseline_agent.py")

# Adapter code path
ADAPTER_CODE = Path("/home/stephanie_jarmak/CodeContextBench/benchmarks/locobench_agent/adapter.py")

# Broken project prefixes (from audit document)
BROKEN_PROJECT_PREFIXES = [
    "c_api_microservice_expert_080",
    "cpp_system_security_expert_064",
    "cpp_web_blog_expert_040",
    "csharp_data_warehouse_expert_012",
    "csharp_ml_training_expert_087",
    "csharp_web_blog_expert_076",
    "go_ml_nlp_expert_053",
    "javascript_ml_nlp_expert_053",
    "python_data_streaming_expert_085",
    "python_desktop_development_expert_021",
    "rust_api_microservice_expert_008",
    "rust_data_streaming_expert_013",
    "rust_ml_computer_vision_expert_054",
    "rust_web_social_expert_073",
    "typescript_system_monitoring_expert_061",
]

# All 50 tasks (from task list)
ALL_TASKS = [
    "csharp_data_warehouse_expert_012_architectural_understanding_expert_01",
    "rust_web_social_expert_073_architectural_understanding_expert_01",
    "c_blockchain_nft_expert_071_architectural_understanding_expert_01",
    "c_api_microservice_expert_080_architectural_understanding_expert_01",
    "rust_api_microservice_expert_008_architectural_understanding_expert_01",
    "python_data_streaming_expert_085_architectural_understanding_expert_01",
    "c_api_graphql_expert_079_architectural_understanding_expert_01",
    "rust_data_streaming_expert_013_architectural_understanding_expert_01",
    "python_game_engine_expert_032_architectural_understanding_expert_01",
    "cpp_web_blog_expert_040_architectural_understanding_expert_01",
    "rust_ml_computer_vision_expert_054_architectural_understanding_expert_01",
    "typescript_system_monitoring_expert_061_architectural_understanding_expert_01",
    "cpp_data_analytics_expert_010_architectural_understanding_expert_01",
    "java_web_ecommerce_expert_000_architectural_understanding_expert_01",
    "python_desktop_development_expert_021_architectural_understanding_expert_01",
    "python_fintech_payment_expert_029_architectural_understanding_expert_01",
    "rust_blockchain_nft_expert_071_architectural_understanding_expert_01",
    "c_ml_nlp_expert_017_architectural_understanding_expert_01",
    "csharp_web_blog_expert_076_architectural_understanding_expert_01",
    "csharp_mobile_game_expert_024_architectural_understanding_expert_01",
    "csharp_blockchain_defi_expert_070_architectural_understanding_expert_01",
    "java_web_ecommerce_expert_036_architectural_understanding_expert_01",
    "javascript_ml_nlp_expert_053_architectural_understanding_expert_01",
    "cpp_system_security_expert_064_architectural_understanding_expert_01",
    "cpp_web_dashboard_expert_039_architectural_understanding_expert_01",
    "java_mobile_social_expert_058_architectural_understanding_expert_01",
    "go_ml_nlp_expert_053_architectural_understanding_expert_01",
    "typescript_desktop_productivity_expert_055_architectural_understanding_expert_01",
    "javascript_web_social_expert_073_architectural_understanding_expert_01",
    "csharp_data_etl_expert_047_architectural_understanding_expert_01",
    "c_fintech_payment_expert_065_architectural_understanding_expert_01",
    "csharp_ml_training_expert_087_architectural_understanding_expert_01",
    "java_api_rest_expert_006_architectural_understanding_expert_01",
    "javascript_blockchain_nft_expert_035_architectural_understanding_expert_01",
    "csharp_data_warehouse_expert_012_cross_file_refactoring_expert_01",
    "c_blockchain_nft_expert_071_cross_file_refactoring_expert_01",
    "rust_web_social_expert_073_cross_file_refactoring_expert_01",
    "c_api_microservice_expert_080_cross_file_refactoring_expert_01",
    "python_data_streaming_expert_085_cross_file_refactoring_expert_01",
    "c_api_graphql_expert_079_cross_file_refactoring_expert_01",
    "rust_data_streaming_expert_013_cross_file_refactoring_expert_01",
    "rust_api_microservice_expert_008_cross_file_refactoring_expert_01",
    "python_game_engine_expert_032_cross_file_refactoring_expert_01",
    "rust_ml_computer_vision_expert_054_cross_file_refactoring_expert_01",
    "cpp_web_blog_expert_040_cross_file_refactoring_expert_01",
    "typescript_system_monitoring_expert_061_cross_file_refactoring_expert_01",
    "python_desktop_development_expert_021_cross_file_refactoring_expert_01",
    "csharp_data_warehouse_expert_012_bug_investigation_expert_01",
    "rust_web_social_expert_073_bug_investigation_expert_01",
    "c_blockchain_nft_expert_071_bug_investigation_expert_01",
]


def count_files_in_directory(directory: Path) -> int:
    """Count all files in a directory recursively."""
    if not directory.exists():
        return 0

    try:
        result = subprocess.run(
            ["find", str(directory), "-type", "f"],
            capture_output=True,
            text=True,
            check=True
        )
        return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    except subprocess.CalledProcessError:
        return 0


def check_git_log(directory: Path) -> Tuple[bool, str]:
    """Check if git log works in the directory."""
    git_dir = directory / ".git"
    if not git_dir.exists():
        return False, "No .git directory"

    try:
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip():
            return True, "OK"
        else:
            return False, "No commits"
    except subprocess.CalledProcessError as e:
        return False, f"git log failed: {e.stderr.strip()}"


def check_git_ls_tree(directory: Path) -> Tuple[bool, str]:
    """Check if git ls-tree HEAD works in the directory."""
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True
        )
        file_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
        if file_count > 0:
            return True, f"OK ({file_count} files tracked)"
        else:
            return False, "No files tracked"
    except subprocess.CalledProcessError as e:
        return False, f"git ls-tree failed: {e.stderr.strip()}"


def check_github_repo_files(project_prefix: str) -> Tuple[bool, int, str]:
    """Check GitHub repo file count via API."""
    repo_name = f"locobench-{project_prefix}"

    # Use gh CLI to check repo
    try:
        # Get file tree
        result = subprocess.run(
            ["gh", "api", f"repos/sg-benchmarks/{repo_name}/git/trees/master?recursive=1"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        file_count = len([item for item in data.get("tree", []) if item.get("type") == "blob"])
        status = "OK" if file_count >= 70 else "BROKEN"
        return file_count >= 70, file_count, status
    except subprocess.CalledProcessError as e:
        return False, 0, f"API error: {e.stderr.strip()}"
    except json.JSONDecodeError as e:
        return False, 0, f"JSON parse error: {e}"


def verify_task_files():
    """Verify all 50 tasks have >= 70 files in environment/project/."""
    print("\n=== Verification 1: Task File Counts ===")

    passed = 0
    failed = 0
    results = []

    for task_name in ALL_TASKS:
        task_dir = TASKS_BASE / task_name
        project_dir = task_dir / "environment" / "project"

        file_count = count_files_in_directory(project_dir)
        status = "✓" if file_count >= 70 else "✗"

        if file_count >= 70:
            passed += 1
        else:
            failed += 1
            results.append(f"  {status} {task_name}: {file_count} files (expected >= 70)")

    # Print failures (limit to first 10)
    if results:
        print("\nTasks with insufficient files:")
        for result in results[:10]:
            print(result)
        if len(results) > 10:
            print(f"  ... and {len(results) - 10} more")

    print(f"\n{'✓' if failed == 0 else '✗'} {passed}/50 tasks have correct file count (>= 70 files)")
    return failed == 0


def verify_git_repos():
    """Verify all 50 tasks have working git repos."""
    print("\n=== Verification 2: Git Repository Status ===")

    passed_log = 0
    passed_tree = 0
    failed_log = []
    failed_tree = []

    for task_name in ALL_TASKS:
        task_dir = TASKS_BASE / task_name
        project_dir = task_dir / "environment" / "project"

        # Check git log
        log_ok, log_msg = check_git_log(project_dir)
        if log_ok:
            passed_log += 1
        else:
            failed_log.append(f"  ✗ {task_name}: {log_msg}")

        # Check git ls-tree
        tree_ok, tree_msg = check_git_ls_tree(project_dir)
        if tree_ok:
            passed_tree += 1
        else:
            failed_tree.append(f"  ✗ {task_name}: {tree_msg}")

    # Print failures
    if failed_log:
        print("\nGit log failures:")
        for failure in failed_log[:5]:  # Show first 5
            print(failure)
        if len(failed_log) > 5:
            print(f"  ... and {len(failed_log) - 5} more")

    if failed_tree:
        print("\nGit ls-tree failures:")
        for failure in failed_tree[:5]:  # Show first 5
            print(failure)
        if len(failed_tree) > 5:
            print(f"  ... and {len(failed_tree) - 5} more")

    print(f"\n{'✓' if len(failed_log) == 0 else '✗'} {passed_log}/50 tasks have working git log")
    print(f"{'✓' if len(failed_tree) == 0 else '✗'} {passed_tree}/50 tasks have working git ls-tree HEAD")

    return len(failed_log) == 0 and len(failed_tree) == 0


def verify_github_repos():
    """Verify 15 broken GitHub repos now have >= 70 files."""
    print("\n=== Verification 3: GitHub Repository File Counts ===")

    passed = 0
    failed = 0
    results = []

    for project_prefix in BROKEN_PROJECT_PREFIXES:
        ok, file_count, status = check_github_repo_files(project_prefix)

        status_symbol = "✓" if ok else "✗"
        results.append((status_symbol, f"locobench-{project_prefix}", file_count, ok))

        if ok:
            passed += 1
        else:
            failed += 1

    # Print all results
    for status_symbol, repo, file_count, ok in results:
        print(f"  {status_symbol} {repo}: {file_count} files")

    print(f"\n{'✓' if failed == 0 else '✗'} {passed}/15 repos have correct file count (>= 70 files)")
    return failed == 0


def verify_claude_md_template():
    """Verify agent code has CLAUDE.md template with repo name support."""
    print("\n=== Verification 4: CLAUDE.md Template (Agent Code) ===")

    if not AGENT_CODE.exists():
        print(f"  ✗ Agent code not found: {AGENT_CODE}")
        return False

    try:
        content = AGENT_CODE.read_text()

        # Check for LOCOBENCH_PROJECT_PREFIX support
        has_env_var = "LOCOBENCH_PROJECT_PREFIX" in content
        has_locobench_format = 'locobench-{' in content or "locobench-" in content

        checks = []
        checks.append(("LOCOBENCH_PROJECT_PREFIX env var check", has_env_var))
        checks.append(("locobench repo name format", has_locobench_format))

        all_passed = all(passed for _, passed in checks)

        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")

        if all_passed:
            print(f"\n✓ Agent code supports LOCOBENCH_PROJECT_PREFIX for CLAUDE.md templates")
        else:
            print(f"\n✗ Agent code missing CLAUDE.md template support")

        return all_passed

    except Exception as e:
        print(f"  ✗ Error reading agent code: {e}")
        return False


def verify_instruction_md_template():
    """Verify adapter code has conditional Deep Search logic."""
    print("\n=== Verification 5: instruction.md Template (Adapter Code) ===")

    if not ADAPTER_CODE.exists():
        print(f"  ✗ Adapter code not found: {ADAPTER_CODE}")
        return False

    try:
        content = ADAPTER_CODE.read_text()

        # Check for BASELINE_MCP_TYPE conditional logic
        has_env_var = "BASELINE_MCP_TYPE" in content
        has_conditional = "deepsearch" in content.lower() and ("if " in content or "==" in content)

        checks = []
        checks.append(("BASELINE_MCP_TYPE env var check", has_env_var))
        checks.append(("Conditional Deep Search logic", has_conditional))

        all_passed = all(passed for _, passed in checks)

        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")

        if all_passed:
            print(f"\n✓ Adapter code supports conditional Deep Search in instruction.md")
        else:
            print(f"\n✗ Adapter code missing conditional Deep Search logic")

        return all_passed

    except Exception as e:
        print(f"  ✗ Error reading adapter code: {e}")
        return False


def main():
    """Run all verifications."""
    print("=" * 60)
    print("LoCoBench Data Integrity Fix Verification")
    print("=" * 60)

    results = []

    # Run all verifications
    results.append(("Task file counts (>= 70 files)", verify_task_files()))
    results.append(("Git repositories (log & ls-tree)", verify_git_repos()))
    results.append(("GitHub repo files (15 repos)", verify_github_repos()))
    results.append(("CLAUDE.md template support", verify_claude_md_template()))
    results.append(("instruction.md conditional logic", verify_instruction_md_template()))

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All verifications passed!")
        return 0
    else:
        print("\n✗ Some verifications failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
