"""Inter-judge agreement metrics for ensemble model consensus quality.

Provides Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, and
Spearman correlation to measure agreement across judge models.
All implementations are pure Python with no external dependencies.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from src.judge.models import JudgeVerdict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgreementReport:
    """Report of inter-judge agreement metrics across ensemble models."""

    cohens_kappa: dict[str, float] = field(default_factory=dict)
    fleiss_kappa: float = 0.0
    krippendorff_alpha: float = 0.0
    spearman_correlations: dict[str, float] = field(default_factory=dict)
    low_agreement_flag: bool = False


def compute_cohens_kappa(ratings_a: list, ratings_b: list) -> float:
    """Compute Cohen's kappa for pairwise inter-rater agreement.

    Args:
        ratings_a: Ratings from rater A (categorical values).
        ratings_b: Ratings from rater B (categorical values).

    Returns:
        Cohen's kappa between -1.0 and 1.0. Returns 0.0 if
        computation is not possible.
    """
    n = len(ratings_a)
    if n == 0 or n != len(ratings_b):
        return 0.0

    categories = sorted(set(ratings_a) | set(ratings_b))
    if len(categories) < 2:
        return 1.0 if ratings_a == ratings_b else 0.0

    cat_index = {cat: i for i, cat in enumerate(categories)}
    k = len(categories)

    confusion = [[0] * k for _ in range(k)]
    for a, b in zip(ratings_a, ratings_b):
        confusion[cat_index[a]][cat_index[b]] += 1

    p_observed = sum(confusion[i][i] for i in range(k)) / n

    row_sums = [sum(confusion[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(confusion[i][j] for i in range(k)) for j in range(k)]
    p_expected = sum(row_sums[i] * col_sums[i] for i in range(k)) / (n * n)

    if p_expected == 1.0:
        return 1.0 if p_observed == 1.0 else 0.0

    return (p_observed - p_expected) / (1.0 - p_expected)


def compute_fleiss_kappa(ratings_matrix: list[list]) -> float:
    """Compute Fleiss' kappa for multi-rater agreement.

    Args:
        ratings_matrix: Matrix of shape (n_subjects, n_categories) where
            each entry is the count of raters who assigned that category
            to that subject.

    Returns:
        Fleiss' kappa between -1.0 and 1.0. Returns 0.0 if
        computation is not possible.
    """
    if not ratings_matrix or not ratings_matrix[0]:
        return 0.0

    n_subjects = len(ratings_matrix)
    n_categories = len(ratings_matrix[0])

    n_raters = sum(ratings_matrix[0])
    if n_raters < 2 or n_subjects < 1:
        return 0.0

    for row in ratings_matrix:
        if len(row) != n_categories:
            return 0.0
        if sum(row) != n_raters:
            return 0.0

    p_j = [
        sum(ratings_matrix[i][j] for i in range(n_subjects))
        / (n_subjects * n_raters)
        for j in range(n_categories)
    ]

    p_e = sum(pj * pj for pj in p_j)

    p_i_values = []
    for i in range(n_subjects):
        row_sum_sq = sum(
            ratings_matrix[i][j] * ratings_matrix[i][j]
            for j in range(n_categories)
        )
        p_i = (row_sum_sq - n_raters) / (n_raters * (n_raters - 1))
        p_i_values.append(p_i)

    p_bar = sum(p_i_values) / n_subjects

    if p_e == 1.0:
        return 1.0 if p_bar == 1.0 else 0.0

    return (p_bar - p_e) / (1.0 - p_e)


def compute_krippendorff_alpha(
    ratings_matrix: list[list],
    level: str = "nominal",
) -> float:
    """Compute Krippendorff's alpha for inter-rater reliability.

    Args:
        ratings_matrix: Matrix of shape (n_raters, n_subjects) where
            each entry is the rating given by that rater for that subject.
            Use None for missing ratings.
        level: Measurement level - 'nominal', 'ordinal', or 'interval'.

    Returns:
        Krippendorff's alpha between -1.0 and 1.0. Returns 0.0 if
        computation is not possible.
    """
    if not ratings_matrix or not ratings_matrix[0]:
        return 0.0

    n_raters = len(ratings_matrix)
    n_subjects = len(ratings_matrix[0])

    if n_raters < 2 or n_subjects < 1:
        return 0.0

    for row in ratings_matrix:
        if len(row) != n_subjects:
            return 0.0

    diff_fn = _get_difference_function(level)

    d_observed = 0.0
    d_expected = 0.0
    total_observed_pairs = 0

    all_values: list = []
    for j in range(n_subjects):
        col_values = [
            ratings_matrix[r][j]
            for r in range(n_raters)
            if ratings_matrix[r][j] is not None
        ]
        all_values.extend(col_values)

        m_j = len(col_values)
        if m_j < 2:
            continue

        for a_idx in range(m_j):
            for b_idx in range(a_idx + 1, m_j):
                d_observed += diff_fn(col_values[a_idx], col_values[b_idx])
                total_observed_pairs += 1

    if total_observed_pairs == 0:
        return 0.0

    d_observed /= total_observed_pairs

    n_total = len(all_values)
    if n_total < 2:
        return 0.0

    expected_pairs = 0
    d_expected_sum = 0.0
    for a_idx in range(n_total):
        for b_idx in range(a_idx + 1, n_total):
            d_expected_sum += diff_fn(all_values[a_idx], all_values[b_idx])
            expected_pairs += 1

    if expected_pairs == 0:
        return 0.0

    d_expected = d_expected_sum / expected_pairs

    if d_expected == 0.0:
        return 1.0 if d_observed == 0.0 else 0.0

    return 1.0 - (d_observed / d_expected)


def compute_spearman_correlation(
    scores_a: list[float],
    scores_b: list[float],
) -> tuple[float, float]:
    """Compute Spearman rank correlation between two score sequences.

    Args:
        scores_a: First sequence of numerical scores.
        scores_b: Second sequence of numerical scores.

    Returns:
        Tuple of (rho, p_value). Returns (0.0, 1.0) if computation
        is not possible. p_value is approximate for large n.
    """
    n = len(scores_a)
    if n < 2 or n != len(scores_b):
        return (0.0, 1.0)

    ranks_a = _compute_ranks(scores_a)
    ranks_b = _compute_ranks(scores_b)

    mean_a = sum(ranks_a) / n
    mean_b = sum(ranks_b) / n

    cov = sum(
        (ranks_a[i] - mean_a) * (ranks_b[i] - mean_b) for i in range(n)
    )
    var_a = sum((r - mean_a) ** 2 for r in ranks_a)
    var_b = sum((r - mean_b) ** 2 for r in ranks_b)

    denom = math.sqrt(var_a * var_b)
    if denom == 0.0:
        return (0.0, 1.0)

    rho = cov / denom

    rho = max(-1.0, min(1.0, rho))

    if n <= 2:
        p_value = 1.0
    else:
        t_stat = rho * math.sqrt((n - 2) / (1.0 - rho * rho + 1e-15))
        p_value = _approximate_t_p_value(t_stat, n - 2)

    return (rho, p_value)


def generate_agreement_report(
    verdicts_by_model: dict[str, list[JudgeVerdict]],
    threshold: float = 0.4,
) -> AgreementReport:
    """Generate agreement report from verdicts grouped by model.

    Args:
        verdicts_by_model: Dict mapping model_id to list of JudgeVerdict
            objects. All lists must have the same length (same tasks).
        threshold: Fleiss' kappa threshold below which low_agreement_flag
            is set to True.

    Returns:
        AgreementReport with all agreement metrics computed.
    """
    model_ids = sorted(verdicts_by_model.keys())
    if len(model_ids) < 2:
        return AgreementReport(low_agreement_flag=True)

    n_tasks = len(next(iter(verdicts_by_model.values())))
    for mid in model_ids:
        if len(verdicts_by_model[mid]) != n_tasks:
            logger.warning(
                "Model %s has %d verdicts, expected %d",
                mid,
                len(verdicts_by_model[mid]),
                n_tasks,
            )
            return AgreementReport(low_agreement_flag=True)

    if n_tasks == 0:
        return AgreementReport(low_agreement_flag=True)

    scores_by_model = {
        mid: [v.overall_score for v in verdicts]
        for mid, verdicts in verdicts_by_model.items()
    }

    categorical_by_model = {
        mid: [_categorize_score(v.overall_score) for v in verdicts]
        for mid, verdicts in verdicts_by_model.items()
    }

    cohens_kappa_pairs: dict[str, float] = {}
    spearman_pairs: dict[str, float] = {}
    for i, mid_a in enumerate(model_ids):
        for mid_b in model_ids[i + 1 :]:
            pair_key = f"{mid_a} vs {mid_b}"
            cohens_kappa_pairs[pair_key] = compute_cohens_kappa(
                categorical_by_model[mid_a],
                categorical_by_model[mid_b],
            )
            rho, _ = compute_spearman_correlation(
                scores_by_model[mid_a],
                scores_by_model[mid_b],
            )
            spearman_pairs[pair_key] = rho

    categories = sorted(
        set(
            cat
            for cats in categorical_by_model.values()
            for cat in cats
        )
    )
    cat_index = {cat: idx for idx, cat in enumerate(categories)}
    n_categories = len(categories)

    fleiss_matrix: list[list[int]] = []
    for task_idx in range(n_tasks):
        row = [0] * n_categories
        for mid in model_ids:
            cat = categorical_by_model[mid][task_idx]
            row[cat_index[cat]] += 1
        fleiss_matrix.append(row)

    fleiss = compute_fleiss_kappa(fleiss_matrix)

    krippendorff_matrix = [
        scores_by_model[mid] for mid in model_ids
    ]
    kripp = compute_krippendorff_alpha(krippendorff_matrix, level="interval")

    return AgreementReport(
        cohens_kappa=cohens_kappa_pairs,
        fleiss_kappa=fleiss,
        krippendorff_alpha=kripp,
        spearman_correlations=spearman_pairs,
        low_agreement_flag=fleiss < threshold,
    )


def _categorize_score(score: float) -> str:
    """Categorize a continuous score into pass/partial/fail.

    Uses the 3-point scoring convention from the project:
    pass >= 0.75, partial >= 0.25, fail < 0.25.
    """
    if score >= 0.75:
        return "pass"
    if score >= 0.25:
        return "partial"
    return "fail"


def _compute_ranks(values: list[float]) -> list[float]:
    """Compute fractional ranks for a list of values (average ties)."""
    n = len(values)
    indexed = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i
        while j < n - 1 and values[indexed[j + 1]] == values[indexed[j]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1

    return ranks


def _get_difference_function(level: str):
    """Return the appropriate difference function for Krippendorff's alpha."""
    if level == "nominal":
        return lambda a, b: 0.0 if a == b else 1.0
    if level == "ordinal":
        return lambda a, b: (float(a) - float(b)) ** 2
    if level == "interval":
        return lambda a, b: (float(a) - float(b)) ** 2
    raise ValueError(f"Unsupported measurement level: {level}")


def _approximate_t_p_value(t_stat: float, df: int) -> float:
    """Approximate two-tailed p-value from t-statistic using normal approx.

    For df >= 30, the t-distribution is close to normal.
    For smaller df, this is a rough approximation.
    """
    if df <= 0:
        return 1.0

    x = abs(t_stat)
    if df < 30:
        x = x * (1.0 - 1.0 / (4.0 * df))

    p = math.erfc(x / math.sqrt(2.0))
    return min(1.0, max(0.0, p))
