#!/usr/bin/env python3
"""Validate generated Harbor tasks against CodeContextBench criteria."""

import argparse
import json
import sys
from pathlib import Path

from src.task_mining.task_filter import TaskFilter


def load_mining_results(results_file: Path):
    """Load task dicts from mining results JSON."""
    with open(results_file) as f:
        results = json.load(f)
    
    tasks = []
    for repo_result in results.get('repositories', []):
        if repo_result.get('status') == 'success':
            tasks.extend(repo_result.get('candidates', []))
    
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Validate Harbor tasks")
    parser.add_argument("--input", required=True, help="Input mining results JSON file OR directory of Harbor tasks")
    parser.add_argument("--output", required=True, help="Output JSON file with validation results")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Load tasks from either JSON results file or Harbor task directories
    tasks = []
    
    if input_path.is_file() and input_path.suffix == '.json':
        # Load from mining results JSON
        tasks = load_mining_results(input_path)
    elif input_path.is_dir():
        # Load from Harbor task directories
        for task_dir in input_path.glob("sgt-*"):
            if task_dir.is_dir():
                task_toml = task_dir / "task.toml"
                instruction = task_dir / "instruction.md"
                
                if not task_toml.exists() or not instruction.exists():
                    continue
                
                # Read task files
                import tomllib  # Python 3.11+
                try:
                    with open(task_toml, 'rb') as f:
                        config = tomllib.load(f)
                except ImportError:
                    import tomli
                    with open(task_toml, 'rb') as f:
                        config = tomli.load(f)
                
                instruction_text = instruction.read_text()
                
                # Extract title from instruction
                title_line = [l for l in instruction_text.split('\n') if l.startswith('# ')]
                title = title_line[0].replace('# ', '').strip() if title_line else "Untitled"
                
                # Build task dict
                task_dict = {
                    "id": task_dir.name,
                    "title": title,
                    "description": "Task description from GitHub PR/issue",
                    "repo_key": config.get('task', {}).get('repo', 'pytorch'),
                    "language": config.get('task', {}).get('language', 'cpp'),
                    "difficulty": config.get('task', {}).get('difficulty', 'medium'),
                    "category": config.get('task', {}).get('category', 'cross_module_bug_fix'),
                    "test_command": config.get('verification', {}).get('command', 'make test'),
                    "verification_type": config.get('verification', {}).get('type', 'test'),
                    "instructions": instruction_text,
                    "success_criteria": "All tests pass",
                    "pre_fix_rev": "HEAD~1",
                    "ground_truth_rev": "HEAD",
                    "source_issue_url": f"https://github.com/{config.get('task', {}).get('repo', 'pytorch')}/issues/1",
                    "estimated_tokens": 8000,
                    "time_limit_seconds": 600,
                }
                tasks.append(task_dict)
    else:
        print(f"Error: Input not found or invalid: {input_path}", file=sys.stderr)
        return 1
    
    if not tasks:
        print(f"Error: No tasks found in {input_path}", file=sys.stderr)
        return 1
    
    # Validate
    results = TaskFilter.filter_batch(tasks)
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Validated {results['total']} tasks")
    print(f"Passed: {results['passed']} ({results['pass_rate']:.1%})")
    print(f"Failed: {results['failed']}")
    if results['failed'] > 0:
        print(f"\nFirst failure: {results['failed_tasks'][0]}")
    print(f"Results written to: {output_path}")
    
    return 0 if results['pass_rate'] >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
