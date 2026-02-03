"""Human annotation collection tool for judge training data.

Provides a Streamlit view for collecting human preference judgments
across three annotation modes: pairwise, direct, and reference-based.
Annotations are saved to JSONL for DPO fine-tuning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ANNOTATIONS_DIR = _PROJECT_ROOT / "data" / "human_annotations"
_ANNOTATIONS_FILE = _ANNOTATIONS_DIR / "annotations.jsonl"
_EXPERIMENTS_DIR = _PROJECT_ROOT / "eval_runs_v2" / "judge_experiments"
_EXTERNAL_RUNS_DIR = Path(
    __import__("os").environ.get(
        "CCB_EXTERNAL_RUNS_DIR",
        str(Path.home() / "evals" / "custom_agents" / "agents" / "claudecode" / "runs"),
    )
)
_ANNOTATION_TARGET = 200


@dataclass(frozen=True)
class AnnotationTask:
    """A single task presented for annotation."""

    task_id: str
    task_description: str
    agent_outputs: dict[str, str]
    reference_answer: str = ""
    evaluation_criteria: str = ""
    source: str = ""


@dataclass(frozen=True)
class Annotation:
    """A single human annotation record."""

    annotator_id: str
    timestamp: str
    task_id: str
    mode: str
    scores: dict[str, Any] = field(default_factory=dict)
    preference: str = ""
    reasoning: str = ""


def _load_annotations() -> list[dict[str, Any]]:
    """Load existing annotations from JSONL file."""
    if not _ANNOTATIONS_FILE.exists():
        return []
    annotations: list[dict[str, Any]] = []
    try:
        with open(_ANNOTATIONS_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        annotations.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError as exc:
        logger.warning("Failed to read annotations: %s", exc)
    return annotations


def _save_annotation(annotation: Annotation) -> None:
    """Append a single annotation to JSONL file."""
    _ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "annotator_id": annotation.annotator_id,
        "timestamp": annotation.timestamp,
        "task_id": annotation.task_id,
        "mode": annotation.mode,
        "scores": dict(annotation.scores),
        "preference": annotation.preference,
        "reasoning": annotation.reasoning,
    }
    with open(_ANNOTATIONS_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _load_tasks_from_experiments() -> list[AnnotationTask]:
    """Load tasks from judge experiment results."""
    tasks: list[AnnotationTask] = []

    if not _EXPERIMENTS_DIR.is_dir():
        return tasks

    for exp_dir in sorted(_EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
            continue
        results_path = exp_dir / "results.json"
        if not results_path.exists():
            continue
        try:
            with open(results_path) as f:
                data = json.load(f)
            for result in data.get("results", []):
                task_id = result.get("task_id", "")
                if not task_id:
                    continue
                desc = result.get("task_description", task_id)
                agent_output = result.get("agent_output", "")
                reference = result.get("reference_answer", "")
                criteria = result.get("evaluation_criteria", "")
                tasks.append(
                    AnnotationTask(
                        task_id=task_id,
                        task_description=desc,
                        agent_outputs={"default": agent_output} if agent_output else {},
                        reference_answer=reference,
                        evaluation_criteria=criteria,
                        source=exp_dir.name,
                    )
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load experiment %s: %s", exp_dir.name, exc)

    return tasks


def _load_tasks_from_runs() -> list[AnnotationTask]:
    """Load tasks from raw run directories."""
    tasks: list[AnnotationTask] = []

    if not _EXTERNAL_RUNS_DIR.is_dir():
        return tasks

    for run_dir in sorted(_EXTERNAL_RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        result_path = run_dir / "result.json"
        if not result_path.exists():
            continue
        try:
            with open(result_path) as f:
                data = json.load(f)
            task_name = data.get("task_name", "")
            if not task_name:
                task_id_raw = data.get("task_id")
                if isinstance(task_id_raw, dict):
                    task_name = task_id_raw.get("path", "")
                elif isinstance(task_id_raw, str):
                    task_name = task_id_raw
            if not task_name:
                continue

            agent_output = _extract_agent_output(run_dir)
            if not agent_output:
                continue

            tasks.append(
                AnnotationTask(
                    task_id=task_name,
                    task_description=task_name,
                    agent_outputs={run_dir.name: agent_output},
                    source=f"runs/{run_dir.name}",
                )
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load run %s: %s", run_dir.name, exc)

    return tasks


def _extract_agent_output(run_dir: Path) -> str:
    """Extract agent output from a run directory."""
    solution_path = run_dir / "logs" / "agent" / "solution.md"
    if solution_path.exists():
        try:
            return solution_path.read_text(errors="replace")[:20000]
        except OSError:
            pass

    agent_dir = run_dir / "logs" / "agent"
    if agent_dir.is_dir():
        for md_file in sorted(agent_dir.glob("*.md")):
            try:
                return md_file.read_text(errors="replace")[:20000]
            except OSError:
                continue

    submission_path = run_dir / "submission.txt"
    if submission_path.exists():
        try:
            return submission_path.read_text(errors="replace")[:20000]
        except OSError:
            pass

    return ""


def _merge_tasks_by_id(
    experiment_tasks: list[AnnotationTask],
    run_tasks: list[AnnotationTask],
) -> list[AnnotationTask]:
    """Merge tasks from experiments and runs, combining outputs per task_id."""
    by_id: dict[str, dict[str, Any]] = {}

    for task in experiment_tasks + run_tasks:
        if task.task_id not in by_id:
            by_id[task.task_id] = {
                "task_id": task.task_id,
                "task_description": task.task_description,
                "agent_outputs": dict(task.agent_outputs),
                "reference_answer": task.reference_answer,
                "evaluation_criteria": task.evaluation_criteria,
                "source": task.source,
            }
        else:
            existing = by_id[task.task_id]
            existing["agent_outputs"] = {
                **existing["agent_outputs"],
                **task.agent_outputs,
            }
            if task.reference_answer and not existing["reference_answer"]:
                existing["reference_answer"] = task.reference_answer
            if task.evaluation_criteria and not existing["evaluation_criteria"]:
                existing["evaluation_criteria"] = task.evaluation_criteria

    return [
        AnnotationTask(
            task_id=data["task_id"],
            task_description=data["task_description"],
            agent_outputs=data["agent_outputs"],
            reference_answer=data["reference_answer"],
            evaluation_criteria=data["evaluation_criteria"],
            source=data["source"],
        )
        for data in by_id.values()
    ]


def _init_session_state() -> None:
    """Initialize session state for annotation view."""
    if "annotation_annotator" not in st.session_state:
        st.session_state.annotation_annotator = ""
    if "annotation_task_index" not in st.session_state:
        st.session_state.annotation_task_index = 0
    if "annotation_mode" not in st.session_state:
        st.session_state.annotation_mode = "pairwise"


def _render_progress_bar(annotation_count: int) -> None:
    """Render annotation progress indicator."""
    progress = min(annotation_count / _ANNOTATION_TARGET, 1.0)
    st.progress(progress)
    st.caption(f"{annotation_count} annotations collected, target {_ANNOTATION_TARGET}")


def _render_pairwise_annotation(
    task: AnnotationTask,
    annotator_id: str,
) -> None:
    """Render pairwise preference selection interface."""
    outputs = task.agent_outputs
    if len(outputs) < 2:
        st.warning("Pairwise mode requires at least 2 agent outputs for this task.")
        return

    condition_names = sorted(outputs.keys())

    st.markdown(f"**Task:** {task.task_description}")
    st.markdown("---")

    cols = st.columns(len(condition_names))
    for idx, name in enumerate(condition_names):
        with cols[idx]:
            st.markdown(f"**Output {idx + 1}** (`{name}`)")
            content = outputs[name]
            display = content[:3000] + "..." if len(content) > 3000 else content
            st.text_area(
                f"Content ({name})",
                value=display,
                height=300,
                disabled=True,
                key=f"annot_pairwise_output_{task.task_id}_{name}",
            )

    preference = st.radio(
        "Which output is better?",
        options=condition_names + ["Tie"],
        key=f"annot_pairwise_pref_{task.task_id}",
        horizontal=True,
    )

    reasoning = st.text_area(
        "Reasoning (why this preference?)",
        key=f"annot_pairwise_reason_{task.task_id}",
        height=100,
    )

    if st.button("Submit Pairwise Annotation", key=f"annot_pairwise_submit_{task.task_id}"):
        if not annotator_id:
            st.error("Please enter your annotator name above.")
            return
        annotation = Annotation(
            annotator_id=annotator_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task.task_id,
            mode="pairwise",
            preference=preference or "",
            reasoning=reasoning,
            scores={"conditions": condition_names},
        )
        _save_annotation(annotation)
        st.success("Annotation saved.")
        st.rerun()


def _render_direct_annotation(
    task: AnnotationTask,
    annotator_id: str,
) -> None:
    """Render direct score assignment interface (1-5 per dimension)."""
    outputs = task.agent_outputs
    if not outputs:
        st.warning("No agent output available for this task.")
        return

    output_key = sorted(outputs.keys())[0]
    output_content = outputs[output_key]

    st.markdown(f"**Task:** {task.task_description}")
    st.markdown("---")

    display = output_content[:5000] + "..." if len(output_content) > 5000 else output_content
    st.text_area(
        "Agent Output",
        value=display,
        height=300,
        disabled=True,
        key=f"annot_direct_output_{task.task_id}",
    )

    dimensions = [
        "Correctness",
        "Completeness",
        "Code Quality",
        "Efficiency",
        "Security",
    ]

    st.markdown("**Score each dimension (1-5):**")
    scores: dict[str, int] = {}
    cols = st.columns(len(dimensions))
    for idx, dim in enumerate(dimensions):
        with cols[idx]:
            score = st.selectbox(
                dim,
                options=[1, 2, 3, 4, 5],
                index=2,
                key=f"annot_direct_score_{task.task_id}_{dim}",
            )
            scores[dim] = score

    reasoning = st.text_area(
        "Overall reasoning",
        key=f"annot_direct_reason_{task.task_id}",
        height=100,
    )

    if st.button("Submit Direct Annotation", key=f"annot_direct_submit_{task.task_id}"):
        if not annotator_id:
            st.error("Please enter your annotator name above.")
            return
        annotation = Annotation(
            annotator_id=annotator_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task.task_id,
            mode="direct",
            scores=dict(scores),
            reasoning=reasoning,
        )
        _save_annotation(annotation)
        st.success("Annotation saved.")
        st.rerun()


def _render_reference_annotation(
    task: AnnotationTask,
    annotator_id: str,
) -> None:
    """Render reference correctness rating interface (pass/partial/fail)."""
    outputs = task.agent_outputs
    if not outputs:
        st.warning("No agent output available for this task.")
        return

    output_key = sorted(outputs.keys())[0]
    output_content = outputs[output_key]

    st.markdown(f"**Task:** {task.task_description}")
    st.markdown("---")

    col_out, col_ref = st.columns(2)

    with col_out:
        st.markdown("**Agent Output**")
        display = output_content[:3000] + "..." if len(output_content) > 3000 else output_content
        st.text_area(
            "Agent Output",
            value=display,
            height=300,
            disabled=True,
            key=f"annot_ref_agent_{task.task_id}",
            label_visibility="collapsed",
        )

    with col_ref:
        st.markdown("**Reference Answer**")
        ref = task.reference_answer or "(No reference available)"
        ref_display = ref[:3000] + "..." if len(ref) > 3000 else ref
        st.text_area(
            "Reference",
            value=ref_display,
            height=300,
            disabled=True,
            key=f"annot_ref_reference_{task.task_id}",
            label_visibility="collapsed",
        )

    if task.evaluation_criteria:
        with st.expander("Evaluation Criteria"):
            st.markdown(task.evaluation_criteria)

    rating_options = ["pass", "partial", "fail"]
    dimensions = ["Oracle Correctness", "Oracle Completeness", "Approach Alignment"]

    scores: dict[str, str] = {}
    cols = st.columns(len(dimensions))
    for idx, dim in enumerate(dimensions):
        with cols[idx]:
            rating = st.radio(
                dim,
                options=rating_options,
                key=f"annot_ref_rating_{task.task_id}_{dim}",
            )
            scores[dim] = rating

    reasoning = st.text_area(
        "Reasoning",
        key=f"annot_ref_reason_{task.task_id}",
        height=100,
    )

    if st.button("Submit Reference Annotation", key=f"annot_ref_submit_{task.task_id}"):
        if not annotator_id:
            st.error("Please enter your annotator name above.")
            return
        annotation = Annotation(
            annotator_id=annotator_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task.task_id,
            mode="reference",
            scores=dict(scores),
            reasoning=reasoning,
        )
        _save_annotation(annotation)
        st.success("Annotation saved.")
        st.rerun()


def show_judge_annotation() -> None:
    """Main entry point for the human annotation collection view."""
    _init_session_state()

    st.title("Human Annotation Collection")
    st.caption("Collect human preference judgments for judge training data")

    existing_annotations = _load_annotations()
    _render_progress_bar(len(existing_annotations))

    st.markdown("---")

    config_col1, config_col2 = st.columns([1, 2])

    with config_col1:
        annotator = st.text_input(
            "Annotator Name",
            value=st.session_state.annotation_annotator,
            key="annot_annotator_input",
        )
        if annotator != st.session_state.annotation_annotator:
            st.session_state.annotation_annotator = annotator

    with config_col2:
        mode = st.radio(
            "Annotation Mode",
            options=["pairwise", "direct", "reference"],
            index=["pairwise", "direct", "reference"].index(
                st.session_state.annotation_mode
            ),
            horizontal=True,
            key="annot_mode_radio",
        )
        if mode != st.session_state.annotation_mode:
            st.session_state.annotation_mode = mode

    st.markdown("---")

    with st.spinner("Loading tasks..."):
        experiment_tasks = _load_tasks_from_experiments()
        run_tasks = _load_tasks_from_runs()
        all_tasks = _merge_tasks_by_id(experiment_tasks, run_tasks)

    if not all_tasks:
        st.info(
            "No tasks found. Run judge evaluations first or ensure run directories "
            "contain result.json files."
        )
        return

    task_count = len(all_tasks)
    current_index = st.session_state.annotation_task_index
    if current_index >= task_count:
        st.session_state.annotation_task_index = 0
        current_index = 0

    nav_col1, nav_col2, nav_col3 = st.columns([1, 3, 1])

    with nav_col1:
        if st.button(
            "Previous",
            key="annot_nav_prev",
            disabled=(current_index == 0),
        ):
            st.session_state.annotation_task_index = max(0, current_index - 1)
            st.rerun()

    with nav_col2:
        st.markdown(
            f"Task {current_index + 1} of {task_count}",
        )

    with nav_col3:
        if st.button(
            "Next",
            key="annot_nav_next",
            disabled=(current_index >= task_count - 1),
        ):
            st.session_state.annotation_task_index = min(
                task_count - 1, current_index + 1
            )
            st.rerun()

    st.markdown("---")

    task = all_tasks[current_index]

    annotator_id = st.session_state.annotation_annotator
    annotation_mode = st.session_state.annotation_mode

    if annotation_mode == "pairwise":
        _render_pairwise_annotation(task, annotator_id)
    elif annotation_mode == "direct":
        _render_direct_annotation(task, annotator_id)
    elif annotation_mode == "reference":
        _render_reference_annotation(task, annotator_id)

    with st.expander("Recent Annotations"):
        recent = existing_annotations[-10:] if existing_annotations else []
        if recent:
            for ann in reversed(recent):
                st.caption(
                    f"{ann.get('annotator_id', '?')} | "
                    f"{ann.get('mode', '?')} | "
                    f"{ann.get('task_id', '?')[:40]} | "
                    f"{ann.get('timestamp', '?')[:19]}"
                )
        else:
            st.caption("No annotations yet.")
