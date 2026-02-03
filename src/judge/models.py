"""Unified judge data models for all evaluation modes.

Provides frozen (immutable) dataclasses for judge inputs, outputs,
and verdicts across pairwise, direct, and reference-based evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvaluationMode(Enum):
    """Evaluation modes supported by the unified judge."""

    PAIRWISE = "pairwise"
    DIRECT = "direct"
    REFERENCE_BASED = "reference_based"


class Severity(Enum):
    """Severity level for line-level code review comments."""

    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    PRAISE = "praise"


class CommentCategory(Enum):
    """Category of a code review comment."""

    CORRECTNESS = "correctness"
    STYLE = "style"
    SECURITY = "security"
    PERFORMANCE = "performance"


@dataclass(frozen=True)
class JudgeInput:
    """Base input for all evaluation modes."""

    task_id: str
    task_description: str
    evaluation_mode: EvaluationMode
    ground_truth: str | None = None
    evaluation_criteria: str | None = None


@dataclass(frozen=True)
class PairwiseInput(JudgeInput):
    """Input for pairwise comparison evaluation.

    outputs is keyed by condition name (e.g. BASELINE, MCP_BASE, MCP_FULL).
    """

    outputs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectInput(JudgeInput):
    """Input for direct (PR-review style) evaluation."""

    agent_output: str = ""
    code_changes: str | None = None
    trajectory: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class ReferenceInput(JudgeInput):
    """Input for reference-based evaluation against ground truth."""

    agent_output: str = ""
    reference_answer: str = ""
    context_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LineComment:
    """A line-level code review comment."""

    file_path: str
    line_range: tuple[int, int]
    severity: Severity
    comment: str
    category: CommentCategory


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single evaluation dimension."""

    dimension: str
    score: float
    weight: float
    evidence: str
    reasoning: str


@dataclass(frozen=True)
class JudgeVerdict:
    """Verdict from a single judge evaluation."""

    mode: EvaluationMode
    scores: dict[str, DimensionScore]
    overall_score: float
    reasoning: str
    evidence: list[str]
    confidence: float
    model_id: str
    line_comments: list[LineComment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PairwiseVerdict(JudgeVerdict):
    """Verdict from a pairwise comparison evaluation."""

    rankings: list[str] = field(default_factory=list)
    win_rates: dict[str, float] = field(default_factory=dict)
    preference_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    ties: int = 0


@dataclass(frozen=True)
class EnsembleVerdict:
    """Verdict from a multi-model ensemble evaluation."""

    consensus_score: float
    per_model_verdicts: list[JudgeVerdict]
    vote_distribution: dict[str, Any]
    agreement_score: float
    confidence: float
