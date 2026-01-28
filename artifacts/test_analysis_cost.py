"""Tests for cost analyzer."""

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
from src.analysis.cost_analyzer import (
    CostAnalyzer,
    CostMetrics,
    CostDelta,
    CostAnalysisResult,
    CLAUDE_PRICING,
)


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def basic_scenario(db):
    """Create basic scenario with two agents."""
    # Baseline: 70% pass rate, moderate tokens
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
                exit_code=0 if i < 7 else 1,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 7,
                reward={"mrr": 0.7},
                duration_seconds=5.0,
            ),
            passed=i < 7,
            model_name="claude-haiku-4-5-20251001",
            agent_name="baseline",
            duration_seconds=55.0,
        )
        job_id = f"job_baseline_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
        
        # Add tool usage with token counts
        metrics = TranscriptMetrics(
            total_tool_calls=10,
            mcp_calls=5,
            deep_search_calls=2,
            local_calls=3,
            other_calls=0,
            tool_calls_by_name={"Read": 5, "deepsearch": 2, "Grep": 3},
            total_input_tokens=10000,
            total_output_tokens=3000,
            avg_tokens_per_call=1300.0,
            successful_calls=10,
            failed_calls=0,
            success_rate=1.0,
            mcp_vs_local_ratio=1.67,
            files_accessed={"file1.py", "file2.py"},
            unique_file_count=2,
            search_queries=["query1"],
            transcript_length=5000,
        )
        db.store_tool_usage(f"baseline_task_{i:03d}", metrics, "exp001", job_id)
    
    # Variant: 80% pass rate, higher tokens (more MCP usage)
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
                exit_code=0 if i < 8 else 1,
                duration_seconds=60.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 8,
                reward={"mrr": 0.75},
                duration_seconds=5.0,
            ),
            passed=i < 8,
            model_name="claude-haiku-4-5-20251001",
            agent_name="variant",
            duration_seconds=65.0,
        )
        job_id = f"job_variant_{i:03d}"
        db.store_harbor_result(result, "exp001", job_id)
        
        # Higher token usage
        metrics = TranscriptMetrics(
            total_tool_calls=15,
            mcp_calls=10,
            deep_search_calls=5,
            local_calls=5,
            other_calls=0,
            tool_calls_by_name={"Read": 5, "deepsearch": 5, "Grep": 5},
            total_input_tokens=15000,
            total_output_tokens=5000,
            avg_tokens_per_call=1333.0,
            successful_calls=15,
            failed_calls=0,
            success_rate=1.0,
            mcp_vs_local_ratio=2.0,
            files_accessed={"file1.py", "file2.py", "file3.py"},
            unique_file_count=3,
            search_queries=["query1", "query2"],
            transcript_length=8000,
        )
        db.store_tool_usage(f"variant_task_{i:03d}", metrics, "exp001", job_id)
    
    return db


@pytest.fixture
def multi_model_scenario(db):
    """Create scenario with different models."""
    models = [
        ("claude-haiku-4-5-20251001", "haiku_agent"),
        ("claude-sonnet-4-20250514", "sonnet_agent"),
    ]
    
    for model, agent in models:
        for i in range(5):
            result = HarborResult(
                task_id=f"{agent}_task_{i:03d}",
                task_metadata=HarborTaskMetadata(
                    task_id=f"{agent}_task_{i:03d}",
                    task_name=f"Task {i}",
                    category="test",
                    difficulty="medium",
                ),
                agent_output=HarborAgentOutput(
                    exit_code=0 if i < 4 else 1,
                    duration_seconds=50.0,
                ),
                verifier_result=HarborVerifierResult(
                    passed=i < 4,
                    reward={"mrr": 0.7},
                    duration_seconds=5.0,
                ),
                passed=i < 4,
                model_name=model,
                agent_name=agent,
                duration_seconds=55.0,
            )
            job_id = f"job_{agent}_{i:03d}"
            db.store_harbor_result(result, "exp001", job_id)
            
            metrics = TranscriptMetrics(
                total_tool_calls=10,
                mcp_calls=5,
                deep_search_calls=2,
                local_calls=3,
                other_calls=0,
                tool_calls_by_name={"Read": 5, "deepsearch": 2, "Grep": 3},
                total_input_tokens=10000,
                total_output_tokens=3000,
                avg_tokens_per_call=1300.0,
                successful_calls=10,
                failed_calls=0,
                success_rate=1.0,
                mcp_vs_local_ratio=1.67,
                files_accessed={"file1.py"},
                unique_file_count=1,
                search_queries=[],
                transcript_length=5000,
            )
            db.store_tool_usage(f"{agent}_task_{i:03d}", metrics, "exp001", job_id)
    
    return db


def test_cost_analyzer_initialization(db):
    """Test analyzer initialization."""
    analyzer = CostAnalyzer(db)
    assert analyzer.db is db


def test_analyze_experiment_basic(basic_scenario):
    """Test basic experiment analysis."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    assert result.experiment_id == "exp001"
    assert "baseline" in result.agent_metrics
    assert "variant" in result.agent_metrics
    assert result.total_cost_usd > 0
    assert result.total_tokens > 0


def test_cost_metrics_computation(basic_scenario):
    """Test cost metrics are computed correctly."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    baseline = result.agent_metrics["baseline"]
    assert baseline.task_count == 10
    assert baseline.success_count == 7
    assert baseline.success_rate == 0.7
    assert baseline.total_input_tokens > 0
    assert baseline.total_cost_usd > 0
    assert baseline.avg_cost_per_task_usd > 0


def test_cost_delta_computation(basic_scenario):
    """Test cost deltas between agents."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001", baseline_agent="baseline")
    
    assert "baseline__variant" in result.deltas
    delta = result.deltas["baseline__variant"]
    
    # Variant has higher tokens, so should be more expensive
    assert delta.total_tokens_delta > 0
    assert delta.is_more_expensive


def test_efficiency_score_computation(basic_scenario):
    """Test efficiency score computation."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    for agent_name, metrics in result.agent_metrics.items():
        assert metrics.cost_efficiency_score >= 0
        # Efficiency = success_rate / avg_cost
        if metrics.avg_cost_per_task_usd > 0:
            expected = metrics.success_rate / metrics.avg_cost_per_task_usd
            assert abs(metrics.cost_efficiency_score - expected) < 0.01


def test_rankings_computed(basic_scenario):
    """Test agent rankings are computed."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    assert result.cheapest_agent is not None
    assert result.most_expensive_agent is not None
    assert result.most_efficient_agent is not None
    assert result.least_efficient_agent is not None


def test_model_pricing_applied(multi_model_scenario):
    """Test different model pricing is applied."""
    db = multi_model_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    haiku = result.agent_metrics["haiku_agent"]
    sonnet = result.agent_metrics["sonnet_agent"]
    
    # Same tokens, but sonnet costs more
    assert haiku.total_tokens == sonnet.total_tokens
    assert sonnet.total_cost_usd > haiku.total_cost_usd


def test_cost_per_success(basic_scenario):
    """Test cost per success calculation."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    baseline = result.agent_metrics["baseline"]
    # Cost per success = total_cost / success_count
    if baseline.success_count > 0:
        expected = baseline.total_cost_usd / baseline.success_count
        assert abs(baseline.cost_per_success_usd - expected) < 0.0001


def test_tokens_per_success(basic_scenario):
    """Test tokens per success calculation."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    
    baseline = result.agent_metrics["baseline"]
    if baseline.success_count > 0:
        expected = baseline.total_tokens / baseline.success_count
        assert abs(baseline.tokens_per_success - expected) < 1


def test_cost_regression_detection(basic_scenario):
    """Test cost regression detection."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001", baseline_agent="baseline")
    
    # Variant is more expensive (>10% increase)
    delta = result.deltas["baseline__variant"]
    if delta.cost_delta_percent > 10:
        assert "variant" in result.cost_regressions


def test_serialization(basic_scenario):
    """Test result serialization."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    result_dict = result.to_dict()
    
    assert "experiment_id" in result_dict
    assert "summary" in result_dict
    assert "agent_metrics" in result_dict
    assert "deltas" in result_dict


def test_cost_metrics_serialization(basic_scenario):
    """Test cost metrics serialization."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001")
    metrics = result.agent_metrics["baseline"]
    metrics_dict = metrics.to_dict()
    
    assert "agent_name" in metrics_dict
    assert "tokens" in metrics_dict
    assert "cost_usd" in metrics_dict
    assert "efficiency" in metrics_dict


def test_delta_serialization(basic_scenario):
    """Test delta serialization."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001", baseline_agent="baseline")
    delta = result.deltas["baseline__variant"]
    delta_dict = delta.to_dict()
    
    assert "baseline_agent" in delta_dict
    assert "variant_agent" in delta_dict
    assert "tokens" in delta_dict
    assert "cost_usd" in delta_dict
    assert "assessment" in delta_dict


def test_interpretation_generation(basic_scenario):
    """Test interpretation strings are generated."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    result = analyzer.analyze_experiment("exp001", baseline_agent="baseline")
    delta = result.deltas["baseline__variant"]
    
    assert len(delta.interpretation) > 0
    assert "efficient" in delta.interpretation.lower() or "expensive" in delta.interpretation.lower()


def test_compare_experiments(basic_scenario):
    """Test comparing agent across experiments."""
    db = basic_scenario
    analyzer = CostAnalyzer(db)
    
    # Just tests that the method runs (needs multiple experiments for full test)
    metrics_list = analyzer.compare_experiments(["exp001"], "baseline")
    
    assert len(metrics_list) == 1
    assert metrics_list[0].agent_name == "baseline"


def test_empty_experiment_handling(db):
    """Test handling of empty experiment."""
    analyzer = CostAnalyzer(db)
    
    with pytest.raises(ValueError, match="No results found"):
        analyzer.analyze_experiment("nonexistent")


def test_missing_tool_usage_fallback(db):
    """Test fallback when tool usage is missing."""
    # Create result without tool usage
    for i in range(5):
        result = HarborResult(
            task_id=f"task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
                difficulty="medium",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=100.0,  # Use duration for estimation
            ),
            verifier_result=HarborVerifierResult(
                passed=True,
                reward={"mrr": 0.7},
                duration_seconds=5.0,
            ),
            passed=True,
            model_name="claude-haiku-4-5-20251001",
            agent_name="agent",
            duration_seconds=105.0,
        )
        db.store_harbor_result(result, "exp001", f"job_{i:03d}")
    
    analyzer = CostAnalyzer(db)
    result = analyzer.analyze_experiment("exp001")
    
    # Should still compute costs using duration-based estimation
    metrics = result.agent_metrics["agent"]
    assert metrics.total_tokens > 0
    assert metrics.total_cost_usd > 0


def test_pricing_constants():
    """Test pricing constants are defined."""
    assert "claude-haiku-4-5-20251001" in CLAUDE_PRICING
    assert "claude-sonnet-4-20250514" in CLAUDE_PRICING
    assert "default" in CLAUDE_PRICING
    
    for model, pricing in CLAUDE_PRICING.items():
        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] > 0
        assert pricing["output"] > 0
