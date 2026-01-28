"""
Add Benchmark

Register new benchmarks to the system.
"""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import BenchmarkRegistry


def show_add_benchmark():
    """Main add benchmark page."""
    st.title("Add Benchmark")
    st.write("Register a new benchmark to the system")

    with st.form("add_benchmark_form"):
        name = st.text_input(
            "Benchmark Name",
            placeholder="My Custom Benchmark"
        )

        folder_name = st.text_input(
            "Folder Name",
            placeholder="my_custom_benchmark",
            help="Folder name under benchmarks/"
        )

        adapter_type = st.selectbox(
            "Adapter Type",
            ["custom", "swebench", "repoqa", "dibench", "dependeval", "other"]
        )

        description = st.text_area(
            "Description",
            placeholder="Describe what this benchmark tests..."
        )

        submitted = st.form_submit_button("Add Benchmark")

        if submitted:
            if not name or not folder_name:
                st.error("Name and folder name are required")
                return

            # Check if folder exists
            benchmark_path = Path("benchmarks") / folder_name

            if not benchmark_path.exists():
                st.warning(f"Folder does not exist yet: {benchmark_path}")
                st.info("You can still register it and add tasks later")

            # Check if already exists
            existing = BenchmarkRegistry.get_by_name(name)
            if existing:
                st.error(f"Benchmark '{name}' already exists")
                return

            # Count tasks if folder exists
            task_count = 0
            if benchmark_path.exists():
                task_count = len([
                    d for d in benchmark_path.iterdir()
                    if d.is_dir() and (d / "task.toml").exists()
                ])

            try:
                bench_id = BenchmarkRegistry.add(
                    name=name,
                    folder_name=folder_name,
                    adapter_type=adapter_type,
                    description=description,
                    metadata={"task_count": task_count}
                )

                BenchmarkRegistry.update(bench_id, task_count=task_count)

                st.success(f"Benchmark '{name}' added successfully!")
                st.info(f"Found {task_count} tasks in {folder_name}")

            except Exception as e:
                st.error(f"Failed to add benchmark: {e}")

    st.markdown("---")
    st.subheader("Existing Benchmarks")

    benchmarks = BenchmarkRegistry.list_all()

    if benchmarks:
        for b in benchmarks:
            st.write(f"- **{b['name']}** (`{b['folder_name']}`) - {b.get('task_count', 0)} tasks")
    else:
        st.info("No benchmarks registered yet")


if __name__ == "__main__":
    show_add_benchmark()
