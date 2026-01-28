"""
Tests for task quality scorer.
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.quality.task_quality_scorer import (
    CriterionScore,
    QualityCriterion,
    TaskQualityReport,
    TaskQualityResult,
    TaskQualityScorer,
)


class TestCriterionScore:
    """Tests for CriterionScore dataclass."""

    def test_weighted_score(self) -> None:
        """Test weighted score calculation."""
        score = CriterionScore(
            criterion=QualityCriterion.INSTRUCTION_CLARITY,
            score=0.8,
            weight=0.35,
        )
        assert score.weighted_score() == pytest.approx(0.28, abs=0.001)

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        score = CriterionScore(
            criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
            score=0.9,
            weight=0.35,
            details={"presence": 1.0, "structure": 0.8},
            notes="Test notes",
        )
        result = score.to_dict()
        assert result["criterion"] == "ground_truth_validity"
        assert result["score"] == 0.9
        assert result["weight"] == 0.35
        assert result["weighted_score"] == pytest.approx(0.315, abs=0.001)
        assert result["details"]["presence"] == 1.0
        assert result["notes"] == "Test notes"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "criterion": "evaluation_determinism",
            "score": 0.75,
            "weight": 0.30,
            "details": {"test_script": 1.0},
            "notes": "Some notes",
        }
        score = CriterionScore.from_dict(data)
        assert score.criterion == QualityCriterion.EVALUATION_DETERMINISM
        assert score.score == 0.75
        assert score.weight == 0.30
        assert score.details["test_script"] == 1.0
        assert score.notes == "Some notes"


class TestTaskQualityResult:
    """Tests for TaskQualityResult dataclass."""

    def test_auto_compute_score(self) -> None:
        """Test automatic score computation from criterion scores."""
        criterion_scores = [
            CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.8,
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                score=0.9,
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.EVALUATION_DETERMINISM,
                score=0.7,
                weight=0.30,
            ),
        ]
        result = TaskQualityResult(
            task_id="test-001",
            task_directory="/path/to/task",
            timestamp="2024-01-01T00:00:00",
            score=0.0,  # Will be computed
            criterion_scores=criterion_scores,
            threshold=0.7,
        )
        # 0.8*0.35 + 0.9*0.35 + 0.7*0.30 = 0.28 + 0.315 + 0.21 = 0.805
        assert result.score == pytest.approx(0.805, abs=0.001)
        assert not result.needs_review  # 0.805 > 0.7

    def test_needs_review_flag(self) -> None:
        """Test that needs_review is set correctly based on threshold."""
        criterion_scores = [
            CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.5,
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                score=0.5,
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.EVALUATION_DETERMINISM,
                score=0.5,
                weight=0.30,
            ),
        ]
        result = TaskQualityResult(
            task_id="test-002",
            task_directory="/path/to/task",
            timestamp="2024-01-01T00:00:00",
            score=0.0,
            criterion_scores=criterion_scores,
            threshold=0.7,
        )
        assert result.score == pytest.approx(0.5, abs=0.001)
        assert result.needs_review  # 0.5 < 0.7

    def test_get_score_breakdown(self) -> None:
        """Test score breakdown dictionary."""
        criterion_scores = [
            CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.8,
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                score=0.9,
                weight=0.35,
            ),
        ]
        result = TaskQualityResult(
            task_id="test-003",
            task_directory="/path/to/task",
            timestamp="2024-01-01T00:00:00",
            score=0.85,
            criterion_scores=criterion_scores,
        )
        breakdown = result.get_score_breakdown()
        assert breakdown["instruction_clarity"] == 0.8
        assert breakdown["ground_truth_validity"] == 0.9

    def test_get_failing_criteria(self) -> None:
        """Test getting criteria below threshold."""
        criterion_scores = [
            CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.5,  # Below threshold
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                score=0.9,  # Above threshold
                weight=0.35,
            ),
            CriterionScore(
                criterion=QualityCriterion.EVALUATION_DETERMINISM,
                score=0.6,  # Below threshold
                weight=0.30,
            ),
        ]
        result = TaskQualityResult(
            task_id="test-004",
            task_directory="/path/to/task",
            timestamp="2024-01-01T00:00:00",
            score=0.65,
            criterion_scores=criterion_scores,
        )
        failing = result.get_failing_criteria(threshold=0.7)
        assert len(failing) == 2
        assert failing[0].criterion == QualityCriterion.INSTRUCTION_CLARITY
        assert failing[1].criterion == QualityCriterion.EVALUATION_DETERMINISM

    def test_to_dict_and_from_dict(self) -> None:
        """Test round-trip serialization."""
        criterion_scores = [
            CriterionScore(
                criterion=QualityCriterion.INSTRUCTION_CLARITY,
                score=0.8,
                weight=0.35,
            ),
        ]
        original = TaskQualityResult(
            task_id="test-005",
            task_directory="/path/to/task",
            timestamp="2024-01-01T00:00:00",
            score=0.8,
            criterion_scores=criterion_scores,
            needs_review=False,
            threshold=0.7,
            metadata={"custom": "value"},
        )
        data = original.to_dict()
        restored = TaskQualityResult.from_dict(data)

        assert restored.task_id == original.task_id
        assert restored.score == original.score
        assert restored.threshold == original.threshold
        assert restored.metadata["custom"] == "value"
        assert len(restored.criterion_scores) == 1


class TestTaskQualityReport:
    """Tests for TaskQualityReport dataclass."""

    @pytest.fixture
    def sample_results(self) -> list[TaskQualityResult]:
        """Create sample task results for testing."""
        return [
            TaskQualityResult(
                task_id="task-001",
                task_directory="/path/task-001",
                timestamp="2024-01-01T00:00:00",
                score=0.85,
                criterion_scores=[
                    CriterionScore(
                        criterion=QualityCriterion.INSTRUCTION_CLARITY,
                        score=0.85,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                        score=0.9,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.EVALUATION_DETERMINISM,
                        score=0.8,
                        weight=0.30,
                    ),
                ],
                threshold=0.7,
            ),
            TaskQualityResult(
                task_id="task-002",
                task_directory="/path/task-002",
                timestamp="2024-01-01T00:00:00",
                score=0.6,
                criterion_scores=[
                    CriterionScore(
                        criterion=QualityCriterion.INSTRUCTION_CLARITY,
                        score=0.5,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                        score=0.7,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.EVALUATION_DETERMINISM,
                        score=0.6,
                        weight=0.30,
                    ),
                ],
                needs_review=True,
                threshold=0.7,
            ),
            TaskQualityResult(
                task_id="task-003",
                task_directory="/path/task-003",
                timestamp="2024-01-01T00:00:00",
                score=0.95,
                criterion_scores=[
                    CriterionScore(
                        criterion=QualityCriterion.INSTRUCTION_CLARITY,
                        score=0.95,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.GROUND_TRUTH_VALIDITY,
                        score=1.0,
                        weight=0.35,
                    ),
                    CriterionScore(
                        criterion=QualityCriterion.EVALUATION_DETERMINISM,
                        score=0.9,
                        weight=0.30,
                    ),
                ],
                threshold=0.7,
            ),
        ]

    def test_auto_compute_statistics(
        self, sample_results: list[TaskQualityResult]
    ) -> None:
        """Test automatic statistics computation."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        assert report.total_tasks == 3
        assert report.mean_score == pytest.approx(0.8, abs=0.01)
        assert report.tasks_needing_review == 1

    def test_get_review_rate(self, sample_results: list[TaskQualityResult]) -> None:
        """Test review rate calculation."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        # 1 out of 3 needs review = 33.33%
        assert report.get_review_rate() == pytest.approx(33.33, abs=0.01)

    def test_get_tasks_needing_review(
        self, sample_results: list[TaskQualityResult]
    ) -> None:
        """Test getting tasks that need review."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        tasks = report.get_tasks_needing_review()
        assert len(tasks) == 1
        assert tasks[0].task_id == "task-002"

    def test_get_score_distribution(
        self, sample_results: list[TaskQualityResult]
    ) -> None:
        """Test score distribution buckets."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        dist = report.get_score_distribution()
        # task-002 (0.6) falls in 0.6-0.8 bucket since 0.6 >= 0.6 and 0.6 < 0.8
        assert dist["0.6-0.8"] == 1  # task-002 (0.6)
        assert dist["0.8-1.0"] == 2  # task-001 (0.85), task-003 (0.95)

    def test_get_criterion_averages(
        self, sample_results: list[TaskQualityResult]
    ) -> None:
        """Test criterion average calculation."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        avgs = report.get_criterion_averages()
        # (0.85 + 0.5 + 0.95) / 3 = 0.767
        assert avgs["instruction_clarity"] == pytest.approx(0.767, abs=0.01)
        # (0.9 + 0.7 + 1.0) / 3 = 0.867
        assert avgs["ground_truth_validity"] == pytest.approx(0.867, abs=0.01)

    def test_to_markdown(self, sample_results: list[TaskQualityResult]) -> None:
        """Test markdown report generation."""
        report = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
        )
        markdown = report.to_markdown()
        assert "# Task Quality Report: test-benchmark" in markdown
        assert "Total Tasks:** 3" in markdown
        assert "Tasks Needing Review" in markdown
        assert "task-002" in markdown

    def test_to_dict_and_from_dict(
        self, sample_results: list[TaskQualityResult]
    ) -> None:
        """Test round-trip serialization."""
        original = TaskQualityReport(
            benchmark_name="test-benchmark",
            timestamp="2024-01-01T00:00:00",
            results=sample_results,
            metadata={"version": "1.0"},
        )
        data = original.to_dict()
        restored = TaskQualityReport.from_dict(data)

        assert restored.benchmark_name == original.benchmark_name
        assert restored.total_tasks == original.total_tasks
        assert restored.mean_score == pytest.approx(original.mean_score, abs=0.001)
        assert len(restored.results) == len(original.results)


class TestTaskQualityScorer:
    """Tests for TaskQualityScorer class."""

    @pytest.fixture
    def temp_task_dir(self) -> Generator[Path, None, None]:
        """Create a temporary task directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task_dir = Path(tmpdir) / "test-task"
            task_dir.mkdir()
            yield task_dir

    @pytest.fixture
    def valid_task_dir(self, temp_task_dir: Path) -> Path:
        """Create a valid task directory with all required files."""
        # Create task.toml
        task_toml = temp_task_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "test-task-001"
category = "test"

[verifier]
timeout_sec = 300
command = "python verify.py"
"""
        )

        # Create instruction.md
        instruction_md = temp_task_dir / "instruction.md"
        instruction_md.write_text(
            """
# Task: Implement a Calculator

## Objective

Create a simple calculator that supports basic arithmetic operations.

## Requirements

1. The calculator must support addition, subtraction, multiplication, and division
2. The calculator should handle invalid input gracefully
3. Division by zero should return an appropriate error message

## Input

The calculator receives two numbers and an operator as input:
- First number: float
- Operator: one of +, -, *, /
- Second number: float

## Expected Output

The result of the arithmetic operation as a float.

## Example

```python
calculator(5, '+', 3)  # Returns 8.0
calculator(10, '/', 2) # Returns 5.0
```
"""
        )

        # Create ground_truth.json
        ground_truth = temp_task_dir / "ground_truth.json"
        ground_truth.write_text(
            json.dumps(
                {
                    "expected_output": 8.0,
                    "test_cases": [
                        {"input": [5, "+", 3], "expected": 8.0},
                        {"input": [10, "/", 2], "expected": 5.0},
                    ],
                }
            )
        )

        # Create test.sh
        test_sh = temp_task_dir / "test.sh"
        test_sh.write_text("#!/bin/bash\npython test_calculator.py")
        test_sh.chmod(0o755)

        return temp_task_dir

    @pytest.fixture
    def minimal_task_dir(self, temp_task_dir: Path) -> Path:
        """Create a minimal task directory with bare minimum content."""
        # Create minimal task.toml
        task_toml = temp_task_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "minimal-task"

[verifier]
timeout_sec = 60
command = "echo test"
"""
        )

        # Create very short instruction.md
        instruction_md = temp_task_dir / "instruction.md"
        instruction_md.write_text("Do something.")

        return temp_task_dir

    def test_scorer_initialization(self) -> None:
        """Test scorer initialization with default weights."""
        scorer = TaskQualityScorer()
        assert scorer.threshold == 0.7
        total_weight = sum(scorer.weights.values())
        assert total_weight == pytest.approx(1.0, abs=0.001)

    def test_scorer_custom_threshold(self) -> None:
        """Test scorer with custom threshold."""
        scorer = TaskQualityScorer(threshold=0.8)
        assert scorer.threshold == 0.8

    def test_scorer_custom_weights(self) -> None:
        """Test scorer with custom weights."""
        custom_weights = {
            QualityCriterion.INSTRUCTION_CLARITY: 0.5,
            QualityCriterion.GROUND_TRUTH_VALIDITY: 0.3,
            QualityCriterion.EVALUATION_DETERMINISM: 0.2,
        }
        scorer = TaskQualityScorer(weights=custom_weights)
        assert scorer.weights[QualityCriterion.INSTRUCTION_CLARITY] == 0.5
        assert scorer.weights[QualityCriterion.GROUND_TRUTH_VALIDITY] == 0.3
        assert scorer.weights[QualityCriterion.EVALUATION_DETERMINISM] == 0.2

    def test_score_valid_task(self, valid_task_dir: Path) -> None:
        """Test scoring a valid, well-structured task."""
        scorer = TaskQualityScorer()
        result = scorer.score_task(valid_task_dir)

        assert result.task_id == "test-task-001"
        assert result.score > 0.5  # Should have a decent score
        assert len(result.criterion_scores) == 3

        # Check that all criteria are scored
        criteria_names = [cs.criterion.value for cs in result.criterion_scores]
        assert "instruction_clarity" in criteria_names
        assert "ground_truth_validity" in criteria_names
        assert "evaluation_determinism" in criteria_names

    def test_score_minimal_task(self, minimal_task_dir: Path) -> None:
        """Test scoring a minimal task with poor quality."""
        scorer = TaskQualityScorer()
        result = scorer.score_task(minimal_task_dir)

        assert result.task_id == "minimal-task"
        assert result.score < 0.7  # Should be flagged for review
        assert result.needs_review

    def test_score_nonexistent_instruction(self, temp_task_dir: Path) -> None:
        """Test scoring when instruction.md is missing."""
        # Create only task.toml
        task_toml = temp_task_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "no-instruction"

[verifier]
timeout_sec = 60
command = "echo test"
"""
        )

        scorer = TaskQualityScorer()
        result = scorer.score_task(temp_task_dir)

        # Instruction clarity should be 0
        instruction_score = next(
            cs
            for cs in result.criterion_scores
            if cs.criterion == QualityCriterion.INSTRUCTION_CLARITY
        )
        assert instruction_score.score == 0.0
        assert result.needs_review

    def test_score_nonexistent_ground_truth(self, temp_task_dir: Path) -> None:
        """Test scoring when ground_truth.json is missing."""
        # Create task.toml and instruction.md but no ground_truth.json
        task_toml = temp_task_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "no-ground-truth"

[verifier]
timeout_sec = 60
command = "echo test"
"""
        )

        instruction_md = temp_task_dir / "instruction.md"
        instruction_md.write_text("# Task\n\nThis is a test task with some content.\n\n" * 10)

        scorer = TaskQualityScorer()
        result = scorer.score_task(temp_task_dir)

        # Ground truth validity should be 0
        gt_score = next(
            cs
            for cs in result.criterion_scores
            if cs.criterion == QualityCriterion.GROUND_TRUTH_VALIDITY
        )
        assert gt_score.score == 0.0

    def test_score_multiple_tasks(self, valid_task_dir: Path) -> None:
        """Test scoring multiple tasks."""
        # Create another task directory
        task2_dir = valid_task_dir.parent / "test-task-2"
        task2_dir.mkdir()

        task_toml = task2_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "test-task-002"

[verifier]
timeout_sec = 120
command = "pytest"
"""
        )

        instruction_md = task2_dir / "instruction.md"
        instruction_md.write_text("# Another Task\n\nImplement this feature.\n\n" * 5)

        scorer = TaskQualityScorer()
        report = scorer.score_multiple_tasks(
            [valid_task_dir, task2_dir],
            benchmark_name="test-benchmark",
        )

        assert report.benchmark_name == "test-benchmark"
        assert report.total_tasks == 2
        assert len(report.results) == 2

    def test_instruction_clarity_placeholders(self, temp_task_dir: Path) -> None:
        """Test that placeholders reduce instruction clarity score."""
        task_toml = temp_task_dir / "task.toml"
        task_toml.write_text(
            """
version = "1.0"

[metadata]
task_id = "placeholder-task"

[verifier]
timeout_sec = 60
command = "echo test"
"""
        )

        instruction_md = temp_task_dir / "instruction.md"
        instruction_md.write_text(
            """
# Task: {task_name}

## TODO: Add description here

Implement {feature} with {requirement}.

## Requirements

- FIXME: List requirements
- {placeholder}
"""
        )

        scorer = TaskQualityScorer()
        result = scorer.score_task(temp_task_dir)

        instruction_score = next(
            cs
            for cs in result.criterion_scores
            if cs.criterion == QualityCriterion.INSTRUCTION_CLARITY
        )
        # Should have reduced clarity score due to placeholders
        assert instruction_score.details["clarity"] < 0.8

    def test_get_criteria_descriptions(self) -> None:
        """Test getting criteria descriptions."""
        scorer = TaskQualityScorer()
        descriptions = scorer.get_criteria_descriptions()

        assert "instruction_clarity" in descriptions
        assert "ground_truth_validity" in descriptions
        assert "evaluation_determinism" in descriptions
        assert "clear" in descriptions["instruction_clarity"].lower()


class TestTaskQualityScorerIntegration:
    """Integration tests for task quality scoring."""

    @pytest.fixture
    def adapter_output_dir(self) -> Generator[Path, None, None]:
        """Create a temporary adapter output directory with multiple tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "adapter_output"
            output_dir.mkdir()

            # Create high-quality task
            task1 = output_dir / "high-quality-task"
            task1.mkdir()
            (task1 / "task.toml").write_text(
                """
version = "1.0"

[metadata]
task_id = "high-quality-task"
category = "coding"

[verifier]
timeout_sec = 300
command = "python verify.py"
"""
            )
            (task1 / "instruction.md").write_text(
                """
# Task: Implement Binary Search

## Objective

Create a function that implements binary search algorithm.

## Requirements

1. The function must accept a sorted list and a target value
2. Return the index of the target if found, -1 otherwise
3. Time complexity must be O(log n)

## Input

- `arr`: A sorted list of integers
- `target`: The integer to search for

## Expected Output

Return the index of the target element, or -1 if not found.

## Example

```python
binary_search([1, 2, 3, 4, 5], 3)  # Returns 2
binary_search([1, 2, 3, 4, 5], 6)  # Returns -1
```
"""
            )
            (task1 / "ground_truth.json").write_text(
                json.dumps(
                    {
                        "test_cases": [
                            {"input": [[1, 2, 3, 4, 5], 3], "expected": 2},
                            {"input": [[1, 2, 3, 4, 5], 6], "expected": -1},
                        ]
                    }
                )
            )
            test_sh = task1 / "test.sh"
            test_sh.write_text("#!/bin/bash\npytest")
            test_sh.chmod(0o755)

            # Create low-quality task
            task2 = output_dir / "low-quality-task"
            task2.mkdir()
            (task2 / "task.toml").write_text(
                """
version = "1.0"

[metadata]
task_id = "low-quality-task"

[verifier]
timeout_sec = 60
command = "test"
"""
            )
            (task2 / "instruction.md").write_text("Do the task TODO")

            yield output_dir

    def test_score_adapter_output(self, adapter_output_dir: Path) -> None:
        """Test scoring all tasks in an adapter output directory."""
        scorer = TaskQualityScorer()
        report = scorer.score_adapter_output(adapter_output_dir)

        assert report.benchmark_name == "adapter_output"
        assert report.total_tasks == 2
        assert report.tasks_needing_review >= 1  # Low quality task should need review

        # Check that high-quality task scores better
        high_quality = next(
            r for r in report.results if r.task_id == "high-quality-task"
        )
        low_quality = next(
            r for r in report.results if r.task_id == "low-quality-task"
        )
        assert high_quality.score > low_quality.score

    def test_report_json_output(self, adapter_output_dir: Path) -> None:
        """Test that report can be serialized to JSON."""
        scorer = TaskQualityScorer()
        report = scorer.score_adapter_output(adapter_output_dir)

        # Should be able to serialize to JSON without errors
        json_output = json.dumps(report.to_dict(), indent=2)
        assert json_output is not None

        # Should be able to deserialize
        restored = TaskQualityReport.from_dict(json.loads(json_output))
        assert restored.total_tasks == report.total_tasks
