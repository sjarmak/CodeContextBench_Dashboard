"""
Agent-as-a-Judge evaluator for Harbor benchmark results.

Provides LLM-based evaluation of agent outputs against specified criteria,
supporting both Anthropic (Claude) and OpenAI backends with configurable
rate limiting and retry logic.

Usage:
    judge = AgentJudge()  # Uses ANTHROPIC_API_KEY by default
    result = judge.evaluate_result(harbor_result, criteria)
"""

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMBackend(Enum):
    """Supported LLM backends for agent-as-a-judge evaluation."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class HarborResult:
    """
    Represents a Harbor benchmark result for evaluation.

    Attributes:
        task_id: Unique identifier for the task
        task_description: Description of the task
        agent_output: The output produced by the agent
        ground_truth: Optional ground truth for comparison
        metadata: Additional metadata about the task/result
    """

    task_id: str
    task_description: str
    agent_output: str
    ground_truth: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarborResult":
        """Create from dictionary representation."""
        return cls(
            task_id=data.get("task_id", data.get("id", "unknown")),
            task_description=data.get("task_description", data.get("description", "")),
            agent_output=data.get("agent_output", data.get("output", "")),
            ground_truth=data.get("ground_truth"),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "agent_output": self.agent_output,
            "ground_truth": self.ground_truth,
            "metadata": self.metadata,
        }


@dataclass
class RequirementScore:
    """Score for a single requirement criterion."""

    criterion_id: str
    criterion_description: str
    satisfied: bool
    score: float  # 0.0 to 1.0
    reasoning: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "criterion_id": self.criterion_id,
            "criterion_description": self.criterion_description,
            "satisfied": self.satisfied,
            "score": self.score,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
        }


@dataclass
class JudgmentResult:
    """
    Result of agent-as-a-judge evaluation.

    Attributes:
        overall_score: Aggregate score from 0.0 to 1.0
        requirement_scores: Dictionary mapping criterion IDs to scores
        reasoning: Overall reasoning for the judgment
        confidence: Confidence level in the judgment (0.0 to 1.0)
        raw_response: Raw LLM response for debugging
        metadata: Additional metadata about the evaluation
    """

    overall_score: float
    requirement_scores: dict[str, RequirementScore]
    reasoning: str
    confidence: float
    raw_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "overall_score": self.overall_score,
            "requirement_scores": {
                k: v.to_dict() for k, v in self.requirement_scores.items()
            },
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "raw_response": self.raw_response,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JudgmentResult":
        """Create from dictionary representation."""
        requirement_scores = {}
        for k, v in data.get("requirement_scores", {}).items():
            if isinstance(v, dict):
                requirement_scores[k] = RequirementScore(
                    criterion_id=v.get("criterion_id", k),
                    criterion_description=v.get("criterion_description", ""),
                    satisfied=v.get("satisfied", False),
                    score=v.get("score", 0.0),
                    reasoning=v.get("reasoning", ""),
                    evidence=v.get("evidence", ""),
                )
            else:
                requirement_scores[k] = v

        return cls(
            overall_score=data.get("overall_score", 0.0),
            requirement_scores=requirement_scores,
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", 0.0),
            raw_response=data.get("raw_response", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting API calls."""

    requests_per_minute: int = 50
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0


class RateLimiter:
    """Rate limiter with exponential backoff retry logic."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize rate limiter with configuration."""
        self.config = config or RateLimitConfig()
        self._request_times: list[float] = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        minute_ago = now - 60.0

        # Clean old requests
        self._request_times = [t for t in self._request_times if t > minute_ago]

        # Check if we need to wait
        if len(self._request_times) >= self.config.requests_per_minute:
            # Wait until oldest request is more than 1 minute old
            wait_time = self._request_times[0] - minute_ago
            if wait_time > 0:
                time.sleep(wait_time)

        self._request_times.append(time.time())

    def get_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff."""
        delay = self.config.base_delay_seconds * (
            self.config.backoff_multiplier**attempt
        )
        return min(delay, self.config.max_delay_seconds)


class AgentJudge:
    """
    Agent-as-a-Judge evaluator for Harbor benchmark results.

    Evaluates agent outputs against specified criteria using LLM judgment.
    Supports both Anthropic (Claude) and OpenAI backends.
    """

    # Default model selections
    DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_OPENAI_MODEL = "gpt-4o"

    # Evaluation prompt template
    EVALUATION_PROMPT = """You are an expert evaluator assessing agent performance on a coding task.

## Task Description
{task_description}

## Agent Output
{agent_output}

## Ground Truth (if available)
{ground_truth}

## Evaluation Criteria
{criteria}

## Instructions
For each criterion, determine if the agent's output satisfies it. Provide:
1. A boolean 'satisfied' indicating if the criterion is met
2. A score from 0.0 to 1.0 indicating degree of satisfaction
3. Brief reasoning explaining your judgment
4. Evidence from the agent output supporting your judgment

After evaluating all criteria, provide:
- An overall_score (0.0-1.0) representing aggregate satisfaction
- Overall reasoning summarizing the evaluation
- A confidence score (0.0-1.0) for your judgment

## Response Format
Respond with valid JSON in exactly this format:
{{
    "criteria_evaluations": [
        {{
            "criterion_id": "<id>",
            "satisfied": true/false,
            "score": 0.0-1.0,
            "reasoning": "<explanation>",
            "evidence": "<relevant quote or reference>"
        }}
    ],
    "overall_score": 0.0-1.0,
    "reasoning": "<overall assessment>",
    "confidence": 0.0-1.0
}}"""

    def __init__(
        self,
        backend: LLMBackend | None = None,
        model: str | None = None,
        rate_limit_config: RateLimitConfig | None = None,
    ) -> None:
        """
        Initialize the AgentJudge.

        Args:
            backend: LLM backend to use. Auto-detected from environment if None.
            model: Model name to use. Uses default for backend if None.
            rate_limit_config: Rate limiting configuration.

        Raises:
            ValueError: If no valid API key found in environment.
        """
        self.backend = backend or self._detect_backend()
        self.model = model or self._get_default_model()
        self.rate_limiter = RateLimiter(rate_limit_config)

        # Lazy-loaded client
        self._client: Any = None

    def _detect_backend(self) -> LLMBackend:
        """Detect available backend from environment variables."""
        if os.environ.get("ANTHROPIC_API_KEY"):
            return LLMBackend.ANTHROPIC
        if os.environ.get("OPENAI_API_KEY"):
            return LLMBackend.OPENAI
        raise ValueError(
            "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable."
        )

    def _get_default_model(self) -> str:
        """Get default model for configured backend."""
        if self.backend == LLMBackend.ANTHROPIC:
            return self.DEFAULT_ANTHROPIC_MODEL
        return self.DEFAULT_OPENAI_MODEL

    def _get_client(self) -> Any:
        """Get or create the LLM client."""
        if self._client is not None:
            return self._client

        if self.backend == LLMBackend.ANTHROPIC:
            try:
                import anthropic

                self._client = anthropic.Anthropic()
            except ImportError as err:
                raise ImportError(
                    "anthropic package required for Anthropic backend. "
                    "Install with: pip install anthropic"
                ) from err
        else:
            try:
                import openai

                self._client = openai.OpenAI()
            except ImportError as err:
                raise ImportError(
                    "openai package required for OpenAI backend. "
                    "Install with: pip install openai"
                ) from err

        return self._client

    def evaluate_result(
        self,
        task: HarborResult,
        criteria: list[str],
    ) -> JudgmentResult:
        """
        Evaluate a Harbor result against specified criteria.

        Args:
            task: The Harbor result to evaluate.
            criteria: List of evaluation criteria descriptions.

        Returns:
            JudgmentResult with scores and reasoning.

        Raises:
            ValueError: If criteria list is empty.
            RuntimeError: If LLM call fails after retries.
        """
        if not criteria:
            raise ValueError("Criteria list cannot be empty")

        # Format criteria for prompt
        criteria_text = "\n".join(
            f"{i + 1}. [C{i + 1:03d}] {c}" for i, c in enumerate(criteria)
        )

        # Build prompt
        prompt = self.EVALUATION_PROMPT.format(
            task_description=task.task_description,
            agent_output=task.agent_output[:10000],  # Truncate long outputs
            ground_truth=task.ground_truth or "Not provided",
            criteria=criteria_text,
        )

        # Call LLM with retry logic
        response_text = self._call_llm_with_retry(prompt)

        # Parse response
        return self._parse_response(response_text, criteria)

    def _call_llm_with_retry(self, prompt: str) -> str:
        """Call LLM with rate limiting and retry logic."""
        last_error: Exception | None = None

        for attempt in range(self.rate_limiter.config.max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                return self._call_llm(prompt)
            except Exception as e:
                last_error = e
                if attempt < self.rate_limiter.config.max_retries - 1:
                    delay = self.rate_limiter.get_retry_delay(attempt)
                    time.sleep(delay)

        raise RuntimeError(
            f"LLM call failed after {self.rate_limiter.config.max_retries} retries: {last_error}"
        )

    def _call_llm(self, prompt: str) -> str:
        """Make a single LLM call."""
        client = self._get_client()

        if self.backend == LLMBackend.ANTHROPIC:
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        else:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""

    def _parse_response(
        self, response_text: str, criteria: list[str]
    ) -> JudgmentResult:
        """Parse LLM response into JudgmentResult."""
        # Try to extract JSON from response
        json_str = self._extract_json(response_text)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Return low-confidence result on parse failure
            return JudgmentResult(
                overall_score=0.0,
                requirement_scores={},
                reasoning="Failed to parse LLM response as JSON",
                confidence=0.0,
                raw_response=response_text,
                metadata={"parse_error": True},
            )

        # Build requirement scores
        requirement_scores: dict[str, RequirementScore] = {}
        criteria_evals = data.get("criteria_evaluations", [])

        for i, criterion in enumerate(criteria):
            criterion_id = f"C{i + 1:03d}"

            # Find matching evaluation
            eval_data = next(
                (
                    e
                    for e in criteria_evals
                    if e.get("criterion_id", "").upper() == criterion_id.upper()
                    or e.get("criterion_id", "") == str(i + 1)
                ),
                None,
            )

            if eval_data:
                requirement_scores[criterion_id] = RequirementScore(
                    criterion_id=criterion_id,
                    criterion_description=criterion,
                    satisfied=eval_data.get("satisfied", False),
                    score=float(eval_data.get("score", 0.0)),
                    reasoning=eval_data.get("reasoning", ""),
                    evidence=eval_data.get("evidence", ""),
                )
            else:
                # Missing evaluation - default to not satisfied
                requirement_scores[criterion_id] = RequirementScore(
                    criterion_id=criterion_id,
                    criterion_description=criterion,
                    satisfied=False,
                    score=0.0,
                    reasoning="No evaluation provided by judge",
                    evidence="",
                )

        return JudgmentResult(
            overall_score=float(data.get("overall_score", 0.0)),
            requirement_scores=requirement_scores,
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.5)),
            raw_response=response_text,
            metadata={"model": self.model, "backend": self.backend.value},
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text response."""
        # Try to find JSON block
        text = text.strip()

        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find raw JSON object
        start = text.find("{")
        if start >= 0:
            # Find matching closing brace
            depth = 0
            for i, c in enumerate(text[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]

        return text

    def evaluate_batch(
        self,
        tasks: list[HarborResult],
        criteria: list[str],
        on_progress: Any | None = None,
    ) -> list[JudgmentResult]:
        """
        Evaluate multiple Harbor results.

        Args:
            tasks: List of Harbor results to evaluate.
            criteria: List of evaluation criteria descriptions.
            on_progress: Optional callback(task_index, total) for progress updates.

        Returns:
            List of JudgmentResult objects.
        """
        results = []
        total = len(tasks)

        for i, task in enumerate(tasks):
            if on_progress:
                on_progress(i, total)

            result = self.evaluate_result(task, criteria)
            results.append(result)

        if on_progress:
            on_progress(total, total)

        return results
