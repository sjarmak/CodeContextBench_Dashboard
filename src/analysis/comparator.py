"""
Experiment comparator for baseline vs agent variant analysis.

Compares Harbor evaluation results, tool usage patterns, and reward metrics
across different agents and experiments to measure MCP impact.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.ingest.database import MetricsDatabase


@dataclass
class AgentMetrics:
    """Aggregated metrics for a single agent."""
    agent_name: str
    model_name: Optional[str]
    
    # Harbor metrics
    total_tasks: int = 0
    passed_tasks: int = 0
    pass_rate: float = 0.0
    
    # Timing metrics
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    
    # Reward metrics
    avg_reward_primary: float = 0.0
    reward_metrics: dict = field(default_factory=dict)
    
    # Tool usage metrics
    avg_mcp_calls: float = 0.0
    avg_deep_search_calls: float = 0.0
    avg_local_calls: float = 0.0
    avg_mcp_vs_local_ratio: float = 0.0
    avg_tool_diversity: float = 0.0
    
    # Success rates
    avg_tool_success_rate: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "harbor": {
                "total_tasks": self.total_tasks,
                "passed_tasks": self.passed_tasks,
                "pass_rate": self.pass_rate,
            },
            "timing": {
                "avg_duration_seconds": self.avg_duration_seconds,
                "min_duration_seconds": self.min_duration_seconds,
                "max_duration_seconds": self.max_duration_seconds,
            },
            "rewards": {
                "avg_primary": self.avg_reward_primary,
                "all_metrics": self.reward_metrics,
            },
            "tool_usage": {
                "avg_mcp_calls": self.avg_mcp_calls,
                "avg_deep_search_calls": self.avg_deep_search_calls,
                "avg_local_calls": self.avg_local_calls,
                "avg_mcp_vs_local_ratio": self.avg_mcp_vs_local_ratio,
                "avg_tool_diversity": self.avg_tool_diversity,
            },
            "success_rates": {
                "avg_tool_success_rate": self.avg_tool_success_rate,
            },
        }


@dataclass
class ComparisonDelta:
    """Comparison between two agents."""
    baseline_agent: str
    variant_agent: str
    
    # Deltas (variant - baseline)
    pass_rate_delta: float = 0.0  # Positive = variant is better
    duration_delta_seconds: float = 0.0  # Negative = variant is faster
    mcp_calls_delta: float = 0.0
    deep_search_calls_delta: float = 0.0
    local_calls_delta: float = 0.0
    tool_success_rate_delta: float = 0.0
    reward_primary_delta: float = 0.0
    
    # Statistical significance
    pass_rate_pvalue: Optional[float] = None
    duration_pvalue: Optional[float] = None
    
    # Interpretation
    mcp_impact: str = "neutral"  # "positive", "negative", "neutral"
    efficiency_impact: str = "neutral"  # "faster", "slower", "neutral"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "baseline_agent": self.baseline_agent,
            "variant_agent": self.variant_agent,
            "deltas": {
                "pass_rate": self.pass_rate_delta,
                "duration_seconds": self.duration_delta_seconds,
                "mcp_calls": self.mcp_calls_delta,
                "deep_search_calls": self.deep_search_calls_delta,
                "local_calls": self.local_calls_delta,
                "tool_success_rate": self.tool_success_rate_delta,
                "reward_primary": self.reward_primary_delta,
            },
            "significance": {
                "pass_rate_pvalue": self.pass_rate_pvalue,
                "duration_pvalue": self.duration_pvalue,
            },
            "interpretation": {
                "mcp_impact": self.mcp_impact,
                "efficiency_impact": self.efficiency_impact,
            },
        }


@dataclass
class ComparisonResult:
    """Results from experiment comparison."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)
    
    # Agent metrics
    agent_metrics: dict[str, AgentMetrics] = field(default_factory=dict)
    
    # Pairwise comparisons
    deltas: dict[str, ComparisonDelta] = field(default_factory=dict)  # key: "baseline__variant"
    
    # Summary
    best_agent: str = ""
    worst_agent: str = ""
    
    # Metadata
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "baseline_agent": self.baseline_agent,
            "variant_agents": self.variant_agents,
            "agent_metrics": {
                name: metrics.to_dict()
                for name, metrics in self.agent_metrics.items()
            },
            "comparisons": {
                key: delta.to_dict()
                for key, delta in self.deltas.items()
            },
            "summary": {
                "best_agent": self.best_agent,
                "worst_agent": self.worst_agent,
            },
            "computed_at": self.computed_at,
        }


class ExperimentComparator:
    """Compare agents across experiments."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize comparator.
        
        Args:
            db: MetricsDatabase instance for querying metrics
        """
        self.db = db
    
    def compare_experiment(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> ComparisonResult:
        """
        Compare all agents in an experiment.
        
        Args:
            experiment_id: Experiment ID to analyze
            baseline_agent: Agent to use as baseline (defaults to first agent)
            
        Returns:
            ComparisonResult with detailed metrics and deltas
        """
        # Get all results for experiment
        results = self.db.get_experiment_results(experiment_id)
        
        if not results:
            raise ValueError(f"No results found for experiment: {experiment_id}")
        
        # Group by agent
        agents_data = {}
        for result in results:
            agent = result["agent_name"] or "unknown"
            if agent not in agents_data:
                agents_data[agent] = []
            agents_data[agent].append(result)
        
        if not baseline_agent:
            baseline_agent = sorted(agents_data.keys())[0]
        
        # Compute metrics for each agent
        agent_metrics = {}
        for agent_name, agent_results in agents_data.items():
            metrics = self._compute_agent_metrics(agent_name, agent_results)
            agent_metrics[agent_name] = metrics
        
        # Compute deltas
        variant_agents = [a for a in agent_metrics.keys() if a != baseline_agent]
        deltas = {}
        
        if baseline_agent in agent_metrics:
            baseline_metrics = agent_metrics[baseline_agent]
            
            for variant_agent in variant_agents:
                variant_metrics = agent_metrics[variant_agent]
                delta_key = f"{baseline_agent}__{variant_agent}"
                delta = self._compute_delta(baseline_metrics, variant_metrics)
                deltas[delta_key] = delta
        
        # Determine best/worst
        best_agent = max(
            agent_metrics.keys(),
            key=lambda a: agent_metrics[a].pass_rate,
        ) if agent_metrics else ""
        
        worst_agent = min(
            agent_metrics.keys(),
            key=lambda a: agent_metrics[a].pass_rate,
        ) if agent_metrics else ""
        
        return ComparisonResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=variant_agents,
            agent_metrics=agent_metrics,
            deltas=deltas,
            best_agent=best_agent,
            worst_agent=worst_agent,
        )
    
    def _compute_agent_metrics(
        self,
        agent_name: str,
        results: list[dict],
    ) -> AgentMetrics:
        """Compute aggregated metrics for an agent."""
        durations = []
        passed = 0
        primary_rewards = []
        all_rewards = {}
        
        mcp_calls_list = []
        deep_search_calls_list = []
        local_calls_list = []
        mcp_vs_local_ratios = []
        success_rates = []
        
        for result in results:
            # Pass/fail
            if result["passed"]:
                passed += 1
            
            # Duration
            if result["total_duration_seconds"]:
                durations.append(result["total_duration_seconds"])
            
            # Rewards
            if result["reward_primary"]:
                primary_rewards.append(result["reward_primary"])
            
            # Merge reward metrics
            if result.get("reward_metrics"):
                import json
                try:
                    metrics_dict = json.loads(result["reward_metrics"])
                    for k, v in metrics_dict.items():
                        if k not in all_rewards:
                            all_rewards[k] = []
                        if isinstance(v, (int, float)):
                            all_rewards[k].append(v)
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Query tool usage for this agent
        with self.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tu.mcp_calls, tu.deep_search_calls, tu.local_calls,
                       tu.mcp_vs_local_ratio, tu.success_rate
                FROM tool_usage tu
                INNER JOIN harbor_results hr ON (
                    tu.task_id = hr.task_id 
                    AND tu.experiment_id = hr.experiment_id 
                    AND tu.job_id = hr.job_id
                )
                WHERE hr.agent_name = ? AND hr.experiment_id = (
                    SELECT experiment_id FROM harbor_results
                    WHERE agent_name = ? LIMIT 1
                )
            """, (agent_name, agent_name))
            
            tool_rows = cursor.fetchall()
            for row in tool_rows:
                mcp_calls_list.append(row["mcp_calls"] or 0)
                deep_search_calls_list.append(row["deep_search_calls"] or 0)
                local_calls_list.append(row["local_calls"] or 0)
                if row["mcp_vs_local_ratio"] is not None:
                    mcp_vs_local_ratios.append(row["mcp_vs_local_ratio"])
                if row["success_rate"] is not None:
                    success_rates.append(row["success_rate"])
        
        # Compute averages for reward metrics
        avg_reward_metrics = {}
        for metric_name, values in all_rewards.items():
            if values:
                avg_reward_metrics[metric_name] = statistics.mean(values)
        
        pass_rate = (passed / len(results)) if results else 0.0
        
        return AgentMetrics(
            agent_name=agent_name,
            model_name=results[0].get("model_name") if results else None,
            total_tasks=len(results),
            passed_tasks=passed,
            pass_rate=pass_rate,
            avg_duration_seconds=statistics.mean(durations) if durations else 0.0,
            min_duration_seconds=min(durations) if durations else 0.0,
            max_duration_seconds=max(durations) if durations else 0.0,
            avg_reward_primary=statistics.mean(primary_rewards) if primary_rewards else 0.0,
            reward_metrics=avg_reward_metrics,
            avg_mcp_calls=statistics.mean(mcp_calls_list) if mcp_calls_list else 0.0,
            avg_deep_search_calls=statistics.mean(deep_search_calls_list) if deep_search_calls_list else 0.0,
            avg_local_calls=statistics.mean(local_calls_list) if local_calls_list else 0.0,
            avg_mcp_vs_local_ratio=statistics.mean(mcp_vs_local_ratios) if mcp_vs_local_ratios else 0.0,
            avg_tool_success_rate=statistics.mean(success_rates) if success_rates else 0.0,
        )
    
    def _compute_delta(
        self,
        baseline: AgentMetrics,
        variant: AgentMetrics,
    ) -> ComparisonDelta:
        """Compute delta between two agents."""
        delta = ComparisonDelta(
            baseline_agent=baseline.agent_name,
            variant_agent=variant.agent_name,
            pass_rate_delta=variant.pass_rate - baseline.pass_rate,
            duration_delta_seconds=variant.avg_duration_seconds - baseline.avg_duration_seconds,
            mcp_calls_delta=variant.avg_mcp_calls - baseline.avg_mcp_calls,
            deep_search_calls_delta=variant.avg_deep_search_calls - baseline.avg_deep_search_calls,
            local_calls_delta=variant.avg_local_calls - baseline.avg_local_calls,
            tool_success_rate_delta=variant.avg_tool_success_rate - baseline.avg_tool_success_rate,
            reward_primary_delta=variant.avg_reward_primary - baseline.avg_reward_primary,
        )
        
        # Interpret MCP impact
        if delta.mcp_calls_delta > 0:
            delta.mcp_impact = "positive" if delta.pass_rate_delta > 0 else "negative"
        
        # Interpret efficiency
        if abs(delta.duration_delta_seconds) > 5:  # More than 5 seconds difference
            delta.efficiency_impact = "faster" if delta.duration_delta_seconds < 0 else "slower"
        
        return delta
