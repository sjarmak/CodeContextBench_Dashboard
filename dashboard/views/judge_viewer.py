"""
LLM Judge Viewer

Review judge evaluation results and re-run with different templates.
Loads judge scores from experiment_metrics.json in the pipeline output directory.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


# Default pipeline output directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "output"
_DEFAULT_TEMPLATES_DIR = _PROJECT_ROOT / "configs" / "judge_templates"

# Config display names
_CONFIG_DISPLAY = {
    "BASELINE": "Baseline",
    "MCP_BASE": "MCP-Base",
    "MCP_FULL": "MCP-Full",
}

_CONFIG_ORDER = ["BASELINE", "MCP_BASE", "MCP_FULL"]


def _display_config(config: str) -> str:
    """Map internal config name to paper-friendly display name."""
    return _CONFIG_DISPLAY.get(config, config)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


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

    Each returned dict includes ``run_category`` and ``experiment_id``.
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


def _extract_judge_data(trial: dict) -> dict | None:
    """Extract judge scores from a trial dict.

    Returns a normalized dict with mean_score, overall_quality, dimensions,
    confidence, and error fields, or None if no judge data.
    """
    judge_scores = trial.get("judge_scores")
    if not judge_scores:
        return None

    if isinstance(judge_scores, (int, float)):
        return {
            "mean_score": float(judge_scores),
            "overall_quality": "pass" if judge_scores >= 0.75 else ("partial" if judge_scores >= 0.25 else "fail"),
            "dimensions": [],
            "confidence": 1.0,
            "error": None,
        }

    if isinstance(judge_scores, dict):
        dimensions = judge_scores.get("dimensions") or []
        mean_score = judge_scores.get("mean_score")

        # Compute confidence as average of dimension confidences
        confidences = [
            d.get("confidence", 0.0)
            for d in dimensions
            if isinstance(d, dict) and d.get("confidence") is not None
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "mean_score": float(mean_score) if mean_score is not None else 0.0,
            "overall_quality": judge_scores.get("overall_quality", "unknown"),
            "dimensions": dimensions if isinstance(dimensions, list) else [],
            "confidence": avg_confidence,
            "error": judge_scores.get("error"),
        }

    return None


def _load_judge_templates(templates_dir: Path) -> list[Path]:
    """List available judge template JSON files."""
    if not templates_dir.is_dir():
        return []
    templates = sorted(templates_dir.glob("*.json"))
    return templates


def _df_to_csv(df: pd.DataFrame) -> str:
    """Convert DataFrame to CSV string."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Aggregated scores table
# ---------------------------------------------------------------------------


def _render_aggregated_scores(trials: list[dict]) -> None:
    """Render aggregated judge scores by benchmark and config."""
    st.markdown("### Aggregated Judge Scores")

    rows: list[dict] = []
    # Group by (benchmark, config)
    groups: dict[tuple[str, str], list[dict]] = {}
    for trial in trials:
        judge_data = _extract_judge_data(trial)
        if judge_data is None:
            continue
        benchmark = trial.get("benchmark", "unknown")
        config = trial.get("agent_config", "unknown")
        key = (benchmark, config)
        if key not in groups:
            groups[key] = []
        groups[key].append(judge_data)

    if not groups:
        st.info("No judge scores available. Run the judge pipeline first.")
        return

    order_map = {c: i for i, c in enumerate(_CONFIG_ORDER)}
    for (benchmark, config), judge_entries in sorted(groups.items(), key=lambda x: (x[0][0], order_map.get(x[0][1], 99))):
        scores = [e["mean_score"] for e in judge_entries]
        confidences = [e["confidence"] for e in judge_entries]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        n_trials = len(judge_entries)
        n_errors = sum(1 for e in judge_entries if e.get("error"))

        rows.append({
            "Benchmark": benchmark,
            "Config": _display_config(config),
            "N": n_trials,
            "Mean Judge Score": f"{mean_score:.3f}",
            "Vote Confidence": f"{mean_confidence:.2f}",
            "Errors": n_errors,
            "_benchmark": benchmark,
            "_config": config,
        })

    if not rows:
        st.info("No judge scores available. Run the judge pipeline first.")
        return

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_benchmark", "_config"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Export Aggregated Scores (CSV)",
        _df_to_csv(display_df),
        file_name="judge_aggregated_scores.csv",
        mime="text/csv",
        key="jv_agg_csv",
    )


# ---------------------------------------------------------------------------
# Per-task breakdown
# ---------------------------------------------------------------------------


def _render_per_task_breakdown(trials: list[dict]) -> None:
    """Render per-task judge results with expandable vote distribution."""
    st.markdown("### Per-Task Judge Results")

    judged_trials = [
        t for t in trials if _extract_judge_data(t) is not None
    ]

    if not judged_trials:
        st.info("No per-task judge data available.")
        return

    # Build summary table
    rows: list[dict] = []
    for trial in judged_trials:
        judge_data = _extract_judge_data(trial)
        if judge_data is None:
            continue
        rows.append({
            "task_name": trial.get("task_name", "unknown"),
            "benchmark": trial.get("benchmark", "unknown"),
            "config": trial.get("agent_config", "unknown"),
            "mean_score": judge_data["mean_score"],
            "quality": judge_data["overall_quality"],
            "confidence": judge_data["confidence"],
            "error": judge_data.get("error") or "",
            "n_dimensions": len(judge_data["dimensions"]),
        })

    df = pd.DataFrame(rows)
    display_df = df.rename(columns={
        "task_name": "Task",
        "benchmark": "Benchmark",
        "config": "Config",
        "mean_score": "Score",
        "quality": "Quality",
        "confidence": "Confidence",
        "n_dimensions": "Dimensions",
    })
    display_df = display_df.drop(columns=["error"])

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Expandable rows with vote distribution per dimension
    st.markdown("#### Dimension Details")
    st.caption("Expand a trial to see vote distribution per evaluation dimension.")

    for trial in judged_trials:
        judge_data = _extract_judge_data(trial)
        if judge_data is None:
            continue

        task_name = trial.get("task_name", "unknown")
        config = trial.get("agent_config", "unknown")
        score = judge_data["mean_score"]
        quality = judge_data["overall_quality"]

        label = f"{task_name} | {_display_config(config)} | Score: {score:.2f} | {quality}"

        with st.expander(label, expanded=False):
            if judge_data.get("error"):
                st.error(f"Judge error: {judge_data['error']}")

            dimensions = judge_data["dimensions"]
            if not dimensions:
                st.caption("No dimension scores available.")
                continue

            for dim in dimensions:
                if not isinstance(dim, dict):
                    continue

                dim_name = dim.get("dimension", "unknown")
                dim_score = dim.get("score", 0.0)
                dim_label = dim.get("score_label", "unknown")
                dim_confidence = dim.get("confidence", 0.0)
                dim_reasoning = dim.get("reasoning", "")
                vote_dist = dim.get("vote_distribution") or []

                col_name, col_score, col_conf = st.columns([2, 1, 1])
                with col_name:
                    st.markdown(f"**{dim_name}**")
                with col_score:
                    st.metric("Score", f"{dim_score:.1f} ({dim_label})")
                with col_conf:
                    st.metric("Confidence", f"{dim_confidence:.0%}")

                if vote_dist:
                    vote_str = ", ".join(
                        f"{label}: {count}"
                        for label, count in vote_dist
                        if isinstance(label, str)
                    )
                    st.caption(f"Vote distribution: {vote_str}")

                if dim_reasoning:
                    st.caption(f"Reasoning: {dim_reasoning}")

                st.markdown("---")


# ---------------------------------------------------------------------------
# Template selector and re-run
# ---------------------------------------------------------------------------


def _render_rerun_section(trials: list[dict]) -> None:
    """Render template selector and re-run button for judge evaluation."""
    st.markdown("### Re-Run Judge Evaluation")

    # Template selector
    templates = _load_judge_templates(_DEFAULT_TEMPLATES_DIR)

    template_options = ["Default (auto by benchmark)"]
    template_paths: dict[str, Path | None] = {"Default (auto by benchmark)": None}

    for t in templates:
        display_name = t.stem
        template_options.append(display_name)
        template_paths[display_name] = t

    selected_template = st.selectbox(
        "Judge Template",
        template_options,
        key="jv_template_select",
    )

    # Task selection for re-run
    task_names = sorted(set(
        t.get("task_name", "unknown") for t in trials
    ))

    selected_tasks = st.multiselect(
        "Tasks to re-judge (leave empty for all)",
        task_names,
        key="jv_task_select",
    )

    col_btn, col_status = st.columns([1, 3])

    with col_btn:
        rerun_clicked = st.button(
            "Re-run Judge",
            key="jv_rerun_btn",
            type="primary",
        )

    if rerun_clicked:
        _run_judge_subprocess(
            template_path=template_paths.get(selected_template),
            selected_tasks=selected_tasks,
        )


def _run_judge_subprocess(
    template_path: Path | None,
    selected_tasks: list[str],
) -> None:
    """Execute judge.py via subprocess and show progress."""
    metrics_path = _DEFAULT_OUTPUT_DIR / "experiment_metrics.json"
    if not metrics_path.is_file():
        st.error("No experiment_metrics.json found. Run the extract pipeline first.")
        return

    cmd = [
        sys.executable, "-m", "scripts.ccb_pipeline.judge",
        "--input", str(metrics_path),
    ]

    if template_path is not None:
        cmd.extend(["--judge-template", str(template_path)])

    with st.spinner("Running judge evaluation..."):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=600,
            )
            if result.returncode == 0:
                st.success("Judge evaluation completed successfully.")
                if result.stderr.strip():
                    st.code(result.stderr, language="text")
            else:
                st.error("Judge evaluation failed.")
                if result.stderr.strip():
                    st.code(result.stderr, language="text")
                if result.stdout.strip():
                    st.code(result.stdout, language="text")
        except subprocess.TimeoutExpired:
            st.error("Judge evaluation timed out after 10 minutes.")
        except FileNotFoundError:
            st.error("Could not find Python executable to run judge pipeline.")


# ---------------------------------------------------------------------------
# Side-by-side comparison
# ---------------------------------------------------------------------------


def _render_score_comparison(trials: list[dict]) -> None:
    """Render side-by-side score comparison if multiple template runs exist.

    Detects multiple runs by checking if any trial has judge_scores with
    different dimension sets or timestamps.
    """
    st.markdown("### Score Comparison")

    # Check for trials with judge scores that have dimensions
    judged_trials = [
        t for t in trials if _extract_judge_data(t) is not None
    ]

    if len(judged_trials) < 2:
        st.caption(
            "Side-by-side comparison requires at least 2 judged trials. "
            "Re-run the judge with different templates to compare results."
        )
        return

    # Build comparison by task: show all configs for each task
    task_groups: dict[str, list[dict]] = {}
    for trial in judged_trials:
        task_name = trial.get("task_name", "unknown")
        if task_name not in task_groups:
            task_groups[task_name] = []
        task_groups[task_name].append(trial)

    # Only show tasks with multiple configs
    multi_config_tasks = {
        k: v for k, v in task_groups.items() if len(v) > 1
    }

    if not multi_config_tasks:
        st.caption(
            "No tasks with multiple configuration results found. "
            "Compare results across Baseline, MCP-Base, and MCP-Full configs."
        )
        return

    rows: list[dict] = []
    for task_name, task_trials in sorted(multi_config_tasks.items()):
        for trial in task_trials:
            judge_data = _extract_judge_data(trial)
            if judge_data is None:
                continue
            config = trial.get("agent_config", "unknown")
            rows.append({
                "Task": task_name,
                "Config": _display_config(config),
                "Score": f"{judge_data['mean_score']:.3f}",
                "Quality": judge_data["overall_quality"],
                "Confidence": f"{judge_data['confidence']:.2f}",
                "_config": config,
            })

    if rows:
        df = pd.DataFrame(rows)
        display_df = df.drop(columns=["_config"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.download_button(
            "Export Comparison (CSV)",
            _df_to_csv(display_df),
            file_name="judge_score_comparison.csv",
            mime="text/csv",
            key="jv_comparison_csv",
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def show_judge_viewer() -> None:
    """Main entry point for the LLM Judge Viewer."""
    st.title("LLM Judge")
    st.caption("Review judge evaluation results and re-run with different templates.")
    st.markdown("---")

    # Load data
    categories = _load_experiment_metrics(_DEFAULT_OUTPUT_DIR)

    if not categories:
        st.info(
            "No experiment_metrics.json found in output/ directory. "
            "Run the analysis pipeline from the Home page first."
        )

        # Still show re-run section in case user wants to trigger judge
        _render_rerun_section([])
        return

    flat_trials = _flatten_trials(categories)

    if not flat_trials:
        st.warning("experiment_metrics.json loaded but contains no trial data.")
        return

    # Check if any trials have judge scores
    has_judge_data = any(_extract_judge_data(t) is not None for t in flat_trials)

    if has_judge_data:
        # Aggregated scores table
        _render_aggregated_scores(flat_trials)

        st.markdown("---")

        # Per-task breakdown with expandable vote distribution
        _render_per_task_breakdown(flat_trials)

        st.markdown("---")

        # Side-by-side comparison
        _render_score_comparison(flat_trials)

        st.markdown("---")
    else:
        st.info(
            "No judge scores found in the data. "
            "Run the judge pipeline to evaluate trial outputs."
        )

    # Template selector and re-run section
    _render_rerun_section(flat_trials)
