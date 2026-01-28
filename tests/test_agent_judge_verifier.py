"""
Unit tests for the agent-as-a-judge verifier.

Tests cover:
- VerifierConfig creation and defaults
- VerifierResult conversion to reward.json
- Criteria loading from different sources
- Agent output loading from files and directories
- Task description loading
- AgentJudgeVerifier verification modes
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from src.evaluation.agent_judge_verifier import (
    AgentJudgeVerifier,
    VerifierConfig,
    VerifierResult,
    VerifierType,
    load_agent_output,
    load_criteria,
    load_ground_truth,
    load_task_description,
    run_verifier,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_ground_truth() -> dict[str, Any]:
    """Sample ground truth data."""
    return {
        "task_id": "test-task-001",
        "description": "Test task description",
        "evaluation_criteria": [
            "Code compiles without errors",
            "All tests pass",
            "Documentation is complete",
        ],
        "requirements": [
            {"id": "REQ-001", "description": "Implement feature X"},
            {"id": "REQ-002", "description": "Handle edge cases"},
        ],
    }


@pytest.fixture
def ground_truth_file(
    temp_dir: Path, sample_ground_truth: dict[str, Any]
) -> Path:
    """Create a ground truth file."""
    gt_path = temp_dir / "ground_truth.json"
    gt_path.write_text(json.dumps(sample_ground_truth))
    return gt_path


@pytest.fixture
def instruction_file(temp_dir: Path) -> Path:
    """Create an instruction.md file."""
    instruction_path = temp_dir / "instruction.md"
    instruction_path.write_text("# Test Task\n\nComplete this test task.")
    return instruction_path


@pytest.fixture
def agent_output_file(temp_dir: Path) -> Path:
    """Create a single agent output file."""
    output_path = temp_dir / "output.txt"
    output_path.write_text("Agent output content here")
    return output_path


@pytest.fixture
def agent_output_dir(temp_dir: Path) -> Path:
    """Create an agent output directory with multiple files."""
    output_dir = temp_dir / "output"
    output_dir.mkdir()

    (output_dir / "trajectory.json").write_text(
        json.dumps({"steps": [{"action": "test"}], "completed": True})
    )
    (output_dir / "result.json").write_text(
        json.dumps({"status": "success"})
    )
    return output_dir


# ============================================================================
# VerifierConfig Tests
# ============================================================================


class TestVerifierConfig:
    """Tests for VerifierConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = VerifierConfig()

        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_output_length == 50000
        assert config.timeout_seconds == 300
        assert config.hybrid_deterministic_weight == 0.5
        assert config.hybrid_judge_weight == 0.5
        assert config.min_confidence_threshold == 0.3

    def test_from_dict_defaults(self) -> None:
        """Test from_dict with empty dict uses defaults."""
        config = VerifierConfig.from_dict({})

        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_output_length == 50000

    def test_from_dict_custom_values(self) -> None:
        """Test from_dict with custom values."""
        data = {
            "model": "gpt-4o",
            "max_output_length": 100000,
            "timeout_seconds": 600,
            "hybrid_deterministic_weight": 0.7,
            "hybrid_judge_weight": 0.3,
            "min_confidence_threshold": 0.5,
        }
        config = VerifierConfig.from_dict(data)

        assert config.model == "gpt-4o"
        assert config.max_output_length == 100000
        assert config.timeout_seconds == 600
        assert config.hybrid_deterministic_weight == 0.7
        assert config.hybrid_judge_weight == 0.3
        assert config.min_confidence_threshold == 0.5


# ============================================================================
# VerifierResult Tests
# ============================================================================


class TestVerifierResult:
    """Tests for VerifierResult dataclass."""

    def test_basic_result(self) -> None:
        """Test basic result creation."""
        result = VerifierResult(score=0.85)

        assert result.score == 0.85
        assert result.metrics == {}
        assert result.judgment is None
        assert result.error is None

    def test_to_reward_json_basic(self) -> None:
        """Test conversion to reward.json format."""
        result = VerifierResult(
            score=0.75,
            metrics={"tests_passed": 5, "tests_failed": 2},
        )
        reward = result.to_reward_json()

        assert reward["score"] == 0.75
        assert reward["metrics"]["tests_passed"] == 5
        assert reward["metrics"]["tests_failed"] == 2

    def test_to_reward_json_with_judgment(self) -> None:
        """Test conversion with judgment data."""
        result = VerifierResult(
            score=0.9,
            metrics={"confidence": 0.85},
            judgment={"reasoning": "Good work", "details": []},
        )
        reward = result.to_reward_json()

        assert reward["score"] == 0.9
        assert "judgment" in reward
        assert reward["judgment"]["reasoning"] == "Good work"

    def test_to_reward_json_with_error(self) -> None:
        """Test conversion with error."""
        result = VerifierResult(
            score=0.0,
            error="Verification failed",
        )
        reward = result.to_reward_json()

        assert reward["score"] == 0.0
        assert reward["error"] == "Verification failed"

    def test_score_rounding(self) -> None:
        """Test that score is rounded to 4 decimal places."""
        result = VerifierResult(score=0.123456789)
        reward = result.to_reward_json()

        assert reward["score"] == 0.1235


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestLoadGroundTruth:
    """Tests for load_ground_truth function."""

    def test_load_valid_file(
        self, ground_truth_file: Path, sample_ground_truth: dict[str, Any]
    ) -> None:
        """Test loading a valid ground truth file."""
        result = load_ground_truth(ground_truth_file)

        assert result["task_id"] == sample_ground_truth["task_id"]
        assert result["description"] == sample_ground_truth["description"]

    def test_file_not_found(self, temp_dir: Path) -> None:
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_ground_truth(temp_dir / "nonexistent.json")

    def test_invalid_json(self, temp_dir: Path) -> None:
        """Test error when file contains invalid JSON."""
        invalid_path = temp_dir / "invalid.json"
        invalid_path.write_text("not valid json {")

        with pytest.raises(json.JSONDecodeError):
            load_ground_truth(invalid_path)


class TestLoadCriteria:
    """Tests for load_criteria function."""

    def test_from_evaluation_criteria(
        self, sample_ground_truth: dict[str, Any]
    ) -> None:
        """Test loading criteria from evaluation_criteria field."""
        criteria = load_criteria(sample_ground_truth)

        assert len(criteria) == 3
        assert "Code compiles without errors" in criteria

    def test_from_criteria_field(self) -> None:
        """Test loading criteria from criteria field."""
        ground_truth = {"criteria": ["Criterion 1", "Criterion 2"]}
        criteria = load_criteria(ground_truth)

        assert criteria == ["Criterion 1", "Criterion 2"]

    def test_from_requirements(self) -> None:
        """Test loading criteria from requirements with descriptions."""
        ground_truth = {
            "requirements": [
                {"id": "R1", "description": "Do X"},
                {"id": "R2", "description": "Do Y"},
            ]
        }
        criteria = load_criteria(ground_truth)

        assert "Do X" in criteria
        assert "Do Y" in criteria

    def test_from_requirements_strings(self) -> None:
        """Test loading criteria from requirements as strings."""
        ground_truth = {"requirements": ["Do X", "Do Y"]}
        criteria = load_criteria(ground_truth)

        assert criteria == ["Do X", "Do Y"]

    def test_default_criterion(self) -> None:
        """Test default criterion when none specified."""
        criteria = load_criteria({})

        assert len(criteria) == 1
        assert "successfully completed" in criteria[0].lower()

    def test_from_criteria_file(self, temp_dir: Path) -> None:
        """Test loading criteria from dedicated criteria file."""
        criteria_file = temp_dir / "criteria.json"
        criteria_file.write_text(
            json.dumps({"criteria": ["Custom criterion 1", "Custom criterion 2"]})
        )

        criteria = load_criteria({}, criteria_file)

        assert criteria == ["Custom criterion 1", "Custom criterion 2"]


class TestLoadAgentOutput:
    """Tests for load_agent_output function."""

    def test_load_single_file(self, agent_output_file: Path) -> None:
        """Test loading output from a single file."""
        output = load_agent_output(agent_output_file)

        assert output == "Agent output content here"

    def test_load_directory(self, agent_output_dir: Path) -> None:
        """Test loading output from a directory."""
        output = load_agent_output(agent_output_dir)

        assert "trajectory.json" in output
        assert "completed" in output

    def test_nonexistent_path(self, temp_dir: Path) -> None:
        """Test loading from nonexistent path returns empty string."""
        output = load_agent_output(temp_dir / "nonexistent")

        assert output == ""

    def test_max_length_truncation(self, temp_dir: Path) -> None:
        """Test output is truncated to max_length."""
        long_file = temp_dir / "long_output.txt"
        long_file.write_text("x" * 1000)

        output = load_agent_output(long_file, max_length=100)

        assert len(output) == 100


class TestLoadTaskDescription:
    """Tests for load_task_description function."""

    def test_from_instruction_file(self, instruction_file: Path) -> None:
        """Test loading description from instruction.md."""
        description = load_task_description(instruction_file)

        assert "Test Task" in description

    def test_from_ground_truth_task_description(self) -> None:
        """Test loading from ground truth task_description field."""
        ground_truth = {"task_description": "Do this task"}
        description = load_task_description(None, ground_truth)

        assert description == "Do this task"

    def test_from_ground_truth_description(self) -> None:
        """Test loading from ground truth description field."""
        ground_truth = {"description": "Task description"}
        description = load_task_description(None, ground_truth)

        assert description == "Task description"

    def test_from_ground_truth_instruction(self) -> None:
        """Test loading from ground truth instruction field."""
        ground_truth = {"instruction": "Follow these steps"}
        description = load_task_description(None, ground_truth)

        assert description == "Follow these steps"

    def test_default_description(self) -> None:
        """Test default description when nothing available."""
        description = load_task_description(None, None)

        assert "Complete" in description


# ============================================================================
# AgentJudgeVerifier Tests
# ============================================================================


class TestAgentJudgeVerifier:
    """Tests for AgentJudgeVerifier class."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        verifier = AgentJudgeVerifier()

        assert verifier.verifier_type == VerifierType.AGENT_JUDGE
        assert verifier.config.model == "claude-sonnet-4-20250514"

    def test_init_deterministic_type(self) -> None:
        """Test initialization with deterministic type."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.DETERMINISTIC)

        assert verifier.verifier_type == VerifierType.DETERMINISTIC

    def test_init_hybrid_type(self) -> None:
        """Test initialization with hybrid type."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.HYBRID)

        assert verifier.verifier_type == VerifierType.HYBRID

    def test_verify_deterministic_no_result(self) -> None:
        """Test deterministic verification without result returns error."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.DETERMINISTIC)

        result = verifier.verify(
            agent_output="test output",
            task_description="test task",
            criteria=["criterion 1"],
            deterministic_result=None,
        )

        assert result.score == 0.0
        assert result.error is not None
        assert "No deterministic result" in result.error

    def test_verify_deterministic_with_result(self) -> None:
        """Test deterministic verification with provided result."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.DETERMINISTIC)

        result = verifier.verify(
            agent_output="test output",
            task_description="test task",
            criteria=["criterion 1"],
            deterministic_result={"score": 0.8, "metrics": {"tests_passed": 4}},
        )

        assert result.score == 0.8
        assert result.metrics.get("tests_passed") == 4

    def test_verify_agent_judge_no_criteria(self) -> None:
        """Test agent-judge verification fails without criteria."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.AGENT_JUDGE)

        result = verifier.verify(
            agent_output="test output",
            task_description="test task",
            criteria=[],
        )

        assert result.score == 0.0
        assert result.error is not None
        assert "No evaluation criteria" in result.error

    def test_verify_agent_judge_no_output(self) -> None:
        """Test agent-judge verification fails without output."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.AGENT_JUDGE)

        result = verifier.verify(
            agent_output="",
            task_description="test task",
            criteria=["criterion 1"],
        )

        assert result.score == 0.0
        assert result.error is not None
        assert "No agent output" in result.error

    @patch("src.evaluation.agent_judge.AgentJudge")
    def test_verify_agent_judge_success(self, mock_judge_class: MagicMock) -> None:
        """Test successful agent-judge verification."""
        # Setup mock
        mock_judge = MagicMock()
        mock_judge_class.return_value = mock_judge

        mock_judgment = MagicMock()
        mock_judgment.overall_score = 0.85
        mock_judgment.confidence = 0.9
        mock_judgment.requirement_scores = {}
        mock_judgment.to_dict.return_value = {
            "overall_score": 0.85,
            "confidence": 0.9,
        }
        mock_judge.evaluate_result.return_value = mock_judgment

        verifier = AgentJudgeVerifier(verifier_type=VerifierType.AGENT_JUDGE)

        result = verifier.verify(
            agent_output="test output content",
            task_description="test task description",
            criteria=["criterion 1", "criterion 2"],
        )

        assert result.score == 0.85
        assert result.error is None
        assert result.judgment is not None

    @patch("src.evaluation.agent_judge.AgentJudge")
    def test_verify_agent_judge_low_confidence(
        self, mock_judge_class: MagicMock
    ) -> None:
        """Test agent-judge verification with low confidence."""
        mock_judge = MagicMock()
        mock_judge_class.return_value = mock_judge

        mock_judgment = MagicMock()
        mock_judgment.overall_score = 0.5
        mock_judgment.confidence = 0.1  # Below threshold
        mock_judgment.requirement_scores = {}
        mock_judgment.to_dict.return_value = {
            "overall_score": 0.5,
            "confidence": 0.1,
        }
        mock_judge.evaluate_result.return_value = mock_judgment

        verifier = AgentJudgeVerifier(verifier_type=VerifierType.AGENT_JUDGE)

        result = verifier.verify(
            agent_output="test output",
            task_description="test task",
            criteria=["criterion 1"],
        )

        assert result.score == 0.5
        assert result.error is not None
        assert "Low confidence" in result.error


class TestVerifyHybrid:
    """Tests for hybrid verification mode."""

    def test_hybrid_equal_weights(self) -> None:
        """Test hybrid verification with equal weights."""
        verifier = AgentJudgeVerifier(verifier_type=VerifierType.HYBRID)

        # Mock the agent judge to avoid actual API calls
        with patch.object(
            verifier, "_verify_agent_judge"
        ) as mock_judge:
            mock_judge.return_value = VerifierResult(
                score=0.8,
                metrics={"confidence": 0.9},
            )

            result = verifier.verify(
                agent_output="test",
                task_description="task",
                criteria=["c1"],
                deterministic_result={"score": 0.6, "metrics": {}},
            )

            # (0.5 * 0.6) + (0.5 * 0.8) = 0.7
            assert abs(result.score - 0.7) < 0.01
            assert result.metrics.get("hybrid_mode") is True

    def test_hybrid_custom_weights(self) -> None:
        """Test hybrid verification with custom weights."""
        config = VerifierConfig(
            hybrid_deterministic_weight=0.7,
            hybrid_judge_weight=0.3,
        )
        verifier = AgentJudgeVerifier(
            verifier_type=VerifierType.HYBRID,
            config=config,
        )

        with patch.object(
            verifier, "_verify_agent_judge"
        ) as mock_judge:
            mock_judge.return_value = VerifierResult(
                score=1.0,
                metrics={"confidence": 0.9},
            )

            result = verifier.verify(
                agent_output="test",
                task_description="task",
                criteria=["c1"],
                deterministic_result={"score": 0.5, "metrics": {}},
            )

            # (0.7 * 0.5) + (0.3 * 1.0) = 0.35 + 0.3 = 0.65
            assert abs(result.score - 0.65) < 0.01


# ============================================================================
# Integration Tests
# ============================================================================


class TestRunVerifier:
    """Integration tests for run_verifier function."""

    def test_run_verifier_file_not_found(self, temp_dir: Path) -> None:
        """Test run_verifier with missing ground truth."""
        output_path = temp_dir / "reward.json"

        result = run_verifier(
            agent_output_path=temp_dir / "output",
            ground_truth_path=temp_dir / "missing.json",
            output_path=output_path,
        )

        assert result.score == 0.0
        assert result.error is not None
        assert "not found" in result.error.lower()
        assert output_path.exists()

    def test_run_verifier_invalid_json(self, temp_dir: Path) -> None:
        """Test run_verifier with invalid ground truth JSON."""
        gt_path = temp_dir / "ground_truth.json"
        gt_path.write_text("invalid json")
        output_path = temp_dir / "reward.json"

        result = run_verifier(
            agent_output_path=temp_dir / "output",
            ground_truth_path=gt_path,
            output_path=output_path,
        )

        assert result.score == 0.0
        assert result.error is not None
        assert "invalid" in result.error.lower()

    def test_run_verifier_creates_output_file(
        self,
        temp_dir: Path,
        ground_truth_file: Path,
        agent_output_file: Path,
    ) -> None:
        """Test that run_verifier creates output file."""
        output_path = temp_dir / "results" / "reward.json"

        # Mock the verifier to avoid API calls
        with patch(
            "src.evaluation.agent_judge_verifier.AgentJudgeVerifier.verify"
        ) as mock_verify:
            mock_verify.return_value = VerifierResult(
                score=0.75,
                metrics={"test": True},
            )

            result = run_verifier(
                agent_output_path=agent_output_file,
                ground_truth_path=ground_truth_file,
                output_path=output_path,
                verifier_type="agent_judge",
            )

            assert output_path.exists()
            assert result.score == 0.75

            # Check output file contents
            output_data = json.loads(output_path.read_text())
            assert output_data["score"] == 0.75

    def test_run_verifier_deterministic_mode(
        self,
        temp_dir: Path,
        ground_truth_file: Path,
        agent_output_file: Path,
    ) -> None:
        """Test run_verifier in deterministic mode."""
        output_path = temp_dir / "reward.json"

        # No deterministic result provided
        result = run_verifier(
            agent_output_path=agent_output_file,
            ground_truth_path=ground_truth_file,
            output_path=output_path,
            verifier_type="deterministic",
        )

        assert result.score == 0.0
        assert result.error is not None


# ============================================================================
# VerifierType Enum Tests
# ============================================================================


class TestVerifierTypeEnum:
    """Tests for VerifierType enum."""

    def test_values(self) -> None:
        """Test enum values."""
        assert VerifierType.DETERMINISTIC.value == "deterministic"
        assert VerifierType.AGENT_JUDGE.value == "agent_judge"
        assert VerifierType.HYBRID.value == "hybrid"

    def test_from_string(self) -> None:
        """Test creating enum from string."""
        assert VerifierType("deterministic") == VerifierType.DETERMINISTIC
        assert VerifierType("agent_judge") == VerifierType.AGENT_JUDGE
        assert VerifierType("hybrid") == VerifierType.HYBRID

    def test_invalid_value(self) -> None:
        """Test error with invalid value."""
        with pytest.raises(ValueError):
            VerifierType("invalid")
