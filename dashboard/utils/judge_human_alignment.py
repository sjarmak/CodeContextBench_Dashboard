"""
Human alignment score entry for LLM judge evaluation.

Provides a UI for entering human scores alongside LLM judge scores,
with SQLite persistence and progress tracking. Supports per-dimension
scoring on a 1-5 scale with annotator tracking.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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

SESSION_KEY_PREFIX = "judge_human_alignment"

# Default SQLite database path (relative to project root)
HUMAN_SCORES_DB = "data/human_alignment_scores.db"


def _session_key(suffix: str) -> str:
    """Build a session state key for the human alignment tab."""
    return f"{SESSION_KEY_PREFIX}_{suffix}"


@dataclass(frozen=True)
class HumanScore:
    """A single human score entry."""

    task_id: str
    dimension: str
    human_score: int  # 1-5
    llm_score: str  # "1"-"5" or "N/A"
    annotator: str
    timestamp: str  # ISO format


@dataclass(frozen=True)
class TaskAlignmentRow:
    """Row data for the alignment table display."""

    task_id: str
    dimension_scores: tuple[tuple[str, str, int | None], ...]
    # Each: (dimension_name, llm_score, human_score_or_None)


def _get_db_path(project_root: Path) -> Path:
    """Get the path to the human alignment SQLite database.

    Args:
        project_root: Project root directory

    Returns:
        Path to the SQLite database file
    """
    return project_root / HUMAN_SCORES_DB


def init_database(db_path: Path) -> None:
    """Initialize the human alignment scores database.

    Creates the table if it doesn't exist.

    Args:
        db_path: Path to the SQLite database file
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS human_alignment_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                dimension TEXT NOT NULL,
                human_score INTEGER NOT NULL CHECK(human_score BETWEEN 1 AND 5),
                llm_score TEXT NOT NULL,
                annotator TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL,
                UNIQUE(task_id, dimension, annotator)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_human_score(
    db_path: Path,
    task_id: str,
    dimension: str,
    human_score: int,
    llm_score: str,
    annotator: str,
) -> None:
    """Save or update a human score in the database.

    Uses INSERT OR REPLACE to upsert based on (task_id, dimension, annotator).

    Args:
        db_path: Path to the SQLite database
        task_id: Task identifier
        dimension: Scoring dimension name
        human_score: Human-assigned score (1-5)
        llm_score: LLM-assigned score string
        annotator: Name of the human annotator
    """
    if human_score < 1 or human_score > 5:
        raise ValueError(f"human_score must be 1-5, got {human_score}")

    timestamp = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO human_alignment_scores
                (task_id, dimension, human_score, llm_score, annotator, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, dimension, human_score, llm_score, annotator, timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def load_human_scores(
    db_path: Path,
    annotator: str = "",
) -> list[HumanScore]:
    """Load all human scores from the database.

    Args:
        db_path: Path to the SQLite database
        annotator: If provided, filter by annotator

    Returns:
        List of HumanScore entries
    """
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        if annotator:
            cursor.execute(
                """
                SELECT task_id, dimension, human_score, llm_score, annotator, timestamp
                FROM human_alignment_scores
                WHERE annotator = ?
                ORDER BY task_id, dimension
                """,
                (annotator,),
            )
        else:
            cursor.execute(
                """
                SELECT task_id, dimension, human_score, llm_score, annotator, timestamp
                FROM human_alignment_scores
                ORDER BY task_id, dimension
                """
            )

        rows = cursor.fetchall()
        return [
            HumanScore(
                task_id=row[0],
                dimension=row[1],
                human_score=row[2],
                llm_score=row[3],
                annotator=row[4],
                timestamp=row[5],
            )
            for row in rows
        ]
    finally:
        conn.close()


def load_scores_for_tasks(
    db_path: Path,
    task_ids: list[str],
    annotator: str = "",
) -> dict[str, dict[str, int]]:
    """Load human scores for specific tasks.

    Args:
        db_path: Path to the SQLite database
        task_ids: List of task IDs to load scores for
        annotator: If provided, filter by annotator

    Returns:
        Dict of task_id -> {dimension: human_score}
    """
    if not db_path.exists() or not task_ids:
        return {}

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in task_ids)

        if annotator:
            cursor.execute(
                f"""
                SELECT task_id, dimension, human_score
                FROM human_alignment_scores
                WHERE task_id IN ({placeholders}) AND annotator = ?
                ORDER BY task_id, dimension
                """,
                [*task_ids, annotator],
            )
        else:
            cursor.execute(
                f"""
                SELECT task_id, dimension, human_score
                FROM human_alignment_scores
                WHERE task_id IN ({placeholders})
                ORDER BY task_id, dimension
                """,
                task_ids,
            )

        result: dict[str, dict[str, int]] = {}
        for row in cursor.fetchall():
            task_id, dimension, score = row[0], row[1], row[2]
            if task_id not in result:
                result = {**result, task_id: {dimension: score}}
            else:
                result = {
                    **result,
                    task_id: {**result[task_id], dimension: score},
                }

        return result
    finally:
        conn.close()


def count_reviewed_tasks(
    db_path: Path,
    task_ids: list[str],
    dimensions: list[str],
    annotator: str = "",
) -> int:
    """Count how many tasks have been fully reviewed.

    A task is fully reviewed when all dimensions have human scores.

    Args:
        db_path: Path to the SQLite database
        task_ids: List of all task IDs
        dimensions: List of dimension names to check
        annotator: If provided, filter by annotator

    Returns:
        Number of fully reviewed tasks
    """
    if not task_ids or not dimensions:
        return 0

    existing = load_scores_for_tasks(db_path, task_ids, annotator)
    dim_count = len(dimensions)

    reviewed = 0
    for task_id in task_ids:
        task_scores = existing.get(task_id, {})
        scored_dims = sum(1 for d in dimensions if d in task_scores)
        if scored_dims >= dim_count:
            reviewed += 1

    return reviewed


def _run_llm_evaluation(
    config: JudgeConfig,
    tasks: list[tuple[str, Path]],
    progress_callback: object | None = None,
) -> dict[str, TestPromptResult]:
    """Run LLM evaluation on all tasks.

    Args:
        config: Judge config to use
        tasks: List of (task_id, task_dir) tuples
        progress_callback: Optional callable(current, total)

    Returns:
        Dict of task_id -> TestPromptResult
    """
    results: dict[str, TestPromptResult] = {}

    for i, (task_id, task_dir) in enumerate(tasks):
        result = run_test_prompt(config, task_dir, task_id)
        results = {**results, task_id: result}

        if progress_callback is not None:
            progress_callback(i + 1, len(tasks))

    return results


def _build_alignment_table_data(
    tasks: list[tuple[str, Path]],
    llm_results: dict[str, TestPromptResult],
    human_scores: dict[str, dict[str, int]],
    dimensions: list[str],
) -> list[dict]:
    """Build table data for the alignment display.

    Args:
        tasks: List of (task_id, task_dir) tuples
        llm_results: LLM evaluation results by task_id
        human_scores: Human scores by task_id -> dimension -> score
        dimensions: List of dimension names

    Returns:
        List of row dicts for DataFrame
    """
    rows: list[dict] = []

    for task_id, _ in tasks:
        row: dict = {"Task ID": task_id}

        llm_result = llm_results.get(task_id)
        task_human = human_scores.get(task_id, {})

        for dim_name in dimensions:
            # LLM score
            llm_score = "N/A"
            if llm_result and llm_result.dimension_results:
                for dim_result in llm_result.dimension_results:
                    if dim_result.name == dim_name:
                        llm_score = dim_result.score
                        break

            row[f"LLM: {dim_name}"] = llm_score

            # Human score
            human_val = task_human.get(dim_name)
            row[f"Human: {dim_name}"] = human_val if human_val is not None else "-"

        rows.append(row)

    return rows


def _render_progress_indicator(
    reviewed_count: int,
    total_count: int,
) -> None:
    """Render the review progress indicator.

    Args:
        reviewed_count: Number of tasks fully reviewed
        total_count: Total number of tasks
    """
    if total_count == 0:
        st.info("No tasks to review.")
        return

    progress = reviewed_count / total_count
    st.progress(progress)
    st.caption(f"{reviewed_count} of {total_count} tasks reviewed")


def _render_score_entry_table(
    tasks: list[tuple[str, Path]],
    llm_results: dict[str, TestPromptResult],
    human_scores: dict[str, dict[str, int]],
    dimensions: list[str],
    db_path: Path,
    annotator: str,
) -> None:
    """Render the score entry table with editable human score inputs.

    Args:
        tasks: List of (task_id, task_dir) tuples
        llm_results: LLM evaluation results
        human_scores: Existing human scores
        dimensions: Dimension names
        db_path: Path to SQLite database for saving
        annotator: Current annotator name
    """
    if not tasks:
        st.info("No tasks available.")
        return

    for task_idx, (task_id, _) in enumerate(tasks):
        llm_result = llm_results.get(task_id)
        task_human = human_scores.get(task_id, {})

        with st.expander(f"**{task_id}**", expanded=task_idx == 0):
            for dim_name in dimensions:
                # Get LLM score for this dimension
                llm_score = "N/A"
                if llm_result and llm_result.dimension_results:
                    for dim_result in llm_result.dimension_results:
                        if dim_result.name == dim_name:
                            llm_score = dim_result.score
                            break

                col_dim, col_llm, col_human = st.columns([2, 1, 2])

                with col_dim:
                    st.markdown(f"**{dim_name}**")

                with col_llm:
                    st.markdown(f"LLM: **{llm_score}**")

                with col_human:
                    existing_val = task_human.get(dim_name, 0)
                    widget_key = _session_key(
                        f"score_{task_idx}_{dim_name}"
                    )
                    human_val = st.number_input(
                        f"Human score for {dim_name}",
                        min_value=0,
                        max_value=5,
                        value=existing_val,
                        step=1,
                        key=widget_key,
                        label_visibility="collapsed",
                    )

                    # Save when value changes (non-zero)
                    if human_val > 0 and human_val != existing_val:
                        save_human_score(
                            db_path=db_path,
                            task_id=task_id,
                            dimension=dim_name,
                            human_score=human_val,
                            llm_score=llm_score,
                            annotator=annotator,
                        )


def render_human_alignment_tab(project_root: Path) -> None:
    """Render the Human Alignment tab UI.

    Displays a table with LLM scores and editable human score inputs,
    progress indicator, and save functionality.

    Args:
        project_root: Path to the project root directory
    """
    st.subheader("Human Alignment Scoring")
    st.markdown(
        "Enter human scores alongside LLM judge scores to measure "
        "agreement between human and LLM evaluations."
    )

    # Initialize database
    db_path = _get_db_path(project_root)
    init_database(db_path)

    # Annotator name
    annotator = st.text_input(
        "Annotator Name",
        value=st.session_state.get(_session_key("annotator"), ""),
        key=_session_key("annotator_input"),
        help="Your name or identifier for tracking who reviewed each task",
    )
    if annotator:
        st.session_state[_session_key("annotator")] = annotator

    st.markdown("---")

    # Template selector
    infos = list_template_infos(project_root)
    if not infos:
        st.info(
            "No saved templates found. Save a template from the "
            "'Prompt & Rubric Editor' tab first."
        )
        return

    template_names = [info.name for info in infos]
    template_filenames = [info.filename for info in infos]

    selected_template_idx = st.selectbox(
        "Judge Template",
        range(len(template_names)),
        format_func=lambda i: template_names[i],
        key=_session_key("template"),
        help="Template used for LLM evaluation",
    )

    if selected_template_idx is None:
        return

    config = load_config(project_root, template_filenames[selected_template_idx])
    dimension_names = [d.name for d in config.dimensions]

    st.markdown("---")

    # Experiment and task selector
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
        default=task_ids[:10] if len(task_ids) > 10 else task_ids,
        key=_session_key("tasks"),
    )

    if not selected_task_ids:
        st.info("Select at least one task.")
        return

    selected_tasks = [
        (tid, tdir) for tid, tdir in tasks if tid in selected_task_ids
    ]

    st.markdown("---")

    # Run LLM evaluation (or use cached results)
    results_key = _session_key("llm_results")
    exp_key = _session_key("llm_results_exp")

    llm_results: dict[str, TestPromptResult] = st.session_state.get(
        results_key, {}
    )
    cached_exp = st.session_state.get(exp_key, "")

    needs_eval = not llm_results or cached_exp != selected_exp

    if needs_eval:
        if st.button(
            "Run LLM Evaluation",
            key=_session_key("run_eval_btn"),
            type="primary",
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_cb(current: int, total: int) -> None:
                progress_bar.progress(current / total)
                status_text.text(f"Evaluating task {current}/{total}...")

            with st.spinner("Running LLM evaluation..."):
                llm_results = _run_llm_evaluation(
                    config=config,
                    tasks=selected_tasks,
                    progress_callback=progress_cb,
                )

            progress_bar.progress(1.0)
            status_text.text("Evaluation complete!")

            st.session_state[results_key] = llm_results
            st.session_state[exp_key] = selected_exp
            st.rerun()

        st.info(
            "Click 'Run LLM Evaluation' to generate LLM scores for the "
            "selected tasks. Human scoring will be enabled after evaluation."
        )
        return

    # Load existing human scores
    existing_human = load_scores_for_tasks(
        db_path,
        [t[0] for t in selected_tasks],
        annotator=annotator,
    )

    # Progress indicator
    reviewed = count_reviewed_tasks(
        db_path=db_path,
        task_ids=[t[0] for t in selected_tasks],
        dimensions=dimension_names,
        annotator=annotator,
    )
    _render_progress_indicator(reviewed, len(selected_tasks))

    st.markdown("---")

    # Score entry table
    _render_score_entry_table(
        tasks=selected_tasks,
        llm_results=llm_results,
        human_scores=existing_human,
        dimensions=dimension_names,
        db_path=db_path,
        annotator=annotator,
    )
