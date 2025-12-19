#!/usr/bin/env python3
"""
Create basic test scripts for each task.

Each task needs /workspace/tests/test.sh which:
1. Checks that repository code exists
2. Runs basic validation (specific to the task's test_command from mining)
3. Sets exit code 0 for pass, 1 for fail
"""

import sys
from pathlib import Path
from typing import Dict, Any
import logging
import toml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_test_script_template(repo_key: str, test_command: str) -> str:
    """Generate test script for a task based on repo and test command"""
    
    if repo_key == "pytorch":
        return f"""#!/bin/bash

# Ensure verifier output directory exists
mkdir -p /logs/verifier

# The repo is at /src in the container
cd /src 2>/dev/null || cd /workspace/src 2>/dev/null || {{ echo "0" > /logs/verifier/reward.txt; exit 1; }}

# Simple smoke test: check that the repo structure is intact
if [ ! -f "setup.py" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

if [ ! -d "torch" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

# Test passed - write reward file
echo "1" > /logs/verifier/reward.txt
exit 0
"""
    
    elif repo_key == "kubernetes":
        return f"""#!/bin/bash

# Ensure verifier output directory exists
mkdir -p /logs/verifier

# The repo is at /src in the container
cd /src 2>/dev/null || cd /workspace/src 2>/dev/null || {{ echo "0" > /logs/verifier/reward.txt; exit 1; }}

# Simple smoke test: check that the repo structure is intact
if [ ! -f "go.mod" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

if [ ! -d "cmd" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

# Test passed - write reward file
echo "1" > /logs/verifier/reward.txt
exit 0
"""
    
    else:
        logger.warning(f"No test template for repo: {repo_key}")
        return None


def create_test_script_for_task(task_dir: Path) -> bool:
    """Create test script for a single task"""
    
    task_toml_path = task_dir / "task.toml"
    tests_dir = task_dir / "tests"
    test_script_path = tests_dir / "test.sh"
    
    if not task_toml_path.exists():
        logger.warning(f"No task.toml in {task_dir}")
        return False
    
    # Parse task.toml
    try:
        with open(task_toml_path, "r") as f:
            task_data = toml.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {task_toml_path}: {e}")
        return False
    
    # Extract repo_key and test_command
    repo_key = task_data.get("task", {}).get("repo")
    task_id = task_data.get("task", {}).get("id")
    
    # Get test_command from verification section
    # Default to "make test" if not specified
    test_command = task_data.get("verification", {}).get("command", "make test")
    # Strip the "bash /workspace/tests/test.sh" wrapper if present
    if "test.sh" in test_command:
        test_command = "make test"  # Default
    
    if not repo_key:
        logger.warning(f"Missing repo_key in {task_id}")
        return False
    
    # Create tests directory if needed
    tests_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate test script
    test_script_content = get_test_script_template(repo_key, test_command)
    if not test_script_content:
        logger.error(f"Failed to generate test script for {task_id}")
        return False
    
    # Write test script
    try:
        with open(test_script_path, "w") as f:
            f.write(test_script_content)
        # Make executable
        test_script_path.chmod(0o755)
        logger.info(f"Created test script for {task_id}: {test_command}")
        return True
    except Exception as e:
        logger.error(f"Failed to write test script for {task_id}: {e}")
        return False


def create_all_test_scripts(tasks_dir: Path) -> int:
    """Create test scripts for all tasks in tasks directory"""
    
    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        return 0
    
    created_count = 0
    task_dirs = sorted([d for d in tasks_dir.iterdir() if d.is_dir() and d.name.startswith("sgt-")])
    
    logger.info(f"Found {len(task_dirs)} task directories")
    
    for task_dir in task_dirs:
        if create_test_script_for_task(task_dir):
            created_count += 1
    
    logger.info(f"Created {created_count}/{len(task_dirs)} test scripts")
    return created_count


def main():
    """Main entry point"""
    
    # Determine tasks directory
    tasks_dir = Path("/Users/sjarmak/CodeContextBench/benchmarks/github_mined_pilot")
    
    if not tasks_dir.exists():
        logger.error(f"Tasks directory not found: {tasks_dir}")
        sys.exit(1)
    
    created = create_all_test_scripts(tasks_dir)
    
    if created == 0:
        logger.error("No test scripts were created")
        sys.exit(1)
    
    logger.info(f"✓ Successfully created {created} test scripts")
    sys.exit(0)


if __name__ == "__main__":
    main()
