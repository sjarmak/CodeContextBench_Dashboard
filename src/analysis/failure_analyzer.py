"""
Failure pattern analyzer for identifying patterns in failed tasks.

Detects common failure modes and provides recommendations for improvement.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter
from datetime import datetime

from src.ingest.database import MetricsDatabase


@dataclass
class FailurePattern:
    """A detected failure pattern."""
    pattern_name: str
    description: str
    affected_tasks: list[str] = field(default_factory=list)
    frequency: int = 0
    
    # Pattern characteristics
    common_categories: list[str] = field(default_factory=list)
    common_difficulties: list[str] = field(default_factory=list)
    avg_duration_seconds: float = 0.0
    
    # Recommendation
    suggested_fix: str = ""
    confidence: float = 0.0  # 0.0-1.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pattern_name": self.pattern_name,
            "description": self.description,
            "affected_tasks": self.affected_tasks,
            "frequency": self.frequency,
            "characteristics": {
                "common_categories": self.common_categories,
                "common_difficulties": self.common_difficulties,
                "avg_duration_seconds": self.avg_duration_seconds,
            },
            "recommendation": {
                "suggested_fix": self.suggested_fix,
                "confidence": self.confidence,
            },
        }


@dataclass
class FailureAnalysisResult:
    """Results from failure analysis."""
    experiment_id: str
    agent_name: str
    
    total_failures: int = 0
    total_tasks: int = 0
    failure_rate: float = 0.0
    
    # Detected patterns
    patterns: list[FailurePattern] = field(default_factory=list)
    
    # Top failure characteristics
    top_failing_categories: list[tuple[str, int]] = field(default_factory=list)
    top_failing_difficulties: list[tuple[str, int]] = field(default_factory=list)
    
    # Comparison to baseline
    failure_rate_vs_baseline: Optional[float] = None
    is_worse_than_baseline: bool = False
    
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "agent_name": self.agent_name,
            "failure_stats": {
                "total_failures": self.total_failures,
                "total_tasks": self.total_tasks,
                "failure_rate": self.failure_rate,
            },
            "patterns": [p.to_dict() for p in self.patterns],
            "top_characteristics": {
                "failing_categories": self.top_failing_categories,
                "failing_difficulties": self.top_failing_difficulties,
            },
            "baseline_comparison": {
                "failure_rate_delta": self.failure_rate_vs_baseline,
                "is_worse_than_baseline": self.is_worse_than_baseline,
            },
            "computed_at": self.computed_at,
        }


class FailureAnalyzer:
    """Analyze failure patterns in experiment results."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize failure analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_failures(
        self,
        experiment_id: str,
        agent_name: Optional[str] = None,
        baseline_agent: Optional[str] = None,
    ) -> FailureAnalysisResult:
        """
        Analyze failures for an agent in an experiment.
        
        Args:
            experiment_id: Experiment ID
            agent_name: Specific agent to analyze (optional)
            baseline_agent: Baseline agent for comparison
            
        Returns:
            FailureAnalysisResult with pattern analysis
        """
        # Get results
        results = self.db.get_experiment_results(experiment_id)
        
        if not results:
            raise ValueError(f"No results found for experiment: {experiment_id}")
        
        # Filter by agent if specified
        if agent_name:
            results = [r for r in results if r.get("agent_name") == agent_name]
        else:
            # Use first agent if not specified
            if results:
                agent_name = results[0].get("agent_name") or "unknown"
            results = [r for r in results if r.get("agent_name") == agent_name]
        
        # Separate failures
        failures = [r for r in results if not r.get("passed")]
        
        failure_rate = (len(failures) / len(results)) if results else 0.0
        
        # Extract patterns
        patterns = self._detect_patterns(failures)
        
        # Get top characteristics
        categories = Counter(r.get("task_category", "unknown") for r in failures)
        difficulties = Counter(r.get("task_difficulty", "unknown") for r in failures)
        
        # Compute baseline comparison
        failure_rate_vs_baseline = None
        is_worse = False
        
        if baseline_agent:
            baseline_failures = [
                r for r in results
                if not r.get("passed") and r.get("agent_name") == baseline_agent
            ]
            baseline_rate = (len(baseline_failures) / len(results)) if results else 0.0
            failure_rate_vs_baseline = failure_rate - baseline_rate
            is_worse = failure_rate_vs_baseline > 0.05  # More than 5% worse
        
        return FailureAnalysisResult(
            experiment_id=experiment_id,
            agent_name=agent_name,
            total_failures=len(failures),
            total_tasks=len(results),
            failure_rate=failure_rate,
            patterns=patterns,
            top_failing_categories=categories.most_common(5),
            top_failing_difficulties=difficulties.most_common(5),
            failure_rate_vs_baseline=failure_rate_vs_baseline,
            is_worse_than_baseline=is_worse,
        )
    
    def _detect_patterns(self, failures: list[dict]) -> list[FailurePattern]:
        """Detect common failure patterns."""
        patterns = []
        
        if not failures:
            return patterns
        
        # Pattern 1: High-difficulty failures
        hard_failures = [f for f in failures if f.get("task_difficulty") in ["hard", "expert"]]
        if len(hard_failures) > 0:
            pattern = FailurePattern(
                pattern_name="High-Difficulty Task Failures",
                description="Agent struggles with harder tasks",
                affected_tasks=[f.get("task_id", "") for f in hard_failures],
                frequency=len(hard_failures),
                common_difficulties=["hard", "expert"],
                suggested_fix="Improve reasoning and planning for complex tasks; consider more focused Deep Search usage",
                confidence=min(1.0, len(hard_failures) / len(failures)),
            )
            patterns.append(pattern)
        
        # Pattern 2: Specific category failures
        categories = Counter(f.get("task_category") for f in failures if f.get("task_category"))
        top_category = categories.most_common(1)
        
        if top_category and top_category[0][1] >= len(failures) * 0.3:
            pattern = FailurePattern(
                pattern_name=f"Category-Specific Failures: {top_category[0][0]}",
                description=f"Agent fails predominantly on {top_category[0][0]} tasks",
                affected_tasks=[
                    f.get("task_id", "")
                    for f in failures
                    if f.get("task_category") == top_category[0][0]
                ],
                frequency=top_category[0][1],
                common_categories=[top_category[0][0]],
                suggested_fix=f"Review benchmark tasks for {top_category[0][0]}; may need domain-specific prompting",
                confidence=top_category[0][1] / len(failures),
            )
            patterns.append(pattern)
        
        # Pattern 3: Timeout/duration-related failures
        long_failures = [
            f for f in failures
            if f.get("total_duration_seconds", 0) > 300  # Over 5 minutes
        ]
        
        if len(long_failures) > 0:
            pattern = FailurePattern(
                pattern_name="Duration-Related Failures",
                description="Agent times out or exceeds time limits",
                affected_tasks=[f.get("task_id", "") for f in long_failures],
                frequency=len(long_failures),
                avg_duration_seconds=sum(
                    f.get("total_duration_seconds", 0) for f in long_failures
                ) / len(long_failures) if long_failures else 0,
                suggested_fix="Optimize tool usage; reduce redundant searches; improve task decomposition",
                confidence=len(long_failures) / len(failures),
            )
            patterns.append(pattern)
        
        # Pattern 4: Low reward metric failures
        low_reward_failures = [
            f for f in failures
            if f.get("reward_primary") is not None and f.get("reward_primary") < 0.3
        ]
        
        if len(low_reward_failures) > 0:
            pattern = FailurePattern(
                pattern_name="Low-Quality Solutions",
                description="Agent produces solutions with low reward scores",
                affected_tasks=[f.get("task_id", "") for f in low_reward_failures],
                frequency=len(low_reward_failures),
                suggested_fix="Focus on solution quality; improve code generation and testing",
                confidence=len(low_reward_failures) / len(failures),
            )
            patterns.append(pattern)
        
        return patterns
