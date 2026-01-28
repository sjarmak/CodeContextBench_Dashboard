"""
LLM judge A/B comparison mode.

Runs two different judge templates on the same set of tasks and
displays side-by-side score comparisons with summary statistics
including mean scores, correlation, and agreement rate.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.utils.judge_config import (
    JudgeConfig,
    list_template_infos,
    load_config,
)
from dashboard.utils.judge_test_prompt import (
    TestPromptResult,
    _find_experiment_tasks,
    run_test_prompt,
)

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "judge_ab"


def _session_key(suffix: str) -> str:
    """Build a session state key for the A/B comparison."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class TaskComparisonResult:
    """Comparison result for a single task evaluated by both templates."""

    task_id: str
    template_a_result: TestPromptResult
    template_b_result: TestPromptResult


@dataclass(frozen=True)
class ComparisonSummary:
    """Summary statistics for an A/B comparison run."""

    template_a_name: str
    template_b_name: str
    task_count: int
    template_a_mean: float
    template_b_mean: float
    correlation: float
    agreement_rate: float
    task_results: tuple[TaskComparisonResult, ...]


def _parse_score(score_str: str) -> float | None:
    """Parse a score string into a float.

    Args:
        score_str: Score as string (e.g., "3", "4.5", "N/A")

    Returns:
        Float score or None if not parseable
    """
    try:
        return float(score_str)
    except (ValueError, TypeError):
        return None


def _compute_mean_overall_score(results: tuple[TestPromptResult, ...]) -> float:
    """Compute the mean overall score across multiple results.

    Args:
        results: Tuple of TestPromptResult instances

    Returns:
        Mean score, or 0.0 if no valid scores
    """
    scores = [
        s
        for r in results
        if (s := _parse_score(r.overall_score)) is not None
    ]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _compute_pearson_correlation(
    scores_a: list[float],
    scores_b: list[float],
) -> float:
    """Compute Pearson correlation between two lists of scores.

    Uses manual computation to avoid numpy dependency.

    Args:
        scores_a: Scores from template A
        scores_b: Scores from template B

    Returns:
        Pearson correlation coefficient, or 0.0 if not computable
    """
    n = len(scores_a)
    if n < 2 or len(scores_b) != n:
        return 0.0

    mean_a = sum(scores_a) / n
    mean_b = sum(scores_b) / n

    numerator = sum(
        (a - mean_a) * (b - mean_b)
        for a, b in zip(scores_a, scores_b)
    )
    sum_sq_a = sum((a - mean_a) ** 2 for a in scores_a)
    sum_sq_b = sum((b - mean_b) ** 2 for b in scores_b)

    denominator = (sum_sq_a * sum_sq_b) ** 0.5
    if denominator == 0:
        return 0.0

    return numerator / denominator


def _compute_agreement_rate(
    scores_a: list[float],
    scores_b: list[float],
    threshold: float = 1.0,
) -> float:
    """Compute the fraction of tasks where both templates agree within threshold.

    Args:
        scores_a: Scores from template A
        scores_b: Scores from template B
        threshold: Maximum absolute difference for agreement

    Returns:
        Agreement rate as a fraction (0.0 to 1.0)
    """
    if not scores_a or len(scores_a) != len(scores_b):
        return 0.0

    agreements = sum(
        1 for a, b in zip(scores_a, scores_b)
        if abs(a - b) <= threshold
    )
    return agreements / len(scores_a)


def compute_comparison_summary(
    template_a_name: str,
    template_b_name: str,
    task_results: tuple[TaskComparisonResult, ...],
) -> ComparisonSummary:
    """Compute summary statistics for an A/B comparison.

    Args:
        template_a_name: Display name for template A
        template_b_name: Display name for template B
        task_results: Results for each task

    Returns:
        ComparisonSummary with statistics
    """
    results_a = tuple(r.template_a_result for r in task_results)
    results_b = tuple(r.template_b_result for r in task_results)

    mean_a = _compute_mean_overall_score(results_a)
    mean_b = _compute_mean_overall_score(results_b)

    # Build paired score lists for correlation and agreement
    paired_a: list[float] = []
    paired_b: list[float] = []
    for r in task_results:
        score_a = _parse_score(r.template_a_result.overall_score)
        score_b = _parse_score(r.template_b_result.overall_score)
        if score_a is not None and score_b is not None:
            paired_a.append(score_a)
            paired_b.append(score_b)

    correlation = _compute_pearson_correlation(paired_a, paired_b)
    agreement = _compute_agreement_rate(paired_a, paired_b)

    return ComparisonSummary(
        template_a_name=template_a_name,
        template_b_name=template_b_name,
        task_count=len(task_results),
        template_a_mean=mean_a,
        template_b_mean=mean_b,
        correlation=correlation,
        agreement_rate=agreement,
        task_results=task_results,
    )


def run_ab_comparison(
    config_a: JudgeConfig,
    config_b: JudgeConfig,
    template_a_name: str,
    template_b_name: str,
    tasks: list[tuple[str, Path]],
    progress_callback: object | None = None,
) -> ComparisonSummary:
    """Run both judge templates on all tasks and compute comparison.

    Args:
        config_a: Judge config for template A
        config_b: Judge config for template B
        template_a_name: Display name for template A
        template_b_name: Display name for template B
        tasks: List of (task_id, task_dir) tuples
        progress_callback: Optional callable(current, total) for progress

    Returns:
        ComparisonSummary with all results
    """
    task_results: list[TaskComparisonResult] = []

    for i, (task_id, task_dir) in enumerate(tasks):
        result_a = run_test_prompt(config_a, task_dir, task_id)
        result_b = run_test_prompt(config_b, task_dir, task_id)

        task_results.append(
            TaskComparisonResult(
                task_id=task_id,
                template_a_result=result_a,
                template_b_result=result_b,
            )
        )

        if progress_callback is not None:
            progress_callback(i + 1, len(tasks))

    return compute_comparison_summary(
        template_a_name=template_a_name,
        template_b_name=template_b_name,
        task_results=tuple(task_results),
    )


def _build_results_table(summary: ComparisonSummary) -> pd.DataFrame:
    """Build a results DataFrame from a ComparisonSummary.

    Columns: task_id, per-dimension scores for each template, delta.

    Args:
        summary: ComparisonSummary with task results

    Returns:
        DataFrame with comparison data
    """
    rows: list[dict] = []

    for task_result in summary.task_results:
        row: dict = {"Task ID": task_result.task_id}

        # Template A dimension scores
        for dim_result in task_result.template_a_result.dimension_results:
            col_name = f"A: {dim_result.name}"
            row[col_name] = dim_result.score

        # Template A overall
        row["A: Overall"] = task_result.template_a_result.overall_score

        # Template B dimension scores
        for dim_result in task_result.template_b_result.dimension_results:
            col_name = f"B: {dim_result.name}"
            row[col_name] = dim_result.score

        # Template B overall
        row["B: Overall"] = task_result.template_b_result.overall_score

        # Delta (B - A)
        score_a = _parse_score(task_result.template_a_result.overall_score)
        score_b = _parse_score(task_result.template_b_result.overall_score)
        if score_a is not None and score_b is not None:
            row["Delta (B-A)"] = f"{score_b - score_a:+.1f}"
        else:
            row["Delta (B-A)"] = "N/A"

        rows.append(row)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _render_summary_stats(summary: ComparisonSummary) -> None:
    """Render summary statistics as metric cards.

    Args:
        summary: ComparisonSummary with statistics
    """
    st.markdown("### Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            f"Mean Score ({summary.template_a_name})",
            f"{summary.template_a_mean:.2f}",
        )
    with col2:
        st.metric(
            f"Mean Score ({summary.template_b_name})",
            f"{summary.template_b_mean:.2f}",
        )
    with col3:
        st.metric("Correlation", f"{summary.correlation:.3f}")
    with col4:
        st.metric(
            "Agreement Rate",
            f"{summary.agreement_rate:.0%}",
        )


def _render_results_table(summary: ComparisonSummary) -> None:
    """Render the per-task results table.

    Args:
        summary: ComparisonSummary with task results
    """
    st.markdown("### Per-Task Results")

    df = _build_results_table(summary)
    if df.empty:
        st.info("No results to display.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export button
    csv_data = df.to_csv(index=False)
    st.download_button(
        "Export as CSV",
        data=csv_data,
        file_name="ab_comparison_results.csv",
        mime="text/csv",
        key=_session_key("export_csv"),
    )


def _render_comparison_results(summary: ComparisonSummary) -> None:
    """Render the full comparison results display.

    Args:
        summary: ComparisonSummary with all results and stats
    """
    _render_summary_stats(summary)
    st.markdown("---")
    _render_results_table(summary)


def render_ab_comparison_tab(project_root: Path) -> None:
    """Render the A/B Comparison tab UI.

    Displays two template selectors, a task set selector,
    a run button, and results when available.

    Args:
        project_root: Path to the project root directory
    """
    st.subheader("A/B Template Comparison")
    st.markdown(
        "Run two different judge templates on the same tasks "
        "and compare scores side-by-side."
    )

    # Load available templates
    infos = list_template_infos(project_root)

    if len(infos) < 2:
        st.info(
            "At least 2 saved templates are required for A/B comparison. "
            "Save templates from the 'Prompt & Rubric Editor' tab."
        )
        return

    template_names = [info.name for info in infos]
    template_filenames = [info.filename for info in infos]

    # Template selectors
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Template A**")
        selected_a_idx = st.selectbox(
            "Template A",
            range(len(template_names)),
            format_func=lambda i: template_names[i],
            key=_session_key("template_a"),
            label_visibility="collapsed",
        )

    with col_b:
        st.markdown("**Template B**")
        # Default to second template if available
        default_b = 1 if len(template_names) > 1 else 0
        selected_b_idx = st.selectbox(
            "Template B",
            range(len(template_names)),
            format_func=lambda i: template_names[i],
            index=default_b,
            key=_session_key("template_b"),
            label_visibility="collapsed",
        )

    if selected_a_idx is None or selected_b_idx is None:
        return

    if selected_a_idx == selected_b_idx:
        st.warning("Select two different templates for comparison.")
        return

    st.markdown("---")

    # Task set selector
    st.markdown("**Select Tasks to Evaluate**")

    runs_dir = Path(
        os.environ.get(
            "CCB_EXTERNAL_RUNS_DIR",
            os.path.expanduser("~/evals/custom_agents/agents/claudecode/runs"),
        )
    )

    if not runs_dir.exists():
        st.info("No experiments directory found. Set CCB_EXTERNAL_RUNS_DIR.")
        return

    experiments: list[str] = []
    for d in sorted(runs_dir.iterdir(), key=lambda x: x.name):
        if d.is_dir() and not d.name.startswith("."):
            experiments.append(d.name)

    if not experiments:
        st.info("No experiments found.")
        return

    selected_exp = st.selectbox(
        "Experiment",
        experiments,
        key=_session_key("experiment"),
    )

    if not selected_exp:
        return

    tasks = _find_experiment_tasks(runs_dir, selected_exp)
    if not tasks:
        st.info("No tasks found in this experiment.")
        return

    task_ids = [t[0] for t in tasks]
    selected_task_ids = st.multiselect(
        "Tasks",
        task_ids,
        default=task_ids[:5] if len(task_ids) > 5 else task_ids,
        key=_session_key("tasks"),
    )

    if not selected_task_ids:
        st.info("Select at least one task.")
        return

    selected_tasks = [
        (tid, tdir) for tid, tdir in tasks if tid in selected_task_ids
    ]

    st.caption(f"{len(selected_tasks)} task(s) selected")

    st.markdown("---")

    # Run comparison button
    if st.button(
        "Run Comparison",
        key=_session_key("run_btn"),
        type="primary",
    ):
        template_a_filename = template_filenames[selected_a_idx]
        template_b_filename = template_filenames[selected_b_idx]

        config_a = load_config(project_root, template_a_filename)
        config_b = load_config(project_root, template_b_filename)

        template_a_name = template_names[selected_a_idx]
        template_b_name = template_names[selected_b_idx]

        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress_callback(current: int, total: int) -> None:
            progress_bar.progress(current / total)
            status_text.text(
                f"Evaluating task {current}/{total}..."
            )

        with st.spinner("Running A/B comparison..."):
            summary = run_ab_comparison(
                config_a=config_a,
                config_b=config_b,
                template_a_name=template_a_name,
                template_b_name=template_b_name,
                tasks=selected_tasks,
                progress_callback=progress_callback,
            )

        progress_bar.progress(1.0)
        status_text.text("Comparison complete!")

        st.session_state[_session_key("results")] = summary
        st.rerun()

    # Display previous results
    prev_results = st.session_state.get(_session_key("results"))
    if prev_results is not None:
        _render_comparison_results(prev_results)
