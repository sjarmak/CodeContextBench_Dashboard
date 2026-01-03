"""
Helpers for extracting and converting analysis results into filterable formats.

Converts dataclass analysis results into dictionaries suitable for filtering
and display in Streamlit views.
"""

from typing import Dict, List, Any, Optional
from src.analysis.comparator import ComparisonResult, AgentMetrics
from src.analysis.failure_analyzer import FailureAnalysisResult
from src.analysis.cost_analyzer import CostAnalysisResult
from src.analysis.statistical_analyzer import StatisticalAnalysisResult
from src.analysis.time_series_analyzer import TimeSeriesAnalysisResult
from src.analysis.ir_analyzer import IRAnalysisResult


def extract_comparison_metrics(result: ComparisonResult) -> Dict[str, Any]:
    """
    Extract metrics from ComparisonResult into dict format suitable for filtering.
    
    Args:
        result: ComparisonResult from ExperimentComparator
        
    Returns:
        Dict with agent_results, agent_deltas, and summary
    """
    agent_results = {}
    
    # Extract agent metrics
    for agent_name, metrics in result.agent_metrics.items():
        agent_results[agent_name] = {
            "pass_rate": metrics.pass_rate,
            "passed_count": metrics.passed_tasks,
            "failed_count": metrics.total_tasks - metrics.passed_tasks,
            "total_tasks": metrics.total_tasks,
            "avg_duration": metrics.avg_duration_seconds,
            "min_duration": metrics.min_duration_seconds,
            "max_duration": metrics.max_duration_seconds,
            "mcp_call_count": metrics.avg_mcp_calls,
            "deep_search_call_count": metrics.avg_deep_search_calls,
            "local_call_count": metrics.avg_local_calls,
            "mcp_vs_local_ratio": metrics.avg_mcp_vs_local_ratio,
            "tool_success_rate": metrics.avg_tool_success_rate,
            "avg_reward": metrics.avg_reward_primary,
        }
    
    # Extract deltas
    agent_deltas = {}
    for delta_key, delta in result.deltas.items():
        agent_deltas[delta_key] = {
            "pass_rate_delta": delta.pass_rate_delta,
            "duration_delta": delta.duration_delta_seconds,
            "mcp_call_delta": delta.mcp_calls_delta,
            "deep_search_call_delta": delta.deep_search_calls_delta,
            "local_call_delta": delta.local_calls_delta,
            "tool_success_rate_delta": delta.tool_success_rate_delta,
            "reward_delta": delta.reward_primary_delta,
            "mcp_impact": delta.mcp_impact,
            "efficiency_impact": delta.efficiency_impact,
            "pass_rate_pvalue": delta.pass_rate_pvalue,
            "duration_pvalue": delta.duration_pvalue,
        }
    
    return {
        "experiment_id": result.experiment_id,
        "baseline_agent": result.baseline_agent,
        "total_tasks": list(result.agent_metrics.values())[0].total_tasks if result.agent_metrics else 0,
        "agent_results": agent_results,
        "agent_deltas": agent_deltas,
        "best_agent": result.best_agent,
        "best_agent_pass_rate": result.agent_metrics[result.best_agent].pass_rate if result.best_agent in result.agent_metrics else 0.0,
        "worst_agent": result.worst_agent,
        "worst_agent_pass_rate": result.agent_metrics[result.worst_agent].pass_rate if result.worst_agent in result.agent_metrics else 0.0,
    }


def extract_failure_metrics(result: FailureAnalysisResult) -> Dict[str, Any]:
    """
    Extract metrics from FailureAnalysisResult into dict format.
    
    Args:
        result: FailureAnalysisResult from FailureAnalyzer
        
    Returns:
        Dict with failure patterns, categories, and analysis
    """
    return {
        "total_failures": result.total_failures if hasattr(result, 'total_failures') else 0,
        "total_tasks": result.total_tasks if hasattr(result, 'total_tasks') else 0,
        "failure_patterns": result.failure_patterns if hasattr(result, 'failure_patterns') else {},
        "failure_categories": result.failure_categories if hasattr(result, 'failure_categories') else {},
        "difficulty_correlation": result.difficulty_correlation if hasattr(result, 'difficulty_correlation') else {},
        "suggested_fixes": result.suggested_fixes if hasattr(result, 'suggested_fixes') else [],
        "agent_failure_rates": result.agent_failure_rates if hasattr(result, 'agent_failure_rates') else {},
        "high_risk_tasks": result.high_risk_tasks if hasattr(result, 'high_risk_tasks') else [],
    }


def extract_cost_metrics(result: CostAnalysisResult) -> Dict[str, Any]:
    """
    Extract metrics from CostAnalysisResult into dict format.
    
    Args:
        result: CostAnalysisResult from CostAnalyzer
        
    Returns:
        Dict with cost data, tokens, and analysis
    """
    return {
        "total_cost": result.total_cost if hasattr(result, 'total_cost') else 0.0,
        "total_tokens": result.total_tokens if hasattr(result, 'total_tokens') else 0,
        "agent_costs": result.agent_costs if hasattr(result, 'agent_costs') else {},
        "cost_regressions": result.cost_regressions if hasattr(result, 'cost_regressions') else [],
        "model_breakdown": result.model_breakdown if hasattr(result, 'model_breakdown') else {},
    }


def extract_statistical_metrics(result: StatisticalAnalysisResult) -> Dict[str, Any]:
    """
    Extract metrics from StatisticalAnalysisResult into dict format.
    
    Args:
        result: StatisticalAnalysisResult from StatisticalAnalyzer
        
    Returns:
        Dict with test results, effect sizes, power analysis
    """
    return {
        "test_results": result.test_results if hasattr(result, 'test_results') else {},
        "effect_sizes": result.effect_sizes if hasattr(result, 'effect_sizes') else {},
        "power_analysis": result.power_analysis if hasattr(result, 'power_analysis') else {},
    }


def extract_timeseries_metrics(result: TimeSeriesAnalysisResult) -> Dict[str, Any]:
    """
    Extract metrics from TimeSeriesAnalysisResult into dict format.
    
    Args:
        result: TimeSeriesAnalysisResult from TimeSeriesAnalyzer
        
    Returns:
        Dict with trends, anomalies, and improvements
    """
    return {
        "trends": result.trends if hasattr(result, 'trends') else {},
        "agent_trends": result.agent_trends if hasattr(result, 'agent_trends') else {},
        "anomalies": result.anomalies if hasattr(result, 'anomalies') else [],
        "best_improving": result.best_improving if hasattr(result, 'best_improving') else {},
        "worst_improving": result.worst_improving if hasattr(result, 'worst_improving') else {},
    }


def extract_ir_metrics(result: Optional[IRAnalysisResult]) -> Dict[str, Any]:
    """
    Extract metrics from IRAnalysisResult into dict format suitable for filtering.
    
    Args:
        result: IRAnalysisResult from IRAnalyzer (may be None)
        
    Returns:
        Dict with IR tool results, impact metrics, and detailed analysis
    """
    if result is None:
        return {
            "ir_tool_results": {},
            "ir_impact": {},
            "detailed_metrics": {},
            "avg_precision_at_k": 0.0,
            "avg_recall_at_k": 0.0,
            "correlation_analysis": {},
        }
    
    return {
        "experiment_id": getattr(result, 'experiment_id', ''),
        "ir_tool_results": getattr(result, 'ir_tool_results', {}),
        "ir_impact": getattr(result, 'ir_impact', {}),
        "detailed_metrics": getattr(result, 'detailed_metrics', {}),
        "avg_precision_at_k": getattr(result, 'avg_precision_at_k', 0.0),
        "avg_recall_at_k": getattr(result, 'avg_recall_at_k', 0.0),
        "correlation_analysis": getattr(result, 'correlation_analysis', {}),
    }
