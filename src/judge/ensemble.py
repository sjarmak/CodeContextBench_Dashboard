"""EnsembleJudge with multi-model consensus voting and agreement metrics.

Evaluates inputs across multiple UnifiedJudge instances (each backed by
a different LLM), then aggregates results via configurable consensus
strategies: majority_vote (categorical) or weighted_average (numerical).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from src.judge.engine import JudgeError, UnifiedJudge
from src.judge.metrics import generate_agreement_report
from src.judge.models import (
    EnsembleVerdict,
    EvaluationMode,
    JudgeInput,
    JudgeVerdict,
    PairwiseVerdict,
)

logger = logging.getLogger(__name__)


class EnsembleError(Exception):
    """Raised when ensemble evaluation cannot produce a valid result."""


@dataclass(frozen=True)
class EnsembleConfig:
    """Configuration for EnsembleJudge.

    Args:
        consensus_strategy: 'majority_vote' for categorical aggregation,
            'weighted_average' for numerical score aggregation.
        model_weights: Optional dict mapping model_id to weight. If not
            provided, all models are weighted equally.
        min_successful: Minimum number of successful model responses
            required for a valid ensemble result.
    """

    consensus_strategy: str = "weighted_average"
    model_weights: dict[str, float] = field(default_factory=dict)
    min_successful: int = 2


class EnsembleJudge:
    """Multi-model ensemble judge with consensus voting.

    Evaluates inputs across multiple UnifiedJudge instances in parallel,
    aggregates results via consensus strategy, and computes agreement metrics.

    Args:
        judges: List of UnifiedJudge instances, each with a different backend.
        config: Optional ensemble configuration. Uses defaults if not provided.
    """

    def __init__(
        self,
        judges: list[UnifiedJudge],
        config: EnsembleConfig | None = None,
    ) -> None:
        if len(judges) < 2:
            raise ValueError("EnsembleJudge requires at least 2 judges")
        self._judges = judges
        self._config = config or EnsembleConfig()

    @property
    def judges(self) -> list[UnifiedJudge]:
        return list(self._judges)

    @property
    def config(self) -> EnsembleConfig:
        return self._config

    async def evaluate(self, judge_input: JudgeInput) -> EnsembleVerdict:
        """Evaluate input across all models and produce consensus verdict.

        All models evaluate in parallel via asyncio.gather. Failed backends
        are logged and skipped. Raises EnsembleError if fewer than
        min_successful models return results.

        Args:
            judge_input: The evaluation input for all judges.

        Returns:
            EnsembleVerdict with consensus score, per-model verdicts,
            vote distribution, agreement score, and confidence.

        Raises:
            EnsembleError: If insufficient models produce valid results.
        """
        tasks = [
            self._safe_evaluate(judge, judge_input) for judge in self._judges
        ]
        results = await asyncio.gather(*tasks)

        successful_verdicts: list[JudgeVerdict] = []
        failed_models: list[str] = []

        for judge, result in zip(self._judges, results):
            if isinstance(result, JudgeVerdict):
                successful_verdicts.append(result)
            else:
                model_id = judge.backend.model_id
                failed_models.append(model_id)
                logger.warning(
                    "Backend %s failed: %s", model_id, result
                )

        if len(successful_verdicts) < self._config.min_successful:
            raise EnsembleError(
                f"Only {len(successful_verdicts)} of {len(self._judges)} "
                f"models succeeded (minimum {self._config.min_successful} required). "
                f"Failed models: {failed_models}"
            )

        strategy = self._config.consensus_strategy
        if strategy == "majority_vote":
            consensus_score, vote_distribution = _majority_vote(
                successful_verdicts
            )
        else:
            consensus_score, vote_distribution = _weighted_average(
                successful_verdicts, self._config.model_weights
            )

        verdicts_by_model = {
            v.model_id: [v] for v in successful_verdicts
        }
        agreement_report = generate_agreement_report(verdicts_by_model)
        agreement_score = agreement_report.fleiss_kappa

        confidence = _compute_ensemble_confidence(
            successful_verdicts, consensus_score
        )

        return EnsembleVerdict(
            consensus_score=consensus_score,
            per_model_verdicts=successful_verdicts,
            vote_distribution=vote_distribution,
            agreement_score=agreement_score,
            confidence=confidence,
        )

    @staticmethod
    async def _safe_evaluate(
        judge: UnifiedJudge, judge_input: JudgeInput
    ) -> JudgeVerdict | Exception:
        """Evaluate with a single judge, catching errors gracefully."""
        try:
            return await judge.evaluate(judge_input)
        except Exception as exc:
            return exc


def _majority_vote(
    verdicts: list[JudgeVerdict],
) -> tuple[float, dict[str, Any]]:
    """Aggregate verdicts via majority vote on categorical scores.

    Categorizes each verdict's overall_score into pass/partial/fail,
    picks the most common category, and maps it back to a score.

    Returns:
        Tuple of (consensus_score, vote_distribution).
    """
    category_map = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

    categories: list[str] = []
    for v in verdicts:
        score = v.overall_score
        if score >= 0.75:
            categories.append("pass")
        elif score >= 0.25:
            categories.append("partial")
        else:
            categories.append("fail")

    vote_counts: dict[str, int] = {}
    for cat in categories:
        vote_counts[cat] = vote_counts.get(cat, 0) + 1

    winning_category = max(vote_counts, key=lambda k: vote_counts[k])

    distribution: dict[str, Any] = {
        "strategy": "majority_vote",
        "vote_counts": vote_counts,
        "winning_category": winning_category,
        "per_model": {
            v.model_id: categories[i] for i, v in enumerate(verdicts)
        },
    }

    return category_map[winning_category], distribution


def _weighted_average(
    verdicts: list[JudgeVerdict],
    model_weights: dict[str, float],
) -> tuple[float, dict[str, Any]]:
    """Aggregate verdicts via weighted average of overall scores.

    Uses configured model weights if provided, otherwise equal weights.

    Returns:
        Tuple of (consensus_score, vote_distribution).
    """
    weights: list[float] = []
    scores: list[float] = []

    for v in verdicts:
        w = model_weights.get(v.model_id, 1.0)
        weights.append(w)
        scores.append(v.overall_score)

    total_weight = sum(weights)
    if total_weight == 0.0:
        consensus = sum(scores) / len(scores) if scores else 0.0
    else:
        consensus = sum(
            s * w for s, w in zip(scores, weights)
        ) / total_weight

    distribution: dict[str, Any] = {
        "strategy": "weighted_average",
        "per_model": {
            v.model_id: {
                "score": v.overall_score,
                "weight": weights[i],
            }
            for i, v in enumerate(verdicts)
        },
        "total_weight": total_weight,
    }

    return consensus, distribution


def _compute_ensemble_confidence(
    verdicts: list[JudgeVerdict],
    consensus_score: float,
) -> float:
    """Compute confidence as inverse of score variance across models.

    High agreement (low variance) yields high confidence. Individual
    model confidence values are also factored in.

    Returns:
        Confidence between 0.0 and 1.0.
    """
    if not verdicts:
        return 0.0

    scores = [v.overall_score for v in verdicts]
    n = len(scores)

    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n

    spread_confidence = max(0.0, 1.0 - (variance * 4.0))

    avg_model_confidence = sum(v.confidence for v in verdicts) / n

    return (spread_confidence * 0.6) + (avg_model_confidence * 0.4)
