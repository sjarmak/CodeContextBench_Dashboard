"""Direct (PR-review style) evaluation with line comments and dimensional scoring.

Provides structured code review with severity-categorized line comments,
configurable dimension weights, and optional custom rubric loading from YAML.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.judge.backends.protocol import JudgeBackend
from src.judge.engine import (
    JudgeConfig,
    _build_dimension_scores,
    _compute_weighted_score,
    _parse_line_comments,
    _truncate,
    parse_json_response,
)
from src.judge.models import (
    DimensionScore,
    EvaluationMode,
    DirectInput,
    JudgeVerdict,
)
from src.judge.prompts.loader import load_template, render

logger = logging.getLogger(__name__)

_DEFAULT_DIRECT_DIMENSIONS: dict[str, float] = {
    "Correctness": 0.3,
    "Completeness": 0.25,
    "Code Quality": 0.2,
    "Efficiency": 0.15,
    "Security": 0.1,
}


def load_rubric(path: str | Path) -> dict[str, float]:
    """Load custom dimension rubric from a YAML file.

    The YAML file should have a top-level 'dimensions' key mapping
    dimension names to their weights.

    Args:
        path: Path to the rubric YAML file.

    Returns:
        Dictionary mapping dimension names to weights.

    Raises:
        FileNotFoundError: If the rubric file does not exist.
        ValueError: If the rubric file has invalid format.
    """
    import yaml

    rubric_path = Path(path)
    if not rubric_path.exists():
        raise FileNotFoundError(f"Rubric file not found: {rubric_path}")

    with open(rubric_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Rubric file must be a YAML mapping, got {type(data).__name__}")

    dimensions = data.get("dimensions", data)
    if not isinstance(dimensions, dict):
        raise ValueError("Rubric must contain a 'dimensions' mapping")

    result: dict[str, float] = {}
    for name, weight in dimensions.items():
        result[str(name)] = float(weight)

    return result


class DirectEvaluator:
    """Evaluates agent output in PR-review style with line comments.

    Provides per-dimension scoring, line-level comments with severity
    and category, and weighted aggregate scoring.

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

    async def evaluate(self, judge_input: DirectInput) -> JudgeVerdict:
        """Evaluate agent output with PR-review style analysis.

        Loads the direct_review prompt template, renders with input data,
        calls the backend, and parses the response into a JudgeVerdict
        with line comments.

        Args:
            judge_input: Direct evaluation input with agent output and
                optional code changes.

        Returns:
            JudgeVerdict with dimension scores, line comments, and
            weighted overall score.
        """
        dimensions = dict(self._config.dimensions)
        rubric_path = self._resolve_rubric_path()
        if rubric_path is not None:
            try:
                dimensions = load_rubric(rubric_path)
                logger.info("Loaded custom rubric from %s", rubric_path)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("Failed to load rubric %s: %s", rubric_path, exc)

        template = load_template(
            Path(self._templates_dir) / "direct_review.yaml"
        )

        limits = self._config.truncation_limits
        dimensions_text = "\n".join(
            f"- {dim} (weight: {weight})"
            for dim, weight in dimensions.items()
        )

        user_prompt = render(
            template,
            task_description=_truncate(
                judge_input.task_description,
                limits.get("task_description", 2000),
            ),
            dimensions=dimensions_text,
            agent_output=_truncate(
                judge_input.agent_output,
                limits.get("agent_output", 20000),
            ),
            code_changes=_truncate(
                judge_input.code_changes or "No code changes provided.",
                limits.get("code_changes", 20000),
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
        return self._build_verdict(parsed, dimensions)

    def _build_verdict(
        self,
        parsed: dict[str, Any],
        dimensions: dict[str, float],
    ) -> JudgeVerdict:
        """Build JudgeVerdict from parsed LLM response.

        Args:
            parsed: Parsed JSON response from the LLM.
            dimensions: Dimension name to weight mapping for score building.

        Returns:
            JudgeVerdict with scores, line comments, and metadata.
        """
        raw_dim_scores = parsed.get("dimension_scores", {})
        dim_scores = _build_dimension_scores(raw_dim_scores, dimensions)

        overall = parsed.get("overall_score")
        if overall is None:
            overall = _compute_weighted_score(dim_scores)

        raw_comments = parsed.get("line_comments", [])
        line_comments = _parse_line_comments(raw_comments)

        return JudgeVerdict(
            mode=EvaluationMode.DIRECT,
            scores=dim_scores,
            overall_score=float(overall),
            reasoning=str(parsed.get("reasoning", "")),
            evidence=[str(parsed.get("reasoning", ""))],
            confidence=float(parsed.get("confidence", 0.0)),
            model_id=self._backend.model_id,
            line_comments=line_comments,
            metadata={"raw_response": parsed},
        )

    def _resolve_rubric_path(self) -> Path | None:
        """Check for a custom rubric in configs/judge_templates/.

        Returns the path to direct_rubric.yaml if it exists, otherwise None.
        """
        templates_parent = Path(self._templates_dir).parent
        rubric_dir = templates_parent / "judge_templates"
        rubric_path = rubric_dir / "direct_rubric.yaml"
        if rubric_path.exists():
            return rubric_path
        return None
