"""
IR (Information Retrieval) metrics analyzer for IR-SDLC benchmarks.

Analyzes precision, recall, MRR, NDCG and other IR metrics extracted
from Harbor reward data to measure retrieval quality improvements.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from src.ingest.database import MetricsDatabase


@dataclass
class IRMetricsAggregate:
    """Aggregated IR metrics for an agent."""
    agent_name: str
    model_name: Optional[str]
    
    total_tasks: int = 0
    
    # Standard IR metrics (aggregated)
    precision_at_1: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    map_score: float = 0.0
    
    # SDLC-specific metrics
    file_level_recall: float = 0.0
    cross_module_coverage: float = 0.0
    context_efficiency: float = 0.0
    
    # Tool usage correlation
    avg_mcp_calls: float = 0.0
    avg_deep_search_calls: float = 0.0
    mcp_vs_local_ratio: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "total_tasks": self.total_tasks,
            "standard_metrics": {
                "precision@1": self.precision_at_1,
                "precision@5": self.precision_at_5,
                "precision@10": self.precision_at_10,
                "recall@1": self.recall_at_1,
                "recall@5": self.recall_at_5,
                "recall@10": self.recall_at_10,
                "mrr": self.mrr,
                "ndcg@10": self.ndcg_at_10,
                "map": self.map_score,
            },
            "sdlc_metrics": {
                "file_level_recall": self.file_level_recall,
                "cross_module_coverage": self.cross_module_coverage,
                "context_efficiency": self.context_efficiency,
            },
            "tool_usage": {
                "avg_mcp_calls": self.avg_mcp_calls,
                "avg_deep_search_calls": self.avg_deep_search_calls,
                "mcp_vs_local_ratio": self.mcp_vs_local_ratio,
            },
        }


@dataclass
class IRDelta:
    """Comparison of IR metrics between two agents."""
    baseline_agent: str
    variant_agent: str
    
    # Metric deltas
    mrr_delta: float = 0.0
    precision_at_10_delta: float = 0.0
    recall_at_10_delta: float = 0.0
    ndcg_at_10_delta: float = 0.0
    file_level_recall_delta: float = 0.0
    cross_module_coverage_delta: float = 0.0
    context_efficiency_delta: float = 0.0
    
    # Interpretation
    retrieval_quality_impact: str = "neutral"  # "improved", "degraded", "neutral"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "baseline_agent": self.baseline_agent,
            "variant_agent": self.variant_agent,
            "metric_deltas": {
                "mrr": self.mrr_delta,
                "precision@10": self.precision_at_10_delta,
                "recall@10": self.recall_at_10_delta,
                "ndcg@10": self.ndcg_at_10_delta,
                "file_level_recall": self.file_level_recall_delta,
                "cross_module_coverage": self.cross_module_coverage_delta,
                "context_efficiency": self.context_efficiency_delta,
            },
            "interpretation": {
                "retrieval_quality_impact": self.retrieval_quality_impact,
            },
        }


@dataclass
class IRAnalysisResult:
    """Results from IR metric analysis."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)
    
    # Agent metrics
    agent_metrics: dict[str, IRMetricsAggregate] = field(default_factory=dict)
    
    # Comparisons
    deltas: dict[str, IRDelta] = field(default_factory=dict)
    
    # Summary insights
    best_mrr_agent: str = ""
    best_recall_agent: str = ""
    most_efficient_agent: str = ""
    
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
            "insights": {
                "best_mrr_agent": self.best_mrr_agent,
                "best_recall_agent": self.best_recall_agent,
                "most_efficient_agent": self.most_efficient_agent,
            },
            "computed_at": self.computed_at,
        }


class IRAnalyzer:
    """Analyze IR metrics from Harbor reward data."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize IR analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_experiment(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> IRAnalysisResult:
        """
        Analyze IR metrics for an experiment.
        
        Args:
            experiment_id: Experiment ID to analyze
            baseline_agent: Baseline agent for comparison
            
        Returns:
            IRAnalysisResult with IR metrics and deltas
        """
        # Get all results
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
        
        # Compute IR metrics for each agent
        agent_metrics = {}
        for agent_name, agent_results in agents_data.items():
            metrics = self._extract_ir_metrics(agent_name, agent_results)
            agent_metrics[agent_name] = metrics
        
        # Compute deltas
        variant_agents = [a for a in agent_metrics.keys() if a != baseline_agent]
        deltas = {}
        
        if baseline_agent in agent_metrics:
            baseline_metrics = agent_metrics[baseline_agent]
            
            for variant_agent in variant_agents:
                variant_metrics = agent_metrics[variant_agent]
                delta_key = f"{baseline_agent}__{variant_agent}"
                delta = self._compute_ir_delta(baseline_metrics, variant_metrics)
                deltas[delta_key] = delta
        
        # Find best agents
        best_mrr_agent = max(
            agent_metrics.keys(),
            key=lambda a: agent_metrics[a].mrr,
        ) if agent_metrics else ""
        
        best_recall_agent = max(
            agent_metrics.keys(),
            key=lambda a: agent_metrics[a].recall_at_10,
        ) if agent_metrics else ""
        
        most_efficient_agent = max(
            agent_metrics.keys(),
            key=lambda a: agent_metrics[a].context_efficiency,
        ) if agent_metrics else ""
        
        return IRAnalysisResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=variant_agents,
            agent_metrics=agent_metrics,
            deltas=deltas,
            best_mrr_agent=best_mrr_agent,
            best_recall_agent=best_recall_agent,
            most_efficient_agent=most_efficient_agent,
        )
    
    def _extract_ir_metrics(
        self,
        agent_name: str,
        results: list[dict],
    ) -> IRMetricsAggregate:
        """Extract and aggregate IR metrics from results."""
        metric_values = {
            "precision_at_1": [],
            "precision_at_5": [],
            "precision_at_10": [],
            "recall_at_1": [],
            "recall_at_5": [],
            "recall_at_10": [],
            "mrr": [],
            "ndcg_at_10": [],
            "map": [],
            "file_level_recall": [],
            "cross_module_coverage": [],
            "context_efficiency": [],
        }
        
        mcp_calls_list = []
        deep_search_calls_list = []
        mcp_vs_local_ratios = []
        
        # Extract metrics from reward JSON
        for result in results:
            if result.get("reward_metrics"):
                try:
                    reward = json.loads(result["reward_metrics"])
                    
                    # Map field names (with @ replaced by _at_)
                    metric_mapping = {
                        "precision_at_1": ["precision@1", "precision_at_1"],
                        "precision_at_5": ["precision@5", "precision_at_5"],
                        "precision_at_10": ["precision@10", "precision_at_10"],
                        "recall_at_1": ["recall@1", "recall_at_1"],
                        "recall_at_5": ["recall@5", "recall_at_5"],
                        "recall_at_10": ["recall@10", "recall_at_10"],
                        "mrr": ["mrr"],
                        "ndcg_at_10": ["ndcg@10", "ndcg_at_10"],
                        "map": ["map"],
                        "file_level_recall": ["file_level_recall"],
                        "cross_module_coverage": ["cross_module_coverage"],
                        "context_efficiency": ["context_efficiency"],
                    }
                    
                    for key, aliases in metric_mapping.items():
                        for alias in aliases:
                            if alias in reward and isinstance(reward[alias], (int, float)):
                                metric_values[key].append(reward[alias])
                                break
                
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Get tool usage
        with self.db._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tu.mcp_calls, tu.deep_search_calls, tu.mcp_vs_local_ratio
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
            
            for row in cursor.fetchall():
                if row["mcp_calls"]:
                    mcp_calls_list.append(row["mcp_calls"])
                if row["deep_search_calls"]:
                    deep_search_calls_list.append(row["deep_search_calls"])
                if row["mcp_vs_local_ratio"]:
                    mcp_vs_local_ratios.append(row["mcp_vs_local_ratio"])
        
        # Compute averages
        def safe_mean(values):
            return statistics.mean(values) if values else 0.0
        
        return IRMetricsAggregate(
            agent_name=agent_name,
            model_name=results[0].get("model_name") if results else None,
            total_tasks=len(results),
            precision_at_1=safe_mean(metric_values["precision_at_1"]),
            precision_at_5=safe_mean(metric_values["precision_at_5"]),
            precision_at_10=safe_mean(metric_values["precision_at_10"]),
            recall_at_1=safe_mean(metric_values["recall_at_1"]),
            recall_at_5=safe_mean(metric_values["recall_at_5"]),
            recall_at_10=safe_mean(metric_values["recall_at_10"]),
            mrr=safe_mean(metric_values["mrr"]),
            ndcg_at_10=safe_mean(metric_values["ndcg_at_10"]),
            map_score=safe_mean(metric_values["map"]),
            file_level_recall=safe_mean(metric_values["file_level_recall"]),
            cross_module_coverage=safe_mean(metric_values["cross_module_coverage"]),
            context_efficiency=safe_mean(metric_values["context_efficiency"]),
            avg_mcp_calls=safe_mean(mcp_calls_list),
            avg_deep_search_calls=safe_mean(deep_search_calls_list),
            mcp_vs_local_ratio=safe_mean(mcp_vs_local_ratios),
        )
    
    def _compute_ir_delta(
        self,
        baseline: IRMetricsAggregate,
        variant: IRMetricsAggregate,
    ) -> IRDelta:
        """Compute delta between two agents."""
        mrr_delta = variant.mrr - baseline.mrr
        precision_delta = variant.precision_at_10 - baseline.precision_at_10
        recall_delta = variant.recall_at_10 - baseline.recall_at_10
        
        # Determine impact
        impact = "neutral"
        if mrr_delta > 0.05:  # More than 5% improvement
            impact = "improved"
        elif mrr_delta < -0.05:  # More than 5% degradation
            impact = "degraded"
        
        return IRDelta(
            baseline_agent=baseline.agent_name,
            variant_agent=variant.agent_name,
            mrr_delta=mrr_delta,
            precision_at_10_delta=precision_delta,
            recall_at_10_delta=recall_delta,
            ndcg_at_10_delta=variant.ndcg_at_10 - baseline.ndcg_at_10,
            file_level_recall_delta=variant.file_level_recall - baseline.file_level_recall,
            cross_module_coverage_delta=variant.cross_module_coverage - baseline.cross_module_coverage,
            context_efficiency_delta=variant.context_efficiency - baseline.context_efficiency,
            retrieval_quality_impact=impact,
        )
