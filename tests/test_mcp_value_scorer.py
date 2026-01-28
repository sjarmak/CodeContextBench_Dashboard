"""Tests for MCP Value Scorer."""

from typing import Any

import pytest
from src.task_selection.mcp_value_scorer import (
    MCPValueScorer,
    ScoredTask,
    ScoringWeights,
    CATEGORY_WEIGHTS,
)


class TestScoringWeights:
    """Tests for ScoringWeights configuration."""

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights should sum to 1.0."""
        weights = ScoringWeights()
        total = (
            weights.context_complexity
            + weights.cross_file_deps
            + weights.semantic_search_potential
            + weights.task_category_weight
        )
        assert abs(total - 1.0) < 0.001

    def test_custom_weights_validation(self) -> None:
        """Custom weights must sum to 1.0."""
        # Valid custom weights
        weights = ScoringWeights(
            context_complexity=0.25,
            cross_file_deps=0.25,
            semantic_search_potential=0.25,
            task_category_weight=0.25,
        )
        assert weights.context_complexity == 0.25

    def test_invalid_weights_raise_error(self) -> None:
        """Weights that don't sum to 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            ScoringWeights(
                context_complexity=0.5,
                cross_file_deps=0.5,
                semantic_search_potential=0.5,
                task_category_weight=0.5,
            )


class TestMCPValueScorer:
    """Tests for MCPValueScorer class."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        """Create a default scorer instance."""
        return MCPValueScorer()

    @pytest.fixture
    def simple_task(self) -> dict:
        """Create a simple task for testing."""
        return {
            "id": "test-001",
            "category": "feature",
            "description": "Add a new button to the UI",
            "files_changed": ["src/ui/button.py"],
        }

    @pytest.fixture
    def complex_task(self) -> dict:
        """Create a complex cross-file task for testing."""
        return {
            "id": "test-002",
            "category": "refactoring",
            "description": (
                "Refactor the authentication module to use a new token-based system. "
                "This involves updating the login flow, session management, and API "
                "authentication across multiple services. Need to find all usages of "
                "the old auth system and update them to use the new token validation."
            ),
            "files_changed": [
                "src/auth/token.py",
                "src/auth/session.py",
                "src/api/middleware.py",
                "src/api/routes/login.py",
                "src/services/user.py",
                "src/services/api_client.py",
                "tests/test_auth.py",
            ],
            "requirements": [
                "Token generation must be secure",
                "Session management must be backwards compatible",
                "All API endpoints must validate tokens",
                "Unit tests must pass",
                "Integration tests must pass",
                "Documentation must be updated",
            ],
            "estimated_tokens": 8000,
            "cross_module": True,
        }

    def test_scorer_initialization(self, scorer: MCPValueScorer) -> None:
        """Test scorer initializes with default weights."""
        assert scorer.weights is not None
        assert scorer.category_weights is not None

    def test_score_task_returns_float(
        self, scorer: MCPValueScorer, simple_task: dict
    ) -> None:
        """score_task should return a float between 0.0 and 1.0."""
        score = scorer.score_task(simple_task)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_score_task_complex_higher_than_simple(
        self, scorer: MCPValueScorer, simple_task: dict, complex_task: dict
    ) -> None:
        """Complex tasks should score higher than simple tasks."""
        simple_score = scorer.score_task(simple_task)
        complex_score = scorer.score_task(complex_task)
        assert complex_score > simple_score

    def test_score_task_detailed_returns_scored_task(
        self, scorer: MCPValueScorer, simple_task: dict
    ) -> None:
        """score_task_detailed should return a ScoredTask object."""
        result = scorer.score_task_detailed(simple_task)
        assert isinstance(result, ScoredTask)
        assert result.task_id == "test-001"
        assert result.task == simple_task
        assert 0.0 <= result.total_score <= 1.0
        assert "context_complexity" in result.breakdown
        assert "cross_file_deps" in result.breakdown
        assert "semantic_search_potential" in result.breakdown
        assert "task_category_weight" in result.breakdown

    def test_score_task_detailed_breakdown_valid_range(
        self, scorer: MCPValueScorer, complex_task: dict
    ) -> None:
        """All breakdown scores should be between 0.0 and 1.0."""
        result = scorer.score_task_detailed(complex_task)
        for dim, score in result.breakdown.items():
            assert 0.0 <= score <= 1.0, f"{dim} score {score} out of range"

    def test_select_top_tasks_returns_correct_count(
        self, scorer: MCPValueScorer
    ) -> None:
        """select_top_tasks should return requested number of tasks."""
        tasks = [
            {"id": f"task-{i}", "category": "feature"} for i in range(10)
        ]
        result = scorer.select_top_tasks(tasks, n=5)
        assert len(result) == 5

    def test_select_top_tasks_respects_n_limit(
        self, scorer: MCPValueScorer
    ) -> None:
        """select_top_tasks should not return more than available tasks."""
        tasks = [
            {"id": f"task-{i}", "category": "feature"} for i in range(3)
        ]
        result = scorer.select_top_tasks(tasks, n=10)
        assert len(result) == 3

    def test_select_top_tasks_sorted_descending(
        self, scorer: MCPValueScorer
    ) -> None:
        """select_top_tasks should return tasks sorted by score descending."""
        tasks: list[dict[str, Any]] = [
            {"id": "low", "category": "typo", "description": "Fix typo"},
            {"id": "high", "category": "refactoring", "description": "Major refactoring across the codebase", "files_changed": ["a.py", "b.py", "c.py"]},
            {"id": "medium", "category": "feature", "description": "Add new feature with some complexity"},
        ]
        result = scorer.select_top_tasks(tasks, n=3)
        assert result[0].task_id == "high"
        assert result[-1].task_id == "low"
        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].total_score >= result[i + 1].total_score

    def test_select_top_tasks_min_score_filter(
        self, scorer: MCPValueScorer
    ) -> None:
        """select_top_tasks should filter by minimum score."""
        tasks: list[dict[str, Any]] = [
            {"id": "low", "category": "typo"},
            {"id": "high", "category": "refactoring", "files_changed": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py"]},
        ]
        # Use a threshold that separates the two tasks (high ~0.28, low ~0.04)
        result = scorer.select_top_tasks(tasks, n=10, min_score=0.1)
        # Only the high-scoring task should be returned
        task_ids = [t.task_id for t in result]
        assert "high" in task_ids
        assert "low" not in task_ids
        # All returned tasks should meet the minimum score
        for task in result:
            assert task.total_score >= 0.1

    def test_select_top_tasks_empty_list(self, scorer: MCPValueScorer) -> None:
        """select_top_tasks should handle empty task list."""
        result = scorer.select_top_tasks([], n=5)
        assert result == []


class TestContextComplexityScoring:
    """Tests for context complexity dimension."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        return MCPValueScorer()

    def test_long_description_scores_higher(self, scorer: MCPValueScorer) -> None:
        """Longer descriptions should score higher for context complexity."""
        short_task = {"id": "short", "description": "Fix bug"}
        long_task = {
            "id": "long",
            "description": "A" * 600,  # Very long description
        }
        short_result = scorer.score_task_detailed(short_task)
        long_result = scorer.score_task_detailed(long_task)
        assert (
            long_result.breakdown["context_complexity"]
            > short_result.breakdown["context_complexity"]
        )

    def test_many_requirements_scores_higher(self, scorer: MCPValueScorer) -> None:
        """More requirements should score higher."""
        few_reqs = {"id": "few", "requirements": ["req1"]}
        many_reqs = {
            "id": "many",
            "requirements": [f"req{i}" for i in range(15)],
        }
        few_result = scorer.score_task_detailed(few_reqs)
        many_result = scorer.score_task_detailed(many_reqs)
        assert (
            many_result.breakdown["context_complexity"]
            > few_result.breakdown["context_complexity"]
        )

    def test_high_token_estimate_scores_higher(
        self, scorer: MCPValueScorer
    ) -> None:
        """Higher token estimates should score higher."""
        low_tokens = {"id": "low", "estimated_tokens": 500}
        high_tokens = {"id": "high", "estimated_tokens": 15000}
        low_result = scorer.score_task_detailed(low_tokens)
        high_result = scorer.score_task_detailed(high_tokens)
        assert (
            high_result.breakdown["context_complexity"]
            > low_result.breakdown["context_complexity"]
        )


class TestCrossFileDepsScoring:
    """Tests for cross-file dependencies dimension."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        return MCPValueScorer()

    def test_many_files_scores_higher(self, scorer: MCPValueScorer) -> None:
        """More files changed should score higher."""
        single_file = {"id": "single", "files_changed": ["a.py"]}
        many_files = {
            "id": "many",
            "files_changed": [f"file{i}.py" for i in range(25)],
        }
        single_result = scorer.score_task_detailed(single_file)
        many_result = scorer.score_task_detailed(many_files)
        assert (
            many_result.breakdown["cross_file_deps"]
            > single_result.breakdown["cross_file_deps"]
        )

    def test_multiple_directories_scores_higher(
        self, scorer: MCPValueScorer
    ) -> None:
        """Files in different directories should score higher."""
        same_dir = {
            "id": "same",
            "files_changed": ["src/a.py", "src/b.py", "src/c.py"],
        }
        diff_dirs = {
            "id": "diff",
            "files_changed": [
                "src/api/a.py",
                "src/core/b.py",
                "src/utils/c.py",
                "tests/test_a.py",
                "config/settings.py",
                "docs/readme.md",
            ],
        }
        same_result = scorer.score_task_detailed(same_dir)
        diff_result = scorer.score_task_detailed(diff_dirs)
        assert (
            diff_result.breakdown["cross_file_deps"]
            > same_result.breakdown["cross_file_deps"]
        )

    def test_cross_module_flag_increases_score(
        self, scorer: MCPValueScorer
    ) -> None:
        """cross_module flag should increase score."""
        no_flag = {"id": "no_flag", "files_changed": ["a.py", "b.py"]}
        with_flag = {
            "id": "with_flag",
            "files_changed": ["a.py", "b.py"],
            "cross_module": True,
        }
        no_flag_result = scorer.score_task_detailed(no_flag)
        with_flag_result = scorer.score_task_detailed(with_flag)
        assert (
            with_flag_result.breakdown["cross_file_deps"]
            > no_flag_result.breakdown["cross_file_deps"]
        )


class TestSemanticSearchScoring:
    """Tests for semantic search potential dimension."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        return MCPValueScorer()

    def test_search_keywords_score_higher(self, scorer: MCPValueScorer) -> None:
        """Tasks with search-related keywords should score higher."""
        no_search = {"id": "no_search", "description": "Add a button"}
        with_search = {
            "id": "with_search",
            "description": "Find all usages of the deprecated function and locate where it's called across the codebase",
        }
        no_search_result = scorer.score_task_detailed(no_search)
        with_search_result = scorer.score_task_detailed(with_search)
        assert (
            with_search_result.breakdown["semantic_search_potential"]
            > no_search_result.breakdown["semantic_search_potential"]
        )

    def test_understanding_keywords_score_higher(
        self, scorer: MCPValueScorer
    ) -> None:
        """Tasks requiring understanding should score higher."""
        simple = {"id": "simple", "description": "Fix the bug"}
        understanding = {
            "id": "understanding",
            "description": "Understand how the cache system works and analyze why it fails under load",
        }
        simple_result = scorer.score_task_detailed(simple)
        understanding_result = scorer.score_task_detailed(understanding)
        assert (
            understanding_result.breakdown["semantic_search_potential"]
            > simple_result.breakdown["semantic_search_potential"]
        )


class TestCategoryScoring:
    """Tests for category-based scoring."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        return MCPValueScorer()

    def test_refactoring_scores_high(self, scorer: MCPValueScorer) -> None:
        """Refactoring category should score high."""
        task = {"id": "refactor", "category": "refactoring"}
        result = scorer.score_task_detailed(task)
        assert result.breakdown["task_category_weight"] >= 0.9

    def test_typo_scores_low(self, scorer: MCPValueScorer) -> None:
        """Typo category should score low."""
        task = {"id": "typo", "category": "typo"}
        result = scorer.score_task_detailed(task)
        assert result.breakdown["task_category_weight"] <= 0.3

    def test_unknown_category_uses_default(
        self, scorer: MCPValueScorer
    ) -> None:
        """Unknown category should use default weight."""
        task = {"id": "unknown", "category": "xyz_unknown_category_xyz"}
        result = scorer.score_task_detailed(task)
        assert result.breakdown["task_category_weight"] == CATEGORY_WEIGHTS["default"]

    def test_custom_category_weights(self) -> None:
        """Custom category weights should override defaults."""
        custom_weights = {"my_category": 0.99, "default": 0.1}
        scorer = MCPValueScorer(category_weights=custom_weights)
        task = {"id": "custom", "category": "my_category"}
        result = scorer.score_task_detailed(task)
        assert result.breakdown["task_category_weight"] == 0.99


class TestScoredTask:
    """Tests for ScoredTask dataclass."""

    def test_to_dict(self) -> None:
        """to_dict should return correct dictionary."""
        task = {"id": "test", "category": "feature"}
        scored = ScoredTask(
            task_id="test",
            task=task,
            total_score=0.75,
            breakdown={
                "context_complexity": 0.5,
                "cross_file_deps": 0.8,
                "semantic_search_potential": 0.6,
                "task_category_weight": 0.7,
            },
        )
        result = scored.to_dict()
        assert result["task_id"] == "test"
        assert result["total_score"] == 0.75
        assert result["breakdown"]["context_complexity"] == 0.5
        assert result["task"] == task


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def scorer(self) -> MCPValueScorer:
        return MCPValueScorer()

    def test_empty_task(self, scorer: MCPValueScorer) -> None:
        """Empty task should not raise error."""
        score = scorer.score_task({})
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_missing_fields(self, scorer: MCPValueScorer) -> None:
        """Task with missing fields should not raise error."""
        task = {"id": "partial"}
        score = scorer.score_task(task)
        assert isinstance(score, float)

    def test_none_values(self, scorer: MCPValueScorer) -> None:
        """Task with None values should not raise error."""
        task = {
            "id": "none_values",
            "description": None,
            "files_changed": None,
            "category": None,
        }
        score = scorer.score_task(task)
        assert isinstance(score, float)

    def test_task_id_from_different_keys(
        self, scorer: MCPValueScorer
    ) -> None:
        """ScoredTask should handle both 'id' and 'task_id' keys."""
        task1 = {"id": "from_id", "category": "feature"}
        task2 = {"task_id": "from_task_id", "category": "feature"}
        result1 = scorer.score_task_detailed(task1)
        result2 = scorer.score_task_detailed(task2)
        assert result1.task_id == "from_id"
        assert result2.task_id == "from_task_id"

    def test_score_bounds(self, scorer: MCPValueScorer) -> None:
        """Score should always be between 0.0 and 1.0."""
        # Task designed to maximize score
        max_task = {
            "id": "max",
            "category": "refactoring",
            "description": "A" * 1000,
            "instructions": "find locate search discover trace track across throughout understand analyze how does why does",
            "files_changed": [f"dir{i}/file{j}.py" for i in range(10) for j in range(5)],
            "requirements": [f"req{i}" for i in range(20)],
            "estimated_tokens": 50000,
            "cross_module": True,
        }
        score = scorer.score_task(max_task)
        assert score <= 1.0

        # Empty task (minimum score)
        min_task: dict[str, Any] = {}
        score = scorer.score_task(min_task)
        assert score >= 0.0
