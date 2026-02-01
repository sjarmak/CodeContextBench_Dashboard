"""
Cost analysis for tracking API spending and resource efficiency.

Provides:
- Token usage tracking across experiments
- Cost computation using Claude API pricing
- Efficiency metrics (cost per successful task)
- Multi-agent cost comparison
- Cost regression detection
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from src.ingest.database import MetricsDatabase


# Claude API pricing (per 1M tokens) - as of 2025
CLAUDE_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    # Fallback for unknown models
    "default": {"input": 3.00, "output": 15.00},
}


@dataclass
class TokenUsage:
    """Token usage for a single task or aggregated."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class CostMetrics:
    """Cost metrics for an agent."""
    agent_name: str
    model_name: str
    
    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_task: float = 0.0
    
    # Cost in USD
    total_cost_usd: float = 0.0
    avg_cost_per_task_usd: float = 0.0
    cost_per_success_usd: float = 0.0
    
    # Efficiency
    task_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    tokens_per_success: float = 0.0
    
    # Comparison helpers
    cost_efficiency_score: float = 0.0  # success_rate / avg_cost (higher = better)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "total": self.total_tokens,
                "avg_per_task": self.avg_tokens_per_task,
            },
            "cost_usd": {
                "total": round(self.total_cost_usd, 4),
                "avg_per_task": round(self.avg_cost_per_task_usd, 4),
                "per_success": round(self.cost_per_success_usd, 4),
            },
            "efficiency": {
                "task_count": self.task_count,
                "success_count": self.success_count,
                "success_rate": self.success_rate,
                "tokens_per_success": self.tokens_per_success,
                "cost_efficiency_score": round(self.cost_efficiency_score, 4),
            },
        }


@dataclass
class CostDelta:
    """Cost differences between two agents."""
    baseline_agent: str
    variant_agent: str
    
    # Token deltas
    total_tokens_delta: int = 0
    avg_tokens_delta: float = 0.0
    tokens_delta_percent: float = 0.0
    
    # Cost deltas
    total_cost_delta_usd: float = 0.0
    avg_cost_delta_usd: float = 0.0
    cost_delta_percent: float = 0.0
    
    # Efficiency deltas
    cost_per_success_delta_usd: float = 0.0
    efficiency_score_delta: float = 0.0
    
    # Interpretation
    is_more_expensive: bool = False
    is_more_efficient: bool = False
    interpretation: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "baseline_agent": self.baseline_agent,
            "variant_agent": self.variant_agent,
            "tokens": {
                "total_delta": self.total_tokens_delta,
                "avg_delta": self.avg_tokens_delta,
                "percent_change": self.tokens_delta_percent,
            },
            "cost_usd": {
                "total_delta": round(self.total_cost_delta_usd, 4),
                "avg_delta": round(self.avg_cost_delta_usd, 4),
                "percent_change": self.cost_delta_percent,
            },
            "efficiency": {
                "cost_per_success_delta": round(self.cost_per_success_delta_usd, 4),
                "efficiency_score_delta": round(self.efficiency_score_delta, 4),
            },
            "assessment": {
                "is_more_expensive": self.is_more_expensive,
                "is_more_efficient": self.is_more_efficient,
                "interpretation": self.interpretation,
            },
        }


@dataclass
class CostAnalysisResult:
    """Complete cost analysis result."""
    experiment_id: str
    
    # Per-agent metrics
    agent_metrics: dict[str, CostMetrics] = field(default_factory=dict)
    
    # Deltas (baseline vs variants)
    deltas: dict[str, CostDelta] = field(default_factory=dict)
    
    # Summary
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    
    # Rankings
    cheapest_agent: Optional[str] = None
    most_expensive_agent: Optional[str] = None
    most_efficient_agent: Optional[str] = None
    least_efficient_agent: Optional[str] = None
    
    # Regressions
    cost_regressions: list[str] = field(default_factory=list)  # Agents with cost increases
    efficiency_regressions: list[str] = field(default_factory=list)  # Agents with efficiency drops
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "summary": {
                "total_cost_usd": round(self.total_cost_usd, 4),
                "total_tokens": self.total_tokens,
                "cheapest_agent": self.cheapest_agent,
                "most_expensive_agent": self.most_expensive_agent,
                "most_efficient_agent": self.most_efficient_agent,
                "least_efficient_agent": self.least_efficient_agent,
            },
            "regressions": {
                "cost_regressions": self.cost_regressions,
                "efficiency_regressions": self.efficiency_regressions,
            },
            "agent_metrics": {
                name: metrics.to_dict()
                for name, metrics in self.agent_metrics.items()
            },
            "deltas": {
                key: delta.to_dict()
                for key, delta in self.deltas.items()
            },
        }


class CostAnalyzer:
    """Analyze API costs and resource efficiency."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize cost analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_experiment(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> CostAnalysisResult:
        """
        Analyze costs for an experiment.
        
        Args:
            experiment_id: Experiment ID
            baseline_agent: Optional baseline for comparison
            
        Returns:
            CostAnalysisResult with metrics and deltas
        """
        results = self.db.get_experiment_results(experiment_id)
        
        if not results:
            raise ValueError(f"No results found for experiment: {experiment_id}")
        
        # Group by agent
        agents_data: dict[str, list[dict]] = {}
        for result in results:
            agent = result["agent_name"] or "unknown"
            if agent not in agents_data:
                agents_data[agent] = []
            agents_data[agent].append(result)
        
        # Get tool usage for token counts
        tool_usage = self._get_tool_usage(experiment_id)
        
        # Compute metrics per agent
        analysis = CostAnalysisResult(experiment_id=experiment_id)
        
        for agent_name, agent_results in agents_data.items():
            model_name = agent_results[0].get("model_name") or "default"
            agent_tool_usage = tool_usage.get(agent_name, [])
            
            metrics = self._compute_agent_metrics(
                agent_name, model_name, agent_results, agent_tool_usage
            )
            analysis.agent_metrics[agent_name] = metrics
            analysis.total_cost_usd += metrics.total_cost_usd
            analysis.total_tokens += metrics.total_tokens
        
        # Auto-detect baseline if not provided
        if not baseline_agent and agents_data:
            # Use first agent or one with "baseline" in name
            for agent in agents_data.keys():
                if "baseline" in agent.lower():
                    baseline_agent = agent
                    break
            if not baseline_agent:
                baseline_agent = list(agents_data.keys())[0]
        
        # Compute deltas
        if baseline_agent and baseline_agent in analysis.agent_metrics:
            baseline_metrics = analysis.agent_metrics[baseline_agent]
            
            for agent_name, metrics in analysis.agent_metrics.items():
                if agent_name == baseline_agent:
                    continue
                
                delta = self._compute_delta(baseline_metrics, metrics)
                key = f"{baseline_agent}__{agent_name}"
                analysis.deltas[key] = delta
                
                # Track regressions
                if delta.is_more_expensive and delta.cost_delta_percent > 10:
                    analysis.cost_regressions.append(agent_name)
                if not delta.is_more_efficient and delta.efficiency_score_delta < -0.1:
                    analysis.efficiency_regressions.append(agent_name)
        
        # Compute rankings
        if analysis.agent_metrics:
            by_cost = sorted(
                analysis.agent_metrics.items(),
                key=lambda x: x[1].avg_cost_per_task_usd
            )
            analysis.cheapest_agent = by_cost[0][0]
            analysis.most_expensive_agent = by_cost[-1][0]
            
            by_efficiency = sorted(
                analysis.agent_metrics.items(),
                key=lambda x: x[1].cost_efficiency_score,
                reverse=True
            )
            analysis.most_efficient_agent = by_efficiency[0][0]
            analysis.least_efficient_agent = by_efficiency[-1][0]
        
        return analysis
    
    def compare_experiments(
        self,
        experiment_ids: list[str],
        agent_name: str,
    ) -> list[CostMetrics]:
        """
        Compare costs for an agent across experiments.
        
        Args:
            experiment_ids: List of experiment IDs (chronological)
            agent_name: Agent to track
            
        Returns:
            List of CostMetrics across experiments
        """
        metrics_list = []
        
        for exp_id in experiment_ids:
            try:
                analysis = self.analyze_experiment(exp_id)
                if agent_name in analysis.agent_metrics:
                    metrics_list.append(analysis.agent_metrics[agent_name])
            except ValueError:
                continue  # Skip experiments without results
        
        return metrics_list
    
    def _get_tool_usage(self, experiment_id: str) -> dict[str, list[dict]]:
        """Get tool usage grouped by agent."""
        with self.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tu.*, hr.agent_name
                FROM tool_usage tu
                JOIN harbor_results hr ON tu.task_id = hr.task_id 
                    AND tu.experiment_id = hr.experiment_id 
                    AND tu.job_id = hr.job_id
                WHERE tu.experiment_id = ?
            """, (experiment_id,))
            
            rows = cursor.fetchall()
            
            result: dict[str, list[dict]] = {}
            for row in rows:
                row_dict = dict(row)
                agent = row_dict.get("agent_name") or "unknown"
                if agent not in result:
                    result[agent] = []
                result[agent].append(row_dict)
            
            return result
    
    def _compute_agent_metrics(
        self,
        agent_name: str,
        model_name: str,
        results: list[dict],
        tool_usage: list[dict],
    ) -> CostMetrics:
        """Compute cost metrics for an agent."""
        # Get pricing
        pricing = CLAUDE_PRICING.get(model_name, CLAUDE_PRICING["default"])
        
        # Aggregate tokens from tool_usage
        total_input = sum(t.get("total_input_tokens") or 0 for t in tool_usage)
        total_output = sum(t.get("total_output_tokens") or 0 for t in tool_usage)
        
        # If no token data, estimate from duration (rough heuristic)
        if total_input == 0 and total_output == 0:
            # Estimate ~100 tokens/second as rough proxy
            total_duration = sum(r.get("total_duration_seconds") or 0 for r in results)
            estimated_tokens = int(total_duration * 100)
            total_input = int(estimated_tokens * 0.7)  # 70% input
            total_output = int(estimated_tokens * 0.3)  # 30% output
        
        total_tokens = total_input + total_output
        
        # Compute costs
        input_cost = (total_input / 1_000_000) * pricing["input"]
        output_cost = (total_output / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Compute success metrics
        task_count = len(results)
        success_count = sum(1 for r in results if r.get("passed"))
        success_rate = success_count / task_count if task_count > 0 else 0.0
        
        # Compute averages
        avg_tokens = total_tokens / task_count if task_count > 0 else 0
        avg_cost = total_cost / task_count if task_count > 0 else 0
        cost_per_success = total_cost / success_count if success_count > 0 else float('inf')
        tokens_per_success = total_tokens / success_count if success_count > 0 else float('inf')
        
        # Efficiency score: success_rate / avg_cost (handle zero cost)
        efficiency_score = success_rate / avg_cost if avg_cost > 0 else 0.0
        
        return CostMetrics(
            agent_name=agent_name,
            model_name=model_name,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            avg_tokens_per_task=avg_tokens,
            total_cost_usd=total_cost,
            avg_cost_per_task_usd=avg_cost,
            cost_per_success_usd=cost_per_success if cost_per_success != float('inf') else 0,
            task_count=task_count,
            success_count=success_count,
            success_rate=success_rate,
            tokens_per_success=tokens_per_success if tokens_per_success != float('inf') else 0,
            cost_efficiency_score=efficiency_score,
        )
    
    def _compute_delta(
        self,
        baseline: CostMetrics,
        variant: CostMetrics,
    ) -> CostDelta:
        """Compute cost delta between baseline and variant."""
        # Token deltas
        total_tokens_delta = variant.total_tokens - baseline.total_tokens
        avg_tokens_delta = variant.avg_tokens_per_task - baseline.avg_tokens_per_task
        tokens_percent = (
            (total_tokens_delta / baseline.total_tokens * 100)
            if baseline.total_tokens > 0 else 0
        )
        
        # Cost deltas
        total_cost_delta = variant.total_cost_usd - baseline.total_cost_usd
        avg_cost_delta = variant.avg_cost_per_task_usd - baseline.avg_cost_per_task_usd
        cost_percent = (
            (total_cost_delta / baseline.total_cost_usd * 100)
            if baseline.total_cost_usd > 0 else 0
        )
        
        # Efficiency deltas
        cost_per_success_delta = variant.cost_per_success_usd - baseline.cost_per_success_usd
        efficiency_delta = variant.cost_efficiency_score - baseline.cost_efficiency_score
        
        # Assessments
        is_more_expensive = variant.avg_cost_per_task_usd > baseline.avg_cost_per_task_usd
        is_more_efficient = variant.cost_efficiency_score > baseline.cost_efficiency_score
        
        # Interpretation
        interpretation = self._interpret_delta(
            is_more_expensive, is_more_efficient, cost_percent, efficiency_delta
        )
        
        return CostDelta(
            baseline_agent=baseline.agent_name,
            variant_agent=variant.agent_name,
            total_tokens_delta=total_tokens_delta,
            avg_tokens_delta=avg_tokens_delta,
            tokens_delta_percent=tokens_percent,
            total_cost_delta_usd=total_cost_delta,
            avg_cost_delta_usd=avg_cost_delta,
            cost_delta_percent=cost_percent,
            cost_per_success_delta_usd=cost_per_success_delta,
            efficiency_score_delta=efficiency_delta,
            is_more_expensive=is_more_expensive,
            is_more_efficient=is_more_efficient,
            interpretation=interpretation,
        )
    
    def _interpret_delta(
        self,
        is_more_expensive: bool,
        is_more_efficient: bool,
        cost_percent: float,
        efficiency_delta: float,
    ) -> str:
        """Generate interpretation of cost delta."""
        if is_more_efficient and not is_more_expensive:
            return f"Better value: more efficient ({efficiency_delta:+.2f}) and cheaper ({cost_percent:+.1f}%)"
        elif is_more_efficient and is_more_expensive:
            return f"Trade-off: more efficient ({efficiency_delta:+.2f}) but costs more ({cost_percent:+.1f}%)"
        elif not is_more_efficient and not is_more_expensive:
            return f"Trade-off: less efficient ({efficiency_delta:+.2f}) but cheaper ({cost_percent:+.1f}%)"
        else:
            return f"Worse value: less efficient ({efficiency_delta:+.2f}) and more expensive ({cost_percent:+.1f}%)"
