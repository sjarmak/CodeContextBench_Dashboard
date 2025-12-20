#!/usr/bin/env python3
"""
Filter DependEval tasks to only include examples from indexed repos.

The DependEval dataset contains thousands of examples, but we only have
150 repos indexed in Sourcegraph. This script filters the DependEval data
to create a benchmark that can be evaluated with Sourcegraph MCP.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


def load_indexed_repos(file_path: str) -> set[str]:
    """Load the list of indexed repositories."""
    repos = set()
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Parse format: "owner/repo",
            repo = line.strip('"').rstrip(',').lower()
            if repo:
                repos.add(repo)
    return repos


def extract_repo_from_example(example: Dict[str, Any]) -> str | None:
    """
    Extract repository name from a DependEval example.
    
    Different task types have different structures, so we need flexible parsing.
    """
    # Try different fields where repo info might be stored
    for field in ['repo', 'repository', 'repo_name', 'repo_url', 'path', 'project']:
        if field in example and example[field]:
            value = example[field]
            if isinstance(value, str):
                # Extract owner/repo from various formats
                value = value.lower()
                
                # If it's a URL, extract owner/repo
                if 'github.com' in value:
                    # Format: https://github.com/owner/repo or github.com/owner/repo
                    parts = value.split('/')
                    if len(parts) >= 2:
                        return f"{parts[-2]}/{parts[-1]}".rstrip('.git')
                
                # If it's already owner/repo format
                if '/' in value:
                    parts = value.split('/')
                    if len(parts) == 2:
                        return value
                    # If it's a longer path, take last two parts
                    return f"{parts[-2]}/{parts[-1]}"
    
    return None


def filter_dependeval_data(
    data_file: str,
    indexed_repos: set[str],
    output_file: str,
    task_type: str = "DR"
) -> int:
    """
    Filter DependEval data to only include examples from indexed repos.
    
    Args:
        data_file: Path to DependEval JSON file
        indexed_repos: Set of lowercase "owner/repo" strings
        output_file: Path to write filtered data
        task_type: Task type for logging (DR, RC, ME)
        
    Returns:
        Number of examples written to output file
    """
    matched_count = 0
    total_count = 0
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # DependEval data is a list of examples
    if not isinstance(data, list):
        print(f"Warning: Expected list, got {type(data).__name__}")
        return 0
    
    filtered_examples = []
    
    for example in data:
        total_count += 1
        
        # Extract repo from example
        repo = extract_repo_from_example(example)
        
        if repo and repo in indexed_repos:
            # Found a matching repo
            filtered_examples.append(example)
            matched_count += 1
    
    # Write filtered data
    with open(output_file, 'w') as f:
        json.dump(filtered_examples, f, indent=2)
    
    print(f"{task_type}: {matched_count}/{total_count} examples match indexed repos")
    
    return matched_count


def main():
    """Main entry point."""
    # Load indexed repos
    indexed_repos_file = "dependeval_repos_for_indexing.txt"
    if not Path(indexed_repos_file).exists():
        print(f"Error: {indexed_repos_file} not found")
        sys.exit(1)
    
    indexed_repos = load_indexed_repos(indexed_repos_file)
    print(f"Loaded {len(indexed_repos)} indexed repos")
    print()
    
    # DependEval data directory
    dependeval_data_dir = Path("/Users/sjarmak/DependEval/data")
    if not dependeval_data_dir.exists():
        print(f"Error: DependEval data directory not found at {dependeval_data_dir}")
        sys.exit(1)
    
    # Output directory
    output_dir = Path("benchmarks/dependeval_filtered")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()
    
    # Filter each language and task type
    languages = ["python", "java", "javascript", "typescript", "c", "c++", "c#", "php"]
    task_mappings = {
        "task1": "DR",      # Dependency Recognition
        "task2": "RC",      # Repository Construction
        "task4": "ME"       # Multi-file Editing
    }
    
    total_matched = 0
    
    for language in languages:
        lang_dir = dependeval_data_dir / language
        if not lang_dir.exists():
            continue
        
        output_lang_dir = output_dir / language
        output_lang_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Processing: {language.upper()}")
        print(f"{'='*60}")
        
        for task_file, task_label in task_mappings.items():
            # Look for files like task1_python.json, task2_python_final.json
            for pattern in [f"{task_file}_{language}*.json"]:
                matching_files = list(lang_dir.glob(pattern))
                if not matching_files:
                    continue
                
                input_file = matching_files[0]
                output_file = output_lang_dir / f"{task_file}_{language}_filtered.json"
                
                try:
                    count = filter_dependeval_data(
                        str(input_file),
                        indexed_repos,
                        str(output_file),
                        f"{language.upper()}-{task_label}"
                    )
                    total_matched += count
                except Exception as e:
                    print(f"✗ Error processing {input_file}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Total examples matched: {total_matched}")
    print(f"Filtered data saved to: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
