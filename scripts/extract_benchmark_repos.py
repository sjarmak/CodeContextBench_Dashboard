#!/usr/bin/env python3
"""
Extract repository information from benchmark adapters for sg-benchmarks mirroring.

This script scans benchmark directories and extracts:
- Repository URLs from Dockerfiles (git clone commands)
- Commit hashes (if pinned)
- Task IDs for mapping

Outputs instance_to_mirror.json format compatible with create_mirrors_improved.sh
"""

import json
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class RepoInstance:
    """Represents a repository instance to mirror."""
    instance_id: str
    mirror_name: str
    original_repo: str
    commit: str
    benchmark: str
    language: str = ""
    

def extract_git_clone_info(dockerfile_path: Path) -> Optional[tuple[str, str]]:
    """Extract repo URL and commit from Dockerfile git clone command."""
    if not dockerfile_path.exists():
        return None
    
    content = dockerfile_path.read_text()
    
    # Match: git clone [options] <url> [dest] && git checkout <commit>
    # Or: git clone --depth 1 <url>
    clone_pattern = r'git clone[^&\n]*?(https?://github\.com/[^\s]+\.git|https?://github\.com/[^\s]+)'
    checkout_pattern = r'git checkout\s+([a-f0-9]{7,40})'
    
    clone_match = re.search(clone_pattern, content)
    checkout_match = re.search(checkout_pattern, content)
    
    if clone_match:
        repo_url = clone_match.group(1).rstrip('.git')
        # Extract owner/repo from URL
        repo_parts = repo_url.replace('https://github.com/', '').split('/')
        if len(repo_parts) >= 2:
            repo = f"{repo_parts[0]}/{repo_parts[1]}"
            commit = checkout_match.group(1) if checkout_match else "HEAD"
            return repo, commit
    
    return None


def extract_big_code_mcp_repos(benchmark_dir: Path) -> list[RepoInstance]:
    """Extract repos from big_code_mcp benchmark."""
    instances = []
    
    for task_dir in benchmark_dir.iterdir():
        if not task_dir.is_dir() or task_dir.name.startswith('.'):
            continue
            
        dockerfile = task_dir / "environment" / "Dockerfile"
        result = extract_git_clone_info(dockerfile)
        
        if result:
            repo, commit = result
            repo_name = repo.split('/')[-1]
            commit_short = commit[:8] if commit != "HEAD" else "latest"
            
            instances.append(RepoInstance(
                instance_id=task_dir.name,
                mirror_name=f"{repo_name}--{commit_short}",
                original_repo=repo,
                commit=commit,
                benchmark="big_code_mcp",
                language=detect_language_from_repo(repo)
            ))
    
    return instances


def extract_tac_repos() -> list[RepoInstance]:
    """Extract TAC repos (from known configuration)."""
    # TAC repos are on private GitLab but based on public OSS projects
    tac_repos = [
        {
            "instance_id": "tac-implement-hyperloglog",
            "original_repo": "cmu-db/bustub",
            "task_gitlab": "http://the-agent-company.com:8929/root/bustub",
            "language": "cpp"
        },
        {
            "instance_id": "tac-buffer-pool-manager", 
            "original_repo": "cmu-db/bustub",
            "task_gitlab": "http://the-agent-company.com:8929/root/bustub",
            "language": "cpp"
        },
        {
            "instance_id": "tac-write-unit-test",
            "original_repo": "All-Hands-AI/OpenHands",
            "task_gitlab": "http://the-agent-company.com:8929/root/openhands",
            "language": "python"
        },
        {
            "instance_id": "tac-dependency-change",
            "original_repo": "All-Hands-AI/OpenHands",
            "task_gitlab": "http://the-agent-company.com:8929/root/openhands",
            "language": "python"
        },
        {
            "instance_id": "tac-troubleshoot-dev-setup",
            "original_repo": "All-Hands-AI/OpenHands",
            "task_gitlab": "http://the-agent-company.com:8929/root/openhands",
            "language": "python"
        },
        {
            "instance_id": "tac-copilot-arena-endpoint",
            "original_repo": "lmarena/copilot-arena",
            "task_gitlab": "http://the-agent-company.com:8929/root/copilot-arena-server",
            "language": "python"
        },
        {
            "instance_id": "tac-find-in-codebase-1",
            "original_repo": "ggerganov/llama.cpp",
            "task_gitlab": "http://the-agent-company.com:8929/root/llama.cpp",
            "language": "cpp"
        },
        {
            "instance_id": "tac-find-in-codebase-2",
            "original_repo": "ggerganov/llama.cpp",
            "task_gitlab": "http://the-agent-company.com:8929/root/llama.cpp",
            "language": "cpp"
        },
    ]
    
    instances = []
    for task in tac_repos:
        repo_name = task["original_repo"].split('/')[-1]
        instances.append(RepoInstance(
            instance_id=task["instance_id"],
            mirror_name=f"{repo_name}--tac",
            original_repo=task["original_repo"],
            commit="EXTRACT_FROM_DOCKER",  # Need to extract from TAC Docker images
            benchmark="tac_mcp_value",
            language=task["language"]
        ))
    
    return instances


def extract_kubernetes_docs_repos(benchmark_dir: Path) -> list[RepoInstance]:
    """Extract repos from kubernetes_docs benchmark."""
    instances = []
    
    # Find all Dockerfiles
    for dockerfile in benchmark_dir.glob("*/Dockerfile"):
        result = extract_git_clone_info(dockerfile)
        if result:
            repo, commit = result
            task_id = dockerfile.parent.name
            repo_name = repo.split('/')[-1]
            commit_short = commit[:8] if commit != "HEAD" else "latest"
            
            instances.append(RepoInstance(
                instance_id=task_id,
                mirror_name=f"{repo_name}--{commit_short}",
                original_repo=repo,
                commit=commit,
                benchmark="kubernetes_docs",
                language="go"
            ))
    
    return instances


def extract_github_mined_repos(benchmark_dir: Path) -> list[RepoInstance]:
    """Extract repos from github_mined benchmark (pytorch tasks)."""
    instances = []
    
    for task_dir in benchmark_dir.iterdir():
        if not task_dir.is_dir() or not task_dir.name.startswith('sgt-'):
            continue
            
        dockerfile = task_dir / "environment" / "Dockerfile"
        if not dockerfile.exists():
            continue
            
        content = dockerfile.read_text()
        
        # Extract commit from git checkout
        checkout_match = re.search(r'git checkout\s+([a-f0-9]{7,40})', content)
        if checkout_match:
            commit = checkout_match.group(1)
            commit_short = commit[:8]
            
            instances.append(RepoInstance(
                instance_id=task_dir.name,
                mirror_name=f"pytorch--{commit_short}",
                original_repo="pytorch/pytorch",
                commit=commit,
                benchmark="github_mined",
                language="python"
            ))
    
    return instances


def detect_language_from_repo(repo: str) -> str:
    """Detect primary language from repo name."""
    repo_lower = repo.lower()
    if 'kubernetes' in repo_lower:
        return 'go'
    elif 'vscode' in repo_lower:
        return 'typescript'
    elif 'servo' in repo_lower:
        return 'rust'
    elif 'tensorrt' in repo_lower:
        return 'cpp'
    elif 'pytorch' in repo_lower:
        return 'python'
    return ''


def deduplicate_by_repo_commit(instances: list[RepoInstance]) -> list[RepoInstance]:
    """Remove duplicate repo+commit combinations."""
    seen = set()
    unique = []
    for inst in instances:
        key = f"{inst.original_repo}@{inst.commit}"
        if key not in seen:
            seen.add(key)
            unique.append(inst)
    return unique


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract benchmark repos for mirroring")
    parser.add_argument("--benchmarks-dir", type=Path, 
                        default=Path(__file__).parent.parent / "benchmarks",
                        help="Path to benchmarks directory")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent.parent / "data" / "instance_to_mirror.json",
                        help="Output JSON file")
    parser.add_argument("--benchmark", type=str, default="all",
                        choices=["all", "big_code_mcp", "tac_mcp_value", "kubernetes_docs", "github_mined"],
                        help="Which benchmark to extract")
    args = parser.parse_args()
    
    all_instances = []
    
    if args.benchmark in ["all", "big_code_mcp"]:
        big_code_dir = args.benchmarks_dir / "big_code_mcp"
        if big_code_dir.exists():
            instances = extract_big_code_mcp_repos(big_code_dir)
            print(f"[big_code_mcp] Found {len(instances)} repo instances")
            all_instances.extend(instances)
    
    if args.benchmark in ["all", "tac_mcp_value"]:
        instances = extract_tac_repos()
        print(f"[tac_mcp_value] Found {len(instances)} repo instances")
        all_instances.extend(instances)
    
    if args.benchmark in ["all", "kubernetes_docs"]:
        k8s_dir = args.benchmarks_dir / "kubernetes_docs"
        if k8s_dir.exists():
            instances = extract_kubernetes_docs_repos(k8s_dir)
            print(f"[kubernetes_docs] Found {len(instances)} repo instances")
            all_instances.extend(instances)
    
    if args.benchmark in ["all", "github_mined"]:
        github_mined_dir = args.benchmarks_dir / "github_mined"
        if github_mined_dir.exists():
            instances = extract_github_mined_repos(github_mined_dir)
            print(f"[github_mined] Found {len(instances)} repo instances")
            all_instances.extend(instances)
    
    # Deduplicate
    unique_instances = deduplicate_by_repo_commit(all_instances)
    print(f"\nTotal unique repo-commit pairs: {len(unique_instances)}")
    
    # Convert to instance_to_mirror.json format
    output = {}
    for inst in unique_instances:
        output[inst.instance_id] = {
            "mirror_name": inst.mirror_name,
            "original_repo": inst.original_repo,
            "commit": inst.commit,
            "benchmark": inst.benchmark,
            "language": inst.language
        }
    
    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Write output
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nWrote {len(output)} instances to {args.output}")
    
    # Summary by benchmark
    print("\nSummary by benchmark:")
    by_benchmark = {}
    for inst in unique_instances:
        by_benchmark.setdefault(inst.benchmark, []).append(inst)
    for bench, insts in sorted(by_benchmark.items()):
        repos = set(i.original_repo for i in insts)
        print(f"  {bench}: {len(insts)} tasks, {len(repos)} unique repos")


if __name__ == "__main__":
    main()
