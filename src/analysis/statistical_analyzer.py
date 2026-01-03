"""
Statistical analysis for significance testing and effect size calculation.

Provides:
- P-value calculations for pass rates (binomial test) and duration (t-test)
- Effect size computation (Cohen's d for continuous, Cramér's V for categorical)
- Power analysis (post-hoc power assessment)
- Interpretation of statistical results
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from scipy import stats as scipy_stats
import math

from src.ingest.database import MetricsDatabase


@dataclass
class EffectSize:
    """Effect size measurement."""
    cohens_d: Optional[float] = None  # For continuous metrics
    cramers_v: Optional[float] = None  # For categorical metrics
    interpretation: str = "negligible"  # negligible, small, medium, large


@dataclass
class SignificanceTest:
    """Results of a single significance test."""
    metric_name: str
    baseline_mean: float
    variant_mean: float
    baseline_n: int
    variant_n: int
    
    # Test results
    p_value: float = 1.0
    t_statistic: Optional[float] = None
    is_significant: bool = False  # p < 0.05
    
    # Effect size
    effect_size: EffectSize = field(default_factory=EffectSize)
    
    # Power analysis
    observed_power: float = 0.0
    
    # Interpretation
    interpretation: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metric": self.metric_name,
            "baseline_mean": self.baseline_mean,
            "variant_mean": self.variant_mean,
            "sample_sizes": {
                "baseline": self.baseline_n,
                "variant": self.variant_n,
            },
            "test_results": {
                "p_value": self.p_value,
                "t_statistic": self.t_statistic,
                "is_significant": self.is_significant,
            },
            "effect_size": {
                "cohens_d": self.effect_size.cohens_d,
                "cramers_v": self.effect_size.cramers_v,
                "interpretation": self.effect_size.interpretation,
            },
            "power_analysis": {
                "observed_power": self.observed_power,
            },
            "interpretation": self.interpretation,
        }


@dataclass
class StatisticalAnalysisResult:
    """Results from statistical significance analysis."""
    experiment_id: str
    baseline_agent: str
    variant_agents: list[str] = field(default_factory=list)
    
    # Test results organized by metric
    tests: dict[str, dict[str, SignificanceTest]] = field(default_factory=dict)
    # Key format: "metric::variant_agent" -> SignificanceTest
    
    # Summary statistics
    total_tests: int = 0
    significant_tests: int = 0
    significance_rate: float = 0.0
    
    # Key findings
    most_significant_finding: Optional[SignificanceTest] = None
    largest_effect_size: Optional[SignificanceTest] = None
    
    # Metadata
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        tests_dict = {}
        for variant, variant_tests in self.tests.items():
            tests_dict[variant] = {
                metric: test.to_dict()
                for metric, test in variant_tests.items()
            }
        
        return {
            "experiment_id": self.experiment_id,
            "baseline_agent": self.baseline_agent,
            "variant_agents": self.variant_agents,
            "tests": tests_dict,
            "summary": {
                "total_tests": self.total_tests,
                "significant_tests": self.significant_tests,
                "significance_rate": self.significance_rate,
            },
            "key_findings": {
                "most_significant": self.most_significant_finding.to_dict() if self.most_significant_finding else None,
                "largest_effect_size": self.largest_effect_size.to_dict() if self.largest_effect_size else None,
            },
            "computed_at": self.computed_at,
        }


class StatisticalAnalyzer:
    """Perform statistical significance testing and effect size analysis."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize statistical analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_statistical_significance(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
        alpha: float = 0.05,
    ) -> StatisticalAnalysisResult:
        """
        Perform statistical significance testing.
        
        Args:
            experiment_id: Experiment ID to analyze
            baseline_agent: Baseline agent (auto-detected if None)
            alpha: Significance level (default 0.05)
            
        Returns:
            StatisticalAnalysisResult with test results
        """
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
        analysis_result = StatisticalAnalysisResult(
            experiment_id=experiment_id,
            baseline_agent=baseline_agent,
            variant_agents=[a for a in agents_data.keys() if a != baseline_agent],
        )
        
        baseline_results = agents_data[baseline_agent]
        
        # Test each variant against baseline
        for variant_agent in analysis_result.variant_agents:
            variant_results = agents_data[variant_agent]
            
            # Test key metrics
            test_results = {}
            
            # 1. Pass rate test (binomial)
            pass_rate_test = self._test_pass_rate(
                baseline_results, variant_results, alpha
            )
            test_results["pass_rate"] = pass_rate_test
            
            # 2. Duration test (t-test)
            duration_test = self._test_duration(
                baseline_results, variant_results, alpha
            )
            test_results["avg_duration_seconds"] = duration_test
            
            # 3. MCP calls test
            mcp_test = self._test_tool_calls(
                baseline_results, variant_results, "mcp_calls", alpha
            )
            if mcp_test:
                test_results["avg_mcp_calls"] = mcp_test
            
            # Store results
            analysis_result.tests[variant_agent] = test_results
            analysis_result.total_tests += len(test_results)
            
            # Count significant tests
            for test in test_results.values():
                if test.is_significant:
                    analysis_result.significant_tests += 1
        
        # Update summary
        if analysis_result.total_tests > 0:
            analysis_result.significance_rate = (
                analysis_result.significant_tests / analysis_result.total_tests
            )
        
        # Find most significant and largest effect size
        all_tests = []
        for variant_tests in analysis_result.tests.values():
            all_tests.extend(variant_tests.values())
        
        if all_tests:
            # Most significant = lowest p-value
            analysis_result.most_significant_finding = min(
                all_tests, key=lambda t: t.p_value
            )
            
            # Largest effect = max Cohen's d or Cramér's V
            def max_effect(test):
                d = test.effect_size.cohens_d or 0
                v = test.effect_size.cramers_v or 0
                return max(abs(d), abs(v))
            
            analysis_result.largest_effect_size = max(
                all_tests, key=max_effect
            )
        
        return analysis_result
    
    def _test_pass_rate(
        self,
        baseline_results: list[dict],
        variant_results: list[dict],
        alpha: float,
    ) -> SignificanceTest:
        """Test pass rate difference using binomial test."""
        baseline_passed = sum(1 for r in baseline_results if r["passed"])
        variant_passed = sum(1 for r in variant_results if r["passed"])
        
        baseline_n = len(baseline_results)
        variant_n = len(variant_results)
        
        baseline_rate = baseline_passed / baseline_n if baseline_n > 0 else 0
        variant_rate = variant_passed / variant_n if variant_n > 0 else 0
        
        # Use Fisher's exact test for 2x2 contingency table
        # [[baseline_passed, baseline_failed], [variant_passed, variant_failed]]
        baseline_failed = baseline_n - baseline_passed
        variant_failed = variant_n - variant_passed
        
        try:
            if baseline_n > 0 and variant_n > 0:
                # Contingency table
                table = [[baseline_passed, baseline_failed], 
                        [variant_passed, variant_failed]]
                _, p_value = scipy_stats.fisher_exact(table)
            else:
                p_value = 1.0
        except:
            p_value = 1.0
        
        # Effect size: Cohen's h (for proportions)
        cohens_h = self._cohens_h(baseline_rate, variant_rate)
        
        # Interpret effect size
        effect_interpretation = "negligible"
        if abs(cohens_h) > 0.2:
            effect_interpretation = "small"
        if abs(cohens_h) > 0.5:
            effect_interpretation = "medium"
        if abs(cohens_h) > 0.8:
            effect_interpretation = "large"
        
        # Power analysis (post-hoc)
        power = self._compute_power_proportion(
            baseline_n, variant_n, baseline_rate, variant_rate
        )
        
        interpretation = f"Pass rate difference: {baseline_rate:.1%} vs {variant_rate:.1%}"
        if p_value < alpha:
            interpretation += f" (significant, p={p_value:.4f})"
        else:
            interpretation += f" (not significant, p={p_value:.4f})"
        
        return SignificanceTest(
            metric_name="pass_rate",
            baseline_mean=baseline_rate,
            variant_mean=variant_rate,
            baseline_n=baseline_n,
            variant_n=variant_n,
            p_value=p_value,
            is_significant=p_value < alpha,
            effect_size=EffectSize(
                cohens_d=cohens_h,
                interpretation=effect_interpretation
            ),
            observed_power=power,
            interpretation=interpretation,
        )
    
    def _test_duration(
        self,
        baseline_results: list[dict],
        variant_results: list[dict],
        alpha: float,
    ) -> SignificanceTest:
        """Test duration difference using t-test."""
        baseline_durations = [
            r["total_duration_seconds"] for r in baseline_results
            if r["total_duration_seconds"]
        ]
        variant_durations = [
            r["total_duration_seconds"] for r in variant_results
            if r["total_duration_seconds"]
        ]
        
        if not baseline_durations or not variant_durations:
            return SignificanceTest(
                metric_name="avg_duration_seconds",
                baseline_mean=0,
                variant_mean=0,
                baseline_n=len(baseline_durations),
                variant_n=len(variant_durations),
                p_value=1.0,
                interpretation="Insufficient data for duration test"
            )
        
        baseline_mean = statistics.mean(baseline_durations)
        variant_mean = statistics.mean(variant_durations)
        baseline_n = len(baseline_durations)
        variant_n = len(variant_durations)
        
        # Independent samples t-test
        try:
            t_stat, p_value = scipy_stats.ttest_ind(
                baseline_durations, variant_durations
            )
        except:
            p_value = 1.0
            t_stat = None
        
        # Effect size: Cohen's d
        cohens_d = self._cohens_d(baseline_durations, variant_durations)
        
        # Interpret effect size
        effect_interpretation = "negligible"
        if abs(cohens_d) > 0.2:
            effect_interpretation = "small"
        if abs(cohens_d) > 0.5:
            effect_interpretation = "medium"
        if abs(cohens_d) > 0.8:
            effect_interpretation = "large"
        
        # Power analysis
        power = self._compute_power_ttest(
            baseline_durations, variant_durations
        )
        
        interpretation = f"Duration: {baseline_mean:.1f}s vs {variant_mean:.1f}s"
        if p_value < alpha:
            direction = "faster" if variant_mean < baseline_mean else "slower"
            interpretation += f" ({direction}, p={p_value:.4f})"
        else:
            interpretation += f" (not significantly different, p={p_value:.4f})"
        
        return SignificanceTest(
            metric_name="avg_duration_seconds",
            baseline_mean=baseline_mean,
            variant_mean=variant_mean,
            baseline_n=baseline_n,
            variant_n=variant_n,
            p_value=p_value,
            t_statistic=t_stat,
            is_significant=p_value < alpha,
            effect_size=EffectSize(
                cohens_d=cohens_d,
                interpretation=effect_interpretation
            ),
            observed_power=power,
            interpretation=interpretation,
        )
    
    def _test_tool_calls(
        self,
        baseline_results: list[dict],
        variant_results: list[dict],
        call_type: str,
        alpha: float,
    ) -> Optional[SignificanceTest]:
        """Test tool call count differences."""
        # Get tool usage data from database
        baseline_calls = self._get_tool_calls(
            baseline_results, call_type
        )
        variant_calls = self._get_tool_calls(
            variant_results, call_type
        )
        
        if not baseline_calls or not variant_calls:
            return None
        
        baseline_mean = statistics.mean(baseline_calls)
        variant_mean = statistics.mean(variant_calls)
        baseline_n = len(baseline_calls)
        variant_n = len(variant_calls)
        
        # T-test
        try:
            t_stat, p_value = scipy_stats.ttest_ind(
                baseline_calls, variant_calls
            )
        except:
            p_value = 1.0
            t_stat = None
        
        # Effect size
        cohens_d = self._cohens_d(baseline_calls, variant_calls)
        
        effect_interpretation = "negligible"
        if abs(cohens_d) > 0.2:
            effect_interpretation = "small"
        if abs(cohens_d) > 0.5:
            effect_interpretation = "medium"
        if abs(cohens_d) > 0.8:
            effect_interpretation = "large"
        
        power = self._compute_power_ttest(baseline_calls, variant_calls)
        
        return SignificanceTest(
            metric_name=f"avg_{call_type}",
            baseline_mean=baseline_mean,
            variant_mean=variant_mean,
            baseline_n=baseline_n,
            variant_n=variant_n,
            p_value=p_value,
            t_statistic=t_stat,
            is_significant=p_value < alpha,
            effect_size=EffectSize(
                cohens_d=cohens_d,
                interpretation=effect_interpretation
            ),
            observed_power=power,
        )
    
    def _get_tool_calls(
        self,
        results: list[dict],
        call_type: str,
    ) -> list[float]:
        """Extract tool call counts from results."""
        calls = []
        
        # Get job IDs and experiment ID for database lookup
        for result in results:
            job_id = result.get("job_id")
            exp_id = result.get("experiment_id")
            task_id = result.get("task_id")
            
            if job_id and exp_id and task_id:
                with self.db._connect() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        SELECT {call_type} FROM tool_usage
                        WHERE task_id = ? AND experiment_id = ? AND job_id = ?
                    """, (task_id, exp_id, job_id))
                    
                    row = cursor.fetchone()
                    if row and row[0] is not None:
                        calls.append(float(row[0]))
        
        return calls
    
    def _cohens_d(
        self,
        group1: list[float],
        group2: list[float],
    ) -> float:
        """Compute Cohen's d effect size."""
        if len(group1) < 2 or len(group2) < 2:
            return 0.0
        
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        
        # Pooled standard deviation
        var1 = statistics.variance(group1)
        var2 = statistics.variance(group2)
        
        n1 = len(group1)
        n2 = len(group2)
        
        pooled_std = math.sqrt(
            ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        )
        
        if pooled_std == 0:
            return 0.0
        
        return (mean1 - mean2) / pooled_std
    
    def _cohens_h(self, p1: float, p2: float) -> float:
        """Compute Cohen's h for proportions."""
        # Cohen's h = 2 * arcsin(sqrt(p1)) - 2 * arcsin(sqrt(p2))
        return 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))
    
    def _compute_power_proportion(
        self,
        n1: int,
        n2: int,
        p1: float,
        p2: float,
    ) -> float:
        """Estimate post-hoc power for proportion test."""
        if n1 < 2 or n2 < 2:
            return 0.0
        
        # Simplified power estimate based on sample size and effect
        effect = abs(p1 - p2)
        pooled_p = (n1 * p1 + n2 * p2) / (n1 + n2)
        se = math.sqrt(pooled_p * (1 - pooled_p) * (1/n1 + 1/n2))
        
        if se == 0:
            return 0.0
        
        # Standard normal for two-tailed test
        z_critical = 1.96  # alpha = 0.05
        z_effect = effect / se
        
        # Approximate power using normal distribution
        try:
            power = scipy_stats.norm.sf(z_critical - z_effect)
            return max(0.0, min(1.0, power))
        except:
            return 0.0
    
    def _compute_power_ttest(
        self,
        group1: list[float],
        group2: list[float],
    ) -> float:
        """Estimate post-hoc power for t-test."""
        if len(group1) < 2 or len(group2) < 2:
            return 0.0
        
        # Simplified power estimate
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        
        var1 = statistics.variance(group1)
        var2 = statistics.variance(group2)
        
        n1 = len(group1)
        n2 = len(group2)
        
        # Effect size
        cohens_d = self._cohens_d(group1, group2)
        
        # Degrees of freedom
        df = n1 + n2 - 2
        
        if df < 1:
            return 0.0
        
        # Non-centrality parameter
        ncp = cohens_d * math.sqrt(n1 * n2 / (n1 + n2))
        
        # Critical t-value for alpha = 0.05, two-tailed
        t_crit = scipy_stats.t.ppf(0.975, df)
        
        try:
            # Power = P(T > t_crit | H1 true)
            power = scipy_stats.nct.sf(t_crit, df, ncp)
            return max(0.0, min(1.0, power))
        except:
            return 0.0
