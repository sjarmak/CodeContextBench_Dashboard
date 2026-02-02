"""
Results Explorer View

Browse per-trial results with filtering by benchmark, config, and outcome.
Loads experiment_metrics.json from the pipeline output directory.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st


# Default pipeline output directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"


def _load_experiment_metrics(output_dir: Path) -> list[dict]:
    """Load experiment_metrics.json from the output directory.

    Returns a list of category dicts, or an empty list on error.
    """
    metrics_path = output_dir / "experiment_metrics.json"
    if not metrics_path.is_file():
        return []
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _flatten_trials(categories: list[dict]) -> list[dict]:
    """Flatten nested categories/experiments/trials into a flat trial list.

    Each returned dict includes the original trial fields plus
    ``run_category`` and ``experiment_id`` from parent containers.
    """
    trials: list[dict] = []
    for category in categories:
        run_category = category.get("run_category", "unknown")
        for experiment in category.get("experiments", []):
            experiment_id = experiment.get("experiment_id", "unknown")
            for trial in experiment.get("trials", []):
                trials.append({
                    **trial,
                    "run_category": run_category,
                    "experiment_id": experiment_id,
                })
    return trials


def _extract_judge_score(trial: dict) -> float | None:
    """Extract a summary judge score from trial data if available."""
    judge_scores = trial.get("judge_scores")
    if not judge_scores:
        return None
    # Judge scores can be a dict with dimension scores; average them
    if isinstance(judge_scores, dict):
        dimensions = judge_scores.get("dimensions", {})
        if isinstance(dimensions, dict) and dimensions:
            scores = [
                s.get("score", 0.0) if isinstance(s, dict) else float(s)
                for s in dimensions.values()
                if s is not None
            ]
            if scores:
                return sum(scores) / len(scores)
        # Fallback: check for a top-level score
        top_score = judge_scores.get("score")
        if top_score is not None:
            return float(top_score)
    if isinstance(judge_scores, (int, float)):
        return float(judge_scores)
    return None


def _build_display_dataframe(trials: list[dict]) -> pd.DataFrame:
    """Build a DataFrame suitable for display from flat trial dicts."""
    rows = []
    for trial in trials:
        tool_util = trial.get("tool_utilization") or {}
        judge_score = _extract_judge_score(trial)

        rows.append({
            "task_name": trial.get("task_name", "unknown"),
            "benchmark": trial.get("benchmark", "unknown"),
            "config": trial.get("agent_config", "unknown"),
            "reward": trial.get("reward"),
            "outcome": trial.get("pass_fail", "unknown"),
            "duration_s": trial.get("duration_seconds"),
            "input_tokens": trial.get("input_tokens", 0),
            "output_tokens": trial.get("output_tokens", 0),
            "judge_score": judge_score,
            "mcp_calls": tool_util.get("mcp_calls", 0),
            "deep_search_calls": tool_util.get("deep_search_calls", 0),
            "total_tool_calls": tool_util.get("total_tool_calls", 0),
            "run_category": trial.get("run_category", "unknown"),
            "experiment_id": trial.get("experiment_id", "unknown"),
            "trial_id": trial.get("trial_id", "unknown"),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter controls and return the filtered DataFrame."""
    col_bench, col_config, col_outcome = st.columns(3)

    with col_bench:
        benchmarks = sorted(df["benchmark"].unique().tolist())
        selected_benchmarks = st.multiselect(
            "Benchmark",
            benchmarks,
            default=benchmarks,
            key="re_filter_benchmark",
        )

    with col_config:
        configs = sorted(df["config"].unique().tolist())
        selected_configs = st.multiselect(
            "Config",
            configs,
            default=configs,
            key="re_filter_config",
        )

    with col_outcome:
        outcomes = sorted(df["outcome"].unique().tolist())
        selected_outcomes = st.multiselect(
            "Outcome",
            outcomes,
            default=outcomes,
            key="re_filter_outcome",
        )

    filtered = df[
        df["benchmark"].isin(selected_benchmarks)
        & df["config"].isin(selected_configs)
        & df["outcome"].isin(selected_outcomes)
    ]

    return filtered


def _render_results_table(filtered_df: pd.DataFrame, all_trials: list[dict]) -> None:
    """Render the results table with expandable rows."""
    if filtered_df.empty:
        st.warning("No trials match the selected filters.")
        return

    # Display columns for the main table
    display_cols = [
        "task_name",
        "benchmark",
        "config",
        "reward",
        "duration_s",
        "input_tokens",
        "output_tokens",
    ]

    # Include judge_score column if any trials have it
    has_judge = filtered_df["judge_score"].notna().any()
    if has_judge:
        display_cols.append("judge_score")

    st.dataframe(
        filtered_df[display_cols].rename(columns={
            "task_name": "Task",
            "benchmark": "Benchmark",
            "config": "Config",
            "reward": "Reward",
            "duration_s": "Duration (s)",
            "input_tokens": "Input Tokens",
            "output_tokens": "Output Tokens",
            "judge_score": "Judge Score",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # Build a lookup for trial details
    trial_lookup: dict[str, dict] = {}
    for trial in all_trials:
        key = f"{trial.get('trial_id', '')}_{trial.get('experiment_id', '')}_{trial.get('task_name', '')}"
        trial_lookup[key] = trial

    # Expandable rows for per-trial detail
    st.markdown("### Trial Details")
    st.caption("Expand a trial to see tool call summary and additional details.")

    for _, row in filtered_df.iterrows():
        trial_key = f"{row['trial_id']}_{row['experiment_id']}_{row['task_name']}"
        trial = trial_lookup.get(trial_key, {})
        tool_util = trial.get("tool_utilization") or {}

        reward_str = f"{row['reward']:.2f}" if row["reward"] is not None else "N/A"
        dur_str = f"{row['duration_s']:.0f}s" if row["duration_s"] is not None else "N/A"
        label = f"{row['task_name']} | {row['config']} | Reward: {reward_str} | {dur_str}"

        with st.expander(label, expanded=False):
            # Summary metrics row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Reward", reward_str)
            m2.metric("Outcome", row["outcome"])
            m3.metric("Duration", dur_str)
            m4.metric("Config", row["config"])

            # Tool call summary
            st.markdown("**Tool Usage**")
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Total Tool Calls", tool_util.get("total_tool_calls", 0))
            tc2.metric("MCP Calls", tool_util.get("mcp_calls", 0))
            tc3.metric("Deep Search Calls", tool_util.get("deep_search_calls", 0))
            fill_rate = tool_util.get("context_fill_rate")
            tc4.metric(
                "Context Fill Rate",
                f"{fill_rate:.1%}" if fill_rate is not None else "N/A",
            )

            # Tool calls by name
            tool_calls_by_name = tool_util.get("tool_calls_by_name")
            if tool_calls_by_name and isinstance(tool_calls_by_name, dict):
                sorted_tools = sorted(
                    tool_calls_by_name.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                if sorted_tools:
                    st.markdown("**Tool Call Breakdown**")
                    tool_df = pd.DataFrame(
                        sorted_tools,
                        columns=["Tool", "Count"],
                    )
                    st.dataframe(
                        tool_df,
                        use_container_width=True,
                        hide_index=True,
                        height=min(35 * len(tool_df) + 40, 300),
                    )

            # Metadata
            st.caption(
                f"Category: {row['run_category']} | "
                f"Experiment: {row['experiment_id']} | "
                f"Trial: {row['trial_id']}"
            )


def _render_csv_export(filtered_df: pd.DataFrame) -> None:
    """Render a CSV export button for the filtered results."""
    csv_buffer = io.StringIO()
    filtered_df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    st.download_button(
        label=f"Export CSV ({len(filtered_df)} rows)",
        data=csv_data,
        file_name="results_explorer_export.csv",
        mime="text/csv",
        key="re_csv_export",
    )


def show_results_explorer() -> None:
    """Main entry point for the Results Explorer view."""
    st.title("Results Explorer")
    st.caption("Browse per-trial results with filtering by benchmark, config, and outcome.")
    st.markdown("---")

    # Load data
    categories = _load_experiment_metrics(_DEFAULT_OUTPUT_DIR)

    if not categories:
        st.info(
            "No experiment_metrics.json found in output/ directory. "
            "Run the analysis pipeline from the Home page first."
        )
        return

    flat_trials = _flatten_trials(categories)
    if not flat_trials:
        st.warning("experiment_metrics.json loaded but contains no trial data.")
        return

    df = _build_display_dataframe(flat_trials)

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trials", len(df))
    c2.metric("Benchmarks", df["benchmark"].nunique())
    c3.metric("Configs", df["config"].nunique())
    pass_count = (df["outcome"] == "pass").sum()
    c4.metric("Pass Rate", f"{pass_count / len(df):.1%}" if len(df) > 0 else "N/A")

    st.markdown("---")

    # Filters
    filtered_df = _render_filters(df)

    st.caption(f"Showing {len(filtered_df)} of {len(df)} trials")

    # CSV export
    _render_csv_export(filtered_df)

    st.markdown("---")

    # Results table + expandable details
    _render_results_table(filtered_df, flat_trials)
