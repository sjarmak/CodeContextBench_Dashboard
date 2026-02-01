"""
Statistical significance testing for experiment comparisons.

Provides statistical rigor to experimental results by computing:
- T-tests for continuous metrics (duration, rewards)
- Chi-square tests for categorical metrics (pass/fail)
- Effect sizes (Cohen's d, Cramér's V)
- Confidence intervals
- P-value interpretation
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional
from scipy import stats

from src.ingest.database import MetricsDatabase


@dataclass
class StatisticalTest:
    """Result of a statistical significance test."""
    test_name: str  # "t-test", "chi-square", "mann-whitney"
    metric_name: str
    baseline_agent: str
    variant_agent: str
    
    # Test parameters
    baseline_values: list[float] = field(default_factory=list)
    variant_values: list[float] = field(default_factory=list)
    
    # Results
    statistic: float = 0.0
    p_value: float = 1.0
    effect_size: float = 0.0
    effect_size_name: str = ""  # "Cohen's d", "Cramér's V", etc.
    
    # Interpretation
    is_significant: bool = False
    confidence_level: float = 0.95  # Alpha = 0.05
    interpretation: str = ""
    
    # Metadata
    sample_size_baseline: int = 0
    sample_size_variant: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "metric_name": self.metric_name,
            "baseline_agent": self.baseline_agent,
            "variant_agent": self.variant_agent,
            "results": {
                "statistic": self.statistic,
                "p_value": self.p_value,
                "is_significant": self.is_significant,
                "significance_level": 1 - self.confidence_level,
            },
            "effect_size": {
                "value": self.effect_size,
                "name": self.effect_size_name,
            },
            "sample_sizes": {
                "baseline": self.sample_size_baseline,
                "variant": self.sample_size_variant,
            },
            "interpretation": self.interpretation,
        }


@dataclass
class StatisticalAnalysisResult:
    """Complete statistical analysis of an experiment."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)
    
    # Test results organized by metric
    tests: dict[str, list[StatisticalTest]] = field(default_factory=dict)
    
    # Summary
    significant_metrics: list[str] = field(default_factory=list)
    non_significant_metrics: list[str] = field(default_factory=list)
    
    # Confidence assessment
    total_tests: int = 0
    significant_tests: int = 0
    power_assessment: str = "unknown"  # "underpowered", "adequate", "well-powered"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        significant_tests = [
            t.to_dict() for metric in self.significant_metrics
            for t in self.tests.get(metric, [])
        ]
        non_significant_tests = [
            t.to_dict() for metric in self.non_significant_metrics
            for t in self.tests.get(metric, [])
        ]
        
        return {
            "experiment_id": self.experiment_id,
            "baseline_agent": self.baseline_agent,
            "variant_agents": self.variant_agents,
            "summary": {
                "total_tests": self.total_tests,
                "significant_tests": self.significant_tests,
                "significance_rate": self.significant_tests / self.total_tests if self.total_tests > 0 else 0,
                "power_assessment": self.power_assessment,
            },
            "results": {
                "significant": {
                    "metrics": self.significant_metrics,
                    "tests": significant_tests,
                },
                "non_significant": {
                    "metrics": self.non_significant_metrics,
                    "tests": non_significant_tests,
                },
            },
        }


class StatisticalAnalyzer:
    """Perform statistical significance testing on comparisons."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize statistical analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_comparison(
        self,
        experiment_id: str,
        baseline_agent: str,
        variant_agents: Optional[list[str]] = None,
        confidence_level: float = 0.95,
    ) -> StatisticalAnalysisResult:
        """
        Perform statistical tests on agent comparison.
        
        Args:
            experiment_id: Experiment ID
            baseline_agent: Baseline agent name
            variant_agents: Agents to compare (defaults to all)
            confidence_level: Statistical confidence level (0.0-1.0)
            
        Returns:
            StatisticalAnalysisResult with all test results
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
        
        if baseline_agent not in agents_data:
            raise ValueError(f"Baseline agent '{baseline_agent}' not found")
        
        if not variant_agents:
            variant_agents = [a for a in agents_data.keys() if a != baseline_agent]
        
        # Extract metrics from baseline
        baseline_results = agents_data[baseline_agent]
        baseline_pass_rates = [1 if r["passed"] else 0 for r in baseline_results]
        baseline_durations = [r["total_duration_seconds"] or 0 for r in baseline_results if r["total_duration_seconds"]]
        baseline_rewards = [r["reward_primary"] or 0 for r in baseline_results if r["reward_primary"]]
        
        # Run tests for each variant
        analysis_result = StatisticalAnalysisResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=variant_agents,
        )
        
        for variant_agent in variant_agents:
            variant_results = agents_data[variant_agent]
            variant_pass_rates = [1 if r["passed"] else 0 for r in variant_results]
            variant_durations = [r["total_duration_seconds"] or 0 for r in variant_results if r["total_duration_seconds"]]
            variant_rewards = [r["reward_primary"] or 0 for r in variant_results if r["reward_primary"]]
            
            # Test 1: Pass rate (Chi-square)
            if baseline_pass_rates and variant_pass_rates:
                test = self._chi_square_test(
                    "pass_rate",
                    baseline_agent,
                    variant_agent,
                    baseline_pass_rates,
                    variant_pass_rates,
                    confidence_level,
                )
                if "pass_rate" not in analysis_result.tests:
                    analysis_result.tests["pass_rate"] = []
                analysis_result.tests["pass_rate"].append(test)
            
            # Test 2: Duration (T-test if normal, Mann-Whitney if not)
            if baseline_durations and variant_durations:
                test = self._duration_test(
                    baseline_agent,
                    variant_agent,
                    baseline_durations,
                    variant_durations,
                    confidence_level,
                )
                if "duration" not in analysis_result.tests:
                    analysis_result.tests["duration"] = []
                analysis_result.tests["duration"].append(test)
            
            # Test 3: Rewards (T-test)
            if baseline_rewards and variant_rewards:
                test = self._t_test(
                    "reward_primary",
                    baseline_agent,
                    variant_agent,
                    baseline_rewards,
                    variant_rewards,
                    confidence_level,
                )
                if "reward_primary" not in analysis_result.tests:
                    analysis_result.tests["reward_primary"] = []
                analysis_result.tests["reward_primary"].append(test)
        
        # Compute summary
        for metric, tests in analysis_result.tests.items():
            for test in tests:
                analysis_result.total_tests += 1
                if test.is_significant:
                    analysis_result.significant_tests += 1
                    if metric not in analysis_result.significant_metrics:
                        analysis_result.significant_metrics.append(metric)
                else:
                    if metric not in analysis_result.non_significant_metrics:
                        analysis_result.non_significant_metrics.append(metric)
        
        # Assess statistical power
        analysis_result.power_assessment = self._assess_power(
            [len(data) for data in agents_data.values()]
        )
        
        return analysis_result
    
    def _t_test(
        self,
        metric_name: str,
        baseline_agent: str,
        variant_agent: str,
        baseline_values: list[float],
        variant_values: list[float],
        confidence_level: float,
    ) -> StatisticalTest:
        """Perform independent samples t-test."""
        alpha = 1 - confidence_level
        
        # Compute t-statistic and p-value
        t_stat, p_value = stats.ttest_ind(baseline_values, variant_values)
        
        # Compute effect size (Cohen's d)
        cohens_d = self._cohens_d(baseline_values, variant_values)
        
        # Interpret
        is_significant = p_value < alpha
        interpretation = self._interpret_p_value(p_value, alpha)
        
        return StatisticalTest(
            test_name="t-test",
            metric_name=metric_name,
            baseline_agent=baseline_agent,
            variant_agent=variant_agent,
            baseline_values=baseline_values,
            variant_values=variant_values,
            statistic=t_stat,
            p_value=p_value,
            effect_size=cohens_d,
            effect_size_name="Cohen's d",
            is_significant=is_significant,
            confidence_level=confidence_level,
            interpretation=interpretation,
            sample_size_baseline=len(baseline_values),
            sample_size_variant=len(variant_values),
        )
    
    def _chi_square_test(
        self,
        metric_name: str,
        baseline_agent: str,
        variant_agent: str,
        baseline_values: list[int],
        variant_values: list[int],
        confidence_level: float,
    ) -> StatisticalTest:
        """Perform chi-square test for independence."""
        alpha = 1 - confidence_level
        
        # Create contingency table
        baseline_success = sum(baseline_values)
        baseline_total = len(baseline_values)
        baseline_failure = baseline_total - baseline_success
        
        variant_success = sum(variant_values)
        variant_total = len(variant_values)
        variant_failure = variant_total - variant_success
        
        contingency_table = [
            [baseline_success, baseline_failure],
            [variant_success, variant_failure],
        ]
        
        # Compute chi-square
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        # Compute effect size (Cramér's V)
        cramers_v = self._cramers_v(chi2, min(baseline_total, variant_total))
        
        # Interpret
        is_significant = p_value < alpha
        interpretation = self._interpret_p_value(p_value, alpha)
        
        return StatisticalTest(
            test_name="chi-square",
            metric_name=metric_name,
            baseline_agent=baseline_agent,
            variant_agent=variant_agent,
            baseline_values=baseline_values,
            variant_values=variant_values,
            statistic=chi2,
            p_value=p_value,
            effect_size=cramers_v,
            effect_size_name="Cramér's V",
            is_significant=is_significant,
            confidence_level=confidence_level,
            interpretation=interpretation,
            sample_size_baseline=baseline_total,
            sample_size_variant=variant_total,
        )
    
    def _duration_test(
        self,
        baseline_agent: str,
        variant_agent: str,
        baseline_values: list[float],
        variant_values: list[float],
        confidence_level: float,
    ) -> StatisticalTest:
        """Test duration differences (T-test or Mann-Whitney)."""
        # Check normality with Shapiro-Wilk
        baseline_normal = len(baseline_values) < 3 or stats.shapiro(baseline_values)[1] > 0.05
        variant_normal = len(variant_values) < 3 or stats.shapiro(variant_values)[1] > 0.05
        
        if baseline_normal and variant_normal:
            # Use t-test
            return self._t_test(
                "total_duration_seconds",
                baseline_agent,
                variant_agent,
                baseline_values,
                variant_values,
                confidence_level,
            )
        else:
            # Use Mann-Whitney U test (non-parametric)
            alpha = 1 - confidence_level
            
            u_stat, p_value = stats.mannwhitneyu(baseline_values, variant_values, alternative="two-sided")
            
            # Effect size (rank-biserial correlation)
            r = 1 - (2 * u_stat) / (len(baseline_values) * len(variant_values))
            
            is_significant = p_value < alpha
            interpretation = self._interpret_p_value(p_value, alpha)
            
            return StatisticalTest(
                test_name="mann-whitney",
                metric_name="total_duration_seconds",
                baseline_agent=baseline_agent,
                variant_agent=variant_agent,
                baseline_values=baseline_values,
                variant_values=variant_values,
                statistic=u_stat,
                p_value=p_value,
                effect_size=abs(r),
                effect_size_name="Rank-biserial correlation",
                is_significant=is_significant,
                confidence_level=confidence_level,
                interpretation=interpretation,
                sample_size_baseline=len(baseline_values),
                sample_size_variant=len(variant_values),
            )
    
    def _cohens_d(self, group1: list[float], group2: list[float]) -> float:
        """Compute Cohen's d effect size."""
        if not group1 or not group2:
            return 0.0
        
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        
        # Pooled standard deviation
        var1 = statistics.variance(group1) if len(group1) > 1 else 0
        var2 = statistics.variance(group2) if len(group2) > 1 else 0
        
        n1, n2 = len(group1), len(group2)
        pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        if pooled_std == 0:
            return 0.0
        
        return (mean1 - mean2) / pooled_std
    
    def _cramers_v(self, chi2: float, n: int) -> float:
        """Compute Cramér's V effect size."""
        if n == 0:
            return 0.0
        return math.sqrt(chi2 / n)
    
    def _interpret_p_value(self, p_value: float, alpha: float) -> str:
        """Generate interpretation of p-value."""
        if p_value < 0.001:
            return f"Highly significant (p < 0.001)"
        elif p_value < 0.01:
            return f"Very significant (p < 0.01)"
        elif p_value < alpha:
            return f"Significant (p = {p_value:.4f})"
        else:
            return f"Not significant (p = {p_value:.4f})"
    
    def _assess_power(self, sample_sizes: list[int]) -> str:
        """Assess statistical power based on sample sizes."""
        min_size = min(sample_sizes) if sample_sizes else 0
        
        if min_size < 5:
            return "underpowered"
        elif min_size < 20:
            return "adequate"
        else:
            return "well-powered"
