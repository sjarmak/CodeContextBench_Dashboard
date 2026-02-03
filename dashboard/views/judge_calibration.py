"""Judge calibration and quality metrics dashboard view.

Displays human-judge alignment metrics, calibration curves, per-model
performance, confusion matrices, and flagged disagreements. Uses data
from human annotations and judge experiment results.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import streamlit as st

from src.judge.metrics import compute_cohens_kappa, compute_spearman_correlation

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ANNOTATIONS_DIR = _PROJECT_ROOT / "data" / "human_annotations"
_ANNOTATIONS_FILE = _ANNOTATIONS_DIR / "annotations.jsonl"
_EXPERIMENTS_DIR = _PROJECT_ROOT / "eval_runs_v2" / "judge_experiments"
_ANNOTATION_THRESHOLD = 50


@dataclass(frozen=True)
class CalibrationData:
    """Paired human and model scores for a single task."""

    task_id: str
    human_score: float
    model_score: float
    model_id: str
    human_category: str = ""
    model_category: str = ""
    dimension_scores: dict[str, float] = field(default_factory=dict)
    human_dimension_scores: dict[str, float] = field(default_factory=dict)


def _categorize_score(score: float) -> str:
    """Categorize a continuous score into pass/partial/fail."""
    if score >= 0.75:
        return "pass"
    if score >= 0.25:
        return "partial"
    return "fail"


def _load_annotations() -> list[dict[str, Any]]:
    """Load human annotations from JSONL file."""
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


def _extract_human_scores(
    annotations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Extract per-task human scores from annotations.

    Returns dict mapping task_id to {score, category, dimension_scores}.
    Averages multiple annotations for the same task.
    """
    by_task: dict[str, list[dict[str, Any]]] = {}

    for ann in annotations:
        task_id = ann.get("task_id", "")
        if not task_id:
            continue
        if task_id not in by_task:
            by_task[task_id] = []
        by_task[task_id].append(ann)

    result: dict[str, dict[str, Any]] = {}

    for task_id, task_anns in by_task.items():
        scores: list[float] = []
        dim_scores: dict[str, list[float]] = {}

        for ann in task_anns:
            mode = ann.get("mode", "")
            ann_scores = ann.get("scores", {})

            if mode == "direct":
                dim_vals = []
                for dim_name, val in ann_scores.items():
                    if isinstance(val, (int, float)):
                        normalized = val / 5.0
                        dim_vals.append(normalized)
                        if dim_name not in dim_scores:
                            dim_scores[dim_name] = []
                        dim_scores[dim_name].append(normalized)
                if dim_vals:
                    scores.append(sum(dim_vals) / len(dim_vals))

            elif mode == "reference":
                rating_map = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
                dim_vals = []
                for dim_name, val in ann_scores.items():
                    if isinstance(val, str) and val in rating_map:
                        mapped = rating_map[val]
                        dim_vals.append(mapped)
                        if dim_name not in dim_scores:
                            dim_scores[dim_name] = []
                        dim_scores[dim_name].append(mapped)
                if dim_vals:
                    scores.append(sum(dim_vals) / len(dim_vals))

            elif mode == "pairwise":
                scores.append(1.0)

        if scores:
            avg_score = sum(scores) / len(scores)
            avg_dims = {
                dim: sum(vals) / len(vals) for dim, vals in dim_scores.items()
            }
            result[task_id] = {
                "score": avg_score,
                "category": _categorize_score(avg_score),
                "dimension_scores": avg_dims,
            }

    return result


def _load_experiment_results() -> list[dict[str, Any]]:
    """Load judge experiment results with per-task scores."""
    experiments: list[dict[str, Any]] = []

    if not _EXPERIMENTS_DIR.is_dir():
        return experiments

    for exp_dir in sorted(_EXPERIMENTS_DIR.iterdir()):
        if not exp_dir.is_dir() or not exp_dir.name.startswith("exp_"):
            continue
        results_path = exp_dir / "results.json"
        config_path = exp_dir / "config.json"
        if not results_path.exists():
            continue
        try:
            with open(results_path) as f:
                data = json.load(f)
            config = {}
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            model_id = config.get("model_id", exp_dir.name)
            if isinstance(model_id, list):
                model_id = ", ".join(model_id)

            task_scores: dict[str, dict[str, Any]] = {}
            for result in data.get("results", []):
                task_id = result.get("task_id", "")
                if not task_id:
                    continue
                overall = result.get("overall_score")
                if overall is None:
                    overall = result.get("consensus_score")
                if overall is None:
                    continue
                dim_scores = {}
                scores_dict = result.get("scores", {})
                for dim_name, dim_data in scores_dict.items():
                    if isinstance(dim_data, dict):
                        dim_scores[dim_name] = dim_data.get("score", 0.0)
                    elif isinstance(dim_data, (int, float)):
                        dim_scores[dim_name] = float(dim_data)

                task_scores[task_id] = {
                    "score": float(overall),
                    "category": _categorize_score(float(overall)),
                    "dimension_scores": dim_scores,
                }

            if task_scores:
                experiments.append({
                    "experiment_id": exp_dir.name,
                    "model_id": model_id,
                    "task_scores": task_scores,
                })
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load experiment %s: %s", exp_dir.name, exc)

    return experiments


def _build_calibration_data(
    human_scores: dict[str, dict[str, Any]],
    experiments: list[dict[str, Any]],
) -> list[CalibrationData]:
    """Build paired calibration data from human and model scores."""
    pairs: list[CalibrationData] = []

    for exp in experiments:
        model_id = exp.get("model_id", "unknown")
        task_scores = exp.get("task_scores", {})

        for task_id, model_data in task_scores.items():
            if task_id not in human_scores:
                continue
            human_data = human_scores[task_id]

            pairs.append(CalibrationData(
                task_id=task_id,
                human_score=human_data["score"],
                model_score=model_data["score"],
                model_id=model_id,
                human_category=human_data["category"],
                model_category=model_data["category"],
                dimension_scores=model_data.get("dimension_scores", {}),
                human_dimension_scores=human_data.get("dimension_scores", {}),
            ))

    return pairs


def _compute_per_model_metrics(
    calibration_data: list[CalibrationData],
) -> list[dict[str, Any]]:
    """Compute alignment metrics grouped by model."""
    by_model: dict[str, list[CalibrationData]] = {}
    for cd in calibration_data:
        if cd.model_id not in by_model:
            by_model[cd.model_id] = []
        by_model[cd.model_id].append(cd)

    results: list[dict[str, Any]] = []

    for model_id, pairs in sorted(by_model.items()):
        human_scores = [p.human_score for p in pairs]
        model_scores = [p.model_score for p in pairs]

        rho, p_value = compute_spearman_correlation(human_scores, model_scores)

        human_cats = [p.human_category for p in pairs]
        model_cats = [p.model_category for p in pairs]
        kappa = compute_cohens_kappa(human_cats, model_cats)

        results.append({
            "model_id": model_id,
            "spearman_rho": rho,
            "spearman_p": p_value,
            "cohens_kappa": kappa,
            "n_tasks": len(pairs),
        })

    return results


def _compute_per_dimension_accuracy(
    calibration_data: list[CalibrationData],
) -> list[dict[str, Any]]:
    """Compute per-dimension categorical accuracy between human and model."""
    dim_data: dict[str, dict[str, list]] = {}

    for cd in calibration_data:
        for dim_name, model_val in cd.dimension_scores.items():
            human_val = cd.human_dimension_scores.get(dim_name)
            if human_val is None:
                continue
            if dim_name not in dim_data:
                dim_data[dim_name] = {"human": [], "model": []}
            dim_data[dim_name]["human"].append(human_val)
            dim_data[dim_name]["model"].append(model_val)

    results: list[dict[str, Any]] = []

    for dim_name, data in sorted(dim_data.items()):
        human_cats = [_categorize_score(s) for s in data["human"]]
        model_cats = [_categorize_score(s) for s in data["model"]]

        matches = sum(1 for h, m in zip(human_cats, model_cats) if h == m)
        accuracy = matches / len(human_cats) if human_cats else 0.0

        common_errors: list[str] = []
        error_counts: dict[str, int] = {}
        for h, m in zip(human_cats, model_cats):
            if h != m:
                err = f"human={h}, model={m}"
                error_counts[err] = error_counts.get(err, 0) + 1
        if error_counts:
            sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
            common_errors = [f"{err} ({cnt}x)" for err, cnt in sorted_errors[:3]]

        results.append({
            "dimension": dim_name,
            "accuracy": accuracy,
            "n_samples": len(human_cats),
            "common_errors": ", ".join(common_errors) if common_errors else "none",
        })

    return results


def _build_confusion_matrix(
    calibration_data: list[CalibrationData],
) -> dict[str, Any]:
    """Build confusion matrix for pass/partial/fail categories."""
    categories = ["pass", "partial", "fail"]
    matrix = [[0] * len(categories) for _ in range(len(categories))]
    cat_idx = {cat: i for i, cat in enumerate(categories)}

    for cd in calibration_data:
        h_idx = cat_idx.get(cd.human_category)
        m_idx = cat_idx.get(cd.model_category)
        if h_idx is not None and m_idx is not None:
            matrix[h_idx][m_idx] += 1

    return {
        "categories": categories,
        "matrix": matrix,
    }


def _find_disagreements(
    calibration_data: list[CalibrationData],
    threshold: float = 1.0,
) -> list[dict[str, Any]]:
    """Find cases where judge and human differ by more than threshold.

    Uses a threshold on the absolute difference when scores are on 0-1 scale.
    A threshold of 1.0 maps to '>1 point' if scores were on a 0-5 scale
    (i.e., >0.2 on normalized 0-1 scale).
    """
    normalized_threshold = threshold / 5.0

    disagreements: list[dict[str, Any]] = []
    for cd in calibration_data:
        diff = abs(cd.human_score - cd.model_score)
        if diff > normalized_threshold:
            disagreements.append({
                "task_id": cd.task_id,
                "model_id": cd.model_id,
                "human_score": cd.human_score,
                "model_score": cd.model_score,
                "difference": diff,
                "human_category": cd.human_category,
                "model_category": cd.model_category,
            })

    return sorted(disagreements, key=lambda x: x["difference"], reverse=True)


def _render_annotation_progress(annotation_count: int) -> None:
    """Render annotation count vs threshold with appropriate messaging."""
    progress = min(annotation_count / _ANNOTATION_THRESHOLD, 1.0)
    st.progress(progress)

    if annotation_count < _ANNOTATION_THRESHOLD:
        st.warning(
            f"Only {annotation_count} annotations collected "
            f"(minimum {_ANNOTATION_THRESHOLD} needed for reliable calibration). "
            "Navigate to **Annotate** view to collect more annotations."
        )
    else:
        st.success(
            f"{annotation_count} annotations collected "
            f"(above {_ANNOTATION_THRESHOLD} minimum threshold)"
        )


def _render_alignment_metrics(
    per_model_metrics: list[dict[str, Any]],
) -> None:
    """Render Spearman and Cohen's kappa as metric cards."""
    if not per_model_metrics:
        st.info("No alignment data available. Need both human annotations and judge results for common tasks.")
        return

    st.subheader("Human-Judge Alignment")

    if len(per_model_metrics) == 1:
        m = per_model_metrics[0]
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Spearman Correlation", f"{m['spearman_rho']:.3f}")
        with col2:
            st.metric("Cohen's Kappa", f"{m['cohens_kappa']:.3f}")
        with col3:
            st.metric("Common Tasks", str(m["n_tasks"]))
    else:
        cols = st.columns(min(len(per_model_metrics), 4))
        for idx, m in enumerate(per_model_metrics):
            with cols[idx % len(cols)]:
                st.markdown(f"**{m['model_id'][:30]}**")
                st.metric(
                    "Spearman rho",
                    f"{m['spearman_rho']:.3f}",
                    key=f"calib_spearman_{idx}",
                )
                st.metric(
                    "Cohen's kappa",
                    f"{m['cohens_kappa']:.3f}",
                    key=f"calib_kappa_{idx}",
                )
                st.caption(f"{m['n_tasks']} tasks")


def _render_calibration_curve(calibration_data: list[CalibrationData]) -> None:
    """Render calibration scatter plot of predicted vs human scores."""
    if not calibration_data:
        return

    st.subheader("Calibration Curve")

    try:
        import plotly.graph_objects as go

        by_model: dict[str, list[CalibrationData]] = {}
        for cd in calibration_data:
            if cd.model_id not in by_model:
                by_model[cd.model_id] = []
            by_model[cd.model_id].append(cd)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line={"dash": "dash", "color": "gray", "width": 1},
            name="Perfect calibration",
            showlegend=True,
        ))

        colors = ["#4a9eff", "#ff6b6b", "#66bb6a", "#ffa726"]
        for idx, (model_id, pairs) in enumerate(sorted(by_model.items())):
            human = [p.human_score for p in pairs]
            model = [p.model_score for p in pairs]
            tasks = [p.task_id[:30] for p in pairs]
            color = colors[idx % len(colors)]

            fig.add_trace(go.Scatter(
                x=human,
                y=model,
                mode="markers",
                marker={"size": 8, "color": color, "opacity": 0.7},
                name=model_id[:30],
                text=tasks,
                hovertemplate="Human: %{x:.2f}<br>Model: %{y:.2f}<br>Task: %{text}",
            ))

        fig.update_layout(
            title="Predicted vs Human Score",
            xaxis_title="Human Score",
            yaxis_title="Model Score",
            xaxis={"range": [0, 1]},
            yaxis={"range": [0, 1]},
            template="plotly_dark",
            height=500,
        )
        st.plotly_chart(fig, use_container_width=True, key="calib_scatter")

    except ImportError:
        st.caption("Install plotly for interactive charts: pip install plotly")
        rows = [
            {
                "Task": cd.task_id[:30],
                "Human": f"{cd.human_score:.3f}",
                "Model": f"{cd.model_score:.3f}",
                "Model ID": cd.model_id[:20],
            }
            for cd in calibration_data
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_per_model_table(per_model_metrics: list[dict[str, Any]]) -> None:
    """Render per-model performance table."""
    if not per_model_metrics:
        return

    st.subheader("Per-Model Performance")

    rows = [
        {
            "Model": m["model_id"][:40],
            "Spearman rho": f"{m['spearman_rho']:.3f}",
            "Cohen's kappa": f"{m['cohens_kappa']:.3f}",
            "Tasks": m["n_tasks"],
        }
        for m in per_model_metrics
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_dimension_accuracy_table(
    dimension_accuracy: list[dict[str, Any]],
) -> None:
    """Render per-dimension accuracy table."""
    if not dimension_accuracy:
        return

    st.subheader("Per-Dimension Accuracy")

    rows = [
        {
            "Dimension": d["dimension"],
            "Accuracy": f"{d['accuracy']:.1%}",
            "Samples": d["n_samples"],
            "Common Errors": d["common_errors"],
        }
        for d in dimension_accuracy
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_confusion_matrix(confusion_data: dict[str, Any]) -> None:
    """Render confusion matrix as a Plotly heatmap."""
    categories = confusion_data.get("categories", [])
    matrix = confusion_data.get("matrix", [])

    if not categories or not matrix:
        return

    st.subheader("Confusion Matrix (Human vs Model)")

    try:
        import plotly.graph_objects as go

        text_labels = [
            [str(matrix[i][j]) for j in range(len(categories))]
            for i in range(len(categories))
        ]

        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=[f"Model: {c}" for c in categories],
            y=[f"Human: {c}" for c in categories],
            colorscale="Blues",
            text=text_labels,
            texttemplate="%{text}",
            hovertemplate="Human: %{y}<br>Model: %{x}<br>Count: %{z}",
        ))
        fig.update_layout(
            title="Categorical Score Agreement",
            template="plotly_dark",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True, key="calib_confusion")

    except ImportError:
        rows = []
        for i, row_cat in enumerate(categories):
            row = {"Human \\ Model": row_cat}
            for j, col_cat in enumerate(categories):
                row[col_cat] = matrix[i][j]
            rows.append(row)
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_disagreements(disagreements: list[dict[str, Any]]) -> None:
    """Render flagged disagreements where judge and human differ significantly."""
    st.subheader("Flagged Disagreements")

    if not disagreements:
        st.info("No significant disagreements found (threshold: >1 point on 5-point scale).")
        return

    st.caption(
        f"{len(disagreements)} cases where judge and human differ "
        "by more than 1 point (on 5-point scale)"
    )

    rows = [
        {
            "Task": d["task_id"][:40],
            "Model": d["model_id"][:20],
            "Human Score": f"{d['human_score']:.3f}",
            "Model Score": f"{d['model_score']:.3f}",
            "Difference": f"{d['difference']:.3f}",
            "Human Category": d["human_category"],
            "Model Category": d["model_category"],
        }
        for d in disagreements[:20]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_judge_calibration() -> None:
    """Main entry point for the judge calibration and quality metrics view."""
    st.title("Judge Calibration & Quality Metrics")
    st.caption(
        "Analyze human-judge alignment, calibration curves, and per-model "
        "quality metrics to validate judge reliability"
    )

    annotations = _load_annotations()
    annotation_count = len(annotations)

    _render_annotation_progress(annotation_count)

    if annotation_count < _ANNOTATION_THRESHOLD:
        st.markdown("---")
        st.info(
            "Collect more annotations to enable calibration analysis. "
            "Go to the **Annotate** view from the sidebar navigation."
        )

    st.markdown("---")

    human_scores = _extract_human_scores(annotations)
    experiments = _load_experiment_results()
    calibration_data = _build_calibration_data(human_scores, experiments)

    if not calibration_data:
        st.warning(
            "No paired human-judge data available. Ensure both human annotations "
            "and judge experiment results exist for common tasks."
        )
        return

    per_model_metrics = _compute_per_model_metrics(calibration_data)
    dimension_accuracy = _compute_per_dimension_accuracy(calibration_data)
    confusion = _build_confusion_matrix(calibration_data)
    disagreements = _find_disagreements(calibration_data)

    _render_alignment_metrics(per_model_metrics)
    st.markdown("---")

    _render_calibration_curve(calibration_data)
    st.markdown("---")

    _render_per_model_table(per_model_metrics)
    st.markdown("---")

    _render_dimension_accuracy_table(dimension_accuracy)
    st.markdown("---")

    _render_confusion_matrix(confusion)
    st.markdown("---")

    _render_disagreements(disagreements)
