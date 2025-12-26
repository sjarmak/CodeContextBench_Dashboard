"""
Add Aider Polyglot to benchmark registry

Aider Polyglot is a pre-installed Harbor dataset with 500+ real coding tasks
across Java, Python, Go, Rust, C++, and JavaScript.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, init_database

def add_aider_polyglot():
    """Add Aider Polyglot benchmark."""
    # Initialize database
    init_database()

    # Check if already exists
    existing = BenchmarkRegistry.get_by_name("Aider Polyglot")
    if existing:
        print(f"✓ Aider Polyglot already registered (ID: {existing['id']})")
        return existing['id']

    # Add to registry
    benchmark_id = BenchmarkRegistry.add(
        name="Aider Polyglot",
        folder_name="aider-polyglot@1.0",  # Harbor dataset name
        adapter_type="harbor_dataset",     # Harbor pre-installed dataset
        description="Aider Polyglot dataset - 500+ real polyglot coding tasks. "
                   "Tests coding ability across Java, Python, Go, Rust, C++, and JavaScript.",
        metadata={
            "source": "harbor",
            "dataset_name": "aider-polyglot",
            "task_count": 500,
            "languages": ["Java", "Python", "Go", "Rust", "C++", "JavaScript"],
            "requires_code_modification": True,
            "difficulty": "medium-hard",
            "avg_time_minutes": 15,
            "harbor_registry": "https://raw.githubusercontent.com/laude-institute/harbor/main/registry.json"
        }
    )

    print(f"✓ Added Aider Polyglot (ID: {benchmark_id})")
    print(f"  - 500+ polyglot coding tasks")
    print(f"  - 6 programming languages")
    print(f"  - Real code modifications required")
    print(f"  - Perfect for testing code diffs!")

    return benchmark_id

if __name__ == "__main__":
    add_aider_polyglot()
