"""
Add SWE-bench Verified to benchmark registry

SWE-bench Verified is a pre-installed Harbor dataset with real GitHub issues
that require code modifications.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, init_database

def add_swebench_verified():
    """Add SWE-bench Verified benchmark."""
    # Initialize database
    init_database()

    # Check if already exists
    existing = BenchmarkRegistry.get_by_name("SWE-bench Verified")
    if existing:
        print(f"✓ SWE-bench Verified already registered (ID: {existing['id']})")
        return existing['id']

    # Add to registry
    benchmark_id = BenchmarkRegistry.add(
        name="SWE-bench Verified",
        folder_name="swebench_verified",  # Reference name
        adapter_type="harbor_dataset",    # Indicates Harbor pre-installed dataset
        description="SWE-bench Verified dataset - Real GitHub issues requiring code modifications. "
                   "Includes 500 validated instances from popular Python repositories.",
        metadata={
            "source": "harbor",
            "dataset_name": "swe_bench_verified",
            "task_count": 500,
            "languages": ["python"],
            "requires_code_modification": True,
            "difficulty": "hard",
            "avg_time_minutes": 20,
            "harbor_docs": "https://harborframework.com/docs/evals"
        }
    )

    print(f"✓ Added SWE-bench Verified (ID: {benchmark_id})")
    print(f"  - 500 real GitHub issues")
    print(f"  - Requires code modifications")
    print(f"  - Perfect for testing code diffs!")

    return benchmark_id

if __name__ == "__main__":
    add_swebench_verified()
