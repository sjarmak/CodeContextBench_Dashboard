#!/usr/bin/env python3
"""Generate Harbor task directories from GitHub mining results."""

import json
import sys
from pathlib import Path

def generate_task_dir(task_dict: dict, output_dir: Path) -> Path:
    """Generate a complete Harbor task directory from task dict."""
    task_id = task_dict['id']
    task_dir = output_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. instruction.md
    instruction = f"""# {task_dict['title']}

**Repository:** {task_dict['repo_key']}  
**Difficulty:** {task_dict['difficulty'].upper()}  
**Category:** {task_dict['category']}

## Description

{task_dict['description']}

## Task

{task_dict['instructions']}

## Success Criteria

{task_dict['success_criteria']}

## Testing

Run the test command to verify your implementation:

```bash
{task_dict['test_command']}
```

**Time Limit:** {task_dict['time_limit_seconds'] // 60} minutes  
**Estimated Context:** {task_dict['estimated_tokens']} tokens
"""
    
    (task_dir / "instruction.md").write_text(instruction)
    
    # 2. task.toml
    task_toml = f"""[metadata]
name = "{task_id}"
description = "{task_dict['description']}"
license = "MIT"

[task]
id = "{task_id}"
repo = "{task_dict['repo_key']}"
category = "{task_dict['category']}"
language = "{task_dict['language']}"
difficulty = "{task_dict['difficulty']}"
time_limit_sec = {task_dict['time_limit_seconds']}

[verification]
type = "{task_dict['verification_type']}"
command = "{task_dict['test_command']}"
"""
    
    (task_dir / "task.toml").write_text(task_toml)
    
    # 3. environment/Dockerfile
    env_dir = task_dir / "environment"
    env_dir.mkdir(exist_ok=True)
    
    lang = task_dict['language'].lower()
    if lang == 'go':
        base_image = 'golang:1.21'
        install_cmd = 'RUN go mod download'
    elif lang == 'cpp':
        base_image = 'gcc:13'
        install_cmd = 'RUN apt-get update && apt-get install -y cmake ninja-build'
    elif lang == 'typescript':
        base_image = 'node:20'
        install_cmd = 'RUN npm ci'
    elif lang == 'python':
        base_image = 'python:3.11'
        install_cmd = 'RUN pip install -q pytest'
    else:
        base_image = 'ubuntu:22.04'
        install_cmd = ''
    
    dockerfile = f"""FROM {base_image}

WORKDIR /workspace

# Install dependencies
{install_cmd}

# Task setup complete
"""
    
    (env_dir / "Dockerfile").write_text(dockerfile)
    
    # 4. tests/test.sh
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    test_command = task_dict['test_command']
    test_sh = f"""#!/bin/bash
set -e

echo "Running test command: {test_command}"
{test_command}

echo "✓ Tests passed"
exit 0
"""
    
    test_sh_path = tests_dir / "test.sh"
    test_sh_path.write_text(test_sh)
    test_sh_path.chmod(0o755)
    
    # 5. repo_path (for BasePatchAgent)
    (task_dir / "repo_path").write_text(f"/repos/{task_dict['repo_key']}\n")
    
    return task_dir

def main():
    input_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/mining_results_full.json")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchmarks/github_mined")
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        return 1
    
    # Load mining results
    with open(input_file) as f:
        results = json.load(f)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    task_count = 0
    
    # Generate tasks from each repository
    for repo_result in results.get('repositories', []):
        if repo_result['status'] != 'success':
            continue
        
        for task_dict in repo_result.get('candidates', []):
            task_dir = generate_task_dir(task_dict, output_dir)
            print(f"✓ Generated {task_dir}")
            task_count += 1
    
    print(f"\n✅ Generated {task_count} Harbor tasks in {output_dir}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
