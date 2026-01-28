"""
Cost analysis for API usage and efficiency metrics.

Provides:
- Token usage and cost calculation
- Cost per success metrics
- Cost regressions detection
- Agent efficiency ranking
- Model pricing integration
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from src.ingest.database import MetricsDatabase


# Default model pricing (Claude 3.5 Haiku - Jan 2025)
DEFAULT_MODEL_PRICING = {
    "claude-3-5-haiku": {
        "input_tokens_per_million": 0.80,  # $0.80 per 1M input tokens
        "output_tokens_per_million": 4.00,  # $4.00 per 1M output tokens
    },
    "claude-3-opus": {
        "input_tokens_per_million": 15.00,
        "output_tokens_per_million": 75.00,
    },
}


@dataclass
class AgentCostMetrics:
    """Cost metrics for a single agent."""
    agent_name: str
    model_name: Optional[str]

    # Task statistics
    total_tasks: int = 0
    passed_tasks: int = 0
    pass_rate: float = 0.0

    # Token costs
    total_input_tokens: float = 0.0
    total_output_tokens: float = 0.0
    total_cached_tokens: float = 0.0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0

    # Cost metrics
    total_cost_usd: float = 0.0
    avg_cost_per_task: float = 0.0
    cost_per_success: float = 0.0  # Cost per passed task

    # Efficiency ranking
    efficiency_rank: Optional[int] = None
    cost_rank: Optional[int] = None

    # Cost breakdown
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0

    # Token breakdown by category (MCP, LOCAL, OTHER, DEEP_SEARCH)
    tokens_by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Token breakdown by tool
    tokens_by_tool: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "tasks": {
                "total": self.total_tasks,
                "passed": self.passed_tasks,
                "pass_rate": self.pass_rate,
            },
            "tokens": {
                "total_input": self.total_input_tokens,
                "total_output": self.total_output_tokens,
                "total_cached": self.total_cached_tokens,
                "avg_input": self.avg_input_tokens,
                "avg_output": self.avg_output_tokens,
            },
            "costs": {
                "total_usd": self.total_cost_usd,
                "avg_per_task": self.avg_cost_per_task,
                "cost_per_success": self.cost_per_success,
                "input_cost_usd": self.input_cost_usd,
                "output_cost_usd": self.output_cost_usd,
            },
            "rankings": {
                "efficiency_rank": self.efficiency_rank,
                "cost_rank": self.cost_rank,
            },
            "tokens_by_category": self.tokens_by_category,
            "tokens_by_tool": self.tokens_by_tool,
        }


@dataclass
class CostRegression:
    """Detected cost regression."""
    agent_name: str
    metric_name: str
    baseline_value: float
    regression_value: float
    delta_percent: float
    severity: str  # "critical", "high", "medium", "low"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent": self.agent_name,
            "metric": self.metric_name,
            "baseline": self.baseline_value,
            "regression": self.regression_value,
            "delta_percent": self.delta_percent,
            "severity": self.severity,
        }


@dataclass
class CostAnalysisResult:
    """Results from cost analysis."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)

    # Agent cost metrics
    agent_metrics: dict[str, AgentCostMetrics] = field(default_factory=dict)

    # Cost regressions detected
    regressions: list[CostRegression] = field(default_factory=list)

    # Summary
    total_experiment_cost: float = 0.0
    total_tokens: int = 0
    total_cached_tokens: int = 0
    cheapest_agent: str = ""
    most_efficient_agent: str = ""  # Best pass rate per dollar
    most_expensive_agent: str = ""

    # Aggregate token breakdown by category across all agents
    tokens_by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Metadata
    model_pricing: Dict[str, Any] = field(default_factory=dict)
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
            "regressions": [r.to_dict() for r in self.regressions],
            "summary": {
                "total_experiment_cost": self.total_experiment_cost,
                "total_tokens": self.total_tokens,
                "total_cached_tokens": self.total_cached_tokens,
                "cheapest_agent": self.cheapest_agent,
                "most_efficient_agent": self.most_efficient_agent,
                "most_expensive_agent": self.most_expensive_agent,
            },
            "tokens_by_category": self.tokens_by_category,
            "computed_at": self.computed_at,
        }


class CostAnalyzer:
    """Analyze costs and efficiency of agents."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize cost analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_costs(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
        model_pricing: Optional[Dict[str, Any]] = None,
    ) -> CostAnalysisResult:
        """
        Analyze costs for an experiment.
        
        Args:
            experiment_id: Experiment ID to analyze
            baseline_agent: Baseline agent (auto-detected if None)
            model_pricing: Optional custom pricing (uses defaults if None)
            
        Returns:
            CostAnalysisResult with cost metrics and regressions
        """
        if model_pricing is None:
            model_pricing = DEFAULT_MODEL_PRICING
        
        # Get results
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
        
        # Initialize result
        analysis_result = CostAnalysisResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=[a for a in agents_data.keys() if a != baseline_agent],
            model_pricing=model_pricing,
        )
        
        # Compute cost metrics for each agent
        agent_costs = {}
        for agent_name, agent_results in agents_data.items():
            metrics = self._compute_agent_costs(
                agent_name, agent_results, model_pricing
            )
            agent_costs[agent_name] = metrics
            analysis_result.agent_metrics[agent_name] = metrics
        
        # Rank agents
        self._rank_agents(agent_costs, analysis_result)
        
        # Detect regressions
        if baseline_agent in agent_costs:
            baseline_metrics = agent_costs[baseline_agent]
            
            for variant_agent in analysis_result.variant_agents:
                if variant_agent in agent_costs:
                    variant_metrics = agent_costs[variant_agent]
                    regressions = self._detect_regressions(
                        baseline_metrics, variant_metrics
                    )
                    analysis_result.regressions.extend(regressions)
        
        # Compute totals
        analysis_result.total_experiment_cost = sum(
            m.total_cost_usd for m in agent_costs.values()
        )
        analysis_result.total_tokens = sum(
            int(m.total_input_tokens + m.total_output_tokens) for m in agent_costs.values()
        )
        analysis_result.total_cached_tokens = sum(
            int(m.total_cached_tokens) for m in agent_costs.values()
        )

        # Aggregate tokens by category across all agents
        aggregated_categories = {}
        for metrics in agent_costs.values():
            for cat, tokens in metrics.tokens_by_category.items():
                if cat not in aggregated_categories:
                    aggregated_categories[cat] = {"prompt": 0, "completion": 0, "cached": 0}
                for key in ["prompt", "completion", "cached"]:
                    aggregated_categories[cat][key] += tokens.get(key, 0)
        analysis_result.tokens_by_category = aggregated_categories

        return analysis_result
    
    def _compute_agent_costs(
        self,
        agent_name: str,
        results: list[dict],
        model_pricing: Dict[str, Any],
    ) -> AgentCostMetrics:
        """Compute cost metrics for an agent."""
        import json

        metrics = AgentCostMetrics(
            agent_name=agent_name,
            model_name=results[0].get("model_name") if results else None,
            total_tasks=len(results),
        )

        # Count passes
        passed = sum(1 for r in results if r["passed"])
        metrics.passed_tasks = passed
        metrics.pass_rate = passed / len(results) if results else 0

        # Get token usage from tool_usage table (including new columns)
        input_tokens_list = []
        output_tokens_list = []
        cached_tokens_list = []
        precomputed_costs = []
        aggregated_by_category = {}  # {category: {prompt: X, completion: Y, cached: Z}}
        aggregated_by_tool = {}  # {tool: {prompt: X, completion: Y, cached: Z}}

        for result in results:
            job_id = result.get("job_id")
            exp_id = result.get("experiment_id")
            task_id = result.get("task_id")

            if job_id and exp_id and task_id:
                with self.db._connect() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT total_input_tokens, total_output_tokens, cached_tokens,
                               cost_usd, tokens_by_category, tokens_by_tool
                        FROM tool_usage
                        WHERE task_id = ? AND experiment_id = ? AND job_id = ?
                    """, (task_id, exp_id, job_id))

                    row = cursor.fetchone()
                    if row:
                        input_tokens = row["total_input_tokens"] or 0
                        output_tokens = row["total_output_tokens"] or 0
                        cached_tokens = row["cached_tokens"] or 0
                        cost_usd = row["cost_usd"]

                        input_tokens_list.append(input_tokens)
                        output_tokens_list.append(output_tokens)
                        cached_tokens_list.append(cached_tokens)

                        if cost_usd is not None:
                            precomputed_costs.append(cost_usd)

                        # Aggregate tokens by category
                        if row["tokens_by_category"]:
                            try:
                                by_category = json.loads(row["tokens_by_category"])
                                for cat, tokens in by_category.items():
                                    if cat not in aggregated_by_category:
                                        aggregated_by_category[cat] = {"prompt": 0, "completion": 0, "cached": 0}
                                    for key in ["prompt", "completion", "cached"]:
                                        aggregated_by_category[cat][key] += tokens.get(key, 0)
                            except (json.JSONDecodeError, TypeError):
                                pass

                        # Aggregate tokens by tool
                        if row["tokens_by_tool"]:
                            try:
                                by_tool = json.loads(row["tokens_by_tool"])
                                for tool, tokens in by_tool.items():
                                    if tool not in aggregated_by_tool:
                                        aggregated_by_tool[tool] = {"prompt": 0, "completion": 0, "cached": 0}
                                    for key in ["prompt", "completion", "cached"]:
                                        aggregated_by_tool[tool][key] += tokens.get(key, 0)
                            except (json.JSONDecodeError, TypeError):
                                pass

        # Calculate token totals and averages
        metrics.total_input_tokens = sum(input_tokens_list)
        metrics.total_output_tokens = sum(output_tokens_list)
        metrics.total_cached_tokens = sum(cached_tokens_list)
        metrics.tokens_by_category = aggregated_by_category
        metrics.tokens_by_tool = aggregated_by_tool

        if results:
            metrics.avg_input_tokens = metrics.total_input_tokens / len(results)
            metrics.avg_output_tokens = metrics.total_output_tokens / len(results)

        # Use precomputed costs if available, otherwise calculate
        if precomputed_costs:
            metrics.total_cost_usd = sum(precomputed_costs)
        else:
            # Calculate costs from token counts
            model_name = metrics.model_name or "claude-3-5-haiku"

            # Normalize model name to match pricing keys
            model_key = None
            for key in model_pricing.keys():
                if key.replace("-", "").lower() in model_name.replace("-", "").lower():
                    model_key = key
                    break

            if not model_key:
                model_key = "claude-3-5-haiku"  # Default fallback

            pricing = model_pricing.get(model_key, model_pricing["claude-3-5-haiku"])

            # Calculate costs in USD
            input_cost_rate = pricing["input_tokens_per_million"] / 1_000_000
            output_cost_rate = pricing["output_tokens_per_million"] / 1_000_000

            metrics.input_cost_usd = metrics.total_input_tokens * input_cost_rate
            metrics.output_cost_usd = metrics.total_output_tokens * output_cost_rate
            metrics.total_cost_usd = metrics.input_cost_usd + metrics.output_cost_usd

        # Cost per task
        if len(results) > 0:
            metrics.avg_cost_per_task = metrics.total_cost_usd / len(results)

        # Cost per success
        if metrics.passed_tasks > 0:
            metrics.cost_per_success = metrics.total_cost_usd / metrics.passed_tasks

        return metrics
    
    def _rank_agents(
        self,
        agent_costs: dict[str, AgentCostMetrics],
        result: CostAnalysisResult,
    ) -> None:
        """Rank agents by cost and efficiency."""
        if not agent_costs:
            return
        
        # Cost ranking (cheapest first)
        sorted_by_cost = sorted(
            agent_costs.items(),
            key=lambda x: x[1].total_cost_usd
        )
        
        for rank, (agent_name, _) in enumerate(sorted_by_cost, 1):
            agent_costs[agent_name].cost_rank = rank
        
        result.cheapest_agent = sorted_by_cost[0][0] if sorted_by_cost else ""
        result.most_expensive_agent = sorted_by_cost[-1][0] if sorted_by_cost else ""
        
        # Efficiency ranking (best pass rate per dollar)
        # Efficiency = pass_rate / cost (higher is better)
        efficiency_scores = []
        for agent_name, metrics in agent_costs.items():
            if metrics.total_cost_usd > 0:
                efficiency = metrics.pass_rate / metrics.total_cost_usd
            else:
                efficiency = metrics.pass_rate
            efficiency_scores.append((agent_name, efficiency))
        
        sorted_by_efficiency = sorted(
            efficiency_scores,
            key=lambda x: x[1],
            reverse=True
        )
        
        for rank, (agent_name, _) in enumerate(sorted_by_efficiency, 1):
            agent_costs[agent_name].efficiency_rank = rank
        
        result.most_efficient_agent = sorted_by_efficiency[0][0] if sorted_by_efficiency else ""
    
    def _detect_regressions(
        self,
        baseline: AgentCostMetrics,
        variant: AgentCostMetrics,
    ) -> list[CostRegression]:
        """Detect cost regressions."""
        regressions = []
        
        # Check total cost
        cost_delta = (variant.total_cost_usd - baseline.total_cost_usd) / baseline.total_cost_usd if baseline.total_cost_usd > 0 else 0
        if cost_delta > 0.1:  # More than 10% increase
            severity = "critical" if cost_delta > 0.3 else "high"
            regressions.append(CostRegression(
                agent_name=variant.agent_name,
                metric_name="total_cost_usd",
                baseline_value=baseline.total_cost_usd,
                regression_value=variant.total_cost_usd,
                delta_percent=cost_delta * 100,
                severity=severity,
            ))
        
        # Check cost per success
        baseline_cps = baseline.cost_per_success or 0
        variant_cps = variant.cost_per_success or 0
        
        if baseline_cps > 0 and variant_cps > baseline_cps:
            cps_delta = (variant_cps - baseline_cps) / baseline_cps
            if cps_delta > 0.1:
                severity = "critical" if cps_delta > 0.3 else "high"
                regressions.append(CostRegression(
                    agent_name=variant.agent_name,
                    metric_name="cost_per_success",
                    baseline_value=baseline_cps,
                    regression_value=variant_cps,
                    delta_percent=cps_delta * 100,
                    severity=severity,
                ))
        
        # Check token increase without pass rate improvement
        token_delta = (variant.total_input_tokens + variant.total_output_tokens) - (baseline.total_input_tokens + baseline.total_output_tokens)
        pass_rate_delta = variant.pass_rate - baseline.pass_rate
        
        if token_delta > 0 and pass_rate_delta <= 0:
            severity = "medium"
            regressions.append(CostRegression(
                agent_name=variant.agent_name,
                metric_name="tokens_without_improvement",
                baseline_value=baseline.total_input_tokens + baseline.total_output_tokens,
                regression_value=variant.total_input_tokens + variant.total_output_tokens,
                delta_percent=(token_delta / (baseline.total_input_tokens + baseline.total_output_tokens) * 100) if (baseline.total_input_tokens + baseline.total_output_tokens) > 0 else 0,
                severity=severity,
            ))
        
        return regressions
