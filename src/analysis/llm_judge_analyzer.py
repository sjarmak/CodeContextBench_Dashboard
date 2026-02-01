"""
LLM Judge analyzer for quality-beyond-pass/fail evaluation.

Provides:
- Multi-dimensional code quality assessment (code quality, correctness, completeness)
- Judge score aggregation by agent
- Baseline vs variant comparison with statistical interpretation
- Integration with Anthropic Claude models (with mock backend for testing)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from src.ingest.database import MetricsDatabase


@dataclass
class JudgeScores:
    """Judge scores for a single task."""
    task_id: str
    agent_name: str
    
    # Dimension scores (0.0 to 1.0)
    code_quality: float = 0.0
    correctness: float = 0.0
    completeness: float = 0.0
    quality: float = 0.0
    efficiency: float = 0.0
    overall_score: float = 0.0
    
    # Reasoning
    code_quality_reasoning: str = ""
    correctness_reasoning: str = ""
    completeness_reasoning: str = ""
    quality_reasoning: str = ""
    efficiency_reasoning: str = ""
    overall_reasoning: str = ""
    
    # Metadata
    judge_model: str = ""
    tokens_used: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "scores": {
                "code_quality": self.code_quality,
                "correctness": self.correctness,
                "completeness": self.completeness,
                "quality": self.quality,
                "efficiency": self.efficiency,
                "overall": self.overall_score,
            },
            "reasoning": {
                "code_quality": self.code_quality_reasoning,
                "correctness": self.correctness_reasoning,
                "completeness": self.completeness_reasoning,
                "quality": self.quality_reasoning,
                "efficiency": self.efficiency_reasoning,
                "overall": self.overall_reasoning,
            },
            "metadata": {
                "judge_model": self.judge_model,
                "tokens_used": self.tokens_used,
            },
        }


@dataclass
class AgentJudgeMetrics:
    """Aggregated judge metrics for an agent."""
    agent_name: str
    total_evaluations: int = 0
    
    # Mean scores
    mean_code_quality: float = 0.0
    mean_correctness: float = 0.0
    mean_completeness: float = 0.0
    mean_quality: float = 0.0
    mean_efficiency: float = 0.0
    mean_overall: float = 0.0
    
    # Std dev
    std_code_quality: float = 0.0
    std_correctness: float = 0.0
    std_completeness: float = 0.0
    std_quality: float = 0.0
    std_efficiency: float = 0.0
    std_overall: float = 0.0
    
    # Min/Max
    min_overall: float = 0.0
    max_overall: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "total_evaluations": self.total_evaluations,
            "means": {
                "code_quality": self.mean_code_quality,
                "correctness": self.mean_correctness,
                "completeness": self.mean_completeness,
                "quality": self.mean_quality,
                "efficiency": self.mean_efficiency,
                "overall": self.mean_overall,
            },
            "std_devs": {
                "code_quality": self.std_code_quality,
                "correctness": self.std_correctness,
                "completeness": self.std_completeness,
                "quality": self.std_quality,
                "efficiency": self.std_efficiency,
                "overall": self.std_overall,
            },
            "range": {
                "min_overall": self.min_overall,
                "max_overall": self.max_overall,
            },
        }


@dataclass
class JudgeDelta:
    """Comparison between two agents' judge scores."""
    baseline_agent: str
    variant_agent: str
    
    # Delta in means (variant - baseline)
    code_quality_delta: float = 0.0
    correctness_delta: float = 0.0
    completeness_delta: float = 0.0
    quality_delta: float = 0.0
    efficiency_delta: float = 0.0
    overall_delta: float = 0.0
    
    # Interpretation
    improvement_areas: list[str] = field(default_factory=list)
    regression_areas: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "baseline_agent": self.baseline_agent,
            "variant_agent": self.variant_agent,
            "deltas": {
                "code_quality": self.code_quality_delta,
                "correctness": self.correctness_delta,
                "completeness": self.completeness_delta,
                "quality": self.quality_delta,
                "efficiency": self.efficiency_delta,
                "overall": self.overall_delta,
            },
            "interpretation": {
                "improvements": self.improvement_areas,
                "regressions": self.regression_areas,
            },
        }


@dataclass
class LLMJudgeAnalysisResult:
    """Results from LLM judge analysis."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)
    
    # Judge scores by task
    individual_scores: dict[str, JudgeScores] = field(default_factory=dict)
    
    # Aggregated metrics
    agent_metrics: dict[str, AgentJudgeMetrics] = field(default_factory=dict)
    
    # Comparisons
    deltas: dict[str, JudgeDelta] = field(default_factory=dict)  # key: "baseline__variant"
    
    # Summary
    best_agent_overall: str = ""
    worst_agent_overall: str = ""
    dimensions_with_improvement: list[str] = field(default_factory=list)
    dimensions_with_regression: list[str] = field(default_factory=list)
    
    # Metadata
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "baseline_agent": self.baseline_agent,
            "variant_agents": self.variant_agents,
            "individual_scores": {
                key: score.to_dict()
                for key, score in self.individual_scores.items()
            },
            "agent_metrics": {
                name: metrics.to_dict()
                for name, metrics in self.agent_metrics.items()
            },
            "comparisons": {
                key: delta.to_dict()
                for key, delta in self.deltas.items()
            },
            "summary": {
                "best_agent_overall": self.best_agent_overall,
                "worst_agent_overall": self.worst_agent_overall,
                "dimensions_with_improvement": self.dimensions_with_improvement,
                "dimensions_with_regression": self.dimensions_with_regression,
            },
            "computed_at": self.computed_at,
        }


class LLMJudgeAnalyzer:
    """Analyze judge scores across experiments."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize judge analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_judge_scores(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> LLMJudgeAnalysisResult:
        """
        Analyze judge scores for an experiment.
        
        Args:
            experiment_id: Experiment ID to analyze
            baseline_agent: Baseline agent for comparison (auto-detected if None)
            
        Returns:
            LLMJudgeAnalysisResult with judge metrics and deltas
        """
        # Get judge results
        all_judge_results = self.db.get_judge_results_for_experiment(experiment_id)
        
        if not all_judge_results:
            raise ValueError(f"No judge results found for experiment: {experiment_id}")
        
        # Group by agent
        agents_data = {}
        for result in all_judge_results:
            agent = result.get("agent_name") or "unknown"
            if agent not in agents_data:
                agents_data[agent] = []
            agents_data[agent].append(result)
        
        if not baseline_agent:
            baseline_agent = sorted(agents_data.keys())[0]
        
        # Initialize result
        analysis_result = LLMJudgeAnalysisResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=[a for a in agents_data.keys() if a != baseline_agent],
        )
        
        # Store individual scores
        for result in all_judge_results:
            key = f"{result['task_id']}__{result['agent_name']}"
            scores = JudgeScores(
                task_id=result["task_id"],
                agent_name=result["agent_name"],
                code_quality=result.get("code_quality", 0.0) or 0.0,
                correctness=result.get("correctness", 0.0) or 0.0,
                completeness=result.get("completeness", 0.0) or 0.0,
                quality=result.get("quality", 0.0) or 0.0,
                efficiency=result.get("efficiency", 0.0) or 0.0,
                overall_score=result.get("overall_score", 0.0) or 0.0,
                code_quality_reasoning=result.get("code_quality_reasoning", ""),
                correctness_reasoning=result.get("correctness_reasoning", ""),
                completeness_reasoning=result.get("completeness_reasoning", ""),
                quality_reasoning=result.get("quality_reasoning", ""),
                efficiency_reasoning=result.get("efficiency_reasoning", ""),
                overall_reasoning=result.get("overall_reasoning", ""),
                judge_model=result.get("judge_model", ""),
                tokens_used=result.get("tokens_used", 0) or 0,
            )
            analysis_result.individual_scores[key] = scores
        
        # Compute aggregated metrics
        for agent_name, results in agents_data.items():
            metrics = self._compute_agent_metrics(agent_name, results)
            analysis_result.agent_metrics[agent_name] = metrics
        
        # Compute deltas
        variant_agents = [a for a in analysis_result.agent_metrics.keys() if a != baseline_agent]
        if baseline_agent in analysis_result.agent_metrics:
            baseline_metrics = analysis_result.agent_metrics[baseline_agent]
            
            for variant_agent in variant_agents:
                if variant_agent in analysis_result.agent_metrics:
                    variant_metrics = analysis_result.agent_metrics[variant_agent]
                    delta_key = f"{baseline_agent}__{variant_agent}"
                    delta = self._compute_delta(baseline_metrics, variant_metrics)
                    analysis_result.deltas[delta_key] = delta
        
        # Determine best/worst
        if analysis_result.agent_metrics:
            best_agent = max(
                analysis_result.agent_metrics.keys(),
                key=lambda a: analysis_result.agent_metrics[a].mean_overall,
            )
            worst_agent = min(
                analysis_result.agent_metrics.keys(),
                key=lambda a: analysis_result.agent_metrics[a].mean_overall,
            )
            analysis_result.best_agent_overall = best_agent
            analysis_result.worst_agent_overall = worst_agent
        
        # Identify dimensions with improvement/regression
        dimensions = ["code_quality", "correctness", "completeness", "quality", "efficiency"]
        for delta in analysis_result.deltas.values():
            for dim in dimensions:
                delta_val = getattr(delta, f"{dim}_delta")
                if delta_val > 0.05:
                    if dim not in analysis_result.dimensions_with_improvement:
                        analysis_result.dimensions_with_improvement.append(dim)
                elif delta_val < -0.05:
                    if dim not in analysis_result.dimensions_with_regression:
                        analysis_result.dimensions_with_regression.append(dim)
        
        return analysis_result
    
    def _compute_agent_metrics(
        self,
        agent_name: str,
        results: list[dict],
    ) -> AgentJudgeMetrics:
        """Compute aggregated metrics for an agent."""
        metrics = AgentJudgeMetrics(
            agent_name=agent_name,
            total_evaluations=len(results),
        )
        
        if not results:
            return metrics
        
        # Extract score lists
        dimensions = {
            "code_quality": [],
            "correctness": [],
            "completeness": [],
            "quality": [],
            "efficiency": [],
            "overall": [],
        }
        
        for result in results:
            code_quality = result.get("code_quality", 0.0) or 0.0
            correctness = result.get("correctness", 0.0) or 0.0
            completeness = result.get("completeness", 0.0) or 0.0
            quality = result.get("quality", 0.0) or 0.0
            efficiency = result.get("efficiency", 0.0) or 0.0
            overall = result.get("overall_score", 0.0) or 0.0
            
            dimensions["code_quality"].append(float(code_quality))
            dimensions["correctness"].append(float(correctness))
            dimensions["completeness"].append(float(completeness))
            dimensions["quality"].append(float(quality))
            dimensions["efficiency"].append(float(efficiency))
            dimensions["overall"].append(float(overall))
        
        # Compute statistics
        for dim in dimensions.keys():
            values = dimensions[dim]
            if values:
                attr_mean = f"mean_{dim}"
                attr_std = f"std_{dim}"
                
                mean_val = statistics.mean(values)
                setattr(metrics, attr_mean, mean_val)
                
                if len(values) > 1:
                    std_val = statistics.stdev(values)
                    setattr(metrics, attr_std, std_val)
        
        # Set min/max overall
        if dimensions["overall"]:
            metrics.min_overall = min(dimensions["overall"])
            metrics.max_overall = max(dimensions["overall"])
        
        return metrics
    
    def _compute_delta(
        self,
        baseline: AgentJudgeMetrics,
        variant: AgentJudgeMetrics,
    ) -> JudgeDelta:
        """Compute delta between two agents."""
        delta = JudgeDelta(
            baseline_agent=baseline.agent_name,
            variant_agent=variant.agent_name,
            code_quality_delta=variant.mean_code_quality - baseline.mean_code_quality,
            correctness_delta=variant.mean_correctness - baseline.mean_correctness,
            completeness_delta=variant.mean_completeness - baseline.mean_completeness,
            quality_delta=variant.mean_quality - baseline.mean_quality,
            efficiency_delta=variant.mean_efficiency - baseline.mean_efficiency,
            overall_delta=variant.mean_overall - baseline.mean_overall,
        )
        
        # Identify improvements and regressions
        threshold = 0.05  # 5% change
        dimensions = {
            "code_quality": delta.code_quality_delta,
            "correctness": delta.correctness_delta,
            "completeness": delta.completeness_delta,
            "quality": delta.quality_delta,
            "efficiency": delta.efficiency_delta,
        }
        
        for dim, delta_val in dimensions.items():
            if delta_val > threshold:
                delta.improvement_areas.append(dim)
            elif delta_val < -threshold:
                delta.regression_areas.append(dim)
        
        return delta
