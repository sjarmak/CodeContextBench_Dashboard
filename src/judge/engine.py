"""Core UnifiedJudge engine for dispatching evaluations and parsing responses.

Routes JudgeInput to the correct evaluation mode handler, calls the backend,
and parses LLM JSON responses into JudgeVerdict objects.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.judge.backends.protocol import JudgeBackend
from src.judge.models import (
    DimensionScore,
    DirectInput,
    EvaluationMode,
    JudgeInput,
    JudgeVerdict,
    LineComment,
    PairwiseInput,
    PairwiseVerdict,
    ReferenceInput,
    Severity,
    CommentCategory,
)
from src.judge.prompts.loader import PromptTemplate, load_template, render

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "judge_prompts"

_DEFAULT_TRUNCATION_LIMITS = {
    "task_description": 2000,
    "code_changes": 20000,
    "agent_output": 20000,
}

_DEFAULT_DIMENSIONS = {
    "Correctness": 0.3,
    "Completeness": 0.25,
    "Code Quality": 0.2,
    "Efficiency": 0.15,
    "Security": 0.1,
}


class JudgeError(Exception):
    """Raised on unrecoverable judge evaluation failures."""


@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for UnifiedJudge evaluation."""

    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 2000
    dimensions: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_DIMENSIONS))
    scoring_scale: str = "0.0-1.0"
    truncation_limits: dict[str, int] = field(
        default_factory=lambda: dict(_DEFAULT_TRUNCATION_LIMITS)
    )
    pairwise_method: str = "simultaneous"
    templates_dir: str | Path = ""


def _truncate(text: str, limit: int) -> str:
    """Truncate text to limit characters, preserving whole words when possible."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.8:
        truncated = truncated[:last_space]
    return truncated + "... [truncated]"


def _strip_markdown_code_blocks(text: str) -> str:
    """Remove markdown code fences from LLM response text."""
    text = text.strip()
    pattern = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)
    match = pattern.match(text)
    if match:
        return match.group(1).strip()
    return text


def _extract_json_object(text: str) -> str:
    """Extract the first JSON object from text using brace matching."""
    start = text.find("{")
    if start == -1:
        raise JudgeError("No JSON object found in response")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise JudgeError("Unterminated JSON object in response")


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse a JSON response from an LLM, handling common formatting issues.

    Tries in order:
    1. Direct JSON parse after stripping markdown code blocks
    2. Regex extraction of first JSON object
    3. Raises JudgeError on failure

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        JudgeError: If JSON cannot be extracted or parsed.
    """
    if not text or not text.strip():
        raise JudgeError("Empty response from LLM")

    stripped = _strip_markdown_code_blocks(text)

    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    try:
        extracted = _extract_json_object(stripped)
        result = json.loads(extracted)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, JudgeError):
        pass

    try:
        extracted = _extract_json_object(text)
        result = json.loads(extracted)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, JudgeError):
        pass

    raise JudgeError(f"Failed to parse JSON from LLM response: {text[:200]}...")


def _build_dimension_scores(
    raw_scores: dict[str, Any], default_dimensions: dict[str, float]
) -> dict[str, DimensionScore]:
    """Build DimensionScore objects from parsed JSON dimension data."""
    scores: dict[str, DimensionScore] = {}
    for dim_name, dim_data in raw_scores.items():
        if isinstance(dim_data, dict):
            weight = dim_data.get("weight", default_dimensions.get(dim_name, 1.0))
            scores[dim_name] = DimensionScore(
                dimension=dim_name,
                score=float(dim_data.get("score", 0.0)),
                weight=float(weight),
                evidence=str(dim_data.get("evidence", "")),
                reasoning=str(dim_data.get("reasoning", "")),
            )
        else:
            scores[dim_name] = DimensionScore(
                dimension=dim_name,
                score=float(dim_data) if dim_data is not None else 0.0,
                weight=default_dimensions.get(dim_name, 1.0),
                evidence="",
                reasoning="",
            )
    return scores


def _compute_weighted_score(scores: dict[str, DimensionScore]) -> float:
    """Compute weighted average score from dimension scores."""
    total_weight = sum(s.weight for s in scores.values())
    if total_weight == 0:
        return 0.0
    return sum(s.score * s.weight for s in scores.values()) / total_weight


def _parse_line_comments(raw_comments: list[dict[str, Any]]) -> list[LineComment]:
    """Parse line comments from LLM response JSON."""
    comments: list[LineComment] = []
    for raw in raw_comments:
        if not isinstance(raw, dict):
            continue
        try:
            line_range_raw = raw.get("line_range", [0, 0])
            if isinstance(line_range_raw, (list, tuple)) and len(line_range_raw) >= 2:
                line_range = (int(line_range_raw[0]), int(line_range_raw[1]))
            else:
                line_range = (0, 0)

            severity_str = str(raw.get("severity", "SUGGESTION")).upper()
            try:
                severity = Severity(severity_str.lower())
            except ValueError:
                severity = Severity.SUGGESTION

            category_str = str(raw.get("category", "CORRECTNESS")).upper()
            try:
                category = CommentCategory(category_str.lower())
            except ValueError:
                category = CommentCategory.CORRECTNESS

            comments.append(
                LineComment(
                    file_path=str(raw.get("file_path", "")),
                    line_range=line_range,
                    severity=severity,
                    comment=str(raw.get("comment", "")),
                    category=category,
                )
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed line comment: %s (%s)", raw, exc)
    return comments


class UnifiedJudge:
    """Core judge engine dispatching evaluations to mode-specific handlers.

    Args:
        backend: An LLM backend implementing JudgeBackend protocol.
        config: Optional judge configuration. Uses defaults if not provided.
    """

    def __init__(
        self,
        backend: JudgeBackend,
        config: JudgeConfig | None = None,
    ) -> None:
        self._backend = backend
        self._config = config or JudgeConfig()
        self._templates_dir = Path(
            self._config.templates_dir or _DEFAULT_TEMPLATES_DIR
        )

    @property
    def backend(self) -> JudgeBackend:
        return self._backend

    @property
    def config(self) -> JudgeConfig:
        return self._config

    async def evaluate(self, judge_input: JudgeInput) -> JudgeVerdict:
        """Evaluate an input by dispatching to the correct mode handler.

        Args:
            judge_input: The evaluation input (PairwiseInput, DirectInput, or ReferenceInput).

        Returns:
            A JudgeVerdict (or PairwiseVerdict for pairwise mode).

        Raises:
            JudgeError: On unrecoverable evaluation or parse failures.
            ValueError: If input type doesn't match the declared evaluation mode.
        """
        mode = judge_input.evaluation_mode

        if mode == EvaluationMode.PAIRWISE:
            if not isinstance(judge_input, PairwiseInput):
                raise ValueError(
                    f"Pairwise mode requires PairwiseInput, got {type(judge_input).__name__}"
                )
            return await self._evaluate_pairwise(judge_input)
        elif mode == EvaluationMode.DIRECT:
            if not isinstance(judge_input, DirectInput):
                raise ValueError(
                    f"Direct mode requires DirectInput, got {type(judge_input).__name__}"
                )
            return await self._evaluate_direct(judge_input)
        elif mode == EvaluationMode.REFERENCE_BASED:
            if not isinstance(judge_input, ReferenceInput):
                raise ValueError(
                    f"Reference mode requires ReferenceInput, got {type(judge_input).__name__}"
                )
            return await self._evaluate_reference(judge_input)
        else:
            raise ValueError(f"Unsupported evaluation mode: {mode}")

    async def _evaluate_pairwise(self, judge_input: PairwiseInput) -> PairwiseVerdict:
        """Handle pairwise comparison evaluation.

        Delegates to PairwiseEvaluator with method selection via config.pairwise_method.
        Supports 'simultaneous' (default) and 'round_robin' methods.
        """
        from src.judge.modes.pairwise import PairwiseEvaluator

        evaluator = PairwiseEvaluator(
            backend=self._backend,
            config=self._config,
            templates_dir=str(self._templates_dir),
        )

        if self._config.pairwise_method == "round_robin":
            return await evaluator.evaluate_roundrobin(judge_input)
        return await evaluator.evaluate_simultaneous(judge_input)

    async def _evaluate_direct(self, judge_input: DirectInput) -> JudgeVerdict:
        """Handle direct (PR-review style) evaluation.

        Delegates to DirectEvaluator for structured PR-review with line comments,
        per-dimension scoring, and weighted aggregation.
        """
        from src.judge.modes.direct import DirectEvaluator

        evaluator = DirectEvaluator(
            backend=self._backend,
            config=self._config,
            templates_dir=str(self._templates_dir),
        )

        return await evaluator.evaluate(judge_input)

    async def _evaluate_reference(self, judge_input: ReferenceInput) -> JudgeVerdict:
        """Handle reference-based evaluation.

        Delegates to ReferenceEvaluator for structured evaluation with
        correctness, completeness, and approach alignment dimensions.
        """
        from src.judge.modes.reference import ReferenceEvaluator

        evaluator = ReferenceEvaluator(
            backend=self._backend,
            config=self._config,
            templates_dir=str(self._templates_dir),
        )

        return await evaluator.evaluate(judge_input)
