"""Tests for failure analyzer."""

import pytest
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)
from src.ingest.transcript_parser import TranscriptMetrics
from src.analysis.failure_analyzer import FailureAnalyzer


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def failure_scenario(db):
    """Create scenario with various types of failures."""
    # Hard tasks that fail
    for i in range(4):
        result = HarborResult(
            task_id=f"hard_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"hard_task_{i:03d}",
                task_name=f"Hard Task {i}",
                category="complex_refactoring",
                difficulty="hard",
            ),
            agent_output=HarborAgentOutput(
                exit_code=1,
                duration_seconds=60.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=False,
                reward={"mrr": 0.3},
                duration_seconds=5.0,
            ),
            passed=False,
            agent_name="test_agent",
            duration_seconds=65.0,
        )
        db.store_harbor_result(result, "exp001")
    
    # Timeout failures (long duration)
    for i in range(2):
        result = HarborResult(
            task_id=f"timeout_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"timeout_task_{i:03d}",
                task_name=f"Timeout Task {i}",
                category="architecture",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=124,  # Timeout exit code
                duration_seconds=400.0,  # Very long
            ),
            verifier_result=HarborVerifierResult(
                passed=False,
                reward={"mrr": 0.2},
                duration_seconds=5.0,
            ),
            passed=False,
            agent_name="test_agent",
            duration_seconds=405.0,
        )
        db.store_harbor_result(result, "exp001")
    
    # Low-quality solutions
    for i in range(3):
        result = HarborResult(
            task_id=f"low_quality_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"low_quality_{i:03d}",
                task_name=f"Low Quality {i}",
                category="feature_addition",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=False,
                reward={"mrr": 0.1},  # Very low score
                duration_seconds=5.0,
            ),
            passed=False,
            agent_name="test_agent",
            duration_seconds=55.0,
        )
        db.store_harbor_result(result, "exp001")
    
    # Some passing tasks for context
    for i in range(5):
        result = HarborResult(
            task_id=f"passing_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"passing_task_{i:03d}",
                task_name=f"Passing Task {i}",
                category="bug_fix",
                difficulty="easy",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=30.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=True,
                reward={"mrr": 0.9},
                duration_seconds=5.0,
            ),
            passed=True,
            agent_name="test_agent",
            duration_seconds=35.0,
        )
        db.store_harbor_result(result, "exp001")
    
    return db


def test_failure_analyzer_initialization(db):
    """Test analyzer initialization."""
    analyzer = FailureAnalyzer(db)
    assert analyzer.db is db


def test_analyze_failures(failure_scenario):
    """Test basic failure analysis."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    assert result.experiment_id == "exp001"
    assert result.agent_name == "test_agent"
    assert result.total_failures == 9
    assert result.total_tasks == 14
    assert result.failure_rate == pytest.approx(9/14, rel=0.01)


def test_pattern_detection(failure_scenario):
    """Test failure pattern detection."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    # Should detect multiple patterns
    assert len(result.patterns) > 0
    
    # Check pattern names
    pattern_names = [p.pattern_name for p in result.patterns]
    assert any("Difficulty" in name for name in pattern_names)
    assert any("Duration" in name or "timeout" in name.lower() for name in pattern_names)


def test_top_failing_categories(failure_scenario):
    """Test extraction of top failing categories."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    # Should identify top failing categories
    categories = [cat for cat, count in result.top_failing_categories]
    assert len(categories) > 0
    # Complex refactoring has 4 failures
    assert "complex_refactoring" in categories


def test_high_difficulty_pattern(failure_scenario):
    """Test detection of high-difficulty pattern."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    # Should have hard difficulty pattern
    hard_patterns = [p for p in result.patterns if "Difficulty" in p.pattern_name]
    assert len(hard_patterns) > 0
    
    pattern = hard_patterns[0]
    assert pattern.frequency == 4  # 4 hard tasks failed
    assert "hard" in pattern.common_difficulties


def test_duration_pattern(failure_scenario):
    """Test detection of duration-related failures."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    duration_patterns = [p for p in result.patterns if "Duration" in p.pattern_name]
    assert len(duration_patterns) > 0
    
    pattern = duration_patterns[0]
    assert pattern.frequency >= 2  # At least 2 timeout failures
    assert pattern.avg_duration_seconds > 300


def test_low_quality_pattern(failure_scenario):
    """Test detection of low-quality solutions."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    quality_patterns = [p for p in result.patterns if "Quality" in p.pattern_name]
    assert len(quality_patterns) > 0


def test_failure_rate_calculation(failure_scenario):
    """Test failure rate is calculated correctly."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    # 9 failures out of 14 total
    expected_rate = 9 / 14
    assert result.failure_rate == pytest.approx(expected_rate, rel=0.01)


def test_failure_analysis_serialization(failure_scenario):
    """Test failure analysis result can be serialized."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    result_dict = result.to_dict()
    
    assert "experiment_id" in result_dict
    assert "agent_name" in result_dict
    assert "patterns" in result_dict
    assert "failure_stats" in result_dict
    assert result_dict["failure_stats"]["failure_rate"] == pytest.approx(9/14, rel=0.01)


def test_pattern_recommendation_included(failure_scenario):
    """Test that patterns include recommendations."""
    db = failure_scenario
    analyzer = FailureAnalyzer(db)
    
    result = analyzer.analyze_failures("exp001", agent_name="test_agent")
    
    for pattern in result.patterns:
        assert len(pattern.suggested_fix) > 0
        assert pattern.confidence > 0
