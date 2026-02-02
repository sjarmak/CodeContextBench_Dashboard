"""
Benchmark Manager

View, edit, and validate benchmarks.
Includes oracle validation for sanity checking.
"""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import BenchmarkRegistry, TaskProfileManager
from benchmark.oracle_validator import run_oracle_validation, validate_task_structure
from benchmark.harbor_datasets import get_harbor_dataset_instances
import pandas as pd


def show_benchmark_list():
    """Display list of registered benchmarks."""
    st.subheader("Registered Benchmarks")

    benchmarks = BenchmarkRegistry.list_all()

    if not benchmarks:
        st.info("No benchmarks registered. Add benchmarks to get started.")
        return None

    # Create table
    data = []
    for b in benchmarks:
        data.append({
            "Name": b["name"],
            "Folder": b["folder_name"],
            "Tasks": b.get("task_count", 0),
        })

    df = pd.DataFrame(data)
    # Calculate height to fit all rows without scrolling (35px header + 35px per row + padding)
    table_height = 35 + 35 * len(data) + 10
    st.dataframe(df, use_container_width=True, hide_index=True, height=table_height)

    # Selector
    selected_name = st.selectbox(
        "Select Benchmark to Manage",
        [b["name"] for b in benchmarks],
        key="benchmark_selector"
    )

    return next((b for b in benchmarks if b["name"] == selected_name), None)


def show_benchmark_details(benchmark: dict):
    """Show details and management options for a benchmark."""
    st.subheader(f"Benchmark: {benchmark['name']}")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Folder:** `{benchmark['folder_name']}`")
        st.write(f"**Adapter Type:** {benchmark.get('adapter_type', 'N/A')}")

    with col2:
        st.write(f"**Task Count:** {benchmark.get('task_count', 0)}")
        st.write(f"**Last Validated:** {benchmark.get('last_validated', 'Never')[:19] if benchmark.get('last_validated') else 'Never'}")

    if benchmark.get("description"):
        st.write(f"**Description:** {benchmark['description']}")

    st.markdown("---")

    # Tasks section
    show_tasks_section(benchmark)

    st.markdown("---")

    # Validation section
    show_validation_section(benchmark)


def _load_ccb_tasks(folder_name: str) -> list:
    """Load CCB benchmark tasks from selected_benchmark_tasks.json."""
    import json as _json

    tasks_file = Path(__file__).parent.parent.parent / "data" / "selected_benchmark_tasks.json"
    if not tasks_file.exists():
        return []

    try:
        with open(tasks_file) as f:
            data = _json.load(f)
        return [
            t for t in data.get("tasks", [])
            if t.get("benchmark") == folder_name
        ]
    except Exception:
        return []


def _show_ccb_tasks(benchmark: dict):
    """Display tasks for a CCB adapter benchmark from the task registry."""
    import json as _json

    folder_name = benchmark["folder_name"]
    tasks = _load_ccb_tasks(folder_name)

    # Show metadata
    if benchmark.get("metadata"):
        metadata = _json.loads(benchmark["metadata"]) if isinstance(benchmark["metadata"], str) else benchmark["metadata"]
        if metadata.get("languages"):
            st.write(f"**Languages:** {', '.join(metadata['languages'])}")
        if metadata.get("sdlc_phases"):
            st.write(f"**SDLC Phases:** {', '.join(metadata['sdlc_phases'])}")
        if metadata.get("difficulties"):
            st.write(f"**Difficulties:** {', '.join(metadata['difficulties'])}")

    if not tasks:
        st.warning("No tasks found in task registry for this benchmark.")
        return

    st.write(f"**Total Tasks:** {len(tasks)}")

    # Build task table
    task_data = []
    for t in tasks:
        task_data.append({
            "Task ID": t.get("task_id", ""),
            "SDLC Phase": t.get("sdlc_phase", ""),
            "Language": t.get("language", ""),
            "Difficulty": t.get("difficulty", ""),
            "Repo": t.get("repo", ""),
            "MCP Benefit": f"{t.get('mcp_benefit_score', 0):.2f}",
        })

    st.dataframe(task_data, use_container_width=True, hide_index=True)

    # Show MCP benefit breakdown in expander
    with st.expander("MCP Benefit Details"):
        for t in tasks:
            breakdown = t.get("mcp_breakdown", {})
            if breakdown:
                st.markdown(f"**{t.get('task_id', '')}** (score: {t.get('mcp_benefit_score', 0):.2f})")
                cols = st.columns(4)
                for i, (key, val) in enumerate(breakdown.items()):
                    label = key.replace("_", " ").title()
                    cols[i % 4].write(f"{label}: {val}")


def show_tasks_section(benchmark: dict):
    """Show tasks list and task profiles."""
    st.subheader("Tasks")

    # Check if this is a Harbor dataset
    is_harbor_dataset = benchmark.get("adapter_type") == "harbor_dataset"

    if is_harbor_dataset:
        st.info(f"**Harbor Dataset**: {benchmark['name']}")
        st.write("This is a pre-installed Harbor dataset. Tasks are managed by Harbor.")

        # Load tasks from HuggingFace
        with st.spinner("Loading task list from HuggingFace..."):
            try:
                tasks = get_harbor_dataset_instances(benchmark['folder_name'])
                st.success(f"Loaded {len(tasks)} tasks")
            except Exception as e:
                st.error(f"Failed to load tasks: {e}")
                tasks = []

        # Show metadata if available
        import json
        if benchmark.get("metadata"):
            metadata = json.loads(benchmark["metadata"]) if isinstance(benchmark["metadata"], str) else benchmark["metadata"]
            if metadata.get("languages"):
                st.write(f"**Languages:** {', '.join(metadata['languages'])}")
            if metadata.get("difficulty"):
                st.write(f"**Difficulty:** {metadata['difficulty']}")

        if tasks:
            # Show task list in expandable
            with st.expander(f"View All Tasks ({len(tasks)})", expanded=False):
                # Add search box
                search = st.text_input("Search tasks (e.g., 'django', 'pytest', 'astropy')")

                if search:
                    filtered_tasks = [t for t in tasks if search.lower() in t.lower()]
                    st.write(f"**Showing {len(filtered_tasks)} tasks matching '{search}':**")
                    tasks_to_show = filtered_tasks[:50]  # Limit to 50 for performance
                else:
                    st.write(f"**Showing first 50 of {len(tasks)} tasks:**")
                    tasks_to_show = tasks[:50]

                for task in tasks_to_show:
                    st.write(f"- {task}")

                if not search and len(tasks) > 50:
                    st.info("Use the search box above to filter tasks")

        st.write("**Usage:** Go to 'Evaluation Runner' to select and run tasks from this dataset.")
        return

    # CCB benchmark - load tasks from selected_benchmark_tasks.json
    is_ccb = benchmark.get("adapter_type") == "ccb"
    benchmark_path = Path("benchmarks") / benchmark["folder_name"]

    if is_ccb and not benchmark_path.exists():
        _show_ccb_tasks(benchmark)
        return

    if not benchmark_path.exists():
        st.error(f"Benchmark directory not found: {benchmark_path}")
        return

    # Get tasks
    tasks = []
    for task_dir in sorted(benchmark_path.iterdir()):
        if task_dir.is_dir():
            task_toml = task_dir / "task.toml"
            if task_toml.exists():
                tasks.append(task_dir.name)

    if not tasks:
        st.warning("No tasks found in benchmark directory")
        return

    st.write(f"**Total Tasks:** {len(tasks)}")

    # Show tasks in expandable
    with st.expander(f"View All Tasks ({len(tasks)})"):
        # Paginate if many tasks
        if len(tasks) > 50:
            st.write("Showing first 50 tasks...")
            tasks_to_show = tasks[:50]
        else:
            tasks_to_show = tasks

        for task in tasks_to_show:
            st.write(f"- {task}")

    # Task profiles
    st.markdown("#### Task Profiles")

    profiles = TaskProfileManager.list_for_benchmark(benchmark["id"])

    if profiles:
        profile_names = [p["name"] for p in profiles]
        selected_profile = st.selectbox("Quick Select", ["Custom"] + profile_names)

        if selected_profile != "Custom":
            profile = next(p for p in profiles if p["name"] == selected_profile)
            st.info(f"Profile '{selected_profile}' has {len(profile['task_list'])} tasks")
            if st.button("Load Profile", key=f"load_profile_{benchmark['id']}"):
                st.session_state[f"selected_tasks_{benchmark['id']}"] = profile['task_list']
                st.success("Profile loaded!")

    # Quick selections
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Select All Tasks", key=f"select_all_{benchmark['id']}"):
            st.session_state[f"selected_tasks_{benchmark['id']}"] = tasks

    with col2:
        if st.button("Clear Selection", key=f"clear_selection_{benchmark['id']}"):
            st.session_state[f"selected_tasks_{benchmark['id']}"] = []

    # Manual selection
    selected_tasks = st.multiselect(
        "Select Tasks",
        tasks,
        default=st.session_state.get(f"selected_tasks_{benchmark['id']}", []),
        key=f"task_multiselect_{benchmark['id']}"
    )

    st.session_state[f"selected_tasks_{benchmark['id']}"] = selected_tasks

    st.write(f"**Selected: {len(selected_tasks)} tasks**")


def show_validation_section(benchmark: dict):
    """Show validation controls and results."""
    st.subheader("Validation")

    # Skip validation for Harbor datasets (they're pre-validated)
    is_harbor_dataset = benchmark.get("adapter_type") == "harbor_dataset"
    if is_harbor_dataset:
        st.info("Harbor datasets are pre-validated and maintained by the Harbor team.")
        return

    benchmark_path = Path("benchmarks") / benchmark["folder_name"]

    # Get selected tasks
    selected_tasks = st.session_state.get(f"selected_tasks_{benchmark['id']}", [])

    if not selected_tasks:
        st.info("Select tasks above to run oracle validation")
        return

    st.write(f"**Selected Tasks for Validation:** {len(selected_tasks)}")

    col1, col2 = st.columns([3, 1])

    with col1:
        timeout = st.number_input(
            "Timeout (seconds)",
            min_value=30,
            max_value=3600,
            value=300,
            step=30,
            key=f"validation_timeout_{benchmark['id']}"
        )

    with col2:
        st.write("")  # Spacer
        st.write("")
        validate_button = st.button(
            "Run Oracle Validation",
            key=f"validate_{benchmark['id']}"
        )

    if validate_button:
        st.markdown("---")
        st.write("**Validation Results:**")

        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []

        for i, task_name in enumerate(selected_tasks):
            status_text.text(f"Validating {task_name}...")

            task_path = benchmark_path / task_name

            # Run validation
            result = run_oracle_validation(task_path, timeout_sec=timeout)
            results.append({
                "Task": task_name,
                "Status": result["status"],
                "Reward": result.get("reward", "N/A"),
            })

            progress_bar.progress((i + 1) / len(selected_tasks))

        status_text.text("Validation complete!")

        # Show results table
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Summary
        passed = len([r for r in results if r["Status"] == "passed"])
        failed = len([r for r in results if r["Status"] == "failed"])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Passed", passed)
        with col2:
            st.metric("Failed", failed)
        with col3:
            st.metric("Success Rate", f"{passed/len(results)*100:.1f}%" if results else "0%")

        # Update benchmark validation status
        BenchmarkRegistry.update(
            benchmark["id"],
            last_validated=pd.Timestamp.now().isoformat(),
            validation_status=f"{passed}/{len(results)} passed"
        )


def show_benchmark_manager():
    """Main benchmark manager page."""
    st.title("Benchmark Manager")
    st.write("View, edit, and validate benchmarks")

    # Show benchmark list and selector
    selected_benchmark = show_benchmark_list()

    if selected_benchmark:
        st.markdown("---")
        show_benchmark_details(selected_benchmark)


if __name__ == "__main__":
    show_benchmark_manager()
