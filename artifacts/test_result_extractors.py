"""Tests for result extractor functions."""

import pytest
from datetime import datetime

from dashboard.utils.result_extractors import (
    extract_comparison_metrics,
    extract_failure_metrics,
    extract_cost_metrics,
    extract_statistical_metrics,
    extract_timeseries_metrics,
)
from src.analysis.comparator import ComparisonResult, AgentMetrics, ComparisonDelta
from src.analysis.failure_analyzer import FailureAnalysisResult
from src.analysis.cost_analyzer import CostAnalysisResult
from src.analysis.statistical_analyzer import StatisticalAnalysisResult
from src.analysis.time_series_analyzer import TimeSeriesAnalysisResult


def test_extract_comparison_metrics():
    """Test extracting metrics from ComparisonResult."""
    # Create sample agent metrics
    metrics_baseline = AgentMetrics(
        agent_name="baseline",
        model_name="claude-3-haiku",
        total_tasks=10,
        passed_tasks=8,
        pass_rate=0.8,
        avg_duration_seconds=5.0,
        min_duration_seconds=2.0,
        max_duration_seconds=10.0,
        avg_reward_primary=1.5,
        avg_mcp_calls=2.0,
        avg_deep_search_calls=1.0,
        avg_local_calls=3.0,
    )
    
    metrics_variant = AgentMetrics(
        agent_name="variant",
        model_name="claude-3-haiku",
        total_tasks=10,
        passed_tasks=9,
        pass_rate=0.9,
        avg_duration_seconds=4.5,
        min_duration_seconds=2.0,
        max_duration_seconds=9.0,
        avg_reward_primary=1.6,
        avg_mcp_calls=2.5,
        avg_deep_search_calls=1.2,
        avg_local_calls=2.5,
    )
    
    delta = ComparisonDelta(
        baseline_agent="baseline",
        variant_agent="variant",
        pass_rate_delta=0.1,
        duration_delta_seconds=-0.5,
        mcp_calls_delta=0.5,
    )
    
    result = ComparisonResult(
        experiment_id="exp-001",
        baseline_agent="baseline",
        variant_agents=["variant"],
        agent_metrics={"baseline": metrics_baseline, "variant": metrics_variant},
        deltas={"baseline__variant": delta},
        best_agent="variant",
        worst_agent="baseline",
    )
    
    # Extract metrics
    extracted = extract_comparison_metrics(result)
    
    # Verify structure
    assert extracted["experiment_id"] == "exp-001"
    assert extracted["baseline_agent"] == "baseline"
    assert "baseline" in extracted["agent_results"]
    assert "variant" in extracted["agent_results"]
    assert "baseline__variant" in extracted["agent_deltas"]
    
    # Verify values
    assert extracted["agent_results"]["baseline"]["pass_rate"] == 0.8
    assert extracted["agent_results"]["variant"]["pass_rate"] == 0.9
    assert extracted["agent_deltas"]["baseline__variant"]["pass_rate_delta"] == 0.1


def test_extract_failure_metrics():
    """Test extracting metrics from FailureAnalysisResult."""
    result = FailureAnalysisResult()
    result.total_failures = 5
    result.total_tasks = 20
    result.failure_patterns = {"timeout": 3, "wrong_answer": 2}
    result.failure_categories = {
        "architecture": {"count": 3, "examples": "example1"},
        "prompting": {"count": 2, "examples": "example2"},
    }
    result.difficulty_correlation = {}
    result.suggested_fixes = []
    result.agent_failure_rates = {}
    result.high_risk_tasks = []
    
    # Extract metrics
    extracted = extract_failure_metrics(result)
    
    # Verify structure
    assert extracted["total_failures"] == 5
    assert extracted["total_tasks"] == 20
    assert extracted["failure_patterns"] == {"timeout": 3, "wrong_answer": 2}
    assert len(extracted["failure_categories"]) == 2


def test_extract_cost_metrics():
    """Test extracting metrics from CostAnalysisResult."""
    result = CostAnalysisResult()
    result.total_cost = 100.0
    result.total_tokens = 50000
    result.agent_costs = {
        "agent1": {"total_cost": 50.0, "input_tokens": 25000, "output_tokens": 25000},
        "agent2": {"total_cost": 50.0, "input_tokens": 25000, "output_tokens": 25000},
    }
    result.cost_regressions = []
    result.model_breakdown = {}
    
    # Extract metrics
    extracted = extract_cost_metrics(result)
    
    # Verify structure
    assert extracted["total_cost"] == 100.0
    assert extracted["total_tokens"] == 50000
    assert len(extracted["agent_costs"]) == 2


def test_extract_statistical_metrics():
    """Test extracting metrics from StatisticalAnalysisResult."""
    result = StatisticalAnalysisResult()
    result.test_results = {
        "pass_rate": {
            "baseline__variant": {"p_value": 0.05, "statistic": 1.96, "test_type": "t-test"}
        }
    }
    result.effect_sizes = {
        "pass_rate": {
            "baseline__variant": {"value": 0.5, "name": "Cohen's d", "magnitude": "medium"}
        }
    }
    result.power_analysis = {"pass_rate": {"power": 0.85, "sample_size": 30}}
    
    # Extract metrics
    extracted = extract_statistical_metrics(result)
    
    # Verify structure
    assert "pass_rate" in extracted["test_results"]
    assert "pass_rate" in extracted["effect_sizes"]
    assert "pass_rate" in extracted["power_analysis"]


def test_extract_timeseries_metrics():
    """Test extracting metrics from TimeSeriesAnalysisResult."""
    result = TimeSeriesAnalysisResult()
    result.trends = {
        "pass_rate": {"direction": "IMPROVING", "percent_change": 5.0, "slope": 0.1},
        "duration": {"direction": "STABLE", "percent_change": 0.0, "slope": 0.0},
    }
    result.agent_trends = {
        "agent1": {
            "pass_rate": {"start_value": 0.8, "end_value": 0.85, "change_percent": 5.0}
        }
    }
    result.anomalies = [
        {"experiment_id": "exp-1", "agent_name": "agent1", "metric": "pass_rate", "severity": "high"}
    ]
    result.best_improving = {"pass_rate": 5.0}
    result.worst_improving = {"duration": -2.0}
    
    # Extract metrics
    extracted = extract_timeseries_metrics(result)
    
    # Verify structure
    assert "pass_rate" in extracted["trends"]
    assert "agent1" in extracted["agent_trends"]
    assert len(extracted["anomalies"]) == 1
    assert "pass_rate" in extracted["best_improving"]
    assert "duration" in extracted["worst_improving"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
