"""
Recommendation engine for suggesting configuration improvements.

Analyzes failure patterns, tool usage, and performance deltas to suggest
prompt adjustments, tool configuration changes, and experiment refinements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .comparator import ComparisonResult, ComparisonDelta
from .failure_analyzer import FailureAnalysisResult, FailurePattern
from .ir_analyzer import IRAnalysisResult


@dataclass
class Recommendation:
    """A single recommendation."""
    category: str  # "prompting", "tools", "config", "experiment"
    title: str
    description: str
    affected_agent: str
    
    # Specificity
    target_benchmark: Optional[str] = None
    target_difficulty: Optional[str] = None
    
    # Impact
    expected_impact: str = "medium"  # "high", "medium", "low"
    effort: str = "medium"  # "high", "medium", "low"
    
    # Implementation
    implementation_details: str = ""
    config_changes: dict = field(default_factory=dict)
    
    # Metadata
    source: str = ""  # "failure_pattern", "comparison", "ir_analysis"
    confidence: float = 0.0  # 0.0-1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "affected_agent": self.affected_agent,
            "targeting": {
                "benchmark": self.target_benchmark,
                "difficulty": self.target_difficulty,
            },
            "impact": {
                "expected_impact": self.expected_impact,
                "effort": self.effort,
            },
            "implementation": {
                "details": self.implementation_details,
                "config_changes": self.config_changes,
            },
            "metadata": {
                "source": self.source,
                "confidence": self.confidence,
            },
        }


@dataclass
class RecommendationPlan:
    """A complete recommendation plan."""
    experiment_id: str
    agent_name: str
    
    recommendations: list[Recommendation] = field(default_factory=list)
    
    # Priority levels
    high_priority: list[Recommendation] = field(default_factory=list)
    medium_priority: list[Recommendation] = field(default_factory=list)
    low_priority: list[Recommendation] = field(default_factory=list)
    
    # Summary
    total_issues_detected: int = 0
    quick_wins: list[Recommendation] = field(default_factory=list)
    
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "agent_name": self.agent_name,
            "all_recommendations": [r.to_dict() for r in self.recommendations],
            "by_priority": {
                "high": [r.to_dict() for r in self.high_priority],
                "medium": [r.to_dict() for r in self.medium_priority],
                "low": [r.to_dict() for r in self.low_priority],
            },
            "summary": {
                "total_issues": self.total_issues_detected,
                "quick_wins": [r.to_dict() for r in self.quick_wins],
            },
            "generated_at": self.generated_at,
        }


class RecommendationEngine:
    """Generate recommendations from analysis results."""
    
    def generate_plan(
        self,
        experiment_id: str,
        agent_name: str,
        comparison_result: Optional[ComparisonResult] = None,
        failure_analysis: Optional[FailureAnalysisResult] = None,
        ir_analysis: Optional[IRAnalysisResult] = None,
    ) -> RecommendationPlan:
        """
        Generate a complete recommendation plan.
        
        Args:
            experiment_id: Experiment ID
            agent_name: Agent to generate recommendations for
            comparison_result: Optional comparison result
            failure_analysis: Optional failure analysis
            ir_analysis: Optional IR analysis
            
        Returns:
            RecommendationPlan with prioritized recommendations
        """
        plan = RecommendationPlan(
            experiment_id=experiment_id,
            agent_name=agent_name,
        )
        
        # Generate recommendations from failure analysis
        if failure_analysis:
            plan.recommendations.extend(
                self._recommendations_from_failures(failure_analysis)
            )
        
        # Generate recommendations from comparisons
        if comparison_result and agent_name in comparison_result.agent_metrics:
            plan.recommendations.extend(
                self._recommendations_from_comparison(comparison_result, agent_name)
            )
        
        # Generate recommendations from IR analysis
        if ir_analysis and agent_name in ir_analysis.agent_metrics:
            plan.recommendations.extend(
                self._recommendations_from_ir(ir_analysis, agent_name)
            )
        
        # Prioritize recommendations
        for rec in plan.recommendations:
            if rec.expected_impact == "high" and rec.effort == "low":
                plan.quick_wins.append(rec)
            
            if rec.expected_impact == "high":
                plan.high_priority.append(rec)
            elif rec.expected_impact == "medium":
                plan.medium_priority.append(rec)
            else:
                plan.low_priority.append(rec)
        
        plan.total_issues_detected = len(plan.recommendations)
        
        return plan
    
    def _recommendations_from_failures(
        self,
        failure_analysis: FailureAnalysisResult,
    ) -> list[Recommendation]:
        """Generate recommendations from failure patterns."""
        recommendations = []
        
        if failure_analysis.failure_rate > 0.5:
            recommendations.append(Recommendation(
                category="prompting",
                title="High Overall Failure Rate",
                description=f"Agent has {failure_analysis.failure_rate:.1%} failure rate",
                affected_agent=failure_analysis.agent_name,
                expected_impact="high",
                effort="high",
                implementation_details="Review system prompt; improve task understanding and reasoning",
                source="failure_analysis",
                confidence=min(1.0, failure_analysis.failure_rate),
            ))
        
        for pattern in failure_analysis.patterns:
            if pattern.confidence > 0.3:
                impact = "high" if pattern.confidence > 0.5 else "medium"
                
                recommendations.append(Recommendation(
                    category="prompting" if "Difficulty" in pattern.pattern_name else "config",
                    title=f"Address: {pattern.pattern_name}",
                    description=pattern.description,
                    affected_agent=failure_analysis.agent_name,
                    target_difficulty=pattern.common_difficulties[0] if pattern.common_difficulties else None,
                    target_benchmark=pattern.common_categories[0] if pattern.common_categories else None,
                    expected_impact=impact,
                    effort="medium",
                    implementation_details=pattern.suggested_fix,
                    source="failure_pattern",
                    confidence=pattern.confidence,
                ))
        
        return recommendations
    
    def _recommendations_from_comparison(
        self,
        comparison: ComparisonResult,
        agent_name: str,
    ) -> list[Recommendation]:
        """Generate recommendations from agent comparisons."""
        recommendations = []
        
        agent_metrics = comparison.agent_metrics.get(agent_name)
        if not agent_metrics:
            return recommendations
        
        # Find baseline
        baseline_key = f"{comparison.baseline_agent}__{agent_name}"
        delta = comparison.deltas.get(baseline_key)
        
        if not delta:
            return recommendations
        
        # Tool usage recommendations
        if delta.mcp_calls_delta > 5 and delta.pass_rate_delta < 0:
            recommendations.append(Recommendation(
                category="tools",
                title="Reduce Excessive MCP Tool Usage",
                description="Agent uses significantly more MCP tools but with worse pass rate",
                affected_agent=agent_name,
                expected_impact="high",
                effort="low",
                implementation_details="Reduce MCP tool calls; use Deep Search more strategically",
                config_changes={
                    "mcp_call_limit": 10,
                    "deep_search_threshold": 0.7,
                },
                source="comparison",
                confidence=0.8,
            ))
        
        # Efficiency recommendations
        if delta.duration_delta_seconds > 60:
            recommendations.append(Recommendation(
                category="config",
                title="Improve Execution Efficiency",
                description=f"Agent is {delta.duration_delta_seconds:.0f}s slower than baseline",
                affected_agent=agent_name,
                expected_impact="medium",
                effort="medium",
                implementation_details="Optimize tool call patterns; cache results; reduce redundant searches",
                source="comparison",
                confidence=0.7,
            ))
        
        # Deep Search usage recommendations
        if delta.deep_search_calls_delta < -1 and delta.pass_rate_delta > 0:
            recommendations.append(Recommendation(
                category="prompting",
                title="Increase Deep Search Usage",
                description="Reducing Deep Search usage correlates with worse performance",
                affected_agent=agent_name,
                expected_impact="high",
                effort="low",
                implementation_details="Encourage more Deep Search at critical decision points",
                config_changes={
                    "deep_search_on_stuck": True,
                    "deep_search_frequency": "high",
                },
                source="comparison",
                confidence=0.75,
            ))
        
        return recommendations
    
    def _recommendations_from_ir(
        self,
        ir_analysis: IRAnalysisResult,
        agent_name: str,
    ) -> list[Recommendation]:
        """Generate recommendations from IR analysis."""
        recommendations = []
        
        agent_metrics = ir_analysis.agent_metrics.get(agent_name)
        if not agent_metrics:
            return recommendations
        
        # Find baseline
        baseline_key = f"{ir_analysis.baseline_agent}__{agent_name}"
        delta = ir_analysis.deltas.get(baseline_key)
        
        if not delta:
            return recommendations
        
        # Recall improvements
        if delta.recall_at_10_delta < -0.1:
            recommendations.append(Recommendation(
                category="tools",
                title="Improve File Retrieval Recall",
                description=f"Agent retrieves {abs(delta.recall_at_10_delta):.1%} fewer relevant files",
                affected_agent=agent_name,
                expected_impact="high",
                effort="medium",
                implementation_details="Use Deep Search more; improve query formulation; broaden search scope",
                source="ir_analysis",
                confidence=0.8,
            ))
        
        # Precision improvements
        if delta.precision_at_10_delta < -0.15:
            recommendations.append(Recommendation(
                category="prompting",
                title="Improve Result Ranking/Filtering",
                description="Agent retrieves many irrelevant files",
                affected_agent=agent_name,
                expected_impact="medium",
                effort="medium",
                implementation_details="Better filtering of results; improved relevance assessment",
                source="ir_analysis",
                confidence=0.7,
            ))
        
        # Context efficiency
        if agent_metrics.context_efficiency < 0.5:
            recommendations.append(Recommendation(
                category="tools",
                title="Improve Context Window Efficiency",
                description="Agent includes many irrelevant code snippets in context",
                affected_agent=agent_name,
                expected_impact="medium",
                effort="low",
                implementation_details="Focus on most relevant code; reduce snippet sizes",
                source="ir_analysis",
                confidence=0.6,
            ))
        
        return recommendations
