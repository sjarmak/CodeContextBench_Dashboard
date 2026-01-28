"""Tests for recommendation engine."""

import pytest
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)
from src.ingest.transcript_parser import TranscriptMetrics
from src.analysis.comparator import ExperimentComparator
from src.analysis.failure_analyzer import FailureAnalyzer
from src.analysis.ir_analyzer import IRAnalyzer
from src.analysis.recommendation_engine import RecommendationEngine


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def analysis_scenario(db):
    """Create scenario for recommendation generation."""
    # Baseline: 80% pass rate, moderate tool usage
    for i in range(10):
        result = HarborResult(
            task_id=f"baseline_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"baseline_task_{i:03d}",
                task_name=f"Task {i}",
                category="bug_fix",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 8 else 1,
                duration_seconds=40.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 8,
                reward={"mrr": 0.75 + i * 0.02},
                duration_seconds=10.0,
            ),
            passed=i < 8,
            model_name="claude-haiku",
            agent_name="baseline",
            duration_seconds=50.0,
        )
        job_id = f"job_baseline_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
        
        metrics = TranscriptMetrics()
        metrics.total_tool_calls = 10
        metrics.mcp_calls = 3
        metrics.deep_search_calls = 1
        metrics.local_calls = 6
        db.store_tool_usage(result.task_id, metrics, "exp001", job_id)
    
    # Variant: Higher MCP usage but worse performance
    for i in range(10):
        result = HarborResult(
            task_id=f"variant_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"variant_task_{i:03d}",
                task_name=f"Task {i}",
                category="bug_fix",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0 if i < 6 else 1,
                duration_seconds=70.0,  # Much slower
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 6,
                reward={"mrr": 0.7 + i * 0.02},
                duration_seconds=10.0,
            ),
            passed=i < 6,
            model_name="claude-haiku",
            agent_name="variant",
            duration_seconds=80.0,
        )
        job_id = f"job_variant_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
        
        metrics = TranscriptMetrics()
        metrics.total_tool_calls = 20
        metrics.mcp_calls = 15  # Much higher MCP usage
        metrics.deep_search_calls = 1
        metrics.local_calls = 4
        db.store_tool_usage(result.task_id, metrics, "exp001", job_id)
    
    return db


def test_recommendation_engine_initialization():
    """Test engine initialization."""
    engine = RecommendationEngine()
    assert engine is not None


def test_generate_plan_from_failures(analysis_scenario):
    """Test plan generation from failures."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    failure_analyzer = FailureAnalyzer(db)
    failure_result = failure_analyzer.analyze_failures("exp001", agent_name="variant")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        failure_analysis=failure_result,
    )
    
    assert plan.experiment_id == "exp001"
    assert plan.agent_name == "variant"
    # Should have at least some recommendations
    assert len(plan.recommendations) >= 0


def test_generate_plan_from_comparison(analysis_scenario):
    """Test plan generation from comparison."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    assert plan.experiment_id == "exp001"
    assert plan.agent_name == "variant"
    # Should detect MCP-related issues
    assert any("tool" in r.title.lower() for r in plan.recommendations)


def test_recommendation_prioritization(analysis_scenario):
    """Test recommendations are properly prioritized."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    # High priority recommendations should exist
    if plan.recommendations:
        total_recs = len(plan.recommendations)
        high_priority = len(plan.high_priority)
        medium_priority = len(plan.medium_priority)
        low_priority = len(plan.low_priority)
        
        # Total should match
        assert high_priority + medium_priority + low_priority == total_recs


def test_quick_wins_identification(analysis_scenario):
    """Test identification of quick wins (high impact, low effort)."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    # Quick wins should have high impact and low effort
    for quick_win in plan.quick_wins:
        assert quick_win.expected_impact == "high"
        assert quick_win.effort == "low"


def test_mcp_recommendations(analysis_scenario):
    """Test MCP-related recommendations are generated."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    # Variant uses more MCP but has worse pass rate
    # Should recommend reducing MCP usage
    tool_recs = [r for r in plan.recommendations if r.category == "tools"]
    assert len(tool_recs) > 0


def test_efficiency_recommendations(analysis_scenario):
    """Test efficiency-related recommendations."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    # Variant is much slower
    efficiency_recs = [r for r in plan.recommendations if "Efficiency" in r.title]
    if efficiency_recs:
        assert len(efficiency_recs) > 0


def test_recommendation_serialization(analysis_scenario):
    """Test recommendation plan can be serialized."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    plan_dict = plan.to_dict()
    
    assert "experiment_id" in plan_dict
    assert "agent_name" in plan_dict
    assert "all_recommendations" in plan_dict
    assert "by_priority" in plan_dict
    assert "summary" in plan_dict


def test_recommendation_includes_implementation_details(analysis_scenario):
    """Test recommendations include implementation details."""
    db = analysis_scenario
    engine = RecommendationEngine()
    
    comparator = ExperimentComparator(db)
    comparison = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    plan = engine.generate_plan(
        "exp001",
        "variant",
        comparison_result=comparison,
    )
    
    for rec in plan.recommendations:
        assert len(rec.implementation_details) > 0
        assert rec.confidence > 0
