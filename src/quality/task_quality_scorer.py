"""
Task quality scorer for individual benchmark tasks.

Scores individual tasks against HOW2BENCH quality criteria including
instruction clarity, ground truth validity, and evaluation determinism.
Each task receives a score from 0.0-1.0 with breakdowns by criterion.

Usage:
    scorer = TaskQualityScorer()
    result = scorer.score_task(task_dir)
    if result.needs_review:
        print(f"Task {result.task_id} needs review: {result.score:.2f}")
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


class QualityCriterion(Enum):
    """Quality criteria for task scoring."""

    INSTRUCTION_CLARITY = "instruction_clarity"
    GROUND_TRUTH_VALIDITY = "ground_truth_validity"
    EVALUATION_DETERMINISM = "evaluation_determinism"


@dataclass
class CriterionScore:
    """
    Score for a single quality criterion.

    Attributes:
        criterion: The quality criterion being scored
        score: Score from 0.0 to 1.0
        weight: Weight of this criterion in overall score
        details: Detailed breakdown of scoring components
        notes: Additional notes or context
    """

    criterion: QualityCriterion
    score: float
    weight: float
    details: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def weighted_score(self) -> float:
        """Calculate weighted score contribution."""
        return self.score * self.weight

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "criterion": self.criterion.value,
            "score": self.score,
            "weight": self.weight,
            "weighted_score": self.weighted_score(),
            "details": self.details,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriterionScore":
        """Create from dictionary representation."""
        return cls(
            criterion=QualityCriterion(data["criterion"]),
            score=data["score"],
            weight=data["weight"],
            details=data.get("details", {}),
            notes=data.get("notes", ""),
        )


@dataclass
class TaskQualityResult:
    """
    Quality scoring result for a single task.

    Attributes:
        task_id: Identifier for the scored task
        task_directory: Path to the task directory
        timestamp: When the scoring was performed
        score: Overall quality score (0.0-1.0)
        criterion_scores: Individual scores per criterion
        needs_review: Whether task is flagged for review
        threshold: Threshold used for flagging
        metadata: Additional metadata about the scoring
    """

    task_id: str
    task_directory: str
    timestamp: str
    score: float
    criterion_scores: list[CriterionScore]
    needs_review: bool = False
    threshold: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute overall score and review flag if not set."""
        if self.score == 0.0 and self.criterion_scores:
            self.score = sum(cs.weighted_score() for cs in self.criterion_scores)
        if not self.needs_review:
            self.needs_review = self.score < self.threshold

    def get_score_breakdown(self) -> dict[str, float]:
        """Get breakdown of scores by criterion."""
        return {cs.criterion.value: cs.score for cs in self.criterion_scores}

    def get_failing_criteria(self, threshold: float = 0.7) -> list[CriterionScore]:
        """Get list of criteria that score below threshold."""
        return [cs for cs in self.criterion_scores if cs.score < threshold]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_directory": self.task_directory,
            "timestamp": self.timestamp,
            "score": self.score,
            "criterion_scores": [cs.to_dict() for cs in self.criterion_scores],
            "needs_review": self.needs_review,
            "threshold": self.threshold,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskQualityResult":
        """Create from dictionary representation."""
        criterion_scores = [
            CriterionScore.from_dict(cs) for cs in data.get("criterion_scores", [])
        ]
        return cls(
            task_id=data["task_id"],
            task_directory=data.get("task_directory", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            score=data.get("score", 0.0),
            criterion_scores=criterion_scores,
            needs_review=data.get("needs_review", False),
            threshold=data.get("threshold", 0.7),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskQualityReport:
    """
    Aggregated quality report for multiple tasks.

    Attributes:
        benchmark_name: Name of the benchmark being scored
        timestamp: When the scoring was performed
        results: List of individual task results
        mean_score: Average score across all tasks
        tasks_needing_review: Count of tasks flagged for review
        total_tasks: Total number of tasks scored
        threshold: Threshold used for flagging
        metadata: Additional metadata about the report
    """

    benchmark_name: str
    timestamp: str
    results: list[TaskQualityResult]
    mean_score: float = 0.0
    tasks_needing_review: int = 0
    total_tasks: int = 0
    threshold: float = 0.7
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute aggregate statistics if not set."""
        if self.total_tasks == 0 and self.results:
            self._compute_statistics()

    def _compute_statistics(self) -> None:
        """Compute aggregate statistics from results."""
        self.total_tasks = len(self.results)
        if self.total_tasks > 0:
            self.mean_score = sum(r.score for r in self.results) / self.total_tasks
            self.tasks_needing_review = sum(
                1 for r in self.results if r.needs_review
            )

    def get_review_rate(self) -> float:
        """Calculate percentage of tasks needing review."""
        if self.total_tasks == 0:
            return 0.0
        return (self.tasks_needing_review / self.total_tasks) * 100.0

    def get_tasks_needing_review(self) -> list[TaskQualityResult]:
        """Get list of tasks that need review."""
        return [r for r in self.results if r.needs_review]

    def get_score_distribution(self) -> dict[str, int]:
        """Get distribution of scores in buckets."""
        buckets = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0,
        }
        for result in self.results:
            if result.score < 0.2:
                buckets["0.0-0.2"] += 1
            elif result.score < 0.4:
                buckets["0.2-0.4"] += 1
            elif result.score < 0.6:
                buckets["0.4-0.6"] += 1
            elif result.score < 0.8:
                buckets["0.6-0.8"] += 1
            else:
                buckets["0.8-1.0"] += 1
        return buckets

    def get_criterion_averages(self) -> dict[str, float]:
        """Get average score per criterion across all tasks."""
        criterion_totals: dict[str, float] = {}
        criterion_counts: dict[str, int] = {}

        for result in self.results:
            for cs in result.criterion_scores:
                key = cs.criterion.value
                criterion_totals[key] = criterion_totals.get(key, 0.0) + cs.score
                criterion_counts[key] = criterion_counts.get(key, 0) + 1

        return {
            k: criterion_totals[k] / criterion_counts[k]
            for k in criterion_totals
            if criterion_counts.get(k, 0) > 0
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "benchmark_name": self.benchmark_name,
            "timestamp": self.timestamp,
            "results": [r.to_dict() for r in self.results],
            "mean_score": self.mean_score,
            "tasks_needing_review": self.tasks_needing_review,
            "total_tasks": self.total_tasks,
            "review_rate": self.get_review_rate(),
            "threshold": self.threshold,
            "score_distribution": self.get_score_distribution(),
            "criterion_averages": self.get_criterion_averages(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskQualityReport":
        """Create from dictionary representation."""
        results = [TaskQualityResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            benchmark_name=data["benchmark_name"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            results=results,
            mean_score=data.get("mean_score", 0.0),
            tasks_needing_review=data.get("tasks_needing_review", 0),
            total_tasks=data.get("total_tasks", 0),
            threshold=data.get("threshold", 0.7),
            metadata=data.get("metadata", {}),
        )

    def to_markdown(self) -> str:
        """Generate markdown quality report."""
        lines = [
            f"# Task Quality Report: {self.benchmark_name}",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Total Tasks:** {self.total_tasks}",
            f"**Mean Score:** {self.mean_score:.3f}",
            f"**Review Threshold:** {self.threshold}",
            f"**Tasks Needing Review:** {self.tasks_needing_review} ({self.get_review_rate():.1f}%)",
            "",
            "## Score Distribution",
            "",
            "| Range | Count |",
            "|-------|-------|",
        ]

        for range_key, count in self.get_score_distribution().items():
            lines.append(f"| {range_key} | {count} |")

        lines.extend([
            "",
            "## Criterion Averages",
            "",
            "| Criterion | Average Score |",
            "|-----------|---------------|",
        ])

        for criterion, avg in self.get_criterion_averages().items():
            lines.append(f"| {criterion} | {avg:.3f} |")

        # Add tasks needing review
        tasks_for_review = self.get_tasks_needing_review()
        if tasks_for_review:
            lines.extend([
                "",
                "## Tasks Needing Review",
                "",
                "| Task ID | Score | Failing Criteria |",
                "|---------|-------|------------------|",
            ])

            for task in tasks_for_review:
                failing = ", ".join(
                    cs.criterion.value
                    for cs in task.get_failing_criteria(self.threshold)
                )
                lines.append(f"| {task.task_id} | {task.score:.3f} | {failing or 'None'} |")

        return "\n".join(lines)


class TaskQualityScorer:
    """
    Task quality scorer for benchmark tasks.

    Scores individual tasks against HOW2BENCH quality criteria:
    - Instruction Clarity: Task descriptions are clear and unambiguous
    - Ground Truth Validity: Ground truth solutions are verified as correct
    - Evaluation Determinism: Evaluation produces consistent, deterministic results

    Default weights:
    - instruction_clarity: 0.35
    - ground_truth_validity: 0.35
    - evaluation_determinism: 0.30
    """

    # Default criterion weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        QualityCriterion.INSTRUCTION_CLARITY: 0.35,
        QualityCriterion.GROUND_TRUTH_VALIDITY: 0.35,
        QualityCriterion.EVALUATION_DETERMINISM: 0.30,
    }

    # Instruction clarity scoring thresholds
    MIN_INSTRUCTION_LENGTH = 100  # characters
    GOOD_INSTRUCTION_LENGTH = 500  # characters
    MAX_INSTRUCTION_LENGTH = 10000  # characters (too long is also bad)

    # Minimum word count for instructions
    MIN_WORD_COUNT = 20
    GOOD_WORD_COUNT = 100

    def __init__(
        self,
        threshold: float = 0.7,
        weights: dict[QualityCriterion, float] | None = None,
    ) -> None:
        """
        Initialize the task quality scorer.

        Args:
            threshold: Score threshold for flagging tasks (default: 0.7)
            weights: Optional custom criterion weights
        """
        self.threshold = threshold
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

        # Normalize weights to sum to 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}

    def score_task(self, task_dir: Path | str) -> TaskQualityResult:
        """
        Score a single task against quality criteria.

        Args:
            task_dir: Path to the task directory

        Returns:
            TaskQualityResult with scores and breakdown
        """
        task_dir = Path(task_dir)
        task_id = task_dir.name

        # Load task data
        toml_data = self._load_task_toml(task_dir)
        instruction_content = self._load_instruction_md(task_dir)
        ground_truth_data = self._load_ground_truth(task_dir)

        # Update task_id from toml if available
        if toml_data and "metadata" in toml_data:
            task_id = toml_data["metadata"].get("task_id", task_id)

        # Score each criterion
        criterion_scores = [
            self._score_instruction_clarity(instruction_content, toml_data),
            self._score_ground_truth_validity(ground_truth_data, task_dir),
            self._score_evaluation_determinism(toml_data, task_dir),
        ]

        # Calculate overall score
        overall_score = sum(cs.weighted_score() for cs in criterion_scores)

        return TaskQualityResult(
            task_id=task_id,
            task_directory=str(task_dir),
            timestamp=datetime.now().isoformat(),
            score=overall_score,
            criterion_scores=criterion_scores,
            needs_review=overall_score < self.threshold,
            threshold=self.threshold,
        )

    def score_multiple_tasks(
        self,
        task_dirs: Sequence[Path | str],
        benchmark_name: str = "",
    ) -> TaskQualityReport:
        """
        Score multiple tasks and generate an aggregate report.

        Args:
            task_dirs: List of paths to task directories
            benchmark_name: Name of the benchmark (defaults to parent directory name)

        Returns:
            TaskQualityReport with all results and statistics
        """
        results = [self.score_task(d) for d in task_dirs]

        # Derive benchmark name from first task's parent directory if not provided
        if not benchmark_name and task_dirs:
            first_dir = Path(task_dirs[0])
            benchmark_name = first_dir.parent.name

        return TaskQualityReport(
            benchmark_name=benchmark_name,
            timestamp=datetime.now().isoformat(),
            results=results,
            threshold=self.threshold,
        )

    def score_adapter_output(
        self,
        adapter_dir: Path | str,
        benchmark_name: str = "",
    ) -> TaskQualityReport:
        """
        Score all tasks in an adapter output directory.

        Args:
            adapter_dir: Path to the adapter output directory
            benchmark_name: Name of the benchmark

        Returns:
            TaskQualityReport with all results
        """
        adapter_dir = Path(adapter_dir)
        if not benchmark_name:
            benchmark_name = adapter_dir.name

        # Find all task directories (directories containing task.toml)
        task_dirs: list[Path] = []
        for item in adapter_dir.iterdir():
            if item.is_dir():
                task_toml = item / "task.toml"
                if task_toml.exists():
                    task_dirs.append(item)

        return self.score_multiple_tasks(task_dirs, benchmark_name)

    def _load_task_toml(self, task_dir: Path) -> dict[str, Any]:
        """Load and parse task.toml."""
        task_toml = task_dir / "task.toml"
        if not task_toml.exists():
            return {}
        try:
            with open(task_toml, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def _load_instruction_md(self, task_dir: Path) -> str:
        """Load instruction.md content."""
        instruction_md = task_dir / "instruction.md"
        if not instruction_md.exists():
            return ""
        try:
            return instruction_md.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _load_ground_truth(self, task_dir: Path) -> dict[str, Any]:
        """Load ground_truth.json."""
        # Check common locations
        gt_locations = [
            task_dir / "ground_truth.json",
            task_dir / "tests" / "ground_truth.json",
        ]

        for location in gt_locations:
            if location.exists():
                try:
                    with open(location) as f:
                        return json.load(f)
                except Exception:
                    continue
        return {}

    def _score_instruction_clarity(
        self,
        content: str,
        toml_data: dict[str, Any],
    ) -> CriterionScore:
        """
        Score instruction clarity.

        Factors considered:
        - Length: Is the instruction sufficiently detailed but not overly verbose?
        - Structure: Does it have clear sections/formatting?
        - Completeness: Does it specify requirements, constraints, expected output?
        - Clarity: Are there unresolved placeholders, ambiguous terms?
        """
        weight = self.weights.get(QualityCriterion.INSTRUCTION_CLARITY, 0.35)
        details: dict[str, float] = {}
        notes_parts: list[str] = []

        if not content:
            return CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.0,
                weight=weight,
                details={"length": 0.0, "structure": 0.0, "completeness": 0.0, "clarity": 0.0},
                notes="No instruction.md found",
            )

        # 1. Length score (0.25 weight within criterion)
        char_count = len(content.strip())
        if char_count < self.MIN_INSTRUCTION_LENGTH:
            length_score = char_count / self.MIN_INSTRUCTION_LENGTH * 0.5
            notes_parts.append(f"Instruction too short ({char_count} chars)")
        elif char_count < self.GOOD_INSTRUCTION_LENGTH:
            length_score = 0.5 + (
                (char_count - self.MIN_INSTRUCTION_LENGTH)
                / (self.GOOD_INSTRUCTION_LENGTH - self.MIN_INSTRUCTION_LENGTH)
                * 0.5
            )
        elif char_count <= self.MAX_INSTRUCTION_LENGTH:
            length_score = 1.0
        else:
            # Too long - penalize slightly
            overflow = char_count - self.MAX_INSTRUCTION_LENGTH
            length_score = max(0.7, 1.0 - overflow / self.MAX_INSTRUCTION_LENGTH * 0.3)
            notes_parts.append(f"Instruction very long ({char_count} chars)")
        details["length"] = length_score

        # 2. Structure score (0.25 weight within criterion)
        structure_score = self._score_structure(content)
        details["structure"] = structure_score

        # 3. Completeness score (0.25 weight within criterion)
        completeness_score = self._score_completeness(content, toml_data)
        details["completeness"] = completeness_score

        # 4. Clarity score (0.25 weight within criterion)
        clarity_score, clarity_issues = self._score_clarity(content)
        details["clarity"] = clarity_score
        if clarity_issues:
            notes_parts.extend(clarity_issues)

        # Calculate weighted average
        overall = (
            details["length"] * 0.25
            + details["structure"] * 0.25
            + details["completeness"] * 0.25
            + details["clarity"] * 0.25
        )

        return CriterionScore(
            criterion=QualityCriterion.INSTRUCTION_CLARITY,
            score=overall,
            weight=weight,
            details=details,
            notes="; ".join(notes_parts) if notes_parts else "Instruction clarity adequate",
        )

    def _score_structure(self, content: str) -> float:
        """Score the structural quality of instructions."""
        score = 0.0

        # Check for headers (markdown format)
        header_count = len(re.findall(r"^#+\s+", content, re.MULTILINE))
        if header_count >= 3:
            score += 0.3
        elif header_count >= 1:
            score += 0.15

        # Check for lists (bullet points or numbered)
        list_count = len(re.findall(r"^[\s]*[-*+]\s+|^[\s]*\d+\.\s+", content, re.MULTILINE))
        if list_count >= 5:
            score += 0.25
        elif list_count >= 2:
            score += 0.15

        # Check for code blocks
        code_blocks = len(re.findall(r"```", content)) // 2
        if code_blocks >= 1:
            score += 0.25
        # Also check for inline code
        elif len(re.findall(r"`[^`]+`", content)) >= 3:
            score += 0.15

        # Check for clear paragraphs (multiple newlines)
        paragraphs = len(re.split(r"\n\s*\n", content.strip()))
        if paragraphs >= 3:
            score += 0.2
        elif paragraphs >= 2:
            score += 0.1

        return min(1.0, score)

    def _score_completeness(self, content: str, toml_data: dict[str, Any]) -> float:
        """Score the completeness of instructions."""
        score = 0.0
        content_lower = content.lower()

        # Check for key sections/concepts
        completeness_checks = [
            # Task description
            any(
                term in content_lower
                for term in ["task:", "objective:", "goal:", "implement", "create", "write"]
            ),
            # Requirements/constraints
            any(
                term in content_lower
                for term in ["requirement", "must", "should", "constraint", "criteria"]
            ),
            # Expected output/result
            any(
                term in content_lower
                for term in ["output", "result", "return", "expected", "produce"]
            ),
            # Input specification
            any(term in content_lower for term in ["input", "given", "receive", "parameter"]),
            # Examples
            any(term in content_lower for term in ["example", "sample", "instance"]),
        ]

        # Each check contributes 0.2
        score = sum(0.2 for check in completeness_checks if check)

        # Bonus for having ground truth referenced in task.toml
        if toml_data.get("verifier", {}).get("ground_truth"):
            score = min(1.0, score + 0.1)

        return min(1.0, score)

    def _score_clarity(self, content: str) -> tuple[float, list[str]]:
        """Score the clarity of instructions and return issues found."""
        score = 1.0
        issues: list[str] = []

        # Check for unresolved placeholders
        placeholder_patterns = [
            (r"\{[a-zA-Z_]+\}", "Unresolved {placeholder}"),
            (r"\[\[.*?\]\]", "Unresolved [[placeholder]]"),
            (r"\bTODO\b", "Contains TODO"),
            (r"\bFIXME\b", "Contains FIXME"),
            (r"\bXXX\b", "Contains XXX marker"),
        ]

        for pattern, issue_desc in placeholder_patterns:
            matches = re.findall(pattern, content)
            if matches:
                score -= 0.15 * min(len(matches), 3)  # Penalize up to 3 instances
                issues.append(f"{issue_desc}: {matches[:3]}")

        # Check for vague/ambiguous terms
        vague_patterns = [
            (r"\b(etc|and so on|and more)\b", "Vague language: etc/and so on"),
            (r"\b(some|several|many|few)\s+(?!of)", "Imprecise quantity"),
            (r"\b(probably|maybe|might|could be)\b", "Uncertain language"),
        ]

        for pattern, issue_desc in vague_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.05
                issues.append(issue_desc)

        return max(0.0, score), issues

    def _score_ground_truth_validity(
        self,
        ground_truth: dict[str, Any],
        task_dir: Path,
    ) -> CriterionScore:
        """
        Score ground truth validity.

        Factors considered:
        - Presence: Is ground truth data present?
        - Structure: Does it have expected format/fields?
        - Completeness: Are all required fields populated?
        - Consistency: Does ground truth match task requirements?
        """
        weight = self.weights.get(QualityCriterion.GROUND_TRUTH_VALIDITY, 0.35)
        details: dict[str, float] = {}
        notes_parts: list[str] = []

        if not ground_truth:
            return CriterionScore(
                criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                score=0.0,
                weight=weight,
                details={"presence": 0.0, "structure": 0.0, "completeness": 0.0},
                notes="No ground_truth.json found",
            )

        # 1. Presence score
        details["presence"] = 1.0

        # 2. Structure score - check for common expected fields
        expected_fields = [
            "expected_output",
            "expected_result",
            "solution",
            "answer",
            "criteria",
            "evaluation_criteria",
            "test_cases",
            "requirements",
        ]
        found_fields = [f for f in expected_fields if f in ground_truth]
        if found_fields:
            details["structure"] = min(1.0, len(found_fields) * 0.5)
        else:
            # Still valid if has some non-empty content
            details["structure"] = 0.5 if ground_truth else 0.0
            notes_parts.append("No standard ground truth fields found")

        # 3. Completeness score - check if values are populated
        non_empty_values = sum(
            1 for v in ground_truth.values()
            if v is not None and v != "" and v != [] and v != {}
        )
        total_values = len(ground_truth)
        if total_values > 0:
            details["completeness"] = non_empty_values / total_values
        else:
            details["completeness"] = 0.0

        # Calculate overall
        overall = (
            details["presence"] * 0.3
            + details["structure"] * 0.35
            + details["completeness"] * 0.35
        )

        return CriterionScore(
            criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
            score=overall,
            weight=weight,
            details=details,
            notes="; ".join(notes_parts) if notes_parts else "Ground truth adequate",
        )

    def _score_evaluation_determinism(
        self,
        toml_data: dict[str, Any],
        task_dir: Path,
    ) -> CriterionScore:
        """
        Score evaluation determinism.

        Factors considered:
        - Verifier configuration: Is there a verifier defined?
        - Timeout specification: Are timeouts reasonable?
        - Test script presence: Is test.sh present?
        - Determinism indicators: No random seeds without fixing?
        """
        weight = self.weights.get(QualityCriterion.EVALUATION_DETERMINISM, 0.30)
        details: dict[str, float] = {}
        notes_parts: list[str] = []

        # 1. Verifier configuration
        verifier = toml_data.get("verifier", {})
        if verifier:
            details["verifier_config"] = 1.0 if verifier.get("command") else 0.5
        else:
            details["verifier_config"] = 0.0
            notes_parts.append("No verifier configuration found")

        # 2. Timeout specification
        timeout = verifier.get("timeout_sec")
        if timeout is not None:
            try:
                timeout_val = float(timeout)
                if 10 <= timeout_val <= 86400:  # 10 sec to 24 hours
                    details["timeout"] = 1.0
                else:
                    details["timeout"] = 0.5
                    notes_parts.append(f"Unusual timeout: {timeout_val}s")
            except (TypeError, ValueError):
                details["timeout"] = 0.0
                notes_parts.append("Invalid timeout value")
        else:
            details["timeout"] = 0.5
            notes_parts.append("No timeout specified")

        # 3. Test script presence
        test_sh_locations = [
            task_dir / "test.sh",
            task_dir / "tests" / "test.sh",
        ]
        test_sh_found = any(loc.exists() for loc in test_sh_locations)
        details["test_script"] = 1.0 if test_sh_found else 0.0
        if not test_sh_found:
            notes_parts.append("No test.sh found")

        # 4. Determinism indicators - check for random seed handling
        determinism_score = 1.0

        # Check if verify.py exists and handles randomness
        verify_py_locations = [
            task_dir / "verify.py",
            task_dir / "tests" / "verify.py",
        ]
        for verify_py in verify_py_locations:
            if verify_py.exists():
                try:
                    verify_content = verify_py.read_text(encoding="utf-8")
                    # Penalize if using random without seed
                    if "random" in verify_content.lower():
                        if "seed" not in verify_content.lower():
                            determinism_score = 0.7
                            notes_parts.append("Verifier uses random without explicit seed")
                except Exception:
                    pass

        # Check for non-deterministic patterns in toml
        verifier_cmd = verifier.get("command", "")
        if isinstance(verifier_cmd, str):
            if "random" in verifier_cmd.lower() and "seed" not in verifier_cmd.lower():
                determinism_score = min(determinism_score, 0.7)

        details["determinism"] = determinism_score

        # Calculate overall
        overall = (
            details.get("verifier_config", 0.0) * 0.30
            + details.get("timeout", 0.0) * 0.20
            + details.get("test_script", 0.0) * 0.25
            + details.get("determinism", 0.0) * 0.25
        )

        return CriterionScore(
            criterion=QualityCriterion.EVALUATION_DETERMINISM,
            score=overall,
            weight=weight,
            details=details,
            notes="; ".join(notes_parts) if notes_parts else "Evaluation appears deterministic",
        )

    def get_criteria_descriptions(self) -> dict[str, str]:
        """Get descriptions for each quality criterion."""
        return {
            QualityCriterion.INSTRUCTION_CLARITY.value: (
                "Task descriptions are clear, well-structured, and unambiguous. "
                "Includes proper formatting, required sections, and no placeholders."
            ),
            QualityCriterion.GROUND_TRUTH_VALIDITY.value: (
                "Ground truth solutions are present, properly structured, "
                "and contain all necessary fields for evaluation."
            ),
            QualityCriterion.EVALUATION_DETERMINISM.value: (
                "Evaluation produces consistent, deterministic results. "
                "Includes verifier configuration, timeouts, and test scripts."
            ),
        }
