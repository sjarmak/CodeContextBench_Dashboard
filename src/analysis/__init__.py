"""
Analysis layer for CodeContextBench observability platform.

Provides:
- Comparator: Baseline vs agent comparison
- IR metrics analysis
- Statistical significance testing
- Cost analysis and efficiency metrics
- Failure pattern detection
- Time-series trend analysis
- Recommendation engine
"""

from .comparator import ExperimentComparator, ComparisonResult
from .ir_analyzer import IRAnalyzer, IRAnalysisResult
from .statistical_analyzer import StatisticalAnalyzer, StatisticalAnalysisResult
from .cost_analyzer import CostAnalyzer, CostAnalysisResult
from .failure_analyzer import FailureAnalyzer, FailurePattern
from .recommendation_engine import RecommendationEngine, Recommendation
from .time_series_analyzer import TimeSeriesAnalyzer, TimeSeriesAnalysisResult

__all__ = [
    "ExperimentComparator",
    "ComparisonResult",
    "IRAnalyzer",
    "IRAnalysisResult",
    "StatisticalAnalyzer",
    "StatisticalAnalysisResult",
    "CostAnalyzer",
    "CostAnalysisResult",
    "FailureAnalyzer",
    "FailurePattern",
    "RecommendationEngine",
    "Recommendation",
    "TimeSeriesAnalyzer",
    "TimeSeriesAnalysisResult",
]
