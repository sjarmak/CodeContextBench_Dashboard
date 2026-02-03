"""Reference-based evaluation against ground truth for benchmarks like LoCoBench.

Evaluates agent output against reference answers across three dimensions:
Oracle Correctness, Oracle Completeness, and Approach Alignment. Supports
3-point categorical and 5-point Likert scoring, context file coverage
tracking, and automatic task type detection.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from src.judge.backends.protocol import JudgeBackend
from src.judge.engine import (
    JudgeConfig,
    _build_dimension_scores,
    _compute_weighted_score,
    _truncate,
    parse_json_response,
)
from src.judge.models import (
    DimensionScore,
    EvaluationMode,
    JudgeVerdict,
    ReferenceInput,
)
from src.judge.prompts.loader import load_template, render

logger = logging.getLogger(__name__)

_DEFAULT_REFERENCE_DIMENSIONS: dict[str, float] = {
    "Oracle Correctness": 0.4,
    "Oracle Completeness": 0.35,
    "Approach Alignment": 0.25,
}

_THREE_POINT_SCALE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

_DIFF_PATTERNS = [
    re.compile(r"^diff --git ", re.MULTILINE),
    re.compile(r"^[+-]{3} [ab]/", re.MULTILINE),
    re.compile(r"^@@\s", re.MULTILINE),
]


def detect_task_type(agent_output: str) -> str:
    """Detect whether agent output is code modification or analysis.

    Checks for diff-like patterns in the output. If code diff markers are
    found, returns 'code_modification'; otherwise returns 'analysis'.

    Args:
        agent_output: The agent's output text.

    Returns:
        Either 'code_modification' or 'analysis'.
    """
    for pattern in _DIFF_PATTERNS:
        if pattern.search(agent_output):
            return "code_modification"
    return "analysis"


def compute_context_file_coverage(
    expected_files: list[str],
    agent_output: str,
) -> float:
    """Compute the fraction of expected context files referenced in agent output.

    Args:
        expected_files: List of expected file paths from oracle data.
        agent_output: The agent's output text to search for references.

    Returns:
        Coverage ratio between 0.0 and 1.0.
    """
    if not expected_files:
        return 1.0

    referenced = 0
    for file_path in expected_files:
        normalized = file_path.replace("//", "/")
        basename = Path(normalized).name
        if normalized in agent_output or basename in agent_output:
            referenced += 1

    return referenced / len(expected_files)


def load_oracle_data(scenario: dict[str, Any]) -> dict[str, Any]:
    """Extract oracle evaluation fields from a LoCoBench scenario JSON.

    Handles missing fields gracefully by returning None for absent keys.

    Args:
        scenario: A parsed LoCoBench scenario JSON dict.

    Returns:
        Dict with keys: ground_truth, expected_approach, evaluation_criteria,
        context_files. Values may be None if not present in the scenario.
    """
    return {
        "ground_truth": scenario.get("ground_truth"),
        "expected_approach": scenario.get("expected_approach"),
        "evaluation_criteria": scenario.get("evaluation_criteria"),
        "context_files": scenario.get("context_files") or [],
    }


class ReferenceEvaluator:
    """Evaluates agent output against reference answers and oracle data.

    Supports correctness, completeness, and approach alignment dimensions.
    Uses 3-point categorical scoring by default, with optional 5-point Likert.

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

    async def evaluate(self, judge_input: ReferenceInput) -> JudgeVerdict:
        """Evaluate agent output against reference answer.

        Runs correctness evaluation and, when evaluation_criteria is
        available, also runs completeness evaluation. Merges results
        from both into a single JudgeVerdict.

        Args:
            judge_input: Reference evaluation input with agent output,
                reference answer, and optional context files.

        Returns:
            JudgeVerdict with dimension scores, context coverage, and metadata.
        """
        task_type = detect_task_type(judge_input.agent_output)
        context_coverage = compute_context_file_coverage(
            judge_input.context_files,
            judge_input.agent_output,
        )

        correctness_verdict = await self._evaluate_correctness(judge_input)

        completeness_verdict = None
        if judge_input.evaluation_criteria:
            completeness_verdict = await self._evaluate_completeness(judge_input)

        return self._merge_verdicts(
            correctness_verdict,
            completeness_verdict,
            task_type,
            context_coverage,
            judge_input,
        )

    async def _evaluate_correctness(
        self, judge_input: ReferenceInput
    ) -> JudgeVerdict:
        """Run correctness evaluation using reference_correctness template."""
        template = load_template(
            Path(self._templates_dir) / "reference_correctness.yaml"
        )

        limits = self._config.truncation_limits
        context_files_text = (
            "\n".join(judge_input.context_files)
            if judge_input.context_files
            else "No context files provided."
        )

        user_prompt = render(
            template,
            task_description=_truncate(
                judge_input.task_description,
                limits.get("task_description", 2000),
            ),
            reference_answer=_truncate(
                judge_input.reference_answer,
                limits.get("agent_output", 20000),
            ),
            context_files=context_files_text,
            agent_output=_truncate(
                judge_input.agent_output,
                limits.get("agent_output", 20000),
            ),
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
        return self._build_verdict_from_parsed(parsed, "correctness")

    async def _evaluate_completeness(
        self, judge_input: ReferenceInput
    ) -> JudgeVerdict:
        """Run completeness evaluation using reference_completeness template."""
        template = load_template(
            Path(self._templates_dir) / "reference_completeness.yaml"
        )

        limits = self._config.truncation_limits

        user_prompt = render(
            template,
            task_description=_truncate(
                judge_input.task_description,
                limits.get("task_description", 2000),
            ),
            evaluation_criteria=_truncate(
                judge_input.evaluation_criteria or "",
                limits.get("agent_output", 20000),
            ),
            agent_output=_truncate(
                judge_input.agent_output,
                limits.get("agent_output", 20000),
            ),
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
        return self._build_verdict_from_parsed(parsed, "completeness")

    def _build_verdict_from_parsed(
        self,
        parsed: dict[str, Any],
        evaluation_type: str,
    ) -> JudgeVerdict:
        """Build a JudgeVerdict from parsed LLM response.

        Args:
            parsed: Parsed JSON response dict.
            evaluation_type: Either 'correctness' or 'completeness'.

        Returns:
            JudgeVerdict with dimension scores.
        """
        raw_dim_scores = parsed.get("dimension_scores", {})
        dim_scores = _build_dimension_scores(
            raw_dim_scores, _DEFAULT_REFERENCE_DIMENSIONS
        )
        overall = parsed.get("overall_score", _compute_weighted_score(dim_scores))

        metadata: dict[str, Any] = {
            "evaluation_type": evaluation_type,
            "raw_response": parsed,
        }
        if "context_file_coverage" in parsed:
            metadata["context_file_coverage"] = parsed["context_file_coverage"]
        if "criteria_coverage" in parsed:
            metadata["criteria_coverage"] = parsed["criteria_coverage"]

        scoring_scale = self._config.scoring_scale
        if scoring_scale == "likert_5":
            metadata["scoring_mode"] = "likert_5"

        return JudgeVerdict(
            mode=EvaluationMode.REFERENCE_BASED,
            scores=dim_scores,
            overall_score=float(overall),
            reasoning=str(parsed.get("reasoning", "")),
            evidence=[str(parsed.get("reasoning", ""))],
            confidence=float(parsed.get("confidence", 0.0)),
            model_id=self._backend.model_id,
            metadata=metadata,
        )

    def _merge_verdicts(
        self,
        correctness: JudgeVerdict,
        completeness: JudgeVerdict | None,
        task_type: str,
        context_coverage: float,
        judge_input: ReferenceInput,
    ) -> JudgeVerdict:
        """Merge correctness and completeness verdicts into a single verdict.

        When completeness is None (missing evaluation_criteria), only
        correctness scores are used.

        Args:
            correctness: Verdict from correctness evaluation.
            completeness: Verdict from completeness evaluation, or None.
            task_type: Detected task type ('code_modification' or 'analysis').
            context_coverage: Context file coverage ratio.
            judge_input: Original input for reference.

        Returns:
            Merged JudgeVerdict with all dimension scores.
        """
        merged_scores = dict(correctness.scores)

        if completeness is not None:
            for dim_name, dim_score in completeness.scores.items():
                if dim_name not in merged_scores:
                    merged_scores[dim_name] = dim_score

        overall = _compute_weighted_score(merged_scores)

        all_reasonings = [correctness.reasoning]
        if completeness is not None:
            all_reasonings.append(completeness.reasoning)

        confidence_values = [correctness.confidence]
        if completeness is not None:
            confidence_values.append(completeness.confidence)
        avg_confidence = sum(confidence_values) / len(confidence_values)

        metadata: dict[str, Any] = {
            "task_type": task_type,
            "context_file_coverage": context_coverage,
            "has_completeness_eval": completeness is not None,
        }

        if correctness.metadata.get("raw_response"):
            metadata["correctness_response"] = correctness.metadata["raw_response"]
        if completeness is not None and completeness.metadata.get("raw_response"):
            metadata["completeness_response"] = completeness.metadata["raw_response"]
        if completeness is not None and completeness.metadata.get("criteria_coverage"):
            metadata["criteria_coverage"] = completeness.metadata["criteria_coverage"]

        missing_dims: list[str] = []
        for dim in _DEFAULT_REFERENCE_DIMENSIONS:
            if dim not in merged_scores:
                missing_dims.append(dim)
                logger.warning(
                    "Dimension '%s' missing from evaluation for task %s",
                    dim,
                    judge_input.task_id,
                )
        if missing_dims:
            metadata["missing_dimensions"] = missing_dims

        return JudgeVerdict(
            mode=EvaluationMode.REFERENCE_BASED,
            scores=merged_scores,
            overall_score=float(overall),
            reasoning="\n---\n".join(all_reasonings),
            evidence=all_reasonings,
            confidence=avg_confidence,
            model_id=self._backend.model_id,
            metadata=metadata,
        )
