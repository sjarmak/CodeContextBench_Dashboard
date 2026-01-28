#!/usr/bin/env python3
"""
Add LoCoBench-Agent to benchmark registry.

LoCoBench-Agent provides long-context code understanding scenarios
across multiple programming languages.

Run this to register the benchmark in the dashboard.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, init_database


def add_locobench():
    """Add LoCoBench-Agent benchmark."""

    # Ensure database is initialized
    init_database()

    benchmark_name = "LoCoBench-Agent"

    # Check if already registered
    existing = BenchmarkRegistry.get_by_name(benchmark_name)
    if existing:
        print(f"LoCoBench-Agent already registered (ID: {existing['id']})")
        print("Updating task count...")

        # Update task count from selected_tasks.json
        selected_tasks_file = Path("benchmarks/locobench_agent/selected_tasks.json")
        task_count = 0
        if selected_tasks_file.exists():
            with open(selected_tasks_file) as f:
                data = json.load(f)
                task_count = len(data.get("tasks", []))

        BenchmarkRegistry.update(existing["id"], task_count=task_count)
        print(f"✓ Updated task count: {task_count}")
        return existing["id"]

    # Load task metadata from selected_tasks.json
    selected_tasks_file = Path("benchmarks/locobench_agent/selected_tasks.json")
    if not selected_tasks_file.exists():
        print("Warning: selected_tasks.json not found.")
        print("Run the task selector first:")
        print("  python benchmarks/locobench_agent/select_tasks.py")
        task_count = 0
        languages = []
        categories = []
    else:
        with open(selected_tasks_file) as f:
            data = json.load(f)
            tasks = data.get("tasks", [])
            task_count = len(tasks)
            languages = list(set(t.get("language", "unknown") for t in tasks))
            categories = list(set(t.get("task_category", "unknown") for t in tasks))

    # Register benchmark
    benchmark_id = BenchmarkRegistry.add(
        name=benchmark_name,
        folder_name="locobench_agent",
        adapter_type="locobench_agent",
        description="LoCoBench-Agent: Long-context code understanding scenarios for agentic evaluation across multiple languages",
        metadata={
            "languages": sorted(languages)
            if languages
            else [
                "python",
                "javascript",
                "typescript",
                "java",
                "go",
                "rust",
                "cpp",
                "c",
                "csharp",
            ],
            "categories": sorted(categories)
            if categories
            else [
                "architectural_understanding",
                "bug_investigation",
                "cross_file_refactoring",
            ],
            "difficulty": "expert",
            "source": "LoCoBench-Agent",
            "mcp_enabled": True,
            "min_context_length": 50000,
        },
    )

    # Update task count
    BenchmarkRegistry.update(benchmark_id, task_count=task_count)

    print(f"✓ Added LoCoBench-Agent (ID: {benchmark_id})")
    print(f"  Tasks: {task_count}")
    print(f"  Languages: {', '.join(sorted(languages)) if languages else 'N/A'}")
    print(f"  Categories: {', '.join(sorted(categories)) if categories else 'N/A'}")
    print(f"  MCP Enabled: Yes")

    return benchmark_id


if __name__ == "__main__":
    add_locobench()
