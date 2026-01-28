"""Tests for experiment comparator."""

import pytest
import json
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)
from src.ingest.transcript_parser import TranscriptMetrics
from src.analysis.comparator import ExperimentComparator


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def sample_results(db):
    """Create sample results for two agents."""
    # Baseline agent results (80% pass rate)
    for i in range(10):
        result = HarborResult(
            task_id=f"baseline_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"baseline_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 8,  # 8 pass, 2 fail
                reward={"mrr": 0.8 + i * 0.02},
                duration_seconds=10.0,
            ),
            passed=i < 8,
            model_name="claude-haiku",
            agent_name="baseline",
        )
        job_id = f"job_baseline_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
        
        # Add tool usage
        metrics = TranscriptMetrics()
        metrics.total_tool_calls = 15
        metrics.mcp_calls = 5
        metrics.deep_search_calls = 1
        metrics.local_calls = 9
        metrics.mcp_vs_local_ratio = 0.67
        metrics.success_rate = 0.9
        db.store_tool_usage(result.task_id, metrics, "exp001", job_id)
    
    # Variant agent results (90% pass rate, more MCP usage)
    for i in range(10):
        result = HarborResult(
            task_id=f"variant_task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"variant_task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=60.0,  # Slightly slower
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 9,  # 9 pass, 1 fail
                reward={"mrr": 0.85 + i * 0.01},
                duration_seconds=10.0,
            ),
            passed=i < 9,
            model_name="claude-haiku",
            agent_name="variant",
        )
        job_id = f"job_variant_{i:03d}"
        # Total is agent + verifier duration
        result.duration_seconds = 60.0 + 10.0
        db.store_harbor_result(result, "exp001", job_id)
        
        # Add tool usage (more MCP)
        metrics = TranscriptMetrics()
        metrics.total_tool_calls = 18
        metrics.mcp_calls = 10  # Higher MCP usage
        metrics.deep_search_calls = 2
        metrics.local_calls = 6
        metrics.mcp_vs_local_ratio = 2.0
        metrics.success_rate = 0.92
        db.store_tool_usage(result.task_id, metrics, "exp001", job_id)
    
    return db


def test_comparator_initialization(db):
    """Test comparator initialization."""
    comparator = ExperimentComparator(db)
    assert comparator.db is db


def test_compare_experiment(sample_results):
    """Test basic experiment comparison."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    assert result.experiment_id == "exp001"
    assert result.baseline_agent == "baseline"
    assert "variant" in result.variant_agents
    assert "baseline" in result.agent_metrics
    assert "variant" in result.agent_metrics


def test_agent_metrics_computation(sample_results):
    """Test agent metrics are computed correctly."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001")
    
    # Check baseline metrics
    baseline_metrics = result.agent_metrics["baseline"]
    assert baseline_metrics.total_tasks == 10
    assert baseline_metrics.passed_tasks == 8
    assert baseline_metrics.pass_rate == pytest.approx(0.8, rel=0.01)
    
    # Check variant metrics
    variant_metrics = result.agent_metrics["variant"]
    assert variant_metrics.total_tasks == 10
    assert variant_metrics.passed_tasks == 9
    assert variant_metrics.pass_rate == pytest.approx(0.9, rel=0.01)


def test_delta_computation(sample_results):
    """Test delta computation between agents."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    delta_key = "baseline__variant"
    assert delta_key in result.deltas
    
    delta = result.deltas[delta_key]
    assert delta.baseline_agent == "baseline"
    assert delta.variant_agent == "variant"
    assert delta.pass_rate_delta == pytest.approx(0.1, rel=0.01)
    assert delta.mcp_calls_delta > 0  # Variant uses more MCP
    assert delta.duration_delta_seconds > 0  # Variant is slower


def test_best_worst_agent_selection(sample_results):
    """Test best/worst agent selection."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001")
    
    # Variant should be best (higher pass rate)
    assert result.best_agent == "variant"
    assert result.worst_agent == "baseline"


def test_comparison_result_serialization(sample_results):
    """Test comparison result can be serialized."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001")
    result_dict = result.to_dict()
    
    assert "experiment_id" in result_dict
    assert "agent_metrics" in result_dict
    assert "comparisons" in result_dict
    assert "baseline" in result_dict["agent_metrics"]


def test_mcp_impact_interpretation(sample_results):
    """Test MCP impact interpretation."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    delta = result.deltas["baseline__variant"]
    
    # Variant has more MCP calls AND better pass rate
    if delta.mcp_calls_delta > 0 and delta.pass_rate_delta > 0:
        assert delta.mcp_impact == "positive"


def test_efficiency_impact_interpretation(sample_results):
    """Test efficiency impact interpretation."""
    db = sample_results
    comparator = ExperimentComparator(db)
    
    result = comparator.compare_experiment("exp001", baseline_agent="baseline")
    
    delta = result.deltas["baseline__variant"]
    
    # Variant is slightly slower
    if delta.duration_delta_seconds > 5:
        assert delta.efficiency_impact == "slower"
