"""Pairwise comparison evaluation with simultaneous and round-robin modes.

Supports N-way comparison with position bias mitigation via dual-ordering
evaluation and win-rate aggregation.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

from src.judge.backends.protocol import JudgeBackend
from src.judge.engine import (
    JudgeConfig,
    JudgeError,
    _build_dimension_scores,
    _compute_weighted_score,
    _truncate,
    parse_json_response,
)
from src.judge.models import (
    DimensionScore,
    EvaluationMode,
    PairwiseInput,
    PairwiseVerdict,
)
from src.judge.prompts.loader import load_template, render

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairResult:
    """Result of a single A vs B pairwise comparison."""

    condition_a: str
    condition_b: str
    winner: str
    scores_a: dict[str, DimensionScore]
    scores_b: dict[str, DimensionScore]
    confidence: float
    reasoning: str


class PairwiseEvaluator:
    """Evaluates pairwise comparisons using simultaneous or round-robin methods.

    Args:
        backend: An LLM backend implementing JudgeBackend protocol.
        config: Judge configuration with dimensions and truncation limits.
        templates_dir: Path to prompt template YAML files.
    """

    def __init__(
        self,
        backend: JudgeBackend,
        config: JudgeConfig,
        templates_dir: str,
    ) -> None:
        self._backend = backend
        self._config = config
        self._templates_dir = templates_dir

    async def evaluate_simultaneous(
        self, judge_input: PairwiseInput
    ) -> PairwiseVerdict:
        """Evaluate all outputs simultaneously in a single prompt.

        Sends all outputs to the LLM at once for ranking and scoring.

        Args:
            judge_input: Pairwise input with outputs keyed by condition name.

        Returns:
            PairwiseVerdict with rankings, win_rates, and preference_matrix.
        """
        from pathlib import Path

        template = load_template(
            Path(self._templates_dir) / "pairwise_simultaneous.yaml"
        )

        dimensions_text = "\n".join(
            f"- {dim} (weight: {weight})"
            for dim, weight in self._config.dimensions.items()
        )

        limits = self._config.truncation_limits
        outputs_text = "\n\n".join(
            f"### {name}\n{_truncate(output, limits.get('agent_output', 20000))}"
            for name, output in judge_input.outputs.items()
        )

        user_prompt = render(
            template,
            task_description=_truncate(
                judge_input.task_description,
                limits.get("task_description", 2000),
            ),
            dimensions=dimensions_text,
            outputs=outputs_text,
            output_format=template.output_format_spec,
        )

        backend_config = {
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }

        raw_response = await self._backend.evaluate(
            prompt=user_prompt,
            system_prompt=template.system_prompt,
            config=backend_config,
        )

        parsed = parse_json_response(raw_response)
        return self._build_simultaneous_verdict(parsed, judge_input)

    async def evaluate_roundrobin(
        self, judge_input: PairwiseInput
    ) -> PairwiseVerdict:
        """Evaluate all N-choose-2 pairs with position bias mitigation.

        Each pair is evaluated in both orderings (A|B and B|A). Results are
        averaged to mitigate position bias. Inconsistent pairs where ordering
        changes the verdict are flagged.

        Args:
            judge_input: Pairwise input with outputs keyed by condition name.

        Returns:
            PairwiseVerdict with rankings, win_rates, preference_matrix, and tie count.
        """
        conditions = list(judge_input.outputs.keys())
        pairs = list(itertools.combinations(conditions, 2))

        all_pair_results: list[PairResult] = []
        inconsistent_pairs: list[tuple[str, str]] = []

        for cond_a, cond_b in pairs:
            result_ab = await self._evaluate_single_pair(
                judge_input, cond_a, cond_b
            )
            result_ba = await self._evaluate_single_pair(
                judge_input, cond_b, cond_a
            )

            merged = self._merge_pair_results(
                result_ab, result_ba, cond_a, cond_b
            )
            all_pair_results.append(merged)

            if self._is_inconsistent(result_ab, result_ba, cond_a, cond_b):
                inconsistent_pairs.append((cond_a, cond_b))

        return self._aggregate_roundrobin(
            all_pair_results, conditions, inconsistent_pairs, judge_input
        )

    async def _evaluate_single_pair(
        self,
        judge_input: PairwiseInput,
        cond_a: str,
        cond_b: str,
    ) -> PairResult:
        """Evaluate a single A vs B pair."""
        from pathlib import Path

        template = load_template(
            Path(self._templates_dir) / "pairwise_roundrobin.yaml"
        )

        dimensions_text = "\n".join(
            f"- {dim} (weight: {weight})"
            for dim, weight in self._config.dimensions.items()
        )

        limits = self._config.truncation_limits
        output_a = _truncate(
            judge_input.outputs[cond_a],
            limits.get("agent_output", 20000),
        )
        output_b = _truncate(
            judge_input.outputs[cond_b],
            limits.get("agent_output", 20000),
        )

        user_prompt = render(
            template,
            task_description=_truncate(
                judge_input.task_description,
                limits.get("task_description", 2000),
            ),
            dimensions=dimensions_text,
            output_a=output_a,
            output_b=output_b,
            output_format=template.output_format_spec,
        )

        backend_config = {
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }

        raw_response = await self._backend.evaluate(
            prompt=user_prompt,
            system_prompt=template.system_prompt,
            config=backend_config,
        )

        parsed = parse_json_response(raw_response)
        return self._parse_pair_result(parsed, cond_a, cond_b)

    def _parse_pair_result(
        self,
        parsed: dict[str, Any],
        cond_a: str,
        cond_b: str,
    ) -> PairResult:
        """Parse LLM response into a PairResult."""
        winner_raw = str(parsed.get("winner", "TIE")).upper()
        if winner_raw == "A":
            winner = cond_a
        elif winner_raw == "B":
            winner = cond_b
        else:
            winner = "TIE"

        raw_scores = parsed.get("scores", {})
        scores_a_raw = raw_scores.get("A", {})
        scores_b_raw = raw_scores.get("B", {})

        scores_a = _build_dimension_scores(scores_a_raw, self._config.dimensions)
        scores_b = _build_dimension_scores(scores_b_raw, self._config.dimensions)

        return PairResult(
            condition_a=cond_a,
            condition_b=cond_b,
            winner=winner,
            scores_a=scores_a,
            scores_b=scores_b,
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=str(parsed.get("reasoning", "")),
        )

    def _merge_pair_results(
        self,
        result_ab: PairResult,
        result_ba: PairResult,
        cond_a: str,
        cond_b: str,
    ) -> PairResult:
        """Merge A|B and B|A evaluations by averaging scores.

        In result_ab: A is position A, B is position B.
        In result_ba: B is position A, A is position B.
        So result_ba.scores_a are actually cond_b's scores and vice versa.
        """
        merged_scores_a = self._average_dimension_scores(
            result_ab.scores_a, result_ba.scores_b
        )
        merged_scores_b = self._average_dimension_scores(
            result_ab.scores_b, result_ba.scores_a
        )

        weighted_a = _compute_weighted_score(merged_scores_a)
        weighted_b = _compute_weighted_score(merged_scores_b)

        if abs(weighted_a - weighted_b) < 0.05:
            winner = "TIE"
        elif weighted_a > weighted_b:
            winner = cond_a
        else:
            winner = cond_b

        return PairResult(
            condition_a=cond_a,
            condition_b=cond_b,
            winner=winner,
            scores_a=merged_scores_a,
            scores_b=merged_scores_b,
            confidence=(result_ab.confidence + result_ba.confidence) / 2.0,
            reasoning=f"AB: {result_ab.reasoning}\nBA: {result_ba.reasoning}",
        )

    def _average_dimension_scores(
        self,
        scores_1: dict[str, DimensionScore],
        scores_2: dict[str, DimensionScore],
    ) -> dict[str, DimensionScore]:
        """Average two sets of dimension scores."""
        all_dims = set(scores_1.keys()) | set(scores_2.keys())
        merged: dict[str, DimensionScore] = {}

        for dim in all_dims:
            s1 = scores_1.get(dim)
            s2 = scores_2.get(dim)

            if s1 is not None and s2 is not None:
                merged[dim] = DimensionScore(
                    dimension=dim,
                    score=(s1.score + s2.score) / 2.0,
                    weight=(s1.weight + s2.weight) / 2.0,
                    evidence=f"{s1.evidence}; {s2.evidence}",
                    reasoning=f"{s1.reasoning}; {s2.reasoning}",
                )
            elif s1 is not None:
                merged[dim] = s1
            elif s2 is not None:
                merged[dim] = s2

        return merged

    def _is_inconsistent(
        self,
        result_ab: PairResult,
        result_ba: PairResult,
        cond_a: str,
        cond_b: str,
    ) -> bool:
        """Check if position swap changed the verdict (potential position bias).

        In result_ab, winner is expressed as cond_a/cond_b/TIE.
        In result_ba, positions are swapped: A=cond_b, B=cond_a.
        So result_ba.winner "A" means cond_b won, "B" means cond_a won.
        """
        winner_ab = result_ab.winner

        winner_ba_raw = result_ba.winner
        if winner_ba_raw == result_ba.condition_a:
            winner_ba_mapped = cond_b
        elif winner_ba_raw == result_ba.condition_b:
            winner_ba_mapped = cond_a
        elif winner_ba_raw == "TIE":
            winner_ba_mapped = "TIE"
        else:
            winner_ba_mapped = winner_ba_raw

        return winner_ab != winner_ba_mapped

    def _build_simultaneous_verdict(
        self,
        parsed: dict[str, Any],
        judge_input: PairwiseInput,
    ) -> PairwiseVerdict:
        """Build PairwiseVerdict from simultaneous evaluation response."""
        rankings = parsed.get("rankings", [])
        per_output = parsed.get("per_output_scores", {})

        all_scores: dict[str, DimensionScore] = {}
        win_rates: dict[str, float] = {}

        for condition_name, condition_scores in per_output.items():
            dim_scores = _build_dimension_scores(
                condition_scores, self._config.dimensions
            )
            weighted = _compute_weighted_score(dim_scores)
            win_rates[condition_name] = weighted
            for dim_name, ds in dim_scores.items():
                all_scores[f"{condition_name}/{dim_name}"] = ds

        conditions = list(judge_input.outputs.keys())
        preference_matrix = self._build_preference_matrix_from_rankings(
            rankings, conditions
        )

        ties_raw = parsed.get("ties", [])
        ties_count = len(ties_raw) if isinstance(ties_raw, list) else int(ties_raw or 0)

        return PairwiseVerdict(
            mode=EvaluationMode.PAIRWISE,
            scores=all_scores,
            overall_score=parsed.get(
                "overall_score",
                _compute_weighted_score(all_scores) if all_scores else 0.0,
            ),
            reasoning=str(parsed.get("reasoning", "")),
            evidence=[str(parsed.get("reasoning", ""))],
            confidence=float(parsed.get("confidence", 0.0)),
            model_id=self._backend.model_id,
            rankings=rankings,
            win_rates=win_rates,
            preference_matrix=preference_matrix,
            ties=ties_count,
        )

    def _aggregate_roundrobin(
        self,
        pair_results: list[PairResult],
        conditions: list[str],
        inconsistent_pairs: list[tuple[str, str]],
        judge_input: PairwiseInput,
    ) -> PairwiseVerdict:
        """Aggregate round-robin pair results into a PairwiseVerdict."""
        wins: dict[str, float] = {c: 0.0 for c in conditions}
        total_pairs = len(pair_results)

        preference_matrix: dict[str, dict[str, float]] = {
            c: {c2: 0.0 for c2 in conditions} for c in conditions
        }

        all_scores: dict[str, DimensionScore] = {}
        all_reasonings: list[str] = []

        for pr in pair_results:
            if pr.winner == pr.condition_a:
                wins[pr.condition_a] += 1.0
                preference_matrix[pr.condition_a][pr.condition_b] = 1.0
                preference_matrix[pr.condition_b][pr.condition_a] = 0.0
            elif pr.winner == pr.condition_b:
                wins[pr.condition_b] += 1.0
                preference_matrix[pr.condition_b][pr.condition_a] = 1.0
                preference_matrix[pr.condition_a][pr.condition_b] = 0.0
            else:
                wins[pr.condition_a] += 0.5
                wins[pr.condition_b] += 0.5
                preference_matrix[pr.condition_a][pr.condition_b] = 0.5
                preference_matrix[pr.condition_b][pr.condition_a] = 0.5

            for dim_name, ds in pr.scores_a.items():
                key = f"{pr.condition_a}/{dim_name}"
                existing = all_scores.get(key)
                if existing is not None:
                    all_scores[key] = DimensionScore(
                        dimension=dim_name,
                        score=(existing.score + ds.score) / 2.0,
                        weight=ds.weight,
                        evidence=f"{existing.evidence}; {ds.evidence}",
                        reasoning=f"{existing.reasoning}; {ds.reasoning}",
                    )
                else:
                    all_scores[key] = ds

            for dim_name, ds in pr.scores_b.items():
                key = f"{pr.condition_b}/{dim_name}"
                existing = all_scores.get(key)
                if existing is not None:
                    all_scores[key] = DimensionScore(
                        dimension=dim_name,
                        score=(existing.score + ds.score) / 2.0,
                        weight=ds.weight,
                        evidence=f"{existing.evidence}; {ds.evidence}",
                        reasoning=f"{existing.reasoning}; {ds.reasoning}",
                    )
                else:
                    all_scores[key] = ds

            all_reasonings.append(pr.reasoning)

        max_wins = total_pairs if total_pairs > 0 else 1
        win_rates = {c: w / max_wins for c, w in wins.items()}

        rankings = sorted(conditions, key=lambda c: win_rates[c], reverse=True)

        ties_count = sum(1 for pr in pair_results if pr.winner == "TIE")

        avg_confidence = (
            sum(pr.confidence for pr in pair_results) / len(pair_results)
            if pair_results
            else 0.0
        )

        metadata: dict[str, Any] = {
            "method": "round_robin",
            "total_pairs": total_pairs,
            "inconsistent_pairs": [
                f"{a} vs {b}" for a, b in inconsistent_pairs
            ],
            "inconsistency_rate": (
                len(inconsistent_pairs) / total_pairs if total_pairs > 0 else 0.0
            ),
        }

        return PairwiseVerdict(
            mode=EvaluationMode.PAIRWISE,
            scores=all_scores,
            overall_score=_compute_weighted_score(all_scores) if all_scores else 0.0,
            reasoning="\n---\n".join(all_reasonings),
            evidence=all_reasonings,
            confidence=avg_confidence,
            model_id=self._backend.model_id,
            rankings=rankings,
            win_rates=win_rates,
            preference_matrix=preference_matrix,
            ties=ties_count,
            metadata=metadata,
        )

    def _build_preference_matrix_from_rankings(
        self,
        rankings: list[str],
        conditions: list[str],
    ) -> dict[str, dict[str, float]]:
        """Build a preference matrix from a ranking list.

        Higher-ranked conditions get 1.0 against lower-ranked, 0.5 for ties.
        """
        matrix: dict[str, dict[str, float]] = {
            c: {c2: 0.5 for c2 in conditions} for c in conditions
        }

        for i, higher in enumerate(rankings):
            if higher not in matrix:
                continue
            for lower in rankings[i + 1 :]:
                if lower not in matrix:
                    continue
                matrix[higher][lower] = 1.0
                matrix[lower][higher] = 0.0

        return matrix
