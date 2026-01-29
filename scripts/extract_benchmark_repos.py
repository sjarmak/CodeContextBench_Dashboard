#!/usr/bin/env python3
"""
Extract unique repository + commit combinations from CodeContextBench benchmarks.

This script scans benchmark directories and extracts all unique (repo, commit) pairs
that need to be mirrored for Sourcegraph indexing.

Benchmarks handled:
- big_code_mcp: Large repos cloned at HEAD (kubernetes, vscode, servo, tensorrt-llm)
- github_mined: PyTorch at specific commits (from Dockerfiles)
- tac_mcp_value: TAC repos (bustub, OpenHands, llama.cpp, copilot-arena) - need Docker extraction

Output: data/instance_to_mirror.json with structure for each task
"""

import json
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from collections import defaultdict

# Known mappings for TAC tasks to their upstream repos
TAC_REPO_MAPPING = {
    "tac-buffer-pool-manager": ("cmu-db/bustub", "EXTRACT_FROM_DOCKER"),
    "tac-implement-hyperloglog": ("cmu-db/bustub", "EXTRACT_FROM_DOCKER"),
    "tac-dependency-change": ("All-Hands-AI/OpenHands", "EXTRACT_FROM_DOCKER"),
    "tac-write-unit-test": ("All-Hands-AI/OpenHands", "EXTRACT_FROM_DOCKER"),
    "tac-troubleshoot-dev-setup": ("All-Hands-AI/OpenHands", "EXTRACT_FROM_DOCKER"),
    "tac-find-in-codebase-1": ("ggerganov/llama.cpp", "EXTRACT_FROM_DOCKER"),
    "tac-find-in-codebase-2": ("ggerganov/llama.cpp", "EXTRACT_FROM_DOCKER"),
    "tac-copilot-arena-endpoint": ("lmarena/copilot-arena", "EXTRACT_FROM_DOCKER"),
}


@dataclass
class RepoInstance:
    task_id: str
    benchmark: str
    repo: str
    commit: str
    mirror_name: str
    language: Optional[str] = None


def extract_from_dockerfile(dockerfile_path: Path) -> tuple[str, str]:
    """Extract repo and commit from a Dockerfile's git clone command."""
    content = dockerfile_path.read_text()

    # Pattern for: git clone ... https://github.com/org/repo.git ...
    clone_match = re.search(
        r'git clone.*https://github\.com/([^/]+/[^/\s]+?)(?:\.git)?\s',
        content
    )

    # Pattern for: git checkout <commit>
    checkout_match = re.search(
        r'git checkout\s+([a-f0-9]{40}|[a-f0-9]{7,12}|v[\d.]+)',
        content
    )

    if clone_match:
        repo = clone_match.group(1).rstrip('.git')
    else:
        repo = None

    commit = checkout_match.group(1) if checkout_match else "HEAD"

    return repo, commit


def extract_from_task_toml(task_toml_path: Path) -> dict:
    """Extract metadata from task.toml file."""
    content = task_toml_path.read_text()

    result = {}

    # Extract repo
    repo_match = re.search(r'^repo\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if repo_match:
        result['repo'] = repo_match.group(1)

    # Extract pre_fix_rev (commit)
    rev_match = re.search(r'^pre_fix_rev\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if rev_match:
        result['commit'] = rev_match.group(1)

    # Extract language
    lang_match = re.search(r'^language\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if lang_match:
        result['language'] = lang_match.group(1)

    # Extract task id
    id_match = re.search(r'^id\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if id_match:
        result['task_id'] = id_match.group(1)

    return result


def extract_big_code_mcp(benchmarks_dir: Path) -> list[RepoInstance]:
    """Extract repos from big_code_mcp benchmark."""
    instances = []
    benchmark_path = benchmarks_dir / "big_code_mcp"

    if not benchmark_path.exists():
        return instances

    # Known mappings: short name -> full GitHub repo
    repo_mappings = {
        "kubernetes": "kubernetes/kubernetes",
        "servo": "servo/servo",
        "vscode": "microsoft/vscode",
        "tensorrt-llm": "NVIDIA/TensorRT-LLM",
    }

    for task_dir in benchmark_path.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue

        task_toml = task_dir / "task.toml"
        dockerfile = task_dir / "environment" / "Dockerfile"

        if not task_toml.exists():
            continue

        toml_data = extract_from_task_toml(task_toml)
        task_id = toml_data.get('task_id', task_dir.name)
        repo_short = toml_data.get('repo', '')

        # Try to get full repo from Dockerfile
        if dockerfile.exists():
            docker_repo, docker_commit = extract_from_dockerfile(dockerfile)
            if docker_repo:
                repo = docker_repo
                commit = docker_commit
            elif repo_short in repo_mappings:
                repo = repo_mappings[repo_short]
                commit = "HEAD"
            else:
                continue
        elif repo_short in repo_mappings:
            repo = repo_mappings[repo_short]
            commit = "HEAD"
        else:
            continue

        # Generate mirror name
        repo_name = repo.split('/')[-1]
        if commit == "HEAD":
            mirror_name = f"{repo_name}--latest"
        else:
            mirror_name = f"{repo_name}--{commit[:8]}"

        instances.append(RepoInstance(
            task_id=task_id,
            benchmark="big_code_mcp",
            repo=repo,
            commit=commit,
            mirror_name=mirror_name,
            language=toml_data.get('language')
        ))

    return instances


def extract_github_mined(benchmarks_dir: Path) -> list[RepoInstance]:
    """Extract repos from github_mined benchmark."""
    instances = []
    benchmark_path = benchmarks_dir / "github_mined"

    if not benchmark_path.exists():
        return instances

    for task_dir in benchmark_path.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue

        task_toml = task_dir / "task.toml"
        dockerfile = task_dir / "environment" / "Dockerfile"

        if not task_toml.exists():
            continue

        toml_data = extract_from_task_toml(task_toml)
        task_id = toml_data.get('task_id', task_dir.name)

        # Get repo and commit from Dockerfile
        if dockerfile.exists():
            docker_repo, docker_commit = extract_from_dockerfile(dockerfile)
            if docker_repo:
                repo = docker_repo
                commit = docker_commit if docker_commit != "HEAD" else toml_data.get('commit', 'HEAD')
            else:
                # Fallback to task.toml
                repo_short = toml_data.get('repo', '')
                if repo_short == 'pytorch':
                    repo = 'pytorch/pytorch'
                else:
                    continue
                commit = toml_data.get('commit', 'HEAD')
        else:
            continue

        # Generate mirror name
        repo_name = repo.split('/')[-1]
        mirror_name = f"{repo_name}--{commit[:8]}"

        instances.append(RepoInstance(
            task_id=task_id,
            benchmark="github_mined",
            repo=repo,
            commit=commit,
            mirror_name=mirror_name,
            language=toml_data.get('language')
        ))

    return instances


def extract_tac_mcp_value(benchmarks_dir: Path) -> list[RepoInstance]:
    """Extract repos from tac_mcp_value benchmark."""
    instances = []
    benchmark_path = benchmarks_dir / "tac_mcp_value"

    if not benchmark_path.exists():
        return instances

    for task_dir in benchmark_path.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue

        task_id = task_dir.name

        if task_id not in TAC_REPO_MAPPING:
            continue

        repo, commit = TAC_REPO_MAPPING[task_id]

        # Generate mirror name
        repo_name = repo.split('/')[-1]
        if commit == "EXTRACT_FROM_DOCKER":
            mirror_name = f"{repo_name}--PENDING"
        else:
            mirror_name = f"{repo_name}--{commit[:8]}"

        task_toml = task_dir / "task.toml"
        language = None
        if task_toml.exists():
            toml_data = extract_from_task_toml(task_toml)
            language = toml_data.get('language')

        instances.append(RepoInstance(
            task_id=task_id,
            benchmark="tac_mcp_value",
            repo=repo,
            commit=commit,
            mirror_name=mirror_name,
            language=language
        ))

    return instances


def extract_kubernetes_docs(benchmarks_dir: Path) -> list[RepoInstance]:
    """Extract repos from kubernetes_docs benchmark (if it uses external repos)."""
    instances = []
    benchmark_path = benchmarks_dir / "kubernetes_docs"

    if not benchmark_path.exists():
        return instances

    # Check if this benchmark uses external repos
    for task_dir in benchmark_path.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue

        dockerfile = task_dir / "environment" / "Dockerfile"
        if dockerfile.exists():
            docker_repo, docker_commit = extract_from_dockerfile(dockerfile)
            if docker_repo:
                task_toml = task_dir / "task.toml"
                toml_data = extract_from_task_toml(task_toml) if task_toml.exists() else {}

                repo_name = docker_repo.split('/')[-1]
                mirror_name = f"{repo_name}--{docker_commit[:8] if docker_commit != 'HEAD' else 'latest'}"

                instances.append(RepoInstance(
                    task_id=toml_data.get('task_id', task_dir.name),
                    benchmark="kubernetes_docs",
                    repo=docker_repo,
                    commit=docker_commit,
                    mirror_name=mirror_name,
                    language=toml_data.get('language')
                ))

    return instances


def main():
    # Find benchmarks directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    benchmarks_dir = repo_root / "benchmarks"
    data_dir = repo_root / "data"

    if not benchmarks_dir.exists():
        print(f"Error: benchmarks directory not found at {benchmarks_dir}")
        sys.exit(1)

    data_dir.mkdir(exist_ok=True)

    all_instances = []

    # Extract from each benchmark
    extractors = [
        ("big_code_mcp", extract_big_code_mcp),
        ("tac_mcp_value", extract_tac_mcp_value),
        ("kubernetes_docs", extract_kubernetes_docs),
        ("github_mined", extract_github_mined),
    ]

    for benchmark_name, extractor in extractors:
        instances = extractor(benchmarks_dir)
        if instances:
            print(f"[{benchmark_name}] Found {len(instances)} repo instances")
            all_instances.extend(instances)

    # Deduplicate by (repo, commit) to get unique mirrors needed
    seen = {}
    unique_instances = []

    for inst in all_instances:
        key = (inst.repo, inst.commit)
        if key not in seen:
            seen[key] = inst
            unique_instances.append(inst)
        else:
            # Track that multiple tasks use this repo-commit
            pass

    print(f"\nTotal unique repo-commit pairs: {len(unique_instances)}")

    # Write output
    output = []
    for inst in unique_instances:
        output.append(asdict(inst))

    output_file = data_dir / "instance_to_mirror.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {len(output)} instances to {output_file}")

    # Summary by benchmark
    by_benchmark = defaultdict(list)
    for inst in unique_instances:
        by_benchmark[inst.benchmark].append(inst)

    print("\nSummary by benchmark:")
    for benchmark, instances in sorted(by_benchmark.items()):
        repos = set(inst.repo for inst in instances)
        print(f"  {benchmark}: {len(instances)} tasks, {len(repos)} unique repos")


if __name__ == "__main__":
    main()
