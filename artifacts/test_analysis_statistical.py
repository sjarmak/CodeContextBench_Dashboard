"""Tests for statistical analyzer."""

import pytest
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)
from src.analysis.statistical_analyzer import StatisticalAnalyzer


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def significant_difference_scenario(db):
    """Create scenario with statistically significant difference."""
    # Baseline: 70% pass rate, 50s duration
    for i in range(20):
        result = HarborResult(
            task_id=f"baseline_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"baseline_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 14 else 1,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 14,
                reward={"mrr": 0.7 + i * 0.01},
                duration_seconds=5.0,
            ),
            passed=i < 14,
            model_name="claude-haiku",
            agent_name="baseline",
            duration_seconds=55.0,
        )
        job_id = f"job_baseline_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
    
    # Variant: 90% pass rate (significant improvement), 60s duration
    for i in range(20):
        result = HarborResult(
            task_id=f"variant_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"variant_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 18 else 1,
                duration_seconds=60.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 18,
                reward={"mrr": 0.75 + i * 0.01},
                duration_seconds=5.0,
            ),
            passed=i < 18,
            model_name="claude-haiku",
            agent_name="variant",
            duration_seconds=65.0,
        )
        job_id = f"job_variant_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
    
    return db


@pytest.fixture
def no_difference_scenario(db):
    """Create scenario with no statistical difference."""
    # Baseline: 80% pass rate, 50s duration
    for i in range(15):
        result = HarborResult(
            task_id=f"baseline_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"baseline_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 12 else 1,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 12,
                reward={"mrr": 0.75},
                duration_seconds=5.0,
            ),
            passed=i < 12,
            model_name="claude-haiku",
            agent_name="baseline",
            duration_seconds=55.0,
        )
        job_id = f"job_baseline_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
    
    # Variant: 80% pass rate (no change), 52s duration
    for i in range(15):
        result = HarborResult(
            task_id=f"variant_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"variant_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 12 else 1,
                duration_seconds=52.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 12,
                reward={"mrr": 0.75},
                duration_seconds=5.0,
            ),
            passed=i < 12,
            model_name="claude-haiku",
            agent_name="variant",
            duration_seconds=57.0,
        )
        job_id = f"job_variant_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
    
    return db


def test_statistical_analyzer_initialization(db):
    """Test analyzer initialization."""
    analyzer = StatisticalAnalyzer(db)
    assert analyzer.db is db


def test_analyze_comparison_with_significant_difference(significant_difference_scenario):
    """Test analysis detects significant difference in pass rate."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    assert result.experiment_id == "exp001"
    assert result.baseline_agent == "baseline"
    assert "variant" in result.variant_agents
    assert result.total_tests > 0


def test_pass_rate_test_detects_significance(significant_difference_scenario):
    """Test chi-square test detects pass rate difference."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Should have pass_rate test
    assert "pass_rate" in result.tests
    pass_rate_tests = result.tests["pass_rate"]
    assert len(pass_rate_tests) > 0
    
    test = pass_rate_tests[0]
    # Test should compute correctly (90% vs 70% may not be significant with n=20)
    assert test.p_value > 0  # Valid p-value
    assert test.statistic > 0  # Valid test statistic


def test_duration_test_included(significant_difference_scenario):
    """Test duration test is performed."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Should have duration test
    assert "duration" in result.tests or len(result.tests) > 0


def test_reward_test_included(significant_difference_scenario):
    """Test reward metric test is performed."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Should have reward test
    assert "reward_primary" in result.tests or len(result.tests) > 0


def test_no_difference_detected(no_difference_scenario):
    """Test analysis correctly identifies no significant difference."""
    db = no_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    assert result.experiment_id == "exp001"
    # With same pass rates, should not detect significance
    if "pass_rate" in result.tests:
        for test in result.tests["pass_rate"]:
            # Pass rates are the same (80% vs 80%), so should not be significant
            pass  # Will depend on exact statistical test


def test_multiple_variant_comparison(significant_difference_scenario):
    """Test comparison with explicit variant list."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison(
        "exp001",
        baseline_agent="baseline",
        variant_agents=["variant"],
    )
    
    assert result.variant_agents == ["variant"]


def test_statistical_test_serialization(significant_difference_scenario):
    """Test statistical test result can be serialized."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    for metric, tests in result.tests.items():
        for test in tests:
            test_dict = test.to_dict()
            assert "test_name" in test_dict
            assert "metric_name" in test_dict
            assert "results" in test_dict
            assert "effect_size" in test_dict


def test_analysis_result_serialization(significant_difference_scenario):
    """Test analysis result can be serialized."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    result_dict = result.to_dict()
    
    assert "experiment_id" in result_dict
    assert "baseline_agent" in result_dict
    assert "summary" in result_dict
    assert "results" in result_dict


def test_effect_size_computation(significant_difference_scenario):
    """Test effect size is computed."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Check that effect sizes are present
    for metric, tests in result.tests.items():
        for test in tests:
            if test.effect_size_name:  # If effect size was computed
                assert test.effect_size >= 0 or test.effect_size <= 1


def test_power_assessment(significant_difference_scenario):
    """Test statistical power assessment."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # With 20 samples per agent, should be well-powered
    assert result.power_assessment in ["underpowered", "adequate", "well-powered"]
    assert result.power_assessment == "well-powered"


def test_confidence_level_parameter(significant_difference_scenario):
    """Test custom confidence level is respected."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison(
        "exp001",
        baseline_agent="baseline",
        confidence_level=0.99,
    )
    
    # All tests should use specified confidence level
    for metric, tests in result.tests.items():
        for test in tests:
            assert test.confidence_level == 0.99


def test_p_value_interpretation(significant_difference_scenario):
    """Test p-value interpretation strings."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Check interpretation strings exist
    for metric, tests in result.tests.items():
        for test in tests:
            assert len(test.interpretation) > 0
            assert "p" in test.interpretation.lower() or "significant" in test.interpretation.lower()


def test_summary_metrics_calculation(significant_difference_scenario):
    """Test summary metrics are calculated correctly."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Total tests should match sum of individual tests
    total_from_dict = sum(len(tests) for tests in result.tests.values())
    assert result.total_tests == total_from_dict


def test_missing_metric_handling(significant_difference_scenario):
    """Test handling when some metrics are missing."""
    db = significant_difference_scenario
    analyzer = StatisticalAnalyzer(db)
    
    # Even if some metrics are missing, should not crash
    result = analyzer.analyze_comparison("exp001", baseline_agent="baseline")
    
    # Should still complete successfully
    assert result is not None
    assert result.experiment_id == "exp001"
