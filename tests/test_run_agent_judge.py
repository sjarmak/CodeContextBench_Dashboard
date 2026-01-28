"""
Tests for the run_agent_judge.py CLI script.

Tests cover:
- Criteria loading from JSON and YAML
- Harbor result file discovery
- Harbor result loading and parsing
- Summary computation
- CLI argument parsing
"""

import json
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Import from the scripts directory
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_agent_judge import (
    EvaluationSummary,
    compute_summary,
    find_harbor_results,
    load_criteria,
    load_harbor_result,
)
from src.evaluation.agent_judge import JudgmentResult, RequirementScore


class TestLoadCriteria:
    """Tests for load_criteria function."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_json_array(self, temp_dir: Path) -> None:
        """Test loading criteria from JSON array."""
        criteria_file = temp_dir / "criteria.json"
        criteria_file.write_text(
            json.dumps(["Criterion 1", "Criterion 2", "Criterion 3"])
        )

        result = load_criteria(criteria_file)

        assert result == ["Criterion 1", "Criterion 2", "Criterion 3"]

    def test_load_json_object(self, temp_dir: Path) -> None:
        """Test loading criteria from JSON object with 'criteria' key."""
        criteria_file = temp_dir / "criteria.json"
        criteria_file.write_text(
            json.dumps(
                {
                    "criteria": ["Criterion A", "Criterion B"],
                    "version": "1.0",
                }
            )
        )

        result = load_criteria(criteria_file)

        assert result == ["Criterion A", "Criterion B"]

    def test_load_yaml_list(self, temp_dir: Path) -> None:
        """Test loading criteria from YAML list."""
        pytest.importorskip("yaml")

        criteria_file = temp_dir / "criteria.yaml"
        criteria_file.write_text("- Criterion 1\n- Criterion 2\n- Criterion 3")

        result = load_criteria(criteria_file)

        assert result == ["Criterion 1", "Criterion 2", "Criterion 3"]

    def test_load_yaml_object(self, temp_dir: Path) -> None:
        """Test loading criteria from YAML object with 'criteria' key."""
        pytest.importorskip("yaml")

        criteria_file = temp_dir / "criteria.yml"
        criteria_file.write_text("criteria:\n  - Criterion X\n  - Criterion Y")

        result = load_criteria(criteria_file)

        assert result == ["Criterion X", "Criterion Y"]

    def test_file_not_found(self, temp_dir: Path) -> None:
        """Test error when criteria file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_criteria(temp_dir / "nonexistent.json")

    def test_invalid_json_format(self, temp_dir: Path) -> None:
        """Test error with invalid JSON format (not array or object with criteria)."""
        criteria_file = temp_dir / "criteria.json"
        criteria_file.write_text(json.dumps({"other_key": "value"}))

        with pytest.raises(ValueError, match="must be a JSON/YAML array"):
            load_criteria(criteria_file)

    def test_converts_to_strings(self, temp_dir: Path) -> None:
        """Test that numeric criteria are converted to strings."""
        criteria_file = temp_dir / "criteria.json"
        criteria_file.write_text(json.dumps([1, 2, 3]))

        result = load_criteria(criteria_file)

        assert result == ["1", "2", "3"]


class TestFindHarborResults:
    """Tests for find_harbor_results function."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_find_results_in_task_subdirs(self, temp_dir: Path) -> None:
        """Test finding result.json in task subdirectories."""
        # Create task directories with results
        (temp_dir / "task-001").mkdir()
        (temp_dir / "task-001" / "result.json").write_text("{}")

        (temp_dir / "task-002").mkdir()
        (temp_dir / "task-002" / "result.json").write_text("{}")

        result = find_harbor_results(temp_dir)

        assert len(result) == 2
        task_ids = [t[0] for t in result]
        assert "task-001" in task_ids
        assert "task-002" in task_ids

    def test_find_nested_results(self, temp_dir: Path) -> None:
        """Test finding result.json in nested directories."""
        (temp_dir / "run" / "task-001").mkdir(parents=True)
        (temp_dir / "run" / "task-001" / "result.json").write_text("{}")

        result = find_harbor_results(temp_dir)

        assert len(result) == 1
        assert result[0][0] == "task-001"

    def test_empty_directory(self, temp_dir: Path) -> None:
        """Test with directory containing no results."""
        result = find_harbor_results(temp_dir)

        assert result == []

    def test_deduplication_prefers_shorter_path(self, temp_dir: Path) -> None:
        """Test that duplicate task IDs use shorter path."""
        # Create same task ID at different depths
        (temp_dir / "task-001").mkdir()
        (temp_dir / "task-001" / "result.json").write_text('{"v": 1}')

        (temp_dir / "deep" / "nested" / "task-001").mkdir(parents=True)
        (temp_dir / "deep" / "nested" / "task-001" / "result.json").write_text(
            '{"v": 2}'
        )

        result = find_harbor_results(temp_dir)

        # Should only have one result with shorter path
        assert len(result) == 1
        assert result[0][0] == "task-001"
        assert "deep" not in str(result[0][1])


class TestLoadHarborResult:
    """Tests for load_harbor_result function."""

    @pytest.fixture
    def temp_dir(self) -> Generator[Path, None, None]:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_basic_result(self, temp_dir: Path) -> None:
        """Test loading a basic result.json file."""
        task_dir = temp_dir / "task-001"
        task_dir.mkdir()

        result_data = {
            "task_description": "Test task description",
            "agent_output": "Test agent output",
            "verifier_result": {"rewards": {"reward": 1.0}},
        }
        (task_dir / "result.json").write_text(json.dumps(result_data))

        result = load_harbor_result("task-001", task_dir / "result.json")

        assert result is not None
        assert result.task_id == "task-001"
        assert result.task_description == "Test task description"
        assert result.agent_output == "Test agent output"

    def test_load_with_instruction_file(self, temp_dir: Path) -> None:
        """Test loading result with instruction.md file."""
        task_dir = temp_dir / "task-001"
        task_dir.mkdir()

        (task_dir / "result.json").write_text(json.dumps({}))
        (task_dir / "instruction.md").write_text("# Task Instructions\nDo something.")

        result = load_harbor_result("task-001", task_dir / "result.json")

        assert result is not None
        assert "Task Instructions" in result.task_description

    def test_load_with_trajectory(self, temp_dir: Path) -> None:
        """Test loading result with trajectory.json file."""
        task_dir = temp_dir / "task-001"
        task_dir.mkdir()

        (task_dir / "result.json").write_text(json.dumps({}))
        (task_dir / "instruction.md").write_text("Test task")
        (task_dir / "trajectory.json").write_text(
            json.dumps(
                {
                    "steps": [
                        {"source": "agent", "content": "Step 1 content"},
                        {"source": "user", "content": "User input"},
                        {"source": "agent", "content": "Step 2 content"},
                    ]
                }
            )
        )

        result = load_harbor_result("task-001", task_dir / "result.json")

        assert result is not None
        assert "Step 1 content" in result.agent_output or "Step 2 content" in result.agent_output

    def test_load_with_ground_truth(self, temp_dir: Path) -> None:
        """Test loading result with ground_truth.json file."""
        task_dir = temp_dir / "task-001"
        task_dir.mkdir()

        (task_dir / "result.json").write_text(json.dumps({"agent_output": "output"}))
        (task_dir / "instruction.md").write_text("Test task")
        (task_dir / "ground_truth.json").write_text(
            json.dumps({"expected": "value", "answer": 42})
        )

        result = load_harbor_result("task-001", task_dir / "result.json")

        assert result is not None
        assert result.ground_truth is not None
        assert "expected" in result.ground_truth

    def test_load_invalid_json(self, temp_dir: Path) -> None:
        """Test handling of invalid JSON file."""
        task_dir = temp_dir / "task-001"
        task_dir.mkdir()
        (task_dir / "result.json").write_text("not valid json")

        result = load_harbor_result("task-001", task_dir / "result.json")

        assert result is None

    def test_load_missing_file(self, temp_dir: Path) -> None:
        """Test handling of missing result file."""
        result = load_harbor_result(
            "task-001", temp_dir / "nonexistent" / "result.json"
        )

        assert result is None


class TestComputeSummary:
    """Tests for compute_summary function."""

    def test_empty_judgments(self) -> None:
        """Test summary with no judgments."""
        summary = compute_summary({}, "test-model")

        assert summary.total_tasks == 0
        assert summary.successful_evaluations == 0
        assert summary.mean_overall_score == 0.0
        assert summary.model_used == "test-model"

    def test_single_judgment(self) -> None:
        """Test summary with single judgment."""
        judgments = {
            "task-001": JudgmentResult(
                overall_score=0.8,
                requirement_scores={
                    "C001": RequirementScore(
                        criterion_id="C001",
                        criterion_description="Test criterion",
                        satisfied=True,
                        score=0.8,
                        reasoning="Good",
                    )
                },
                reasoning="Overall good",
                confidence=0.9,
            )
        }

        summary = compute_summary(judgments, "test-model")

        assert summary.total_tasks == 1
        assert summary.successful_evaluations == 1
        assert summary.failed_evaluations == 0
        assert summary.mean_overall_score == 0.8
        assert summary.mean_confidence == 0.9

    def test_multiple_judgments(self) -> None:
        """Test summary with multiple judgments."""
        judgments = {
            "task-001": JudgmentResult(
                overall_score=0.9,
                requirement_scores={
                    "C001": RequirementScore(
                        criterion_id="C001",
                        criterion_description="Crit 1",
                        satisfied=True,
                        score=0.9,
                        reasoning="Good",
                    )
                },
                reasoning="Good",
                confidence=0.8,
            ),
            "task-002": JudgmentResult(
                overall_score=0.5,
                requirement_scores={
                    "C001": RequirementScore(
                        criterion_id="C001",
                        criterion_description="Crit 1",
                        satisfied=False,
                        score=0.5,
                        reasoning="Partial",
                    )
                },
                reasoning="Partial",
                confidence=0.7,
            ),
        }

        summary = compute_summary(judgments, "test-model")

        assert summary.total_tasks == 2
        assert summary.successful_evaluations == 2
        assert summary.mean_overall_score == 0.7  # (0.9 + 0.5) / 2
        assert summary.mean_confidence == 0.75  # (0.8 + 0.7) / 2

    def test_score_distribution(self) -> None:
        """Test that score distribution is computed correctly."""
        judgments = {
            "task-001": JudgmentResult(
                overall_score=0.1,
                requirement_scores={},
                reasoning="",
                confidence=0.8,
            ),
            "task-002": JudgmentResult(
                overall_score=0.3,
                requirement_scores={},
                reasoning="",
                confidence=0.8,
            ),
            "task-003": JudgmentResult(
                overall_score=0.5,
                requirement_scores={},
                reasoning="",
                confidence=0.8,
            ),
            "task-004": JudgmentResult(
                overall_score=0.7,
                requirement_scores={},
                reasoning="",
                confidence=0.8,
            ),
            "task-005": JudgmentResult(
                overall_score=0.95,
                requirement_scores={},
                reasoning="",
                confidence=0.8,
            ),
        }

        summary = compute_summary(judgments, "test-model")

        assert summary.score_distribution["0.0-0.2"] == 1  # 0.1
        assert summary.score_distribution["0.2-0.4"] == 1  # 0.3
        assert summary.score_distribution["0.4-0.6"] == 1  # 0.5
        assert summary.score_distribution["0.6-0.8"] == 1  # 0.7
        assert summary.score_distribution["0.8-1.0"] == 1  # 0.95

    def test_criteria_satisfaction(self) -> None:
        """Test that criteria satisfaction rates are computed correctly."""
        judgments = {
            "task-001": JudgmentResult(
                overall_score=0.8,
                requirement_scores={
                    "C001": RequirementScore(
                        criterion_id="C001",
                        criterion_description="Crit 1",
                        satisfied=True,
                        score=1.0,
                        reasoning="",
                    ),
                    "C002": RequirementScore(
                        criterion_id="C002",
                        criterion_description="Crit 2",
                        satisfied=False,
                        score=0.0,
                        reasoning="",
                    ),
                },
                reasoning="",
                confidence=0.8,
            ),
            "task-002": JudgmentResult(
                overall_score=0.6,
                requirement_scores={
                    "C001": RequirementScore(
                        criterion_id="C001",
                        criterion_description="Crit 1",
                        satisfied=True,
                        score=1.0,
                        reasoning="",
                    ),
                    "C002": RequirementScore(
                        criterion_id="C002",
                        criterion_description="Crit 2",
                        satisfied=True,
                        score=1.0,
                        reasoning="",
                    ),
                },
                reasoning="",
                confidence=0.8,
            ),
        }

        summary = compute_summary(judgments, "test-model")

        # C001: 2/2 satisfied = 100%
        assert summary.criteria_satisfaction["C001"] == 1.0
        # C002: 1/2 satisfied = 50%
        assert summary.criteria_satisfaction["C002"] == 0.5

    def test_failed_evaluations_excluded_from_means(self) -> None:
        """Test that failed evaluations (confidence=0) are excluded from mean calculations."""
        judgments = {
            "task-001": JudgmentResult(
                overall_score=0.8,
                requirement_scores={},
                reasoning="Good",
                confidence=0.9,
            ),
            "task-002": JudgmentResult(
                overall_score=0.0,
                requirement_scores={},
                reasoning="Failed to parse",
                confidence=0.0,  # Failed evaluation
            ),
        }

        summary = compute_summary(judgments, "test-model")

        assert summary.total_tasks == 2
        assert summary.successful_evaluations == 1
        assert summary.failed_evaluations == 1
        # Mean should only include successful evaluation
        assert summary.mean_overall_score == 0.8
        assert summary.mean_confidence == 0.9


class TestEvaluationSummary:
    """Tests for EvaluationSummary dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        summary = EvaluationSummary(
            total_tasks=10,
            successful_evaluations=8,
            failed_evaluations=2,
            mean_overall_score=0.75,
            mean_confidence=0.85,
            score_distribution={"0.8-1.0": 5, "0.6-0.8": 3},
            criteria_satisfaction={"C001": 0.9, "C002": 0.6},
            model_used="test-model",
            evaluation_timestamp="2026-01-28T12:00:00",
        )

        result = summary.to_dict()

        assert result["total_tasks"] == 10
        assert result["successful_evaluations"] == 8
        assert result["failed_evaluations"] == 2
        assert result["mean_overall_score"] == 0.75
        assert result["mean_confidence"] == 0.85
        assert result["score_distribution"]["0.8-1.0"] == 5
        assert result["criteria_satisfaction"]["C001"] == 0.9
        assert result["model_used"] == "test-model"
        assert result["evaluation_timestamp"] == "2026-01-28T12:00:00"

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        summary = EvaluationSummary()

        assert summary.total_tasks == 0
        assert summary.successful_evaluations == 0
        assert summary.failed_evaluations == 0
        assert summary.mean_overall_score == 0.0
        assert summary.score_distribution == {}
        assert summary.criteria_satisfaction == {}
        assert summary.model_used == ""
