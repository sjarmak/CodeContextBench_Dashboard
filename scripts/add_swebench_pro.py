#!/usr/bin/env python3
"""
Add SWE-bench Pro to benchmark registry.

Run this after generating tasks with:
  python benchmarks/swebench_pro/run_adapter.py --all --task-dir benchmarks/swebench_pro/tasks
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, init_database


def add_swebench_pro():
    """Add SWE-bench Pro benchmark."""
    
    # Ensure database is initialized
    init_database()
    
    # Check if already registered
    existing = BenchmarkRegistry.get_by_name("SWE-bench Pro")
    if existing:
        print(f"SWE-bench Pro already registered (ID: {existing['id']})")
        print("Updating task count...")
        
        # Update task count
        tasks_dir = Path("benchmarks/swebench_pro/tasks")
        if tasks_dir.exists():
            task_count = len([
                d for d in tasks_dir.iterdir()
                if d.is_dir() and (d / "task.toml").exists()
            ])
            BenchmarkRegistry.update(existing["id"], task_count=task_count)
            print(f"✓ Updated task count: {task_count}")
        return existing["id"]
    
    # Count tasks
    tasks_dir = Path("benchmarks/swebench_pro/tasks")
    if not tasks_dir.exists():
        print("Error: Tasks directory not found. Run the adapter first:")
        print("  python benchmarks/swebench_pro/run_adapter.py --all --task-dir benchmarks/swebench_pro/tasks")
        sys.exit(1)
    
    task_count = len([
        d for d in tasks_dir.iterdir()
        if d.is_dir() and (d / "task.toml").exists()
    ])
    
    if task_count == 0:
        print("Warning: No tasks found in benchmarks/swebench_pro/tasks/")
        print("Run the adapter first to generate tasks.")
    
    # Register benchmark
    benchmark_id = BenchmarkRegistry.add(
        name="SWE-bench Pro",
        folder_name="swebench_pro/tasks",
        adapter_type="swebench_pro",
        description="SWE-bench Pro: Long-horizon multi-language software engineering tasks (Go, TypeScript, Python, JavaScript)",
        metadata={
            "languages": ["go", "typescript", "python", "javascript"],
            "difficulty": "hard",
            "source": "ScaleAI/SWE-bench_Pro",
            "mcp_enabled": True,
            "repositories": [
                "NodeBB/NodeBB",
                "flipt-io/flipt",
                "qutebrowser/qutebrowser",
                "tutao/tutanota",
                "internetarchive/openlibrary",
                "protonmail/webclients",
                "future-architect/vuls",
            ],
        }
    )
    
    # Update task count
    BenchmarkRegistry.update(benchmark_id, task_count=task_count)
    
    print(f"✓ Added SWE-bench Pro (ID: {benchmark_id})")
    print(f"  Tasks: {task_count}")
    print(f"  Languages: Go, TypeScript, Python, JavaScript")
    print(f"  MCP Enabled: Yes")
    
    return benchmark_id


if __name__ == "__main__":
    add_swebench_pro()
