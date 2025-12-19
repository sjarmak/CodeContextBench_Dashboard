#!/usr/bin/env python3
"""
Update task Dockerfiles to clone repositories and checkout pre_fix_rev.

This script:
1. Reads each task's task.toml to get repo_key and pre_fix_rev
2. Gets repo_url from repo_registry.py
3. Generates a proper Dockerfile that clones the repo and checks out the commit
4. Writes to each task's environment/Dockerfile
"""

import sys
from pathlib import Path
from typing import Dict, Any
import logging
import toml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_repo_registry() -> Dict[str, Dict[str, Any]]:
    """Load repository registry from repo_registry.py"""
    from .repo_registry import REPO_REGISTRY
    # Convert dataclass to dict
    return {k: v.__dict__ for k, v in REPO_REGISTRY.items()}


def get_docker_template_for_repo(repo_key: str, pre_fix_rev: str) -> str:
    """Get appropriate Dockerfile template for repository type"""
    
    repo_configs = load_repo_registry()
    if repo_key not in repo_configs:
        logger.error(f"Unknown repo_key: {repo_key}")
        return None
    
    config = repo_configs[repo_key]
    repo_url = config.get("repo_url", "")
    
    if repo_key == "pytorch":
        return f"""FROM pytorch/pytorch:latest

WORKDIR /src

# Install additional build dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    cmake \\
    ninja-build \\
    && rm -rf /var/lib/apt/lists/*

# Clone PyTorch repository at pre_fix_rev
RUN git clone {repo_url} . 2>/dev/null || true
RUN git fetch origin {pre_fix_rev} 2>/dev/null || true
RUN git checkout {pre_fix_rev} || git checkout -B fix {pre_fix_rev}

# Install PyTorch build dependencies
RUN pip install -q numpy pyyaml mkl mkl-service setuptools cffi typing_extensions future six requests dataclasses
"""
    
    elif repo_key == "kubernetes":
        return f"""FROM golang:1.21-alpine

WORKDIR /workspace

# Install build dependencies
RUN apk add --no-cache git make bash

# Clone Kubernetes repository at pre_fix_rev
RUN git clone --depth 1 {repo_url} /src 2>/dev/null || git clone {repo_url} /src
WORKDIR /src
RUN git fetch origin {pre_fix_rev} 2>/dev/null || true
RUN git checkout {pre_fix_rev} || git checkout -B fix {pre_fix_rev}

# Copy test directory
COPY tests /workspace/tests
WORKDIR /workspace
"""
    
    else:
        logger.warning(f"No template for repo: {repo_key}")
        return None


def update_task_dockerfile(task_dir: Path) -> bool:
    """Update Dockerfile for a single task"""
    
    task_toml_path = task_dir / "task.toml"
    dockerfile_path = task_dir / "environment" / "Dockerfile"
    
    if not task_toml_path.exists():
        logger.warning(f"No task.toml in {task_dir}")
        return False
    
    if not dockerfile_path.parent.exists():
        logger.warning(f"No environment dir in {task_dir}")
        return False
    
    # Parse task.toml
    try:
        with open(task_toml_path, "r") as f:
            task_data = toml.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {task_toml_path}: {e}")
        return False
    
    # Extract repo_key and pre_fix_rev
    repo_key = task_data.get("task", {}).get("repo")
    pre_fix_rev = task_data.get("task", {}).get("pre_fix_rev")
    task_id = task_data.get("task", {}).get("id")
    
    if not repo_key or not pre_fix_rev:
        logger.warning(f"Missing repo_key or pre_fix_rev in {task_id}")
        return False
    
    # Generate Dockerfile
    dockerfile_content = get_docker_template_for_repo(repo_key, pre_fix_rev)
    if not dockerfile_content:
        logger.error(f"Failed to generate Dockerfile template for {task_id}")
        return False
    
    # Write Dockerfile
    try:
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)
        logger.info(f"Updated {task_id}: {repo_key} @ {pre_fix_rev[:12]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to write Dockerfile for {task_id}: {e}")
        return False


def update_all_dockerfiles(tasks_dir: Path) -> int:
    """Update all task Dockerfiles in tasks directory"""
    
    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        return 0
    
    updated_count = 0
    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir() and d.name.startswith("sgt-")])
    
    logger.info(f"Found {len(task_dirs)} task directories")
    
    for task_dir in task_dirs:
        if update_task_dockerfile(task_dir):
            updated_count += 1
    
    logger.info(f"Updated {updated_count}/{len(task_dirs)} task Dockerfiles")
    return updated_count


def main():
    """Main entry point"""
    
    # Determine tasks directory
    tasks_dir = Path("/Users/sjarmak/CodeContextBench/benchmarks/github_mined_pilot")
    
    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        sys.exit(1)
    
    updated = update_all_dockerfiles(tasks_dir)
    
    if updated == 0:
        logger.error("No Dockerfiles were updated")
        sys.exit(1)
    
    logger.info(f"✓ Successfully updated {updated} task Dockerfiles")
    sys.exit(0)


if __name__ == "__main__":
    main()
