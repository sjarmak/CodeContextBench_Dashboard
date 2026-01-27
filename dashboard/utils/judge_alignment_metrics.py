"""
Alignment agreement metrics for LLM judge vs human scoring.

Computes Cohen's kappa, Pearson correlation, mean absolute error,
and disagreement detection between human and LLM judge scores.
Provides Streamlit rendering for metrics display and CSV export.
"""

import logging
from dataclasses import dataclass
from math import sqrt

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScorePair:
    """A paired human and LLM score for a single task-dimension."""

    task_id: str
    dimension: str
    human_score: int
    llm_score: float


@dataclass(frozen=True)
class AlignmentMetrics:
    """Aggregate alignment metrics between human and LLM scores."""

    cohens_kappa: float
    pearson_correlation: float
    mean_absolute_error: float
    score_pairs: tuple[ScorePair, ...]
    total_pairs: int


def _parse_llm_score(score_str: str) -> float | None:
    """Parse an LLM score string into a float.

    Args:
        score_str: Score as string (e.g., "3", "4.5", "N/A")

    Returns:
        Float score or None if not parseable
    """
    try:
        return float(score_str)
    except (ValueError, TypeError):
        return None


def build_score_pairs(
    human_scores: dict[str, dict[str, int]],
    llm_scores: dict[str, dict[str, str]],
    dimensions: list[str],
) -> tuple[ScorePair, ...]:
    """Build paired score list from human and LLM score dicts.

    Only includes pairs where both human and LLM scores are valid.

    Args:
        human_scores: Dict of task_id -> {dimension: human_score (int)}
        llm_scores: Dict of task_id -> {dimension: llm_score (str)}
        dimensions: List of dimension names to include

    Returns:
        Tuple of ScorePair instances
    """
    pairs: list[ScorePair] = []

    for task_id, human_dims in human_scores.items():
        llm_dims = llm_scores.get(task_id, {})

        for dim in dimensions:
            human_val = human_dims.get(dim)
            llm_str = llm_dims.get(dim)

            if human_val is None or llm_str is None:
                continue

            llm_val = _parse_llm_score(llm_str)
            if llm_val is None:
                continue

            pairs.append(
                ScorePair(
                    task_id=task_id,
                    dimension=dim,
                    human_score=human_val,
                    llm_score=llm_val,
                )
            )

    return tuple(pairs)


def compute_pearson_correlation(
    pairs: tuple[ScorePair, ...],
) -> float:
    """Compute Pearson correlation between human and LLM scores.

    Manual computation without numpy dependency.

    Args:
        pairs: Paired scores

    Returns:
        Pearson r coefficient, or 0.0 if not computable
    """
    n = len(pairs)
    if n < 2:
        return 0.0

    human_vals = [p.human_score for p in pairs]
    llm_vals = [p.llm_score for p in pairs]

    mean_h = sum(human_vals) / n
    mean_l = sum(llm_vals) / n

    numerator = sum(
        (h - mean_h) * (lv - mean_l)
        for h, lv in zip(human_vals, llm_vals)
    )
    sum_sq_h = sum((h - mean_h) ** 2 for h in human_vals)
    sum_sq_l = sum((lv - mean_l) ** 2 for lv in llm_vals)

    denominator = sqrt(sum_sq_h * sum_sq_l)
    if denominator == 0:
        return 0.0

    return numerator / denominator


def compute_mean_absolute_error(
    pairs: tuple[ScorePair, ...],
) -> float:
    """Compute mean absolute error between human and LLM scores.

    Args:
        pairs: Paired scores

    Returns:
        Mean absolute error, or 0.0 if no pairs
    """
    if not pairs:
        return 0.0

    total_error = sum(
        abs(p.human_score - p.llm_score) for p in pairs
    )
    return total_error / len(pairs)


def compute_cohens_kappa(
    pairs: tuple[ScorePair, ...],
) -> float:
    """Compute Cohen's kappa for ordinal agreement.

    Treats scores as ordinal categories (rounded LLM scores to
    nearest integer for comparison). Uses standard Cohen's kappa
    formula: kappa = (p_o - p_e) / (1 - p_e).

    Args:
        pairs: Paired scores

    Returns:
        Cohen's kappa coefficient, or 0.0 if not computable
    """
    n = len(pairs)
    if n == 0:
        return 0.0

    # Round LLM scores to nearest integer for categorical comparison
    categories = sorted({
        *{p.human_score for p in pairs},
        *{round(p.llm_score) for p in pairs},
    })

    if len(categories) < 2:
        # All scores are the same category — perfect trivial agreement
        return 1.0

    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    k = len(categories)

    # Build confusion matrix
    matrix: list[list[int]] = [[0] * k for _ in range(k)]
    for p in pairs:
        human_idx = cat_to_idx[p.human_score]
        llm_idx = cat_to_idx[round(p.llm_score)]
        matrix[human_idx][llm_idx] += 1

    # Observed agreement (p_o)
    p_o = sum(matrix[i][i] for i in range(k)) / n

    # Expected agreement (p_e) — marginal probabilities
    row_sums = [sum(matrix[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(matrix[i][j] for i in range(k)) for j in range(k)]

    p_e = sum(
        (row_sums[i] / n) * (col_sums[i] / n)
        for i in range(k)
    )

    if p_e >= 1.0:
        return 0.0

    return (p_o - p_e) / (1.0 - p_e)


def compute_alignment_metrics(
    human_scores: dict[str, dict[str, int]],
    llm_scores: dict[str, dict[str, str]],
    dimensions: list[str],
) -> AlignmentMetrics:
    """Compute all alignment metrics between human and LLM scores.

    Args:
        human_scores: Dict of task_id -> {dimension: human_score (int)}
        llm_scores: Dict of task_id -> {dimension: llm_score (str)}
        dimensions: Dimension names to include

    Returns:
        AlignmentMetrics with all computed statistics
    """
    pairs = build_score_pairs(human_scores, llm_scores, dimensions)

    return AlignmentMetrics(
        cohens_kappa=compute_cohens_kappa(pairs),
        pearson_correlation=compute_pearson_correlation(pairs),
        mean_absolute_error=compute_mean_absolute_error(pairs),
        score_pairs=pairs,
        total_pairs=len(pairs),
    )


def find_disagreements(
    pairs: tuple[ScorePair, ...],
    threshold: float = 2.0,
) -> tuple[ScorePair, ...]:
    """Find score pairs where human and LLM disagree beyond a threshold.

    Args:
        pairs: Paired scores
        threshold: Maximum absolute difference considered agreement

    Returns:
        Tuple of ScorePairs exceeding the threshold
    """
    return tuple(
        p for p in pairs
        if abs(p.human_score - p.llm_score) > threshold
    )


def build_export_dataframe(
    pairs: tuple[ScorePair, ...],
) -> pd.DataFrame:
    """Build a DataFrame for CSV export of human+LLM scores.

    Args:
        pairs: Paired scores

    Returns:
        DataFrame with columns: task_id, dimension, human_score,
        llm_score, absolute_difference
    """
    if not pairs:
        return pd.DataFrame(
            columns=[
                "Task ID",
                "Dimension",
                "Human Score",
                "LLM Score",
                "Absolute Difference",
            ]
        )

    rows = [
        {
            "Task ID": p.task_id,
            "Dimension": p.dimension,
            "Human Score": p.human_score,
            "LLM Score": p.llm_score,
            "Absolute Difference": abs(p.human_score - p.llm_score),
        }
        for p in pairs
    ]

    return pd.DataFrame(rows)


def render_alignment_metrics_panel(
    metrics: AlignmentMetrics,
    session_key_prefix: str = "alignment_metrics",
) -> None:
    """Render the alignment metrics panel with cards, table, and export.

    Args:
        metrics: Computed alignment metrics
        session_key_prefix: Prefix for session state keys
    """
    if metrics.total_pairs == 0:
        st.info(
            "No paired scores available. Enter human scores above "
            "to see alignment metrics."
        )
        return

    st.markdown("### Agreement Metrics")

    # Metric cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Cohen's Kappa", f"{metrics.cohens_kappa:.3f}")
    with col2:
        st.metric("Pearson Correlation", f"{metrics.pearson_correlation:.3f}")
    with col3:
        st.metric("Mean Absolute Error", f"{metrics.mean_absolute_error:.2f}")
    with col4:
        st.metric("Score Pairs", str(metrics.total_pairs))

    st.markdown("---")

    # Disagreement threshold and highlighter
    st.markdown("### Disagreement Analysis")

    threshold = st.slider(
        "Disagreement Threshold",
        min_value=0.5,
        max_value=4.0,
        value=2.0,
        step=0.5,
        key=f"{session_key_prefix}_threshold",
        help="Highlight rows where |human - LLM| exceeds this threshold",
    )

    disagreements = find_disagreements(metrics.score_pairs, threshold)

    if disagreements:
        st.warning(
            f"{len(disagreements)} of {metrics.total_pairs} pairs "
            f"exceed the threshold of {threshold:.1f}"
        )

        # Build DataFrame with highlighting
        df = build_export_dataframe(metrics.score_pairs)

        # Style: highlight rows exceeding threshold
        def highlight_disagreements(row: pd.Series) -> list[str]:
            if row["Absolute Difference"] > threshold:
                return ["background-color: #fee2e2"] * len(row)
            return [""] * len(row)

        styled_df = df.style.apply(highlight_disagreements, axis=1)
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success(
            f"All {metrics.total_pairs} pairs agree within "
            f"threshold of {threshold:.1f}"
        )
        df = build_export_dataframe(metrics.score_pairs)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # CSV export
    export_df = build_export_dataframe(metrics.score_pairs)
    csv_data = export_df.to_csv(index=False)
    st.download_button(
        "Export Scores as CSV",
        data=csv_data,
        file_name="human_llm_alignment_scores.csv",
        mime="text/csv",
        key=f"{session_key_prefix}_export_csv",
    )
