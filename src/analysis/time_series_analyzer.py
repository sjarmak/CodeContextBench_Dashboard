"""
Time-series analysis for tracking experiment metrics over iterations.

Provides trend detection, improvement tracking, and anomaly detection
across multiple experiment runs with metric history.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from src.ingest.database import MetricsDatabase


class TrendDirection(Enum):
    """Direction of a metric trend."""
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass
class TimeSeriesMetric:
    """A single metric measurement at a point in time."""
    timestamp: datetime
    agent_name: str
    metric_name: str  # "pass_rate", "avg_duration", etc.
    value: float
    experiment_id: str
    sample_size: int = 1


@dataclass
class TimeSeriesTrend:
    """Trend analysis for a metric across time."""
    metric_name: str
    agent_name: str
    
    # Trend detection
    direction: TrendDirection
    slope: float  # Change per time unit (positive = improvement for pass_rate, negative for duration)
    confidence: float  # 0.0-1.0, confidence in trend detection
    
    # Statistical properties
    data_points: int
    first_value: float
    last_value: float
    total_change: float
    percent_change: float
    
    # Anomaly detection
    has_anomalies: bool = False
    anomaly_indices: list[int] = field(default_factory=list)
    anomaly_descriptions: list[str] = field(default_factory=list)
    
    # Interpretation
    interpretation: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "agent_name": self.agent_name,
            "trend": {
                "direction": self.direction.value,
                "slope": self.slope,
                "confidence": self.confidence,
                "interpretation": self.interpretation,
            },
            "statistics": {
                "data_points": self.data_points,
                "first_value": self.first_value,
                "last_value": self.last_value,
                "total_change": self.total_change,
                "percent_change": self.percent_change,
            },
            "anomalies": {
                "detected": self.has_anomalies,
                "count": len(self.anomaly_indices),
                "descriptions": self.anomaly_descriptions,
            },
        }


@dataclass
class TimeSeriesAnalysisResult:
    """Complete time-series analysis result."""
    experiment_ids: list[str]
    agent_names: list[str]
    
    # Trend results organized by metric and agent
    trends: dict[str, dict[str, TimeSeriesTrend]] = field(default_factory=dict)  # metric -> agent -> trend
    
    # Summary
    best_improving_metric: Optional[TimeSeriesTrend] = None
    worst_degrading_metric: Optional[TimeSeriesTrend] = None
    most_stable_metric: Optional[TimeSeriesTrend] = None
    
    # Anomaly summary
    total_anomalies: int = 0
    agents_with_anomalies: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        trends_dict = {}
        for metric, agent_trends in self.trends.items():
            trends_dict[metric] = {
                agent: trend.to_dict() for agent, trend in agent_trends.items()
            }
        
        return {
            "experiment_ids": self.experiment_ids,
            "agent_names": self.agent_names,
            "summary": {
                "best_improving": self.best_improving_metric.to_dict() if self.best_improving_metric else None,
                "worst_degrading": self.worst_degrading_metric.to_dict() if self.worst_degrading_metric else None,
                "most_stable": self.most_stable_metric.to_dict() if self.most_stable_metric else None,
                "total_anomalies": self.total_anomalies,
                "agents_with_anomalies": self.agents_with_anomalies,
            },
            "trends": trends_dict,
        }


class TimeSeriesAnalyzer:
    """Analyze metric trends over time across experiments."""
    
    def __init__(self, db: MetricsDatabase):
        """
        Initialize time-series analyzer.
        
        Args:
            db: MetricsDatabase instance
        """
        self.db = db
    
    def analyze_agent_trends(
        self,
        experiment_ids: list[str],
        agent_name: str,
        metrics: Optional[list[str]] = None,
    ) -> TimeSeriesAnalysisResult:
        """
        Analyze trends for a single agent across experiments.
        
        Args:
            experiment_ids: List of experiment IDs in chronological order
            agent_name: Name of agent to analyze
            metrics: Metrics to analyze (defaults to all)
            
        Returns:
            TimeSeriesAnalysisResult with trends and anomalies
        """
        if not experiment_ids:
            raise ValueError("Must provide at least one experiment")
        
        # Default metrics to track
        if not metrics:
            metrics = ["pass_rate", "avg_duration_seconds", "avg_mcp_calls", "avg_deep_search_calls"]
        
        # Collect time series data
        time_series_data = {}  # metric -> list[TimeSeriesMetric]
        
        for metric in metrics:
            time_series_data[metric] = []
            
            for i, exp_id in enumerate(experiment_ids):
                results = self.db.get_experiment_results(exp_id)
                agent_results = [r for r in results if r["agent_name"] == agent_name]
                
                if not agent_results:
                    continue
                
                # Compute metric value
                metric_value = self._compute_metric(metric, agent_results)
                
                if metric_value is not None:
                    # Use ordinal timestamp: index represents iteration order
                    timestamp = datetime(2025, 1, 1 + i)
                    ts_metric = TimeSeriesMetric(
                        timestamp=timestamp,
                        agent_name=agent_name,
                        metric_name=metric,
                        value=metric_value,
                        experiment_id=exp_id,
                        sample_size=len(agent_results),
                    )
                    time_series_data[metric].append(ts_metric)
        
        # Analyze trends
        result = TimeSeriesAnalysisResult(
            experiment_ids=experiment_ids,
            agent_names=[agent_name],
        )
        
        all_trends = []
        
        for metric, data_points in time_series_data.items():
            if len(data_points) < 2:
                continue  # Need at least 2 points for trend
            
            trend = self._analyze_trend(metric, agent_name, data_points)
            
            if metric not in result.trends:
                result.trends[metric] = {}
            result.trends[metric][agent_name] = trend
            all_trends.append(trend)
            
            # Update summary
            if trend.has_anomalies:
                result.total_anomalies += len(trend.anomaly_indices)
                if agent_name not in result.agents_with_anomalies:
                    result.agents_with_anomalies.append(agent_name)
        
        # Find best/worst trends
        if all_trends:
            improving_trends = [t for t in all_trends if t.direction == TrendDirection.IMPROVING]
            degrading_trends = [t for t in all_trends if t.direction == TrendDirection.DEGRADING]
            stable_trends = [t for t in all_trends if t.direction == TrendDirection.STABLE]
            
            if improving_trends:
                result.best_improving_metric = max(improving_trends, key=lambda t: t.slope)
            if degrading_trends:
                result.worst_degrading_metric = min(degrading_trends, key=lambda t: t.slope)
            if stable_trends:
                result.most_stable_metric = min(stable_trends, key=lambda t: abs(t.slope))
        
        return result
    
    def analyze_multi_agent_trends(
        self,
        experiment_ids: list[str],
        agent_names: Optional[list[str]] = None,
    ) -> TimeSeriesAnalysisResult:
        """
        Analyze trends for multiple agents across experiments.
        
        Args:
            experiment_ids: List of experiment IDs in chronological order
            agent_names: Agents to analyze (defaults to all found)
            
        Returns:
            TimeSeriesAnalysisResult with trends for all agents
        """
        if not experiment_ids:
            raise ValueError("Must provide at least one experiment")
        
        # Discover agents if not provided
        if not agent_names:
            agent_names_set = set()
            for exp_id in experiment_ids:
                results = self.db.get_experiment_results(exp_id)
                for r in results:
                    agent_names_set.add(r["agent_name"] or "unknown")
            agent_names = sorted(list(agent_names_set))
        
        # Analyze each agent
        result = TimeSeriesAnalysisResult(
            experiment_ids=experiment_ids,
            agent_names=agent_names,
        )
        
        all_trends = []
        
        for agent_name in agent_names:
            agent_result = self.analyze_agent_trends(experiment_ids, agent_name)
            
            # Merge trends
            for metric, agent_trends in agent_result.trends.items():
                if metric not in result.trends:
                    result.trends[metric] = {}
                result.trends[metric].update(agent_trends)
                all_trends.extend(agent_trends.values())
            
            result.total_anomalies += agent_result.total_anomalies
            result.agents_with_anomalies.extend(agent_result.agents_with_anomalies)
        
        # Update summary
        if all_trends:
            improving_trends = [t for t in all_trends if t.direction == TrendDirection.IMPROVING]
            degrading_trends = [t for t in all_trends if t.direction == TrendDirection.DEGRADING]
            stable_trends = [t for t in all_trends if t.direction == TrendDirection.STABLE]
            
            if improving_trends:
                result.best_improving_metric = max(improving_trends, key=lambda t: t.slope)
            if degrading_trends:
                result.worst_degrading_metric = min(degrading_trends, key=lambda t: t.slope)
            if stable_trends:
                result.most_stable_metric = min(stable_trends, key=lambda t: abs(t.slope))
        
        return result
    
    def _compute_metric(self, metric_name: str, results: list[dict]) -> Optional[float]:
        """Compute a metric value from results."""
        if not results:
            return None
        
        if metric_name == "pass_rate":
            passes = sum(1 for r in results if r["passed"])
            return passes / len(results) if results else 0
        
        elif metric_name == "avg_duration_seconds":
            durations = [r["total_duration_seconds"] for r in results if r["total_duration_seconds"]]
            return statistics.mean(durations) if durations else None
        
        elif metric_name == "avg_mcp_calls":
            # From tool_usage table
            total_calls = sum(r.get("mcp_call_count", 0) for r in results)
            return total_calls / len(results) if results else 0
        
        elif metric_name == "avg_deep_search_calls":
            # From tool_usage table
            total_calls = sum(r.get("deep_search_call_count", 0) for r in results)
            return total_calls / len(results) if results else 0
        
        return None
    
    def _analyze_trend(
        self,
        metric_name: str,
        agent_name: str,
        data_points: list[TimeSeriesMetric],
    ) -> TimeSeriesTrend:
        """Analyze a trend from time series data points."""
        if len(data_points) < 2:
            raise ValueError("Need at least 2 data points for trend analysis")
        
        values = [dp.value for dp in data_points]
        n = len(values)
        
        # Compute simple linear regression slope
        x = list(range(n))
        slope = self._compute_slope(x, values)
        
        # Determine direction
        is_improvement = metric_name in ["pass_rate", "avg_mcp_calls", "avg_deep_search_calls"]
        is_duration = metric_name in ["avg_duration_seconds"]
        
        if is_improvement:
            if slope > 0.01:
                direction = TrendDirection.IMPROVING
            elif slope < -0.01:
                direction = TrendDirection.DEGRADING
            else:
                direction = TrendDirection.STABLE
        elif is_duration:
            if slope < -0.5:  # Duration improving = decreasing
                direction = TrendDirection.IMPROVING
            elif slope > 0.5:
                direction = TrendDirection.DEGRADING
            else:
                direction = TrendDirection.STABLE
        else:
            direction = TrendDirection.UNKNOWN
        
        # Compute confidence (based on R-squared)
        r_squared = self._compute_r_squared(x, values, slope)
        confidence = max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]
        
        # Detect anomalies
        anomalies = self._detect_anomalies(values)
        
        # Interpretation
        first_val = values[0]
        last_val = values[-1]
        total_change = last_val - first_val
        percent_change = (total_change / first_val * 100) if first_val != 0 else 0
        
        interpretation = self._interpret_trend(
            metric_name, direction, slope, confidence, first_val, last_val, percent_change
        )
        
        return TimeSeriesTrend(
            metric_name=metric_name,
            agent_name=agent_name,
            direction=direction,
            slope=slope,
            confidence=confidence,
            data_points=n,
            first_value=first_val,
            last_value=last_val,
            total_change=total_change,
            percent_change=percent_change,
            has_anomalies=len(anomalies) > 0,
            anomaly_indices=anomalies,
            anomaly_descriptions=[f"Point {i}: {values[i]:.3f}" for i in anomalies],
            interpretation=interpretation,
        )
    
    def _compute_slope(self, x: list[float], y: list[float]) -> float:
        """Compute linear regression slope."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        return numerator / denominator if denominator != 0 else 0.0
    
    def _compute_r_squared(self, x: list[float], y: list[float], slope: float) -> float:
        """Compute R-squared value for linear regression."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        # Compute intercept
        intercept = y_mean - slope * x_mean
        
        # Sum of squared residuals
        ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
        
        # Total sum of squares
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        
        if ss_tot == 0:
            return 0.0
        
        return 1 - (ss_res / ss_tot)
    
    def _detect_anomalies(self, values: list[float], threshold: float = 2.0) -> list[int]:
        """Detect anomalies using z-score method."""
        if len(values) < 3:
            return []
        
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            
            if stdev == 0:
                return []
            
            anomalies = []
            for i, val in enumerate(values):
                z_score = abs((val - mean) / stdev)
                if z_score > threshold:
                    anomalies.append(i)
            
            return anomalies
        except:
            return []
    
    def _interpret_trend(
        self,
        metric_name: str,
        direction: TrendDirection,
        slope: float,
        confidence: float,
        first_val: float,
        last_val: float,
        percent_change: float,
    ) -> str:
        """Generate human-readable interpretation of trend."""
        conf_str = f"{confidence:.0%}" if confidence > 0 else "low"
        
        if direction == TrendDirection.IMPROVING:
            return f"{metric_name} improving ({conf_str} confidence): {percent_change:+.1f}% change"
        elif direction == TrendDirection.DEGRADING:
            return f"{metric_name} degrading ({conf_str} confidence): {percent_change:+.1f}% change"
        elif direction == TrendDirection.STABLE:
            return f"{metric_name} stable ({conf_str} confidence): {percent_change:+.1f}% change"
        else:
            return f"{metric_name} trend unknown"
