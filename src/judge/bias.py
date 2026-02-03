"""Bias detection and mitigation for the unified judge system.

Provides metrics for detecting position bias and length-score correlation,
along with anti-bias prompt injection strategies at configurable levels.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

from src.judge.models import (
    JudgeInput,
    JudgeVerdict,
    PairwiseInput,
    PairwiseVerdict,
)

logger = logging.getLogger(__name__)


class BiasLevel(Enum):
    """Level of bias mitigation to apply to judge prompts."""

    NONE = "none"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class BiasReport:
    """Report of detected biases in judge evaluations."""

    position_consistency_rate: float
    length_score_correlation: float
    flagged_pairs: list[str] = field(default_factory=list)
    bias_level_used: BiasLevel = BiasLevel.NONE


def compute_position_consistency(results: list[PairwiseVerdict]) -> float:
    """Compute rate of consistent verdicts across position swaps.

    Looks at round-robin metadata for inconsistent_pairs to determine
    what fraction of pairs had consistent verdicts when positions were swapped.

    Args:
        results: List of PairwiseVerdict objects from round-robin evaluations.

    Returns:
        Float between 0.0 and 1.0 representing consistency rate.
        Returns 1.0 if no pair data is available.
    """
    if not results:
        return 1.0

    total_pairs = 0
    inconsistent_count = 0

    for verdict in results:
        metadata = verdict.metadata or {}
        pairs = metadata.get("total_pairs", 0)
        inconsistent_raw = metadata.get("inconsistent_pairs", [])
        inconsistent = (
            len(inconsistent_raw)
            if isinstance(inconsistent_raw, list)
            else int(inconsistent_raw or 0)
        )

        total_pairs += pairs
        inconsistent_count += inconsistent

    if total_pairs == 0:
        return 1.0

    return 1.0 - (inconsistent_count / total_pairs)


def compute_length_correlation(
    inputs: list[JudgeInput],
    verdicts: list[JudgeVerdict],
) -> float:
    """Compute Pearson correlation between output length and overall score.

    For pairwise inputs, uses per-output lengths. For direct/reference inputs,
    uses the agent_output length.

    Args:
        inputs: List of JudgeInput (or subclass) objects.
        verdicts: Corresponding list of JudgeVerdict objects.

    Returns:
        Pearson correlation coefficient between -1.0 and 1.0.
        Returns 0.0 if insufficient data for computation.
    """
    lengths: list[float] = []
    scores: list[float] = []

    for judge_input, verdict in zip(inputs, verdicts):
        if isinstance(judge_input, PairwiseInput):
            for condition_name, output_text in judge_input.outputs.items():
                output_len = float(len(output_text))
                condition_score = _extract_condition_score(
                    verdict, condition_name
                )
                if condition_score is not None:
                    lengths.append(output_len)
                    scores.append(condition_score)
        else:
            output_text = getattr(judge_input, "agent_output", "")
            lengths.append(float(len(output_text)))
            scores.append(verdict.overall_score)

    return _pearson_correlation(lengths, scores)


def generate_bias_report(
    inputs: list[JudgeInput],
    verdicts: list[JudgeVerdict],
    bias_level: BiasLevel = BiasLevel.NONE,
) -> BiasReport:
    """Generate a comprehensive bias report from evaluation data.

    Args:
        inputs: List of JudgeInput objects used in evaluation.
        verdicts: Corresponding list of JudgeVerdict objects.
        bias_level: The bias mitigation level that was used during evaluation.

    Returns:
        BiasReport with position consistency, length correlation, and flagged pairs.
    """
    pairwise_verdicts = [
        v for v in verdicts if isinstance(v, PairwiseVerdict)
    ]
    position_consistency = compute_position_consistency(pairwise_verdicts)
    length_corr = compute_length_correlation(inputs, verdicts)

    flagged = _find_flagged_pairs(pairwise_verdicts)

    return BiasReport(
        position_consistency_rate=position_consistency,
        length_score_correlation=length_corr,
        flagged_pairs=flagged,
        bias_level_used=bias_level,
    )


def inject_anti_bias_instructions(
    prompt: str,
    bias_level: BiasLevel,
) -> str:
    """Add bias mitigation instructions to a judge prompt.

    Args:
        prompt: The original judge prompt text.
        bias_level: Level of bias mitigation to apply.

    Returns:
        The prompt with anti-bias instructions appended.
        Returns the original prompt unchanged if bias_level is NONE.
    """
    if bias_level == BiasLevel.NONE:
        return prompt

    instructions: list[str] = []

    if bias_level in (BiasLevel.STANDARD, BiasLevel.AGGRESSIVE):
        instructions.extend([
            "\n\n## Bias Mitigation Instructions",
            "- POSITION BIAS: The order in which outputs are presented does NOT "
            "indicate quality. Evaluate each output on its own merits regardless "
            "of position. If outputs are swapped in order, your verdict should "
            "remain the same.",
            "- LENGTH BIAS: Do NOT prefer longer responses over shorter ones. "
            "A concise, correct answer is better than a verbose, padded one. "
            "Evaluate substance and correctness, not word count.",
        ])

    if bias_level == BiasLevel.AGGRESSIVE:
        instructions.extend([
            "- LENGTH NORMALIZATION: When comparing outputs of different lengths, "
            "mentally normalize for length. Consider whether additional content "
            "adds genuine value or is merely padding/repetition.",
            "- SELF-ENHANCEMENT: Do NOT give higher scores to outputs that use "
            "flattering language, confident tone, or self-promotional phrasing. "
            "Focus on technical accuracy and task completion.",
            "- ANCHORING: Do NOT let the first output you read anchor your "
            "expectations. Each output should be evaluated against the task "
            "requirements independently.",
        ])

    return prompt + "\n".join(instructions)


def _extract_condition_score(
    verdict: JudgeVerdict,
    condition_name: str,
) -> float | None:
    """Extract aggregate score for a specific condition from a verdict.

    Looks for dimension scores keyed as '{condition_name}/{dimension}'.
    Returns the average score across all dimensions for that condition,
    or the win_rate if it's a PairwiseVerdict.
    """
    if isinstance(verdict, PairwiseVerdict) and condition_name in verdict.win_rates:
        return verdict.win_rates[condition_name]

    condition_scores = [
        ds.score
        for key, ds in verdict.scores.items()
        if key.startswith(f"{condition_name}/")
    ]

    if not condition_scores:
        return None

    return sum(condition_scores) / len(condition_scores)


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient between two sequences.

    Args:
        xs: First sequence of values.
        ys: Second sequence of values.

    Returns:
        Pearson r between -1.0 and 1.0. Returns 0.0 if computation
        is not possible (e.g., zero variance, insufficient data).
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return 0.0

    return cov / denom


def _find_flagged_pairs(verdicts: list[PairwiseVerdict]) -> list[str]:
    """Extract flagged inconsistent pair IDs from pairwise verdicts.

    Args:
        verdicts: List of PairwiseVerdict objects with metadata.

    Returns:
        List of inconsistent pair descriptions (e.g., "A vs B").
    """
    flagged: list[str] = []
    for verdict in verdicts:
        metadata = verdict.metadata or {}
        inconsistent = metadata.get("inconsistent_pairs", [])
        if isinstance(inconsistent, list):
            flagged.extend(inconsistent)
    return flagged
