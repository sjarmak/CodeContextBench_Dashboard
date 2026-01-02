"""
Analysis layer for CodeContextBench observability platform.

Provides:
- Comparator: Baseline vs agent comparison
- IR metrics analysis
- LLM-as-judge evaluation integration
- Failure pattern detection
- Recommendation engine
"""

from .comparator import ExperimentComparator, ComparisonResult
from .ir_analyzer import IRAnalyzer, IRAnalysisResult
from .failure_analyzer import FailureAnalyzer, FailurePattern
from .recommendation_engine import RecommendationEngine, Recommendation
from .statistical_analyzer import StatisticalAnalyzer, StatisticalTest, StatisticalAnalysisResult
from .time_series_analyzer import TimeSeriesAnalyzer, TimeSeriesTrend, TimeSeriesAnalysisResult, TrendDirection

__all__ = [
    "ExperimentComparator",
    "ComparisonResult",
    "IRAnalyzer",
    "IRAnalysisResult",
    "FailureAnalyzer",
    "FailurePattern",
    "RecommendationEngine",
    "Recommendation",
    "StatisticalAnalyzer",
    "StatisticalTest",
    "StatisticalAnalysisResult",
    "TimeSeriesAnalyzer",
    "TimeSeriesTrend",
    "TimeSeriesAnalysisResult",
    "TrendDirection",
]
