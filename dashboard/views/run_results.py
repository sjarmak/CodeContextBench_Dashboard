"""
Run Results Viewer

View individual evaluation run results with:
- Metrics summary (tokens, time, result, tools)
- Agent trace with tool calls and responses
- Diffs and code changes
- LLM judge evaluation
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from benchmark.database import RunManager, TaskManager
from benchmark.trace_parser import TraceParser

from dashboard.utils.benchmark_detection import detect_benchmark_set
from dashboard.utils.task_list import render_task_list

# External runs directory - configurable via environment or default
EXTERNAL_RUNS_DIR = Path(
    os.environ.get(
        "CCB_EXTERNAL_RUNS_DIR",
        os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs"),
    )
)


def load_external_experiments() -> list:
    """Load experiments from default external runs directory."""
    return load_external_experiments_from_dir(EXTERNAL_RUNS_DIR)


def load_external_experiments_from_dir(runs_dir: Path) -> list:
    """Load experiments from a specified runs directory."""
    experiments = []

    if not runs_dir.exists():
        return experiments

    for exp_dir in sorted(
        runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
    ):
        if not exp_dir.is_dir() or exp_dir.name.startswith("."):
            continue

        result_file = exp_dir / "result.json"
        config_file = exp_dir / "config.json"

        # Check for paired comparison structure (baseline/ and deepsearch/ subdirs)
        baseline_dir = exp_dir / "baseline"
        deepsearch_dir = exp_dir / "deepsearch"

        if baseline_dir.exists() or deepsearch_dir.exists():
            # This is a paired comparison experiment (LoCoBench/SWE-bench style)
            try:
                exp_data = {
                    "path": exp_dir,
                    "name": exp_dir.name,
                    "result": {},
                    "config": {},
                    "is_paired": True,
                    "modes": {},
                }

                # Load baseline results
                if baseline_dir.exists():
                    baseline_tasks = _scan_paired_mode_tasks(baseline_dir)
                    exp_data["modes"]["baseline"] = {
                        "path": baseline_dir,
                        "tasks": baseline_tasks,
                    }

                # Load deepsearch results
                if deepsearch_dir.exists():
                    deepsearch_tasks = _scan_paired_mode_tasks(deepsearch_dir)
                    exp_data["modes"]["deepsearch"] = {
                        "path": deepsearch_dir,
                        "tasks": deepsearch_tasks,
                    }

                # Calculate summary stats
                all_tasks = []
                for mode, mode_data in exp_data["modes"].items():
                    all_tasks.extend(mode_data["tasks"])

                if all_tasks:
                    rewards = [
                        t.get("reward", 0)
                        for t in all_tasks
                        if t.get("reward") is not None
                    ]
                    exp_data["result"] = {
                        "n_total_trials": len(all_tasks),
                        "stats": {
                            "n_errors": sum(1 for t in all_tasks if t.get("error")),
                            "mean_reward": sum(rewards) / len(rewards)
                            if rewards
                            else 0,
                        },
                    }

                experiments.append(exp_data)
            except Exception as e:
                pass  # Skip if can't load

        elif result_file.exists():
            # Standard Harbor format with top-level result.json
            try:
                with open(result_file) as f:
                    result = json.load(f)

                config = {}
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)

                experiments.append(
                    {
                        "path": exp_dir,
                        "name": exp_dir.name,
                        "result": result,
                        "config": config,
                        "is_paired": False,
                    }
                )
            except Exception as e:
                pass  # Skip if can't load

    return experiments


def _scan_paired_mode_tasks(mode_dir: Path) -> list:
    """Scan a baseline/ or deepsearch/ directory for task results."""
    tasks = []

    # Find timestamp subdirectory (e.g., 2026-01-24__22-52-07)
    for subdir in mode_dir.iterdir():
        if not subdir.is_dir():
            continue

        # Check if this is a timestamp directory containing task dirs
        # or directly contains task directories
        task_dirs = []

        # Look for directories with result.json inside
        for item in subdir.iterdir():
            if item.is_dir() and (item / "result.json").exists():
                task_dirs.append(item)

        # If no task dirs found at this level, this might be the task dir itself
        if not task_dirs and (subdir / "result.json").exists():
            task_dirs = [subdir]

        for task_dir in task_dirs:
            result_file = task_dir / "result.json"
            if result_file.exists():
                try:
                    with open(result_file) as f:
                        result = json.load(f)

                    # Extract reward from Harbor format
                    verifier_result = result.get("verifier_result") or {}
                    rewards = verifier_result.get("rewards") or {}
                    reward = rewards.get("reward", 0.0)

                    # Extract timing
                    timing = result.get("timing") or {}

                    # Extract token usage
                    agent_result = result.get("agent_result") or {}

                    tasks.append(
                        {
                            "task_name": result.get("task_name", task_dir.name),
                            "trial_name": result.get("trial_name", task_dir.name),
                            "reward": reward,
                            "status": "completed"
                            if result.get("verifier_result")
                            else "error",
                            "error": result.get("exception_info"),
                            "input_tokens": agent_result.get("n_input_tokens", 0),
                            "output_tokens": agent_result.get("n_output_tokens", 0),
                            "started_at": timing.get("started_at", ""),
                            "finished_at": timing.get("finished_at", ""),
                            "instance_dir": task_dir,
                            "result_path": str(result_file),
                        }
                    )
                except Exception:
                    pass

    return tasks


def load_external_tasks(exp_dir: Path, result: dict) -> list:
    """Load task instances from an external experiment directory."""
    tasks = []

    # Get evals info from result.json
    stats = result.get("stats", {})
    evals = stats.get("evals", {})

    # Scan for instance directories (they contain agent/ subdirectory)
    for item in exp_dir.iterdir():
        if not item.is_dir() or item.name.startswith("."):
            continue

        agent_dir = item / "agent"
        if not agent_dir.exists():
            continue

        # This is a task instance directory
        instance_name = item.name

        # Load instance result.json if exists
        instance_result = {}
        instance_result_file = item / "result.json"
        if instance_result_file.exists():
            try:
                with open(instance_result_file) as f:
                    instance_result = json.load(f)
            except:
                pass

        # Find trace file (claude-code.txt for SWEBench agents)
        claude_file = agent_dir / "claude-code.txt"
        trajectory_file = agent_dir / "trajectory.json"

        # Determine reward from instance result
        reward = instance_result.get("reward", "N/A")
        if reward == "N/A":
            # Try to find from overall stats
            for eval_name, eval_data in evals.items():
                reward_stats = eval_data.get("reward_stats", {}).get("reward", {})
                for reward_val, instances in reward_stats.items():
                    if instance_name in instances:
                        reward = float(reward_val)
                        break

        tasks.append(
            {
                "task_name": instance_name,
                "agent_name": list(evals.keys())[0] if evals else "unknown",
                "status": "completed",
                "reward": reward,
                "total_tokens": instance_result.get("metrics", {}).get(
                    "total_tokens", "N/A"
                ),
                "execution_time": instance_result.get("execution_time", 0),
                "instance_dir": item,
                "claude_file": claude_file if claude_file.exists() else None,
                "trajectory_file": trajectory_file
                if trajectory_file.exists()
                else None,
                "result_path": str(instance_result_file)
                if instance_result_file.exists()
                else None,
            }
        )

    return tasks


def _load_manifest_pairs(experiments: list) -> list[dict]:
    """
    Load pre-defined pairs from manifest.json files across all experiments.

    Returns a list of pair dicts with:
      - pair_id, baseline_run_id, mcp_run_id, status
      - baseline_exp, variant_exp (references to matching experiment dicts)
    """
    pairs: list[dict] = []

    for exp in experiments:
        manifest_path = exp["path"] / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except Exception:
            continue

        manifest_pairs = manifest.get("pairs", [])
        manifest_runs = manifest.get("runs", [])
        if not manifest_pairs or not manifest_runs:
            continue

        # Build run_id -> experiment lookup from manifest runs
        run_id_to_mode: dict[str, str] = {}
        for run_entry in manifest_runs:
            run_id_to_mode[run_entry.get("run_id", "")] = run_entry.get(
                "mcp_mode", ""
            )

        for pair_def in manifest_pairs:
            baseline_run_id = pair_def.get("baseline_run_id", "")
            variant_run_id = pair_def.get("mcp_run_id", "")

            # Try to find matching experiments by name or subdirectory
            baseline_exp = _find_experiment_for_run(
                experiments, exp, baseline_run_id
            )
            variant_exp = _find_experiment_for_run(
                experiments, exp, variant_run_id
            )

            pairs.append(
                {
                    "pair_id": pair_def.get("pair_id", ""),
                    "baseline_run_id": baseline_run_id,
                    "variant_run_id": variant_run_id,
                    "status": pair_def.get("status", "unknown"),
                    "source_experiment": exp["name"],
                    "baseline_exp": baseline_exp,
                    "variant_exp": variant_exp,
                }
            )

    return pairs


def _find_experiment_for_run(
    experiments: list, source_exp: dict, run_id: str
) -> dict | None:
    """
    Find the experiment dict matching a run_id.

    For paired experiments (baseline/deepsearch subdirs), check modes.
    For single experiments, match by name prefix.
    """
    if not run_id:
        return None

    # If source experiment is paired, check its modes
    if source_exp.get("is_paired"):
        for mode_name, mode_data in source_exp.get("modes", {}).items():
            if run_id.endswith(f"_{mode_name}") or mode_name in run_id:
                return {
                    **source_exp,
                    "_matched_mode": mode_name,
                    "_matched_mode_data": mode_data,
                }

    # Search all experiments by name match
    for exp in experiments:
        if exp["name"] in run_id or run_id.startswith(exp["name"]):
            return exp

    return None


def _get_experiment_task_ids(exp: dict) -> set[str]:
    """
    Extract task IDs from an experiment for pairing comparison.

    Works for both paired (has modes) and single (has result.json) experiments.
    """
    task_ids: set[str] = set()
    exp_path = exp["path"]

    if exp.get("is_paired"):
        # For paired experiments, collect task names from all modes
        for mode_data in exp.get("modes", {}).values():
            for task in mode_data.get("tasks", []):
                task_ids.add(task.get("task_name", ""))
    else:
        # For single experiments, scan for task directories
        for item in exp_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                if (item / "agent").exists() or (item / "result.json").exists():
                    task_ids.add(item.name)

    task_ids.discard("")
    return task_ids


def _find_common_task_runs(
    exp_a: dict, exp_b: dict
) -> set[str]:
    """Find task IDs that are common between two experiments."""
    tasks_a = _get_experiment_task_ids(exp_a)
    tasks_b = _get_experiment_task_ids(exp_b)
    return tasks_a & tasks_b


def _group_experiments_by_benchmark(experiments: list) -> dict:
    """
    Group experiments by their detected benchmark set.

    Returns an ordered dict of benchmark_name -> list of experiments.
    Groups with no experiments are excluded.
    """
    groups: dict[str, list] = {}
    for exp in experiments:
        benchmark_name = detect_benchmark_set(exp["path"])
        if benchmark_name not in groups:
            groups[benchmark_name] = []
        groups[benchmark_name] = [*groups[benchmark_name], exp]
    return groups


def show_run_results():
    """Main run results page."""
    st.title("Run Results")

    # Load experiments from external runs directory
    external_experiments = load_external_experiments()

    if not external_experiments:
        st.info(f"No experiments found in {EXTERNAL_RUNS_DIR}")
        st.caption(
            "Set CCB_EXTERNAL_RUNS_DIR environment variable to change the runs directory."
        )
        return

    st.caption(f"Loading from: {EXTERNAL_RUNS_DIR}")

    # Group experiments by benchmark set
    benchmark_groups = _group_experiments_by_benchmark(external_experiments)

    # Benchmark set filter
    group_options = [
        f"{name} ({len(exps)})" for name, exps in benchmark_groups.items()
    ]
    all_option = f"All Benchmarks ({len(external_experiments)})"
    filter_options = [all_option] + group_options

    selected_filter = st.selectbox("Benchmark Set", filter_options)

    # Determine which experiments to show based on filter
    if selected_filter == all_option:
        filtered_experiments = external_experiments
    else:
        # Extract benchmark name from "Name (count)" format
        selected_benchmark = selected_filter.rsplit(" (", 1)[0]
        filtered_experiments = benchmark_groups.get(selected_benchmark, [])

    if not filtered_experiments:
        st.info("No experiments in this benchmark set.")
        return

    # --- Mode toggle: Individual Review vs Paired Comparison ---
    if "experiment_mode" not in st.session_state:
        st.session_state["experiment_mode"] = "Individual Review"

    experiment_mode = st.radio(
        "Selection Mode",
        ["Individual Review", "Paired Comparison"],
        horizontal=True,
        key="experiment_mode_radio",
        index=0
        if st.session_state["experiment_mode"] == "Individual Review"
        else 1,
    )
    st.session_state["experiment_mode"] = experiment_mode

    if experiment_mode == "Individual Review":
        _show_individual_mode(filtered_experiments)
    else:
        _show_paired_mode(filtered_experiments, external_experiments)


def _show_individual_mode(filtered_experiments: list) -> None:
    """Standard single-run experiment selection (existing behavior)."""
    # Experiment selector within the filtered group
    exp_options = []
    for exp in filtered_experiments:
        exp_type = "🔄 Paired" if exp.get("is_paired") else "📦 Single"
        exp_options.append(f"{exp_type} {exp['name']}")

    selected_idx = st.selectbox(
        "Select Experiment",
        range(len(exp_options)),
        format_func=lambda i: exp_options[i],
    )

    if selected_idx is None:
        return

    selected_exp = filtered_experiments[selected_idx]

    st.markdown("---")

    # Route to appropriate view based on experiment type
    if selected_exp.get("is_paired"):
        show_paired_experiment(selected_exp)
    else:
        # Display experiment overview
        show_external_run_overview(selected_exp)
        st.markdown("---")
        # Display task results
        show_external_task_results(selected_exp)


def _show_paired_mode(
    filtered_experiments: list, all_experiments: list
) -> None:
    """Paired comparison mode with baseline/variant dropdowns."""
    # Auto-detect pairs from manifest.json
    detected_pairs = _load_manifest_pairs(all_experiments)

    # --- Pre-defined pairs section ---
    if detected_pairs:
        st.subheader("Detected Pairs")
        pair_labels = []
        for pair in detected_pairs:
            label = (
                f"{pair['source_experiment']}: "
                f"{pair['baseline_run_id']} vs {pair['variant_run_id']}"
            )
            pair_labels.append(label)

        auto_pair_option = "Manual pairing"
        pair_select_options = [auto_pair_option] + pair_labels

        selected_pair_label = st.selectbox(
            "Select a detected pair or choose manual pairing",
            pair_select_options,
            key="paired_mode_pair_select",
        )

        if selected_pair_label != auto_pair_option:
            pair_idx = pair_select_options.index(selected_pair_label) - 1
            selected_pair = detected_pairs[pair_idx]

            st.info(
                f"Pair: **{selected_pair['pair_id']}** "
                f"(status: {selected_pair['status']})"
            )

            baseline_exp = selected_pair.get("baseline_exp")
            variant_exp = selected_pair.get("variant_exp")

            if baseline_exp and variant_exp:
                st.session_state["paired_baseline"] = baseline_exp
                st.session_state["paired_variant"] = variant_exp
                st.markdown("---")
                _show_paired_comparison_view(baseline_exp, variant_exp)
            else:
                st.warning(
                    "Could not resolve both experiments for this pair. "
                    "Try manual pairing below."
                )
            return

    # --- Manual pairing section ---
    st.subheader("Manual Pairing")
    st.caption(
        "Select any two runs that share common tasks for comparison."
    )

    exp_names = [exp["name"] for exp in filtered_experiments]

    col1, col2 = st.columns(2)

    with col1:
        baseline_idx = st.selectbox(
            "Baseline Run",
            range(len(exp_names)),
            format_func=lambda i: exp_names[i],
            key="paired_baseline_select",
        )

    with col2:
        # Default variant to second experiment if available
        default_variant = min(1, len(exp_names) - 1)
        variant_idx = st.selectbox(
            "Variant Run",
            range(len(exp_names)),
            format_func=lambda i: exp_names[i],
            key="paired_variant_select",
            index=default_variant,
        )

    if baseline_idx is None or variant_idx is None:
        return

    baseline_exp = filtered_experiments[baseline_idx]
    variant_exp = filtered_experiments[variant_idx]

    # Store selections in session state
    st.session_state["paired_baseline"] = baseline_exp
    st.session_state["paired_variant"] = variant_exp

    # Show common task count
    if baseline_idx == variant_idx:
        st.warning("Baseline and variant are the same experiment.")
    else:
        common_tasks = _find_common_task_runs(baseline_exp, variant_exp)
        if common_tasks:
            st.success(
                f"Found {len(common_tasks)} common tasks between "
                f"**{baseline_exp['name']}** and **{variant_exp['name']}**."
            )
        else:
            st.warning(
                "No common tasks found between the selected experiments. "
                "Comparison may be limited."
            )

    st.markdown("---")
    _show_paired_comparison_view(baseline_exp, variant_exp)


def _show_paired_comparison_view(
    baseline_exp: dict, variant_exp: dict
) -> None:
    """Display a side-by-side comparison of baseline and variant experiments."""
    st.subheader(
        f"Comparison: {baseline_exp['name']} vs {variant_exp['name']}"
    )

    # Summary metrics side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Baseline**")
        _show_experiment_summary_card(baseline_exp)

    with col2:
        st.markdown("**Variant**")
        _show_experiment_summary_card(variant_exp)

    st.markdown("---")

    # If both are paired experiments, show mode-level comparison
    if baseline_exp.get("is_paired") and variant_exp.get("is_paired"):
        _show_paired_experiment_comparison(baseline_exp, variant_exp)
    else:
        # Show individual experiment details in tabs
        tab_baseline, tab_variant = st.tabs(
            [f"Baseline: {baseline_exp['name']}", f"Variant: {variant_exp['name']}"]
        )

        with tab_baseline:
            if baseline_exp.get("is_paired"):
                show_paired_experiment(baseline_exp)
            else:
                show_external_run_overview(baseline_exp)
                st.markdown("---")
                show_external_task_results(baseline_exp)

        with tab_variant:
            if variant_exp.get("is_paired"):
                show_paired_experiment(variant_exp)
            else:
                show_external_run_overview(variant_exp)
                st.markdown("---")
                show_external_task_results(variant_exp)


def _show_experiment_summary_card(exp: dict) -> None:
    """Display a compact summary card for an experiment."""
    result = exp.get("result", {})
    stats = result.get("stats", {})

    n_trials = result.get("n_total_trials", 0)
    n_errors = stats.get("n_errors", 0)
    mean_reward = stats.get("mean_reward")

    exp_type = "Paired" if exp.get("is_paired") else "Single"

    st.markdown(f"- **Type:** {exp_type}")
    st.markdown(f"- **Tasks:** {n_trials}")
    st.markdown(f"- **Errors:** {n_errors}")
    if mean_reward is not None:
        st.markdown(f"- **Mean Reward:** {mean_reward:.4f}")
    else:
        # Try to extract from evals
        evals = stats.get("evals", {})
        if evals:
            first_eval = next(iter(evals.values()))
            metrics = first_eval.get("metrics", [{}])
            mr = metrics[0].get("mean", "N/A") if metrics else "N/A"
            st.markdown(f"- **Mean Reward:** {mr}")
        else:
            st.markdown("- **Mean Reward:** N/A")


def _show_paired_experiment_comparison(
    baseline_exp: dict, variant_exp: dict
) -> None:
    """Show comparison between two paired experiments at the mode level."""
    baseline_modes = baseline_exp.get("modes", {})
    variant_modes = variant_exp.get("modes", {})

    all_modes = sorted(set(list(baseline_modes.keys()) + list(variant_modes.keys())))

    if not all_modes:
        st.info("No mode data available for comparison.")
        return

    comparison_rows = []
    for mode_name in all_modes:
        row: dict = {"Mode": mode_name}

        for label, modes in [("Baseline", baseline_modes), ("Variant", variant_modes)]:
            mode_data = modes.get(mode_name)
            if mode_data:
                tasks = mode_data.get("tasks", [])
                rewards = [
                    t.get("reward", 0)
                    for t in tasks
                    if t.get("reward") is not None
                ]
                row[f"{label} Tasks"] = len(tasks)
                row[f"{label} Mean Reward"] = (
                    f"{sum(rewards) / len(rewards):.4f}" if rewards else "N/A"
                )
            else:
                row[f"{label} Tasks"] = 0
                row[f"{label} Mean Reward"] = "N/A"

        comparison_rows.append(row)

    st.dataframe(comparison_rows, use_container_width=True, hide_index=True)

    # Side-by-side task list for common mode
    st.markdown("---")
    st.subheader("Task Comparison")

    mode_select_options = [m for m in all_modes if m in baseline_modes and m in variant_modes]
    if mode_select_options:
        selected_mode = st.selectbox(
            "Compare tasks in mode",
            mode_select_options,
            key="paired_compare_mode_select",
        )
        if selected_mode:
            b_tasks = baseline_modes[selected_mode].get("tasks", [])
            v_tasks = variant_modes[selected_mode].get("tasks", [])
            render_task_list(
                b_tasks,
                key_prefix=f"paired_compare_{selected_mode}",
                paired_variant_tasks=v_tasks,
            )
    else:
        st.info("No common modes between baseline and variant for task comparison.")


def show_paired_experiment(exp_data):
    """Display a paired comparison experiment (baseline vs MCP)."""
    st.subheader(f"Paired Experiment: {exp_data['name']}")

    modes = exp_data.get("modes", {})

    # Summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Modes", len(modes))

    with col2:
        total_tasks = sum(len(m["tasks"]) for m in modes.values())
        st.metric("Total Tasks", total_tasks)

    with col3:
        result = exp_data.get("result", {})
        mean_reward = result.get("stats", {}).get("mean_reward", 0)
        st.metric("Overall Mean Reward", f"{mean_reward:.4f}")

    st.markdown("---")

    # Mode comparison table
    st.subheader("Mode Comparison")

    comparison_data = []
    for mode_name, mode_data in modes.items():
        tasks = mode_data["tasks"]
        rewards = [t.get("reward", 0) for t in tasks if t.get("reward") is not None]
        input_tokens = sum(t.get("input_tokens") or 0 for t in tasks)
        output_tokens = sum(t.get("output_tokens") or 0 for t in tasks)

        comparison_data.append(
            {
                "Mode": mode_name,
                "Tasks": len(tasks),
                "Mean Reward": f"{sum(rewards) / len(rewards):.4f}"
                if rewards
                else "N/A",
                "Min Reward": f"{min(rewards):.4f}" if rewards else "N/A",
                "Max Reward": f"{max(rewards):.4f}" if rewards else "N/A",
                "Input Tokens": f"{input_tokens:,}",
                "Output Tokens": f"{output_tokens:,}",
            }
        )

    st.dataframe(comparison_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Mode selector for detailed view
    mode_names = list(modes.keys())
    selected_mode = st.selectbox("Select Mode for Details", mode_names)

    if selected_mode and selected_mode in modes:
        show_paired_mode_tasks(modes[selected_mode], selected_mode)


def show_paired_mode_tasks(mode_data, mode_name):
    """Display tasks for a specific mode in a paired experiment."""
    st.subheader(f"Tasks: {mode_name}")

    tasks = mode_data["tasks"]

    if not tasks:
        st.info("No tasks found for this mode.")
        return

    selected_task_id = render_task_list(
        tasks,
        key_prefix=f"paired_{mode_name}",
    )

    if selected_task_id:
        selected_task = next(
            (t for t in tasks if t["task_name"] == selected_task_id), None
        )
        if selected_task:
            st.markdown("---")
            show_paired_task_detail(selected_task)


def show_paired_task_detail(task):
    """Display detailed view for a task in a paired experiment."""
    st.subheader(f"Task: {task['task_name']}")

    # Load full result data for additional context
    instance_dir = task.get("instance_dir")
    result_data = {}
    task_metadata = {}
    instruction_content = None

    if instance_dir:
        # Load result.json for full metadata
        result_path = instance_dir / "result.json"
        if result_path.exists():
            try:
                with open(result_path) as f:
                    result_data = json.load(f)
            except Exception:
                pass

        # Try to load instruction from benchmark task directory
        task_id_info = result_data.get("task_id", {})
        if isinstance(task_id_info, dict):
            task_path = task_id_info.get("path", "")
            if task_path:
                instruction_file = Path(task_path) / "instruction.md"
                if instruction_file.exists():
                    try:
                        instruction_content = instruction_file.read_text()
                    except Exception:
                        pass
                # Also try task.toml for metadata
                task_toml_file = Path(task_path) / "task.toml"
                if task_toml_file.exists():
                    try:
                        import toml

                        task_metadata = toml.load(task_toml_file)
                    except Exception:
                        pass

    # Task Information Section
    with st.expander("📋 Task Information", expanded=True):
        # Extract repository name from task metadata or task_id
        repo_name = "Unknown"
        if task_metadata.get("task", {}).get("repo"):
            repo_name = task_metadata["task"]["repo"]
        elif "task_id" in result_data:
            task_id_info = result_data.get("task_id", {})
            if isinstance(task_id_info, dict):
                task_path = task_id_info.get("path", "")
                # Extract repo from path like "instance_ansible__ansible-xxx"
                if "instance_" in task_path:
                    parts = task_path.split("/")[-1].replace("instance_", "").split("-")
                    if len(parts) >= 2:
                        repo_name = parts[0].replace("__", "/").replace("_", "-")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Repository:** `{repo_name}`")
            st.markdown(f"**Task ID:** `{task['task_name']}`")
            if task_metadata.get("metadata", {}).get("difficulty"):
                st.markdown(
                    f"**Difficulty:** {task_metadata['metadata']['difficulty']}"
                )
            if task_metadata.get("metadata", {}).get("category"):
                st.markdown(f"**Category:** {task_metadata['metadata']['category']}")

        with col2:
            # Agent/Model info
            agent_info = result_data.get("agent_info", {})
            if agent_info:
                st.markdown(f"**Agent:** {agent_info.get('name', 'Unknown')}")
                model_info = agent_info.get("model_info", {})
                if model_info:
                    st.markdown(f"**Model:** {model_info.get('name', 'Unknown')}")

            # Config info
            config = result_data.get("config", {})
            if config.get("agent", {}).get("model_name"):
                st.markdown(f"**Model:** {config['agent']['model_name']}")

        # Instruction
        if instruction_content:
            st.markdown("---")
            st.markdown("**Instruction:**")
            # Show first 2000 chars with option to expand
            if len(instruction_content) > 2000:
                st.markdown(instruction_content[:2000] + "...")
                with st.expander("Show full instruction"):
                    st.markdown(instruction_content)
            else:
                st.markdown(instruction_content)

    # Timing/Metrics Section
    with st.expander("⏱️ Execution Metrics", expanded=True):
        # Calculate timing metrics
        timing = {}
        if result_data:
            for timing_key in [
                "environment_setup",
                "agent_setup",
                "agent_execution",
                "verifier",
            ]:
                timing_data = result_data.get(timing_key, {})
                if (
                    timing_data
                    and timing_data.get("started_at")
                    and timing_data.get("finished_at")
                ):
                    try:
                        start = datetime.fromisoformat(
                            timing_data["started_at"].replace("Z", "+00:00")
                        )
                        end = datetime.fromisoformat(
                            timing_data["finished_at"].replace("Z", "+00:00")
                        )
                        timing[timing_key] = (end - start).total_seconds()
                    except Exception:
                        pass

        # Overall timing
        if result_data.get("started_at") and result_data.get("finished_at"):
            try:
                start = datetime.fromisoformat(
                    result_data["started_at"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    result_data["finished_at"].replace("Z", "+00:00")
                )
                timing["total"] = (end - start).total_seconds()
            except Exception:
                pass

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            reward = task.get("reward") or 0
            st.metric("Reward", f"{reward:.4f}")

        with col2:
            st.metric("Status", task.get("status") or "unknown")

        with col3:
            total_time = timing.get("total", 0)
            st.metric("Total Time", f"{total_time:.1f}s" if total_time else "N/A")

        with col4:
            agent_time = timing.get("agent_execution", 0)
            st.metric("Agent Time", f"{agent_time:.1f}s" if agent_time else "N/A")

        with col5:
            verifier_time = timing.get("verifier", 0)
            st.metric(
                "Verifier Time", f"{verifier_time:.1f}s" if verifier_time else "N/A"
            )

        # Token metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            input_tokens = task.get("input_tokens") or 0
            st.metric("Input Tokens", f"{input_tokens:,}")

        with col2:
            output_tokens = task.get("output_tokens") or 0
            st.metric("Output Tokens", f"{output_tokens:,}")

        with col3:
            env_setup_time = timing.get("environment_setup", 0)
            st.metric(
                "Env Setup", f"{env_setup_time:.1f}s" if env_setup_time else "N/A"
            )

        with col4:
            agent_setup_time = timing.get("agent_setup", 0)
            st.metric(
                "Agent Setup", f"{agent_setup_time:.1f}s" if agent_setup_time else "N/A"
            )

    st.markdown("---")

    # Tabs for different views
    tabs = st.tabs(["Agent Trace", "Code Diffs", "Result Details", "LLM Judge Context"])

    instance_dir = task.get("instance_dir")

    with tabs[0]:
        if instance_dir:
            claude_file = instance_dir / "agent" / "claude-code.txt"
            trajectory_file = instance_dir / "agent" / "trajectory.json"

            if claude_file.exists():
                show_claude_code_trace(claude_file)
            elif trajectory_file.exists():
                show_agent_trace([], [trajectory_file])
            else:
                st.info("No trace file found.")
        else:
            st.info("No instance directory.")

    with tabs[1]:
        # Comprehensive code diffs tab
        show_comprehensive_diffs(instance_dir)

    with tabs[2]:
        result_path = task.get("result_path")
        if result_path and Path(result_path).exists():
            try:
                with open(result_path) as f:
                    result_json = json.load(f)
                st.json(result_json)
            except Exception as e:
                st.error(f"Failed to load result: {e}")
        elif result_data:
            st.json(result_data)
        else:
            st.info("No result file found.")

    with tabs[3]:
        # LLM Judge Context - all data needed for evaluation
        show_llm_judge_context(
            task, instance_dir, result_data, instruction_content, task_metadata
        )


def show_external_run_overview(exp_data):
    """Display overview for external experiment."""
    st.subheader("Experiment Overview")

    result = exp_data["result"]
    config = exp_data["config"]

    stats = result.get("stats", {})
    evals = stats.get("evals", {})

    # Extract benchmark/dataset info from config
    datasets = config.get("datasets", [])
    benchmark_name = "Unknown"
    benchmark_version = ""
    if datasets:
        first_dataset = datasets[0]
        benchmark_name = first_dataset.get("name", "Unknown")
        benchmark_version = first_dataset.get("version", "")

    # Extract agent info
    agent_name = "Unknown"
    if evals:
        agent_name = list(evals.keys())[0].split("__")[0]
    elif config.get("agents"):
        agent_name = config["agents"][0].get("name", "Unknown")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Trials", result.get("n_total_trials", 0))

    with col2:
        n_errors = stats.get("n_errors", 0)
        st.metric("Errors", n_errors)

    with col3:
        # Calculate success rate from evals
        if evals:
            first_eval = next(iter(evals.values()))
            metrics = first_eval.get("metrics", [{}])
            mean_reward = metrics[0].get("mean", 0) if metrics else 0
            st.metric("Mean Reward", f"{mean_reward:.2f}")
        else:
            st.metric("Mean Reward", "N/A")

    with col4:
        st.metric("Agent", agent_name)

    with col5:
        benchmark_display = (
            f"{benchmark_name}@{benchmark_version}"
            if benchmark_version
            else benchmark_name
        )
        st.metric("Benchmark", benchmark_display)

    # Timing info
    if result.get("started_at"):
        st.write(f"**Started:** {result['started_at'][:19]}")
    if result.get("finished_at"):
        st.write(f"**Finished:** {result['finished_at'][:19]}")

    # Config details
    if config:
        with st.expander("Configuration"):
            st.json(config)


def show_external_task_results(exp_data):
    """Display task results for external experiment."""
    st.subheader("Task Results")

    tasks = load_external_tasks(exp_data["path"], exp_data["result"])

    if not tasks:
        st.info("No task instances found.")
        return

    selected_task_id = render_task_list(
        tasks,
        key_prefix=f"ext_{exp_data['name']}",
    )

    if selected_task_id:
        task_detail = next(
            (t for t in tasks if t["task_name"] == selected_task_id), None
        )
        if task_detail:
            st.markdown("---")
            show_external_task_detail(exp_data, task_detail)


def show_external_task_detail(exp_data, task):
    """Display detailed task results for external experiment."""
    st.subheader(f"Task: {task['task_name']}")

    # Metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Result", task.get("reward", "N/A"))

    with col2:
        st.metric("Status", task["status"])

    with col3:
        st.metric(
            "Agent",
            task["agent_name"].split("__")[0]
            if "__" in task["agent_name"]
            else task["agent_name"],
        )

    st.markdown("---")

    # Tabs for different views
    tabs = st.tabs(["Agent Trace", "Result Details"])

    with tabs[0]:
        if task.get("claude_file"):
            show_claude_code_trace(task["claude_file"])
        elif task.get("trajectory_file"):
            show_agent_trace([], [task["trajectory_file"]])
        else:
            st.info("No trace file found.")

    with tabs[1]:
        if task.get("result_path"):
            try:
                with open(task["result_path"]) as f:
                    result_data = json.load(f)
                st.json(result_data)
            except Exception as e:
                st.error(f"Failed to load result: {e}")
        else:
            st.info("No result file found.")


# Keep original database-backed functions below for compatibility
def show_run_results_database():
    """Original database-backed run results page (kept for reference)."""
    st.title("Run Results (Database)")

    # Get all runs
    runs = RunManager.list_all()

    if not runs:
        st.info(
            "No evaluation runs found. Use 'Evaluation Runner' to start a new evaluation."
        )
        return

    # Run selector
    run_options = [
        f"{r['run_id']} - {r.get('benchmark_name', 'Unknown')} ({r.get('status', 'unknown')})"
        for r in runs
    ]
    run_ids = [r["run_id"] for r in runs]

    selected_index = st.selectbox(
        "Select Run", range(len(run_options)), format_func=lambda i: run_options[i]
    )

    if selected_index is None:
        return

    selected_run_id = run_ids[selected_index]
    run_data = RunManager.get(selected_run_id)

    if not run_data:
        st.error("Run not found")
        return

    st.markdown("---")

    # Display run overview
    show_run_overview(run_data)

    st.markdown("---")

    # Display task results
    show_task_results(run_data)


def show_run_overview(run_data):
    """Display run overview with metrics."""
    st.subheader("Run Overview")

    # Get task counts
    tasks = TaskManager.get_tasks(run_data["run_id"])
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t["status"] == "completed"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_label = run_data.get("status", "unknown").capitalize()
        st.metric("Status", status_label)

    with col2:
        st.metric("Tasks", f"{completed_tasks}/{total_tasks}")

    with col3:
        benchmark_name = run_data.get("benchmark_name", "Unknown")
        st.metric("Benchmark", benchmark_name)

    with col4:
        agents = run_data.get("agents", [])
        agent_display = agents[0].split(":")[-1] if agents else "Unknown"
        st.metric("Agent", agent_display)

    # MCP configuration
    config = run_data.get("config", {})
    mcp_type = config.get("env", {}).get("BASELINE_MCP_TYPE", "none")
    st.write(f"**MCP Configuration:** {mcp_type}")

    # Timing
    if run_data.get("created_at"):
        st.write(f"**Created:** {run_data['created_at'][:19]}")
    if run_data.get("completed_at"):
        st.write(f"**Completed:** {run_data['completed_at'][:19]}")


def show_task_results(run_data):
    """Display task-level results."""
    st.subheader("Task Results")

    # Get task results
    tasks = TaskManager.get_tasks(run_data["run_id"])

    if not tasks:
        st.info("No task results found.")
        return

    # Create summary table
    task_data = []
    for task in tasks:
        task_data.append(
            {
                "Task": task["task_name"],
                "Agent": task["agent_name"].split(":")[-1],
                "Status": task["status"],
                "Reward": task.get("reward", "N/A"),
                "Tokens": task.get("total_tokens", "N/A"),
                "Time (s)": f"{task.get('execution_time', 0):.1f}"
                if task.get("execution_time")
                else "N/A",
            }
        )

    st.dataframe(task_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Task detail selector
    task_names = [t["task_name"] for t in tasks]
    selected_task = st.selectbox("View Task Details", task_names)

    if selected_task:
        task_detail = next((t for t in tasks if t["task_name"] == selected_task), None)
        if task_detail:
            show_task_detail(run_data, task_detail)


def show_task_detail(run_data, task):
    """Display detailed task results with trace."""
    st.subheader(f"Task: {task['task_name']}")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Result", task.get("reward", "N/A"))

    with col2:
        st.metric("Tokens", task.get("total_tokens", "N/A"))

    with col3:
        time_val = task.get("execution_time", 0)
        st.metric("Time", f"{time_val:.1f}s" if time_val else "N/A")

    with col4:
        st.metric("Status", task["status"])

    st.markdown("---")

    # Try to find task output files
    # First check if paths are stored in the database (e.g., from SWEBench imports)
    result_path = task.get("result_path")
    trajectory_path = task.get("trajectory_path")

    result_files = []
    trajectory_files = []
    claude_files = []
    task_output_dir = None

    if result_path and Path(result_path).exists():
        result_files = [Path(result_path)]
        # Derive task output dir from result path (parent of result.json)
        task_output_dir = Path(result_path).parent

    if trajectory_path and Path(trajectory_path).exists():
        traj_path = Path(trajectory_path)
        # trajectory_path might be claude-code.txt (SWEBench) or trajectory.json (Harbor)
        if traj_path.suffix == ".txt":
            claude_files = [traj_path]
        else:
            trajectory_files = [traj_path]
        # Set task_output_dir if not already set
        if task_output_dir is None:
            task_output_dir = traj_path.parent

    # Fallback to constructed path if no stored paths
    if not result_files and not trajectory_files and not claude_files:
        output_dir = Path(run_data.get("output_dir", f"runs/{run_data['run_id']}"))
        # Sanitize agent name same way as orchestrator (replace : with __, / with _)
        safe_agent_name = task["agent_name"].replace(":", "__").replace("/", "_")
        task_output_dir = output_dir / f"{task['task_name']}_{safe_agent_name}"

        if not task_output_dir.exists():
            st.warning(f"Task output directory not found: {task_output_dir}")
            st.info(
                "This may be an imported evaluation. Check if the source files exist."
            )
            return

        # Look for trajectory and result files
        trajectory_files = list(task_output_dir.rglob("trajectory.json"))
        result_files = list(task_output_dir.rglob("result.json"))
        claude_files = list(task_output_dir.rglob("claude.txt"))

    # Tabs for different views
    tabs = st.tabs(
        ["Agent Trace", "Result Details", "Checklist", "LLM Judge", "Task Report"]
    )

    with tabs[0]:
        show_agent_trace(claude_files, trajectory_files)

    with tabs[1]:
        show_result_details(result_files)

    with tabs[2]:
        show_checklist_section(run_data, task, task_output_dir)

    with tabs[3]:
        show_llm_judge_section(run_data, task, task_output_dir)

    with tabs[4]:
        show_task_report_section(
            run_data, task, task_output_dir, trajectory_files, result_files
        )


def show_agent_trace(claude_files, trajectory_files):
    """Display agent execution trace."""
    st.subheader("Agent Trace")

    # Handle SWEBench JSONL format (claude-code.txt)
    if claude_files and not trajectory_files:
        show_claude_code_trace(claude_files[0])
        return

    # Handle Harbor trajectory.json format
    if not trajectory_files:
        st.info("No trajectory file found.")
        return

    trajectory_file = trajectory_files[0]

    try:
        # Parse trajectory
        steps = TraceParser.parse_trajectory_file(trajectory_file)

        # Filter options
        include_sidechain = st.checkbox("Include sidechain steps", value=False)
        filtered_steps = TraceParser.filter_sidechain(steps, include_sidechain)

        # Execution Summary
        with st.expander("Execution Summary", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Token Usage:**")
                token_summary = TraceParser.get_token_summary(steps)
                st.write(f"- Total: {token_summary['total']:,}")
                st.write(f"- Prompt: {token_summary['total_prompt']:,}")
                st.write(f"- Completion: {token_summary['total_completion']:,}")
                st.write(f"- Cached: {token_summary['total_cached']:,}")

            with col2:
                st.write("**Tool Usage:**")
                tool_summary = TraceParser.get_tool_usage_summary(steps)
                for tool_name, count in sorted(
                    tool_summary.items(), key=lambda x: x[1], reverse=True
                ):
                    st.write(f"- {tool_name}: {count}")

        st.markdown("---")

        # Show redesigned conversation view
        show_conversation_view(filtered_steps)

        # Separate sections for aggregated views
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Full Conversation", "Tool Calls", "Code Diffs", "Test Results"]
        )

        with tab1:
            show_full_conversation(filtered_steps)

        with tab2:
            show_all_tool_calls(filtered_steps)

        with tab3:
            show_all_diffs(filtered_steps)

        with tab4:
            show_test_results(trajectory_file)

        # Raw trajectory option
        with st.expander("Raw Trajectory (JSON)", expanded=False):
            with open(trajectory_file) as f:
                trajectory = json.load(f)
            st.json(trajectory)

    except Exception as e:
        st.error(f"Failed to parse trajectory: {e}")
        import traceback

        st.code(traceback.format_exc())


def show_claude_code_trace(claude_file: Path):
    """Display agent trace from SWEBench claude-code.txt JSONL format."""

    # Parse the JSONL transcript
    messages = []
    tool_calls = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read = 0
    model = None
    files_read = []
    edits_made = []
    bash_commands = []

    try:
        with open(claude_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = record.get("type")

                if msg_type == "assistant":
                    message = record.get("message", {})

                    # Extract model
                    if not model:
                        model = message.get("model")

                    # Extract tokens
                    usage = message.get("usage", {})
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    total_cache_read += usage.get("cache_read_input_tokens", 0)

                    # Extract content
                    content = message.get("content", [])
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get("type")

                            if item_type == "text":
                                text = item.get("text", "")
                                if text.strip():
                                    messages.append(
                                        {
                                            "type": "assistant_text",
                                            "content": text,
                                            "line": line_num,
                                        }
                                    )

                            elif item_type == "tool_use":
                                tool_name = item.get("name", "unknown")
                                tool_input = item.get("input", {})
                                tool_id = item.get("id", "")

                                tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1

                                messages.append(
                                    {
                                        "type": "tool_call",
                                        "tool_name": tool_name,
                                        "tool_input": tool_input,
                                        "tool_id": tool_id,
                                        "line": line_num,
                                    }
                                )

                                # Track specific tools
                                if tool_name == "Read":
                                    file_path = tool_input.get("file_path", "")
                                    if file_path:
                                        files_read.append(file_path)

                                elif tool_name == "Edit":
                                    edits_made.append(
                                        {
                                            "file": tool_input.get("file_path", ""),
                                            "old": tool_input.get("old_string", "")[
                                                :200
                                            ],
                                            "new": tool_input.get("new_string", "")[
                                                :200
                                            ],
                                        }
                                    )

                                elif tool_name == "Bash":
                                    cmd = tool_input.get("command", "")
                                    if cmd:
                                        bash_commands.append(cmd)

                elif msg_type == "user":
                    message = record.get("message", {})
                    content = message.get("content", [])
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "tool_result":
                            tool_id = item.get("tool_use_id", "")
                            result_content = item.get("content", "")
                            if isinstance(result_content, str):
                                messages.append(
                                    {
                                        "type": "tool_result",
                                        "tool_id": tool_id,
                                        "content": result_content[:500]
                                        if len(result_content) > 500
                                        else result_content,
                                        "truncated": len(result_content) > 500,
                                        "line": line_num,
                                    }
                                )

        # Display Summary
        with st.expander("📊 Execution Summary", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Token Usage**")
                st.write(f"- Input: {total_input_tokens:,}")
                st.write(f"- Output: {total_output_tokens:,}")
                st.write(f"- Cache Read: {total_cache_read:,}")
                st.write(f"- **Total: {total_input_tokens + total_output_tokens:,}**")

            with col2:
                st.markdown("**Tool Usage**")
                for tool_name, count in sorted(tool_calls.items(), key=lambda x: -x[1])[
                    :10
                ]:
                    st.write(f"- {tool_name}: {count}")

            with col3:
                st.markdown("**Activity**")
                st.write(f"- Files Read: {len(files_read)}")
                st.write(f"- Edits Made: {len(edits_made)}")
                st.write(f"- Bash Commands: {len(bash_commands)}")
                if model:
                    st.write(f"- Model: {model}")

        st.markdown("---")

        # Tabs for different views
        tabs = st.tabs(
            [
                "💬 Conversation",
                "🔧 Tool Calls",
                "📝 Code Changes",
                "🖥️ Bash Commands",
                "📄 Raw",
            ]
        )

        with tabs[0]:
            show_claude_conversation(messages)

        with tabs[1]:
            show_claude_tool_calls(messages, tool_calls)

        with tabs[2]:
            show_claude_edits(edits_made)

        with tabs[3]:
            show_claude_bash(bash_commands)

        with tabs[4]:
            with st.expander("Raw JSONL (first 50 lines)", expanded=False):
                with open(claude_file) as f:
                    lines = f.readlines()[:50]
                st.code("".join(lines), language="json")

    except Exception as e:
        st.error(f"Failed to parse claude-code.txt: {e}")
        import traceback

        st.code(traceback.format_exc())


def show_claude_conversation(messages):
    """Display conversation from claude-code.txt."""
    st.markdown("### Agent Conversation")

    for msg in messages:
        msg_type = msg.get("type")

        if msg_type == "assistant_text":
            with st.chat_message("assistant"):
                st.markdown(msg["content"][:2000])
                if len(msg["content"]) > 2000:
                    st.caption("...(truncated)")

        elif msg_type == "tool_call":
            tool_name = msg["tool_name"]
            with st.expander(f"🔧 Tool: **{tool_name}**", expanded=False):
                st.json(msg["tool_input"])

        elif msg_type == "tool_result":
            with st.expander(f"📤 Tool Result", expanded=False):
                content = msg["content"]
                if msg.get("truncated"):
                    st.code(content + "\n...(truncated)")
                else:
                    st.code(content)


def show_claude_tool_calls(messages, tool_calls):
    """Display tool call summary from claude-code.txt."""
    st.markdown("### Tool Call Summary")

    # Summary chart
    if tool_calls:
        import pandas as pd

        df = pd.DataFrame(
            [
                {"Tool": k, "Calls": v}
                for k, v in sorted(tool_calls.items(), key=lambda x: -x[1])
            ]
        )
        st.bar_chart(df.set_index("Tool"))

    st.markdown("### Tool Call Details")

    tool_messages = [m for m in messages if m.get("type") == "tool_call"]

    for i, msg in enumerate(tool_messages, 1):
        tool_name = msg["tool_name"]
        with st.expander(f"{i}. {tool_name}", expanded=False):
            st.json(msg["tool_input"])


def show_claude_edits(edits_made):
    """Display code edits from claude-code.txt."""
    st.markdown("### Code Changes")

    if not edits_made:
        st.info("No code edits found in this trace.")
        return

    for i, edit in enumerate(edits_made, 1):
        with st.expander(f"Edit {i}: `{edit['file']}`", expanded=i == 1):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Before:**")
                st.code(edit["old"] if edit["old"] else "(empty)", language="python")
            with col2:
                st.markdown("**After:**")
                st.code(edit["new"] if edit["new"] else "(empty)", language="python")


def show_claude_bash(bash_commands):
    """Display bash commands from claude-code.txt."""
    st.markdown("### Bash Commands")

    if not bash_commands:
        st.info("No bash commands found in this trace.")
        return

    for i, cmd in enumerate(bash_commands, 1):
        st.code(f"$ {cmd}", language="bash")


def show_comprehensive_diffs(instance_dir):
    """Display comprehensive code diffs from the agent trace."""
    st.markdown("### Code Changes")

    if not instance_dir:
        st.info("No instance directory available.")
        return

    # Try to find trace files
    claude_file = instance_dir / "agent" / "claude-code.txt"
    trajectory_file = instance_dir / "agent" / "trajectory.json"

    all_diffs = []
    files_modified = set()

    # Define patterns for non-code output files (analysis tasks write to these)
    OUTPUT_FILE_PATTERNS = [
        "/logs/",
        "/solution.md",
        "/report.md",
        "/answer.md",
        "/response.md",
        "/output/",
        "/.solution",
        "/SOLUTION",
        "/answer.txt",
    ]

    def is_output_file(path: str) -> bool:
        """Check if file is an analysis output file rather than source code."""
        return any(pattern in path for pattern in OUTPUT_FILE_PATTERNS)

    if claude_file.exists():
        # Parse JSONL format for diffs
        try:
            with open(claude_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("type") == "assistant":
                            content = record.get("message", {}).get("content", [])
                            for item in content:
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "tool_use"
                                ):
                                    tool_name = item.get("name", "")
                                    tool_input = item.get("input", {})

                                    if tool_name == "Edit":
                                        file_path = tool_input.get("file_path", "")
                                        old_string = tool_input.get("old_string", "")
                                        new_string = tool_input.get("new_string", "")
                                        if file_path:
                                            files_modified.add(file_path)
                                            all_diffs.append(
                                                {
                                                    "type": "edit",
                                                    "file_path": file_path,
                                                    "old_string": old_string,
                                                    "new_string": new_string,
                                                }
                                            )

                                    elif tool_name == "Write":
                                        file_path = tool_input.get("file_path", "")
                                        content_str = tool_input.get("content", "")
                                        if file_path:
                                            files_modified.add(file_path)
                                            all_diffs.append(
                                                {
                                                    "type": "write",
                                                    "file_path": file_path,
                                                    "content": content_str,
                                                }
                                            )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            st.error(f"Failed to parse trace: {e}")

    elif trajectory_file.exists():
        # Parse Harbor trajectory format
        try:
            steps = TraceParser.parse_trajectory_file(trajectory_file)
            for step in steps:
                diffs = TraceParser.extract_diffs(step.tool_calls)
                for diff in diffs:
                    all_diffs.append(diff)
                    if diff.get("file_path"):
                        files_modified.add(diff["file_path"])
        except Exception as e:
            st.error(f"Failed to parse trajectory: {e}")
    else:
        st.info("No trace file found.")
        return

    if not all_diffs:
        st.info("No code changes found in this trace.")
        return

    # Separate code changes from output files
    code_diffs = []
    output_diffs = []
    code_files = set()
    output_files = set()

    for diff in all_diffs:
        file_path = diff.get("file_path", "unknown")
        if is_output_file(file_path):
            output_diffs.append(diff)
            output_files.add(file_path)
        else:
            code_diffs.append(diff)
            code_files.add(file_path)

    # Determine task type based on changes
    if code_diffs and not output_diffs:
        task_type = "Code Modification"
        st.success("📝 **Task Type:** Code Modification (agent edited source files)")
    elif output_diffs and not code_diffs:
        task_type = "Analysis/Understanding"
        st.info(
            "📊 **Task Type:** Analysis/Understanding (agent wrote analysis report)"
        )
    elif code_diffs and output_diffs:
        task_type = "Mixed"
        st.warning("🔄 **Task Type:** Mixed (both code changes and analysis output)")
    else:
        task_type = "Unknown"

    # Summary
    st.markdown(
        f"**Total Changes:** {len(all_diffs)} | "
        f"**Code Files:** {len(code_files)} | "
        f"**Output Files:** {len(output_files)}"
    )

    # List of modified files grouped by type
    if code_files:
        with st.expander(f"📁 Source Code Files ({len(code_files)})", expanded=False):
            for f in sorted(code_files):
                st.markdown(f"- `{f}`")

    if output_files:
        with st.expander(
            f"📄 Analysis Output Files ({len(output_files)})", expanded=False
        ):
            for f in sorted(output_files):
                st.markdown(f"- `{f}`")

    st.markdown("---")

    # Group diffs by file
    diffs_by_file = {}
    for diff in all_diffs:
        file_path = diff.get("file_path", "unknown")
        if file_path not in diffs_by_file:
            diffs_by_file[file_path] = []
        diffs_by_file[file_path].append(diff)

    # Display CODE changes first (more important for evaluation)
    if code_diffs:
        st.markdown("### 🔧 Source Code Changes")
        for file_path in sorted(code_files):
            file_diffs = diffs_by_file.get(file_path, [])
            with st.expander(
                f"📄 `{file_path}` ({len(file_diffs)} changes)", expanded=True
            ):
                for i, diff in enumerate(file_diffs, 1):
                    if diff["type"] == "edit":
                        st.markdown(f"**Edit {i}:**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Before:**")
                            old_str = diff.get("old_string", "")
                            lang = _get_language_from_path(file_path)
                            st.code(old_str if old_str else "(empty)", language=lang)
                        with col2:
                            st.markdown("**After:**")
                            new_str = diff.get("new_string", "")
                            st.code(new_str if new_str else "(empty)", language=lang)

                    elif diff["type"] == "write":
                        st.markdown(f"**Write {i}:** (new file)")
                        content = diff.get("content", "")
                        lang = _get_language_from_path(file_path)
                        if len(content) > 3000:
                            st.code(content[:3000] + "\n... (truncated)", language=lang)
                            with st.expander("Show full content"):
                                st.code(content, language=lang)
                        else:
                            st.code(content, language=lang)

                    if i < len(file_diffs):
                        st.markdown("---")

    # Display OUTPUT files second (analysis reports)
    if output_diffs:
        st.markdown("### 📊 Analysis Output")
        for file_path in sorted(output_files):
            file_diffs = diffs_by_file.get(file_path, [])
            with st.expander(
                f"📄 `{file_path}` ({len(file_diffs)} changes)", expanded=not code_diffs
            ):
                for i, diff in enumerate(file_diffs, 1):
                    if diff["type"] == "edit":
                        st.markdown(f"**Edit {i}:**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Before:**")
                            old_str = diff.get("old_string", "")
                            lang = _get_language_from_path(file_path)
                            st.code(old_str if old_str else "(empty)", language=lang)
                        with col2:
                            st.markdown("**After:**")
                            new_str = diff.get("new_string", "")
                            st.code(new_str if new_str else "(empty)", language=lang)

                    elif diff["type"] == "write":
                        st.markdown(f"**Write {i}:** (new file)")
                        content = diff.get("content", "")
                        lang = _get_language_from_path(file_path)
                        if len(content) > 3000:
                            st.code(content[:3000] + "\n... (truncated)", language=lang)
                            with st.expander("Show full content"):
                                st.code(content, language=lang)
                        else:
                            st.code(content, language=lang)

                    if i < len(file_diffs):
                        st.markdown("---")


def _get_language_from_path(file_path: str) -> str:
    """Get code language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".sh": "bash",
        ".bash": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".xml": "xml",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".md": "markdown",
    }

    for ext, lang in ext_map.items():
        if file_path.lower().endswith(ext):
            return lang
    return "text"


def load_locobench_oracle(task_name: str) -> dict:
    """Load oracle/ground truth data for a LoCoBench task."""
    oracle_data = {
        "ground_truth": None,
        "expected_approach": None,
        "evaluation_criteria": None,
        "context_files": None,
        "task_prompt": None,
    }

    # Try to find the scenario file
    scenarios_dir = (
        Path(__file__).parent.parent.parent
        / "benchmarks"
        / "locobench_agent"
        / "data"
        / "output"
        / "agent_scenarios"
    )

    # Task name might have truncation, try to find matching file
    if scenarios_dir.exists():
        # Try exact match first
        scenario_file = scenarios_dir / f"{task_name}.json"

        if not scenario_file.exists():
            # Try prefix match (task names are often truncated)
            for f in scenarios_dir.glob("*.json"):
                if task_name.startswith(f.stem[:30]) or f.stem.startswith(
                    task_name[:30]
                ):
                    scenario_file = f
                    break

        if scenario_file.exists():
            try:
                with open(scenario_file) as f:
                    scenario = json.load(f)

                orig = scenario.get("original_scenario", {})
                oracle_data["ground_truth"] = orig.get("ground_truth")
                oracle_data["expected_approach"] = orig.get("expected_approach")
                oracle_data["evaluation_criteria"] = orig.get("evaluation_criteria")
                oracle_data["context_files"] = orig.get(
                    "context_files", scenario.get("context_files")
                )
                oracle_data["task_prompt"] = orig.get("task_prompt")
                oracle_data["title"] = orig.get("title", scenario.get("title"))
                oracle_data["difficulty"] = orig.get(
                    "difficulty", scenario.get("difficulty")
                )
                oracle_data["task_category"] = orig.get(
                    "task_category", scenario.get("category")
                )
            except Exception:
                pass

    return oracle_data


def analyze_mcp_tool_usage(tool_counts: dict, trace_content: str = "") -> dict:
    """Analyze MCP and Sourcegraph tool usage patterns."""
    analysis = {
        "mcp_tools_used": [],
        "sourcegraph_tools_used": [],
        "search_patterns": {
            "used_deep_search": False,
            "used_keyword_search": False,
            "used_file_read": False,
            "search_queries": [],
        },
        "recommendations": [],
        "effectiveness_score": 0.0,
    }

    # Identify MCP tools
    mcp_prefixes = ["mcp__", "mcp_"]
    sourcegraph_patterns = ["sourcegraph", "sg_", "deepsearch", "deep_search"]

    for tool_name, count in tool_counts.items():
        tool_lower = tool_name.lower()

        # Check for MCP tools
        if any(tool_lower.startswith(p) for p in mcp_prefixes):
            analysis["mcp_tools_used"].append({"tool": tool_name, "count": count})

            # Check for Sourcegraph specifically
            if any(sg in tool_lower for sg in sourcegraph_patterns):
                analysis["sourcegraph_tools_used"].append(
                    {"tool": tool_name, "count": count}
                )

                if "deepsearch" in tool_lower or "deep_search" in tool_lower:
                    analysis["search_patterns"]["used_deep_search"] = True
                elif "keyword" in tool_lower:
                    analysis["search_patterns"]["used_keyword_search"] = True
                elif "read" in tool_lower:
                    analysis["search_patterns"]["used_file_read"] = True

    # Generate recommendations
    if not analysis["sourcegraph_tools_used"]:
        analysis["recommendations"].append(
            "🔴 **No Sourcegraph MCP tools used.** The agent should use `mcp__sourcegraph__sg_deepsearch` "
            "for semantic code search to better understand the codebase architecture."
        )
    elif not analysis["search_patterns"]["used_deep_search"]:
        analysis["recommendations"].append(
            "🟡 **Deep Search not used.** Consider using `mcp__sourcegraph__sg_deepsearch` for "
            "complex architectural questions that require understanding relationships between components."
        )

    if analysis["search_patterns"]["used_deep_search"]:
        analysis["recommendations"].append(
            "✅ **Good:** Used Deep Search for semantic code understanding."
        )

    # Check for over-reliance on basic tools
    basic_tools = (
        tool_counts.get("Read", 0)
        + tool_counts.get("Grep", 0)
        + tool_counts.get("Glob", 0)
    )
    mcp_search_tools = sum(t["count"] for t in analysis["sourcegraph_tools_used"])

    if basic_tools > 20 and mcp_search_tools < 3:
        analysis["recommendations"].append(
            "🟡 **Heavy use of basic Read/Grep/Glob.** For large codebases, Sourcegraph's semantic "
            "search can find relevant code more efficiently than manual file traversal."
        )

    # Calculate effectiveness score (0-1)
    score = 0.0
    if analysis["search_patterns"]["used_deep_search"]:
        score += 0.4
    if analysis["search_patterns"]["used_keyword_search"]:
        score += 0.2
    if analysis["search_patterns"]["used_file_read"]:
        score += 0.1
    if len(analysis["sourcegraph_tools_used"]) >= 3:
        score += 0.3

    analysis["effectiveness_score"] = min(score, 1.0)

    return analysis


def show_llm_judge_context(
    task, instance_dir, result_data, instruction_content, task_metadata
):
    """Display all context needed for LLM evaluation with oracle data."""
    st.markdown("### LLM Evaluator Context")
    st.caption("Enhanced evaluation with oracle data and MCP tool usage analysis.")

    # Structured context for evaluation
    eval_context = {
        "task_info": {
            "task_name": task.get("task_name"),
            "repository": task_metadata.get("task", {}).get("repo", "Unknown"),
            "difficulty": task_metadata.get("metadata", {}).get(
                "difficulty", "Unknown"
            ),
            "category": task_metadata.get("metadata", {}).get("category", "Unknown"),
        },
        "instruction": instruction_content or "No instruction available",
        "result": {
            "reward": task.get("reward"),
            "status": task.get("status"),
            "input_tokens": task.get("input_tokens"),
            "output_tokens": task.get("output_tokens"),
        },
        "timing": {},
        "code_changes": [],
        "tool_usage": {},
        "agent_trace_summary": "",
    }

    # Extract timing from result_data
    if result_data:
        for timing_key in [
            "environment_setup",
            "agent_setup",
            "agent_execution",
            "verifier",
        ]:
            timing_data = result_data.get(timing_key, {})
            if (
                timing_data
                and timing_data.get("started_at")
                and timing_data.get("finished_at")
            ):
                try:
                    start = datetime.fromisoformat(
                        timing_data["started_at"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(
                        timing_data["finished_at"].replace("Z", "+00:00")
                    )
                    eval_context["timing"][timing_key] = (end - start).total_seconds()
                except Exception:
                    pass

    # Extract code changes and tool usage from trace
    if instance_dir:
        claude_file = instance_dir / "agent" / "claude-code.txt"
        trajectory_file = instance_dir / "agent" / "trajectory.json"

        tool_counts = {}
        code_changes = []
        trace_messages = []

        if claude_file.exists():
            try:
                with open(claude_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            if record.get("type") == "assistant":
                                content = record.get("message", {}).get("content", [])
                                for item in content:
                                    if isinstance(item, dict):
                                        if item.get("type") == "text":
                                            text = item.get("text", "")
                                            if text.strip():
                                                trace_messages.append(text[:500])
                                        elif item.get("type") == "tool_use":
                                            tool_name = item.get("name", "")
                                            tool_input = item.get("input", {})
                                            tool_counts[tool_name] = (
                                                tool_counts.get(tool_name, 0) + 1
                                            )

                                            if tool_name == "Edit":
                                                code_changes.append(
                                                    {
                                                        "type": "edit",
                                                        "file": tool_input.get(
                                                            "file_path", ""
                                                        ),
                                                        "old": tool_input.get(
                                                            "old_string", ""
                                                        )[:500],
                                                        "new": tool_input.get(
                                                            "new_string", ""
                                                        )[:500],
                                                    }
                                                )
                                            elif tool_name == "Write":
                                                code_changes.append(
                                                    {
                                                        "type": "write",
                                                        "file": tool_input.get(
                                                            "file_path", ""
                                                        ),
                                                        "content_preview": tool_input.get(
                                                            "content", ""
                                                        )[:500],
                                                    }
                                                )
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        elif trajectory_file.exists():
            try:
                steps = TraceParser.parse_trajectory_file(trajectory_file)
                for step in steps:
                    if step.tool_calls:
                        for tool in step.tool_calls:
                            tool_counts[tool.tool_name] = (
                                tool_counts.get(tool.tool_name, 0) + 1
                            )

                    diffs = TraceParser.extract_diffs(step.tool_calls)
                    for diff in diffs:
                        if diff["type"] == "edit":
                            code_changes.append(
                                {
                                    "type": "edit",
                                    "file": diff.get("file_path", ""),
                                    "old": diff.get("old_string", "")[:500],
                                    "new": diff.get("new_string", "")[:500],
                                }
                            )
                        elif diff["type"] == "write":
                            code_changes.append(
                                {
                                    "type": "write",
                                    "file": diff.get("file_path", ""),
                                    "content_preview": diff.get("content", "")[:500],
                                }
                            )

                    msg = TraceParser.get_clean_message(step)
                    if msg:
                        trace_messages.append(msg[:500])
            except Exception:
                pass

        eval_context["code_changes"] = code_changes
        eval_context["tool_usage"] = tool_counts
        eval_context["agent_trace_summary"] = "\n---\n".join(
            trace_messages[:20]
        )  # First 20 messages

    # Load oracle data for LoCoBench tasks
    oracle_data = load_locobench_oracle(task.get("task_name", ""))

    # Analyze MCP tool usage
    mcp_analysis = analyze_mcp_tool_usage(eval_context["tool_usage"])

    # Create tabs for different views
    judge_tabs = st.tabs(
        [
            "📊 Oracle & Criteria",
            "🔧 MCP Tool Analysis",
            "📋 Agent Output",
            "📤 Export for LLM Judge",
        ]
    )

    with judge_tabs[0]:
        # Oracle / Ground Truth Section
        st.markdown("#### Oracle Data (Ground Truth)")

        if oracle_data.get("ground_truth"):
            st.success("✅ Oracle data available for this task")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f"**Task Category:** {oracle_data.get('task_category', 'Unknown')}"
                )
                st.markdown(
                    f"**Difficulty:** {oracle_data.get('difficulty', 'Unknown')}"
                )
            with col2:
                st.markdown(f"**Title:** {oracle_data.get('title', 'Unknown')}")

            st.markdown("---")

            # Ground Truth (Expected Answer)
            st.markdown("##### Expected Answer (Ground Truth)")
            with st.expander("Show ground truth", expanded=True):
                st.markdown(oracle_data["ground_truth"])

            # Expected Approach
            if oracle_data.get("expected_approach"):
                st.markdown("##### Expected Approach")
                with st.expander("Show expected approach", expanded=False):
                    st.markdown(oracle_data["expected_approach"])

            # Evaluation Criteria
            if oracle_data.get("evaluation_criteria"):
                st.markdown("##### Evaluation Criteria")
                criteria = oracle_data["evaluation_criteria"]
                if isinstance(criteria, list):
                    for i, criterion in enumerate(criteria, 1):
                        st.markdown(f"{i}. {criterion}")
                else:
                    st.markdown(criteria)

            # Context Files Expected
            if oracle_data.get("context_files"):
                st.markdown("##### Expected Context Files")
                with st.expander(
                    f"Show {len(oracle_data['context_files'])} expected files"
                ):
                    for f in oracle_data["context_files"][:30]:
                        st.markdown(f"- `{f}`")
                    if len(oracle_data["context_files"]) > 30:
                        st.caption(
                            f"... and {len(oracle_data['context_files']) - 30} more"
                        )
        else:
            st.warning(
                "⚠️ No oracle data found for this task. This may not be a LoCoBench task."
            )
            st.caption(
                "Oracle data provides ground truth for evaluating the agent's response."
            )

    with judge_tabs[1]:
        # MCP Tool Usage Analysis
        st.markdown("#### MCP & Sourcegraph Tool Usage Analysis")

        # Effectiveness score
        score = mcp_analysis["effectiveness_score"]
        score_color = "green" if score >= 0.6 else "orange" if score >= 0.3 else "red"
        st.markdown(f"**MCP Tool Effectiveness Score:** :{score_color}[{score:.0%}]")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Sourcegraph Tools Used")
            if mcp_analysis["sourcegraph_tools_used"]:
                for tool in mcp_analysis["sourcegraph_tools_used"]:
                    st.markdown(f"- `{tool['tool']}`: {tool['count']} calls")
            else:
                st.warning("No Sourcegraph MCP tools were used")

            st.markdown("##### Search Patterns")
            patterns = mcp_analysis["search_patterns"]
            st.markdown(
                f"- Deep Search: {'✅' if patterns['used_deep_search'] else '❌'}"
            )
            st.markdown(
                f"- Keyword Search: {'✅' if patterns['used_keyword_search'] else '❌'}"
            )
            st.markdown(f"- File Read: {'✅' if patterns['used_file_read'] else '❌'}")

        with col2:
            st.markdown("##### All MCP Tools Used")
            if mcp_analysis["mcp_tools_used"]:
                for tool in mcp_analysis["mcp_tools_used"]:
                    st.markdown(f"- `{tool['tool']}`: {tool['count']} calls")
            else:
                st.info("No MCP tools were used")

        st.markdown("---")

        # Recommendations
        st.markdown("##### Recommendations for Improving MCP Usage")
        if mcp_analysis["recommendations"]:
            for rec in mcp_analysis["recommendations"]:
                st.markdown(rec)
        else:
            st.success("✅ Good MCP tool usage patterns detected")

        # Compare with basic tool usage
        st.markdown("---")
        st.markdown("##### Tool Usage Comparison")
        basic_tools = {
            "Read": eval_context["tool_usage"].get("Read", 0),
            "Grep": eval_context["tool_usage"].get("Grep", 0),
            "Glob": eval_context["tool_usage"].get("Glob", 0),
            "Bash": eval_context["tool_usage"].get("Bash", 0),
        }
        mcp_total = sum(t["count"] for t in mcp_analysis["sourcegraph_tools_used"])
        basic_total = sum(basic_tools.values())

        st.markdown(f"**Basic Tools (Read/Grep/Glob/Bash):** {basic_total} calls")
        st.markdown(f"**Sourcegraph MCP Tools:** {mcp_total} calls")

        if basic_total > 0:
            ratio = mcp_total / basic_total if basic_total > 0 else 0
            st.markdown(f"**MCP/Basic Ratio:** {ratio:.2f}")
            if ratio < 0.1 and basic_total > 10:
                st.warning(
                    "Consider using more Sourcegraph semantic search for complex codebase exploration"
                )

    with judge_tabs[2]:
        # Agent Output Summary
        st.markdown("#### Agent Output Summary")

        st.markdown("##### Result Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Reward", f"{eval_context['result'].get('reward', 'N/A')}")
        with col2:
            st.metric("Status", eval_context["result"].get("status", "N/A"))
        with col3:
            total_tokens = (eval_context["result"].get("input_tokens", 0) or 0) + (
                eval_context["result"].get("output_tokens", 0) or 0
            )
            st.metric("Total Tokens", f"{total_tokens:,}")

        st.markdown("##### Tool Usage")
        st.json(eval_context["tool_usage"])

        st.markdown("##### Code Changes")
        st.write(f"**Total changes:** {len(eval_context['code_changes'])}")

        if eval_context["code_changes"]:
            changes_by_file = {}
            for change in eval_context["code_changes"]:
                f = change.get("file", "unknown")
                if f not in changes_by_file:
                    changes_by_file[f] = []
                changes_by_file[f].append(change)

            for file_path, changes in changes_by_file.items():
                with st.expander(f"`{file_path}` ({len(changes)} changes)"):
                    for i, change in enumerate(changes, 1):
                        if change["type"] == "edit":
                            st.markdown(f"**Edit {i}:**")
                            st.code(f"- {change.get('old', '')[:200]}", language="diff")
                            st.code(f"+ {change.get('new', '')[:200]}", language="diff")
                        else:
                            st.markdown(f"**Write {i}:** New file")
                            st.code(
                                change.get("content_preview", "")[:200],
                                language=_get_language_from_path(file_path),
                            )

        st.markdown("##### Agent Trace Summary")
        with st.expander("Show trace summary (first 20 messages)", expanded=False):
            st.text(eval_context["agent_trace_summary"])

    with judge_tabs[3]:
        # Export for LLM Judge
        st.markdown("#### Export for LLM Judge Evaluation")
        st.caption(
            "Download a comprehensive JSON file containing all context needed for LLM-based evaluation."
        )

        # Create comprehensive export with oracle data
        export_data = {
            "task": eval_context["task_info"],
            "instruction": eval_context["instruction"],
            "metrics": {
                "result": eval_context["result"],
                "timing": eval_context["timing"],
                "tool_usage": eval_context["tool_usage"],
            },
            "code_changes": eval_context["code_changes"],
            "trace_summary": eval_context["agent_trace_summary"],
            "oracle": {
                "ground_truth": oracle_data.get("ground_truth"),
                "expected_approach": oracle_data.get("expected_approach"),
                "evaluation_criteria": oracle_data.get("evaluation_criteria"),
                "context_files": oracle_data.get("context_files"),
            },
            "mcp_analysis": {
                "effectiveness_score": mcp_analysis["effectiveness_score"],
                "sourcegraph_tools_used": mcp_analysis["sourcegraph_tools_used"],
                "search_patterns": mcp_analysis["search_patterns"],
                "recommendations": mcp_analysis["recommendations"],
            },
        }

        export_json = json.dumps(export_data, indent=2, default=str)

        st.download_button(
            "📥 Download Full LLM Judge Context (JSON)",
            export_json,
            file_name=f"{task.get('task_name', 'task')}_llm_judge_context.json",
            mime="application/json",
        )

        st.markdown("---")

        # Show LLM Judge Prompt Template
        st.markdown("#### LLM Judge Prompt Template")

        judge_prompt = f"""You are an expert evaluator for AI coding agents. Evaluate the agent's performance on this task.

## Task Information
- **Task Name:** {eval_context["task_info"]["task_name"]}
- **Category:** {oracle_data.get("task_category", "Unknown")}
- **Difficulty:** {oracle_data.get("difficulty", "Unknown")}

## Task Prompt
{oracle_data.get("task_prompt", instruction_content or "Not available")}

## Ground Truth (Expected Answer)
{oracle_data.get("ground_truth", "Not available")}

## Expected Approach
{oracle_data.get("expected_approach", "Not available")}

## Evaluation Criteria
{chr(10).join(f"- {c}" for c in (oracle_data.get("evaluation_criteria") or [])) or "Not available"}

## Agent's Output
The agent produced {len(eval_context["code_changes"])} code changes.
Reward score: {eval_context["result"].get("reward", "N/A")}

## MCP Tool Usage
- Sourcegraph tools used: {len(mcp_analysis["sourcegraph_tools_used"])}
- Deep Search used: {mcp_analysis["search_patterns"]["used_deep_search"]}
- Effectiveness score: {mcp_analysis["effectiveness_score"]:.0%}

## Your Evaluation

Please evaluate the agent's performance on the following dimensions (score 1-5):

1. **Correctness:** Did the agent correctly identify the key components and provide accurate analysis?
2. **Completeness:** Did the agent address all aspects of the task?
3. **Code Understanding:** Did the agent demonstrate deep understanding of the codebase?
4. **Tool Effectiveness:** Did the agent effectively use available tools (especially Sourcegraph MCP)?
5. **Communication:** Was the agent's response clear and well-organized?

Also provide:
- **Strengths:** What did the agent do well?
- **Weaknesses:** Where did the agent fall short?
- **MCP Improvement Suggestions:** How could the agent better use Sourcegraph/MCP tools?

Respond with a JSON object containing your evaluation."""

        with st.expander("Show LLM Judge Prompt Template", expanded=False):
            st.code(judge_prompt, language="markdown")

        st.download_button(
            "📥 Download LLM Judge Prompt",
            judge_prompt,
            file_name=f"{task.get('task_name', 'task')}_judge_prompt.md",
            mime="text/markdown",
        )


def show_conversation_view(steps):
    """Show main conversation view: user message → assistant response."""
    # Find first user message
    user_steps = [s for s in steps if s.source == "user"]
    assistant_steps = [s for s in steps if s.source == "assistant"]

    if user_steps:
        st.markdown("### User Request")
        user_msg = TraceParser.get_clean_message(user_steps[0])
        st.markdown(user_msg if user_msg else "_No message_")

    if assistant_steps:
        st.markdown("### Assistant Response")

        # Combine all assistant messages
        for i, step in enumerate(assistant_steps, 1):
            clean_msg = TraceParser.get_clean_message(step)
            if clean_msg:
                st.markdown(clean_msg)

            # Show tool calls inline
            if step.tool_calls:
                with st.expander(
                    f"Tool Calls ({len(step.tool_calls)})", expanded=False
                ):
                    for tool in step.tool_calls:
                        st.markdown(f"**{tool.tool_name}**")
                        if tool.parameters:
                            st.json(tool.parameters)

            # Show diffs inline
            diffs = TraceParser.extract_diffs(step.tool_calls)
            if diffs:
                with st.expander(f"Code Changes ({len(diffs)})", expanded=False):
                    for diff in diffs:
                        if diff["type"] == "edit":
                            st.markdown(f"**Edit:** `{diff['file_path']}`")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Before:**")
                                st.code(diff["old_string"], language="python")
                            with col2:
                                st.markdown("**After:**")
                                st.code(diff["new_string"], language="python")
                        elif diff["type"] == "write":
                            st.markdown(f"**Write:** `{diff['file_path']}`")
                            st.code(diff["content"], language="python")


def show_full_conversation(steps):
    """Show full conversation with all details."""
    for idx, step in enumerate(steps, 1):
        icon = "👤" if step.source == "user" else "🤖"
        source_label = "User" if step.source == "user" else "Assistant"

        st.markdown(f"**{icon} {source_label} - Step {idx}**")
        st.caption(f"Time: {step.timestamp}")

        # Message
        clean_message = TraceParser.get_clean_message(step)
        if clean_message:
            st.markdown(clean_message)

        # Tool calls
        if step.tool_calls:
            st.markdown(f"**Tool Calls ({len(step.tool_calls)}):**")
            for tool in step.tool_calls:
                st.markdown(f"- `{tool.tool_name}`")

        # Diffs
        diffs = TraceParser.extract_diffs(step.tool_calls)
        if diffs:
            st.markdown(f"**Code Changes ({len(diffs)}):**")
            for diff in diffs:
                if diff["type"] == "edit":
                    st.markdown(f"- Edit: `{diff['file_path']}`")
                elif diff["type"] == "write":
                    st.markdown(f"- Write: `{diff['file_path']}`")

        st.markdown("---")


def show_all_tool_calls(steps):
    """Show all tool calls aggregated."""
    all_tools = []
    for step in steps:
        if step.tool_calls:
            for tool in step.tool_calls:
                all_tools.append(
                    {
                        "tool": tool.tool_name,
                        "parameters": tool.parameters,
                        "timestamp": step.timestamp,
                    }
                )

    if not all_tools:
        st.info("No tool calls found")
        return

    st.write(f"**Total Tool Calls: {len(all_tools)}**")

    for i, tool_data in enumerate(all_tools, 1):
        with st.expander(
            f"{i}. {tool_data['tool']} - {tool_data['timestamp']}", expanded=False
        ):
            if tool_data["parameters"]:
                st.json(tool_data["parameters"])
            else:
                st.info("No parameters")


def show_all_diffs(steps):
    """Show all code diffs aggregated."""
    all_diffs = []
    for step in steps:
        diffs = TraceParser.extract_diffs(step.tool_calls)
        for diff in diffs:
            all_diffs.append({**diff, "timestamp": step.timestamp})

    if not all_diffs:
        st.info("No code changes found")
        return

    st.write(f"**Total Code Changes: {len(all_diffs)}**")

    for i, diff in enumerate(all_diffs, 1):
        if diff["type"] == "edit":
            with st.expander(f"{i}. Edit: {diff['file_path']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Before:**")
                    st.code(diff["old_string"], language="python")
                with col2:
                    st.markdown("**After:**")
                    st.code(diff["new_string"], language="python")

        elif diff["type"] == "write":
            with st.expander(f"{i}. Write: {diff['file_path']}", expanded=True):
                st.code(diff["content"], language="python")


def show_test_results(trajectory_file):
    """Show test results and comparisons."""
    # Try to find test results in the trajectory
    try:
        with open(trajectory_file) as f:
            trajectory = json.load(f)

        # Look for test-related tool calls or results
        test_steps = []
        for step in trajectory.get("steps", []):
            # Check if step contains test execution
            content = step.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_result":
                            # Check if this is a test result
                            result_content = item.get("content", "")
                            if any(
                                word in str(result_content).lower()
                                for word in ["test", "pytest", "pass", "fail", "assert"]
                            ):
                                test_steps.append(
                                    {
                                        "tool": step.get("extra", {}).get(
                                            "tool_use_name", "unknown"
                                        ),
                                        "content": result_content,
                                        "timestamp": step.get("timestamp", ""),
                                    }
                                )

        if not test_steps:
            st.info("No test results found in trajectory")
            return

        st.write(f"**Found {len(test_steps)} test-related outputs:**")

        for i, test_step in enumerate(test_steps, 1):
            with st.expander(
                f"{i}. {test_step['tool']} - {test_step['timestamp']}", expanded=True
            ):
                if isinstance(test_step["content"], str):
                    st.code(test_step["content"])
                else:
                    st.json(test_step["content"])

    except Exception as e:
        st.error(f"Failed to load test results: {e}")


def show_trace_step(step, step_number=None):
    """Display a single trace step."""
    # Step header
    icon = "👤" if step.source == "user" else "🤖"
    source_label = "User" if step.source == "user" else "Assistant"

    # Use sequential numbering for display, show actual step_id in parentheses
    step_label = f"Step {step_number}" if step_number else f"Step {step.step_id}"
    if step_number and step.step_id != step_number:
        step_label += f" (ID: {step.step_id})"

    with st.expander(f"{icon} {step_label}: {source_label}", expanded=False):
        # Timestamp
        st.caption(f"Time: {step.timestamp}")

        # Clean message (without tool calls)
        clean_message = TraceParser.get_clean_message(step)
        if clean_message:
            st.markdown("**Message:**")
            st.markdown(clean_message)

        # Tool calls
        if step.tool_calls:
            st.markdown("**Tool Calls:**")

            for i, tool_call in enumerate(step.tool_calls):
                with st.container():
                    st.markdown(f"**{i + 1}. {tool_call.tool_name}**")

                    # Show parameters
                    for param_name, param_value in tool_call.parameters.items():
                        if len(param_value) > 200:
                            with st.expander(f"  {param_name}"):
                                st.code(
                                    param_value,
                                    language="python"
                                    if "content" in param_name
                                    else None,
                                )
                        else:
                            st.code(f"{param_name}: {param_value}", language=None)

        # Diffs
        diffs = TraceParser.extract_diffs(step.tool_calls)
        if diffs:
            st.markdown("**Code Changes:**")

            for diff in diffs:
                if diff["type"] == "edit":
                    st.markdown(f"**Edit:** `{diff['file_path']}`")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Before:**")
                        st.code(diff["old_string"], language="python")
                    with col2:
                        st.markdown("**After:**")
                        st.code(diff["new_string"], language="python")

                elif diff["type"] == "write":
                    st.markdown(f"**Write:** `{diff['file_path']}`")
                    st.code(diff["content"], language="python")

        # Metrics
        if step.metrics:
            with st.expander("Metrics"):
                st.json(step.metrics)


def show_result_details(result_files):
    """Display result details."""
    st.subheader("Result Details")

    if result_files:
        try:
            with open(result_files[0]) as f:
                result = json.load(f)

            st.json(result)

        except Exception as e:
            st.error(f"Failed to load result: {e}")
    else:
        st.info("No result file found.")


def show_checklist_section(run_data, task, task_output_dir):
    """Show checklist evaluation section for documentation tasks."""
    st.subheader("Checklist Evaluation")

    # Check if this is a doc task (kubernetes_docs benchmark)
    benchmark_name = run_data.get("benchmark_name", "").lower()
    is_doc_task = "doc" in benchmark_name or "kubernetes" in benchmark_name

    if not is_doc_task:
        st.info(
            "Checklist evaluation is designed for documentation tasks (e.g., kubernetes_docs benchmark)."
        )
        st.caption(
            "For code-based benchmarks, see the LLM Judge tab for quality assessment."
        )
        return

    # Try to find generated README or documentation
    readme_files = list(task_output_dir.rglob("README.md"))
    doc_files = list(task_output_dir.rglob("*.md"))

    if not doc_files:
        st.warning("No documentation files found in task output.")
        return

    # Load checklist
    try:
        from benchmark.database import ChecklistEvaluationRegistry
        from evaluation.checklist import (
            Checklist,
            ChecklistEvaluator,
            EvaluationStatus,
            Severity,
        )

        checklist_path = (
            Path(__file__).parent.parent.parent
            / "configs"
            / "checklists"
            / "ssa-doc-v1.yaml"
        )

        if not checklist_path.exists():
            st.warning(
                "Checklist file not found. Create configs/checklists/ssa-doc-v1.yaml"
            )
            return

        checklist = Checklist.from_file(checklist_path)

    except ImportError as e:
        st.error(f"Failed to import checklist module: {e}")
        return

    # File selector
    doc_file_options = [str(f.relative_to(task_output_dir)) for f in doc_files]
    selected_doc = st.selectbox("Select document to evaluate", doc_file_options)

    if not selected_doc:
        return

    doc_path = task_output_dir / selected_doc

    # Read document content
    try:
        with open(doc_path) as f:
            doc_content = f.read()
    except Exception as e:
        st.error(f"Failed to read document: {e}")
        return

    # Show document preview
    with st.expander("Document Preview", expanded=False):
        st.markdown(doc_content[:3000] + ("..." if len(doc_content) > 3000 else ""))

    # Run evaluation
    if st.button("Run Checklist Evaluation", key="run_checklist"):
        with st.spinner("Evaluating document against checklist..."):
            evaluator = ChecklistEvaluator(checklist)
            result = evaluator.evaluate_tier_a(doc_content)

            # Store in session state
            st.session_state[f"checklist_result_{task['task_name']}"] = result

            # Store in database
            try:
                ChecklistEvaluationRegistry.add(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    agent_name=task["agent_name"],
                    checklist_id=checklist.checklist_id,
                    covered_items=[e.to_dict() for e in result.item_evaluations],
                    coverage_score=result.coverage_score,
                    accuracy_score=result.accuracy_score,
                    contradiction_count=result.contradiction_count,
                    weighted_score=result.weighted_score,
                    evaluation_details=result.evaluation_details,
                )
                st.success("Evaluation saved to database")
            except Exception as e:
                st.warning(f"Could not save to database: {e}")

    # Display results
    result_key = f"checklist_result_{task['task_name']}"
    if result_key in st.session_state:
        result = st.session_state[result_key]
        _display_checklist_result(result, checklist)
    else:
        # Try to load from database
        try:
            from benchmark.database import ChecklistEvaluationRegistry

            stored = ChecklistEvaluationRegistry.get(
                run_id=run_data["run_id"],
                task_name=task["task_name"],
                agent_name=task["agent_name"],
                checklist_id="ssa-doc-v1",
            )
            if stored:
                st.info("Loaded previous evaluation from database")
                # Display stored results
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Coverage", f"{stored['coverage_score']:.1%}")
                with col2:
                    st.metric("Accuracy", f"{stored['accuracy_score']:.1%}")
                with col3:
                    st.metric("Weighted Score", f"{stored['weighted_score']:.1%}")
                with col4:
                    st.metric("Contradictions", stored["contradiction_count"])
            else:
                st.info("Click 'Run Checklist Evaluation' to evaluate the document.")
        except Exception:
            st.info("Click 'Run Checklist Evaluation' to evaluate the document.")


def _display_checklist_result(result, checklist):
    """Display checklist evaluation results."""
    from evaluation.checklist import EvaluationStatus, Severity

    # Summary metrics
    st.markdown("### Evaluation Results")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Coverage",
            f"{result.coverage_score:.1%}",
            help="Percentage of checklist items covered",
        )
    with col2:
        st.metric(
            "Accuracy",
            f"{result.accuracy_score:.1%}",
            help="Correctness of covered items (from Tier B judge)",
        )
    with col3:
        st.metric(
            "Weighted Score",
            f"{result.weighted_score:.1%}",
            help="0.6*accuracy + 0.4*coverage - penalties",
        )
    with col4:
        st.metric("Covered Items", f"{result.covered_count}/{result.total_items}")

    # Progress bar
    st.progress(
        result.coverage_score,
        text=f"Coverage: {result.covered_count}/{result.total_items} items",
    )

    # Category breakdown
    st.markdown("### Coverage by Category")

    category_stats = {}
    for eval_item in result.item_evaluations:
        item = next((i for i in checklist.items if i.id == eval_item.item_id), None)
        if item:
            cat = item.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "covered": 0}
            category_stats[cat]["total"] += 1
            if eval_item.covered:
                category_stats[cat]["covered"] += 1

    if category_stats:
        cat_df_data = []
        for cat, stats in sorted(category_stats.items()):
            pct = stats["covered"] / stats["total"] * 100 if stats["total"] > 0 else 0
            cat_df_data.append(
                {
                    "Category": cat.title(),
                    "Covered": stats["covered"],
                    "Total": stats["total"],
                    "Coverage": f"{pct:.0f}%",
                }
            )

        st.dataframe(cat_df_data, use_container_width=True, hide_index=True)

    # Item-level details
    st.markdown("### Item Details")

    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        status_filter = st.multiselect(
            "Filter by status",
            ["covered", "not_evaluated"],
            default=["covered", "not_evaluated"],
        )
    with filter_col2:
        severity_filter = st.multiselect(
            "Filter by severity",
            ["must", "should", "nice"],
            default=["must", "should", "nice"],
        )

    # Display filtered items
    for eval_item in result.item_evaluations:
        item = next((i for i in checklist.items if i.id == eval_item.item_id), None)
        if not item:
            continue

        # Apply filters
        status_str = "covered" if eval_item.covered else "not_evaluated"
        if status_str not in status_filter:
            continue
        if item.severity.value not in severity_filter:
            continue

        # Create expander for each item
        status_icon = "✅" if eval_item.covered else "❌"
        severity_badge = {"must": "🔴", "should": "🟡", "nice": "🟢"}[
            item.severity.value
        ]

        with st.expander(
            f"{status_icon} {item.id} {severity_badge} {item.statement[:60]}..."
        ):
            st.write(f"**Statement:** {item.statement}")
            st.write(
                f"**Category:** {item.category} | **Severity:** {item.severity.value}"
            )
            st.write(f"**Status:** {eval_item.status.value}")

            if eval_item.evidence:
                st.write("**Evidence found:**")
                st.code(eval_item.evidence[:500], language="markdown")

            if eval_item.reasoning:
                st.caption(f"Reasoning: {eval_item.reasoning}")


def show_llm_judge_section(run_data, task, task_output_dir):
    """Show LLM judge evaluation section."""
    st.subheader("LLM Judge Evaluation")

    # Import judge modules
    try:
        from benchmark.database import JudgeEvaluationRegistry
        from benchmark.llm_judge import (
            LLMJudge,
            extract_code_changes_from_trajectory,
            extract_tool_calls_from_trajectory,
            load_task_description,
        )
    except ImportError as e:
        st.error(f"Failed to import judge modules: {e}")
        return

    # Check for ANTHROPIC_API_KEY
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning(
            "ANTHROPIC_API_KEY environment variable not set. Cannot run LLM judge."
        )
        return

    # Model selector
    judge_model = st.selectbox(
        "Judge Model",
        [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-5-20251022",
            "claude-opus-4-5-20251022",
        ],
        help="Model to use for judge evaluation. Haiku is fastest and cheapest.",
    )

    # Check if judge evaluation already exists
    existing_evals = JudgeEvaluationRegistry.list_for_task(
        run_data["run_id"], task["task_name"]
    )

    if existing_evals:
        st.info(f"Found {len(existing_evals)} existing judge evaluation(s)")

        # Display existing evaluations
        for eval_data in existing_evals:
            with st.expander(
                f"Judge Evaluation - {eval_data['judge_model']}", expanded=True
            ):
                st.write(f"**Created:** {eval_data['created_at'][:19]}")

                # Parse evaluation data
                if eval_data.get("evaluation_data"):
                    eval_json = eval_data["evaluation_data"]

                    # Display scores
                    col1, col2 = st.columns(2)

                    # Retrieval quality
                    with col1:
                        retrieval = eval_json.get("retrieval_quality", {})
                        if retrieval:
                            st.metric(
                                "Retrieval Quality", f"{retrieval.get('score', 0)}/5"
                            )
                            st.write(
                                f"**Reasoning:** {retrieval.get('reasoning', 'N/A')}"
                            )

                            if retrieval.get("strengths"):
                                st.write("**Strengths:**")
                                for strength in retrieval.get("strengths", []):
                                    st.write(f"- {strength}")

                            if retrieval.get("weaknesses"):
                                st.write("**Weaknesses:**")
                                for weakness in retrieval.get("weaknesses", []):
                                    st.write(f"- {weakness}")

                    # Code quality
                    with col2:
                        code_quality = eval_json.get("code_quality", {})
                        if code_quality:
                            st.metric(
                                "Code Quality", f"{code_quality.get('score', 0)}/5"
                            )
                            st.write(
                                f"**Reasoning:** {code_quality.get('reasoning', 'N/A')}"
                            )

                            if code_quality.get("strengths"):
                                st.write("**Strengths:**")
                                for strength in code_quality.get("strengths", []):
                                    st.write(f"- {strength}")

                            if code_quality.get("weaknesses"):
                                st.write("**Weaknesses:**")
                                for weakness in code_quality.get("weaknesses", []):
                                    st.write(f"- {weakness}")

        st.markdown("---")

    # Run judge button
    if st.button("Run LLM Judge Evaluation", key=f"judge_{task['task_name']}"):
        with st.spinner("Running LLM judge evaluation..."):
            try:
                # Find trajectory and result files
                trajectory_files = list(task_output_dir.rglob("trajectory.json"))
                result_files = list(task_output_dir.rglob("result.json"))

                if not trajectory_files:
                    st.error("No trajectory.json file found")
                    return

                if not result_files:
                    st.error("No result.json file found")
                    return

                # Load trajectory
                with open(trajectory_files[0]) as f:
                    trajectory = json.load(f)

                # Load result
                with open(result_files[0]) as f:
                    result = json.load(f)

                # Get task description
                benchmark_path = Path("benchmarks") / run_data.get("benchmark_name", "")
                task_path = benchmark_path / task["task_name"]

                if task_path.exists():
                    task_description = load_task_description(task_path)
                else:
                    task_description = f"Task: {task['task_name']}"

                # Extract tool calls and code changes
                tool_calls = extract_tool_calls_from_trajectory(trajectory)
                code_changes = extract_code_changes_from_trajectory(trajectory)

                # Get reward (use new Harbor format)
                reward = 0.0
                stats = result.get("stats", {})
                evals = stats.get("evals", {})
                if evals:
                    first_eval = next(iter(evals.values()))
                    metrics = first_eval.get("metrics", [])
                    if metrics and len(metrics) > 0:
                        reward = metrics[0].get("mean", 0.0)

                # Fallback to old format
                if reward == 0.0:
                    reward = (
                        result.get("verifier_result", {})
                        .get("rewards", {})
                        .get("reward", 0.0)
                    )

                # Initialize judge
                judge = LLMJudge(model=judge_model)

                # Evaluate retrieval quality
                st.write("Evaluating retrieval quality...")
                retrieval_assessment = judge.evaluate_retrieval(
                    task_description, tool_calls
                )

                # Evaluate code quality
                st.write("Evaluating code quality...")
                code_assessment = judge.evaluate_code(
                    task_description, code_changes, reward
                )

                # Store in database
                evaluation_data = {
                    "retrieval_quality": retrieval_assessment.to_dict(),
                    "code_quality": code_assessment.to_dict(),
                }

                # Calculate average score
                avg_score = (retrieval_assessment.score + code_assessment.score) / 2.0

                JudgeEvaluationRegistry.add(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    agent_name=task["agent_name"],
                    judge_model=judge_model,
                    score=avg_score,
                    reasoning=f"Retrieval: {retrieval_assessment.score}/5, Code: {code_assessment.score}/5",
                    evaluation_data=evaluation_data,
                )

                st.success("Judge evaluation complete!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to run judge evaluation: {e}")
                import traceback

                st.code(traceback.format_exc())


def show_task_report_section(
    run_data, task, task_output_dir, trajectory_files, result_files
):
    """Show task report generation and export section."""
    st.subheader("Task Report")

    # Import report modules
    try:
        from benchmark.database import EvaluationReportRegistry, JudgeEvaluationRegistry
        from benchmark.report_generator import (
            format_task_report_csv_row,
            format_task_report_json,
            format_task_report_markdown,
            generate_task_report,
        )
    except ImportError as e:
        st.error(f"Failed to import report modules: {e}")
        return

    # Check if report already exists
    existing_report = EvaluationReportRegistry.get_latest(
        run_data["run_id"], task_name=task["task_name"], report_type="task_report"
    )

    if existing_report:
        st.info(f"Report exists - Generated: {existing_report['created_at'][:19]}")

        # Display summary
        report_data = existing_report.get("report_data", {})

        if report_data:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                success = report_data.get("result", {}).get("success", False)
                st.metric("Success", "Yes" if success else "No")

            with col2:
                total_tokens = (
                    report_data.get("metrics", {})
                    .get("tokens", {})
                    .get("total_tokens", 0)
                )
                st.metric("Total Tokens", f"{total_tokens:,}")

            with col3:
                exec_time = (
                    report_data.get("metrics", {})
                    .get("timing", {})
                    .get("agent_execution_sec", 0)
                )
                st.metric("Execution Time", f"{exec_time:.1f}s")

            with col4:
                judge_score = report_data.get("judge_evaluation", {}).get(
                    "score", "N/A"
                )
                if isinstance(judge_score, (int, float)):
                    st.metric("Judge Score", f"{judge_score:.2f}/5")
                else:
                    st.metric("Judge Score", judge_score)

            st.markdown("---")

            # Export options
            st.write("**Export Report:**")

            col1, col2, col3 = st.columns(3)

            with col1:
                markdown = format_task_report_markdown(report_data)
                st.download_button(
                    "Download Markdown",
                    markdown,
                    file_name=f"{task['task_name']}_report.md",
                    mime="text/markdown",
                    key=f"download_md_{task['task_name']}",
                )

            with col2:
                json_str = format_task_report_json(report_data)
                st.download_button(
                    "Download JSON",
                    json_str,
                    file_name=f"{task['task_name']}_report.json",
                    mime="application/json",
                    key=f"download_json_{task['task_name']}",
                )

            with col3:
                csv_row = format_task_report_csv_row(report_data)
                # Add header
                csv_header = "task_name,agent_name,success,reward,total_tokens,input_tokens,output_tokens,cache_tokens,total_time_sec,agent_execution_sec,total_edits,total_writes,files_modified,judge_score,judge_model\n"
                csv_content = csv_header + csv_row
                st.download_button(
                    "Download CSV",
                    csv_content,
                    file_name=f"{task['task_name']}_report.csv",
                    mime="text/csv",
                    key=f"download_csv_{task['task_name']}",
                )

            # Show full report in expander
            with st.expander("View Full Report"):
                st.markdown(markdown)

        st.markdown("---")

    # Generate report button
    if st.button("Generate Task Report", key=f"generate_report_{task['task_name']}"):
        with st.spinner("Generating task report..."):
            try:
                # Load trajectory
                if not trajectory_files:
                    st.error("No trajectory.json file found")
                    return

                with open(trajectory_files[0]) as f:
                    trajectory = json.load(f)

                # Load result
                if not result_files:
                    st.error("No result.json file found")
                    return

                with open(result_files[0]) as f:
                    result = json.load(f)

                # Try to load task metadata
                task_metadata = None
                benchmark_path = Path("benchmarks") / run_data.get("benchmark_name", "")
                task_path = benchmark_path / task["task_name"]

                if task_path.exists():
                    task_toml = task_path / "task.toml"
                    if task_toml.exists():
                        try:
                            import toml

                            with open(task_toml) as f:
                                task_metadata = toml.load(f)
                        except:
                            pass

                # Get judge evaluation if exists
                judge_evals = JudgeEvaluationRegistry.list_for_task(
                    run_data["run_id"], task["task_name"]
                )
                judge_evaluation = judge_evals[0] if judge_evals else None

                # Generate report
                report = generate_task_report(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    agent_name=task["agent_name"],
                    result_data=result,
                    trajectory_data=trajectory,
                    judge_evaluation=judge_evaluation,
                    task_metadata=task_metadata,
                )

                # Store in database
                EvaluationReportRegistry.add(
                    run_id=run_data["run_id"],
                    task_name=task["task_name"],
                    report_type="task_report",
                    report_data=report,
                )

                st.success("Task report generated successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Failed to generate report: {e}")
                import traceback

                st.code(traceback.format_exc())


if __name__ == "__main__":
    show_run_results()
