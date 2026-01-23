#!/usr/bin/env python3
"""
Initialize default benchmarks in the database.

Registers the standard benchmarks:
- kubernetes_docs
- github_mined
- big_code_mcp
- dibench
- dependeval_benchmark
- repoqa
- 10figure
- swebench_pro
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import BenchmarkRegistry


DEFAULT_BENCHMARKS = [
    {
        "name": "Kubernetes Documentation",
        "folder_name": "kubernetes_docs",
        "adapter_type": "custom",
        "description": "Kubernetes documentation tasks",
    },
    {
        "name": "Custom GitHub",
        "folder_name": "github_mined",
        "adapter_type": "custom",
        "description": "GitHub mined tasks",
    },
    {
        "name": "Custom Big Code",
        "folder_name": "big_code_mcp",
        "adapter_type": "custom",
        "description": "Big Code MCP tasks",
    },
    {
        "name": "DIBench",
        "folder_name": "dibench",
        "adapter_type": "dibench",
        "description": "Dependency Injection Benchmark",
    },
    {
        "name": "DependEval",
        "folder_name": "dependeval_benchmark",
        "adapter_type": "dependeval",
        "description": "Dependency Evaluation Benchmark",
    },
    {
        "name": "RepoQA",
        "folder_name": "repoqa",
        "adapter_type": "repoqa",
        "description": "Repository QA tasks",
    },
    {
        "name": "Custom Synthetic",
        "folder_name": "10figure",
        "adapter_type": "custom",
        "description": "10figure synthetic tasks",
    },
    {
        "name": "SWE-bench Pro",
        "folder_name": "swebench_pro/tasks",
        "adapter_type": "swebench_pro",
        "description": "SWE-bench Pro: Long-horizon multi-language software engineering tasks (Go, TypeScript, Python)",
        "metadata": {
            "languages": ["go", "typescript", "python", "javascript"],
            "difficulty": "hard",
            "source": "ScaleAI/SWE-bench_Pro",
            "mcp_enabled": True,
        },
    },
]


def init_benchmarks():
    """Initialize default benchmarks."""
    print("Initializing default benchmarks...")

    benchmarks_dir = Path("benchmarks")

    for bench_config in DEFAULT_BENCHMARKS:
        bench_path = benchmarks_dir / bench_config["folder_name"]

        # Check if folder exists
        if not bench_path.exists():
            print(f"  Warning: {bench_config['folder_name']} directory not found, skipping")
            continue

        # Check if already registered
        existing = BenchmarkRegistry.get_by_name(bench_config["name"])
        if existing:
            print(f"  Skipping {bench_config['name']} (already registered)")
            continue

        # Count tasks - find all task.toml or task.yaml files recursively
        task_count = len(list(bench_path.rglob("task.toml"))) + len(list(bench_path.rglob("task.yaml")))

        # Register benchmark
        try:
            bench_id = BenchmarkRegistry.add(
                name=bench_config["name"],
                folder_name=bench_config["folder_name"],
                adapter_type=bench_config.get("adapter_type"),
                description=bench_config.get("description"),
                metadata={"task_count": task_count}
            )

            # Update task count
            BenchmarkRegistry.update(bench_id, task_count=task_count)

            print(f"  ✓ Registered: {bench_config['name']} ({task_count} tasks)")

        except Exception as e:
            print(f"  Error registering {bench_config['name']}: {e}")

    print("\nDone!")


if __name__ == "__main__":
    init_benchmarks()
