"""
MCP Value Scorer for task selection across benchmarks.

Provides a reusable scoring framework to select high-MCP-value tasks
from any benchmark based on multiple dimensions that correlate with
MCP (Model Context Protocol) benefit.

Scoring dimensions:
- context_complexity (weight: 0.3): How complex is the context the task requires
- cross_file_deps (weight: 0.3): Degree of cross-file dependencies
- semantic_search_potential (weight: 0.2): Potential benefit from semantic search
- task_category_weight (weight: 0.2): Category-specific weights for MCP value
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoringWeights:
    """Configurable weights for MCP value scoring dimensions."""

    context_complexity: float = 0.3
    cross_file_deps: float = 0.3
    semantic_search_potential: float = 0.2
    task_category_weight: float = 0.2

    def __post_init__(self) -> None:
        """Validate weights sum to 1.0."""
        total = (
            self.context_complexity
            + self.cross_file_deps
            + self.semantic_search_potential
            + self.task_category_weight
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass
class ScoredTask:
    """A task with its MCP value score and breakdown."""

    task_id: str
    task: dict[str, Any]
    total_score: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "total_score": self.total_score,
            "breakdown": self.breakdown,
            "task": self.task,
        }


# Category weights for MCP value - higher values indicate more MCP benefit
CATEGORY_WEIGHTS: dict[str, float] = {
    # High MCP value categories
    "refactoring": 0.95,
    "cross_module": 0.90,
    "architecture": 0.90,
    "debugging": 0.85,
    "integration": 0.85,
    "migration": 0.80,
    "api_design": 0.75,
    "feature": 0.70,
    "testing": 0.65,
    # Medium MCP value categories
    "documentation": 0.50,
    "configuration": 0.45,
    "ui": 0.40,
    # Lower MCP value categories
    "typo": 0.20,
    "formatting": 0.15,
    "comment": 0.10,
    # Default
    "default": 0.50,
}


class MCPValueScorer:
    """
    Scorer for evaluating task MCP (Model Context Protocol) value.

    Helps select tasks from benchmarks that will benefit most from
    MCP-enabled tools like semantic search, cross-file navigation,
    and context-aware assistance.
    """

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        category_weights: dict[str, float] | None = None,
    ) -> None:
        """
        Initialize the scorer.

        Args:
            weights: Custom scoring weights. Uses defaults if None.
            category_weights: Custom category weights. Uses defaults if None.
        """
        self.weights = weights or ScoringWeights()
        self.category_weights = category_weights or CATEGORY_WEIGHTS

    def score_task(self, task: dict[str, Any]) -> float:
        """
        Score a single task for MCP value.

        Args:
            task: Task dictionary with fields like 'id', 'category',
                  'files_changed', 'description', etc.

        Returns:
            Float score between 0.0 and 1.0 indicating MCP value.
        """
        breakdown = self._compute_breakdown(task)

        total = (
            breakdown["context_complexity"] * self.weights.context_complexity
            + breakdown["cross_file_deps"] * self.weights.cross_file_deps
            + breakdown["semantic_search_potential"] * self.weights.semantic_search_potential
            + breakdown["task_category_weight"] * self.weights.task_category_weight
        )

        return min(1.0, max(0.0, total))

    def score_task_detailed(self, task: dict[str, Any]) -> ScoredTask:
        """
        Score a task and return detailed breakdown.

        Args:
            task: Task dictionary.

        Returns:
            ScoredTask with total score and component breakdown.
        """
        breakdown = self._compute_breakdown(task)
        total_score = self.score_task(task)
        task_id = str(task.get("id", task.get("task_id", "unknown")))

        return ScoredTask(
            task_id=task_id,
            task=task,
            total_score=total_score,
            breakdown=breakdown,
        )

    def select_top_tasks(
        self,
        tasks: list[dict[str, Any]],
        n: int,
        min_score: float = 0.0,
    ) -> list[ScoredTask]:
        """
        Select the top N tasks by MCP value score.

        Args:
            tasks: List of task dictionaries.
            n: Number of top tasks to select.
            min_score: Minimum score threshold (default: 0.0).

        Returns:
            List of ScoredTask objects, sorted by score descending.
        """
        scored = [self.score_task_detailed(task) for task in tasks]
        filtered = [s for s in scored if s.total_score >= min_score]
        sorted_tasks = sorted(filtered, key=lambda x: x.total_score, reverse=True)
        return sorted_tasks[:n]

    def _compute_breakdown(self, task: dict[str, Any]) -> dict[str, float]:
        """
        Compute score breakdown for each dimension.

        Args:
            task: Task dictionary.

        Returns:
            Dictionary mapping dimension names to scores (0.0-1.0).
        """
        return {
            "context_complexity": self._score_context_complexity(task),
            "cross_file_deps": self._score_cross_file_deps(task),
            "semantic_search_potential": self._score_semantic_search(task),
            "task_category_weight": self._score_category(task),
        }

    def _score_context_complexity(self, task: dict[str, Any]) -> float:
        """
        Score based on context complexity.

        Factors:
        - Description length (longer = more complex)
        - Number of requirements/criteria
        - Estimated tokens
        """
        score = 0.0

        # Description length contributes up to 0.4
        description = task.get("description", "") or ""
        desc_len = len(description)
        if desc_len > 500:
            score += 0.4
        elif desc_len > 200:
            score += 0.3
        elif desc_len > 100:
            score += 0.2
        elif desc_len > 50:
            score += 0.1

        # Requirements count contributes up to 0.3
        requirements = task.get("requirements", []) or []
        criteria = task.get("acceptance_criteria", []) or []
        req_count = len(requirements) + len(criteria)
        if req_count > 10:
            score += 0.3
        elif req_count > 5:
            score += 0.2
        elif req_count > 2:
            score += 0.1

        # Estimated tokens contributes up to 0.3
        estimated_tokens = task.get("estimated_tokens", 0) or 0
        if estimated_tokens > 10000:
            score += 0.3
        elif estimated_tokens > 5000:
            score += 0.2
        elif estimated_tokens > 2000:
            score += 0.1

        return min(1.0, score)

    def _score_cross_file_deps(self, task: dict[str, Any]) -> float:
        """
        Score based on cross-file dependencies.

        Factors:
        - Number of files changed
        - Files in different directories
        - Import/dependency mentions
        """
        score = 0.0

        # Files changed contributes up to 0.5
        files_changed = task.get("files_changed", []) or []
        num_files = task.get("num_files", len(files_changed))
        if num_files > 20:
            score += 0.5
        elif num_files > 10:
            score += 0.4
        elif num_files > 5:
            score += 0.3
        elif num_files > 2:
            score += 0.2
        elif num_files > 1:
            score += 0.1

        # Directory spread contributes up to 0.3
        if files_changed:
            dirs = {self._get_parent_dir(f) for f in files_changed}
            num_dirs = len(dirs)
            if num_dirs > 5:
                score += 0.3
            elif num_dirs > 3:
                score += 0.2
            elif num_dirs > 1:
                score += 0.1

        # Cross-module flag contributes up to 0.2
        if task.get("cross_module") or task.get("cross_file"):
            score += 0.2

        return min(1.0, score)

    def _score_semantic_search(self, task: dict[str, Any]) -> float:
        """
        Score based on semantic search potential.

        Factors:
        - Keywords indicating search need (find, locate, where, etc.)
        - References to unknown locations
        - Codebase exploration indicators
        """
        score = 0.0

        # Check description for search indicators
        description = str(task.get("description", "")).lower()
        instructions = str(task.get("instructions", "")).lower()
        combined = description + " " + instructions

        search_keywords = [
            "find", "locate", "search", "discover", "identify",
            "where", "which file", "which module", "look for",
            "trace", "follow", "track down", "investigate",
            "codebase", "repository", "across", "throughout",
        ]

        keyword_count = sum(1 for kw in search_keywords if kw in combined)
        if keyword_count > 5:
            score += 0.5
        elif keyword_count > 3:
            score += 0.4
        elif keyword_count > 1:
            score += 0.3
        elif keyword_count > 0:
            score += 0.2

        # Exploration/understanding indicators
        understanding_keywords = [
            "understand", "comprehend", "analyze", "examine",
            "how does", "why does", "explain", "behavior",
        ]

        understand_count = sum(1 for kw in understanding_keywords if kw in combined)
        if understand_count > 2:
            score += 0.3
        elif understand_count > 0:
            score += 0.2

        # Unknown location indicators
        unknown_keywords = [
            "somewhere", "unknown", "not sure where",
            "might be", "could be", "possibly in",
        ]

        unknown_count = sum(1 for kw in unknown_keywords if kw in combined)
        if unknown_count > 0:
            score += 0.2

        return min(1.0, score)

    def _score_category(self, task: dict[str, Any]) -> float:
        """
        Score based on task category.

        Uses predefined category weights mapping category names
        to MCP value scores.
        """
        category = str(task.get("category", "")).lower()

        # Direct match
        if category in self.category_weights:
            return self.category_weights[category]

        # Partial match
        for cat_name, weight in self.category_weights.items():
            if cat_name in category or category in cat_name:
                return weight

        # Default
        return self.category_weights.get("default", 0.5)

    @staticmethod
    def _get_parent_dir(file_path: str) -> str:
        """Extract parent directory from file path."""
        parts = file_path.replace("\\", "/").rsplit("/", 1)
        return parts[0] if len(parts) > 1 else ""
