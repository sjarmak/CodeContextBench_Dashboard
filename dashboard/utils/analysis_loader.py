"""
Analysis loader for integrating Phase 4 analysis components into dashboard.

Provides a unified interface to load analysis results from the metrics database
and present them in a format optimized for Streamlit visualization.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from src.ingest.database import MetricsDatabase
from src.analysis.comparator import ExperimentComparator, ComparisonResult
from src.analysis.statistical_analyzer import StatisticalAnalyzer, StatisticalAnalysisResult
from src.analysis.time_series_analyzer import TimeSeriesAnalyzer, TimeSeriesAnalysisResult
from src.analysis.cost_analyzer import CostAnalyzer, CostAnalysisResult
from src.analysis.failure_analyzer import FailureAnalyzer, FailureAnalysisResult
from src.analysis.ir_analyzer import IRAnalyzer, IRAnalysisResult
from src.analysis.llm_judge_analyzer import LLMJudgeAnalyzer, LLMJudgeAnalysisResult
from src.analysis.recommendation_engine import RecommendationEngine, RecommendationPlan


logger = logging.getLogger(__name__)


class AnalysisLoaderError(Exception):
    """Base exception for analysis loader errors."""
    pass


class DatabaseNotFoundError(AnalysisLoaderError):
    """Raised when metrics database is not found."""
    pass


class ExperimentNotFoundError(AnalysisLoaderError):
    """Raised when experiment is not found in database."""
    pass


class AnalysisLoader:
    """
    Unified interface for loading Phase 4 analysis results from metrics database.
    
    Handles:
    - Database connection and error handling
    - Analysis component instantiation
    - Result caching for performance
    - Error reporting for missing data
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize loader with path to metrics database.
        
        Args:
            db_path: Path to metrics.db file
            
        Raises:
            DatabaseNotFoundError: If database file doesn't exist
        """
        self.db_path = Path(db_path)
        
        if not self.db_path.exists():
            raise DatabaseNotFoundError(f"Database not found: {db_path}")
        
        self._db = None
        self._cache = {}
    
    @property
    def db(self) -> MetricsDatabase:
        """Lazy-load database connection."""
        if self._db is None:
            self._db = MetricsDatabase(self.db_path)
        return self._db
    
    def is_healthy(self) -> bool:
        """Check if database connection is healthy."""
        try:
            # Simple query to verify connection
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            cursor.fetchone()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def list_experiments(self) -> List[str]:
        """Get list of available experiments in database."""
        try:
            # Query unique experiment IDs from harbor_results
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT experiment_id FROM harbor_results ORDER BY experiment_id")
            experiments = [row[0] for row in cursor.fetchall()]
            conn.close()
            return experiments
        except Exception as e:
            logger.error(f"Failed to list experiments: {e}")
            return []
    
    def list_agents(self, experiment_id: str) -> List[str]:
        """Get list of agents that ran in an experiment."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT agent_name FROM harbor_results WHERE experiment_id = ? ORDER BY agent_name",
                (experiment_id,)
            )
            agents = [row[0] for row in cursor.fetchall()]
            conn.close()
            return agents
        except Exception as e:
            logger.error(f"Failed to list agents for {experiment_id}: {e}")
            return []
    
    def load_comparison(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> ComparisonResult:
        """
        Load experiment comparison results.
        
        Args:
            experiment_id: ID of experiment to analyze
            baseline_agent: Baseline agent for comparison (auto-detected if None)
            
        Returns:
            ComparisonResult with agent metrics and deltas
            
        Raises:
            ExperimentNotFoundError: If experiment not found in database
        """
        cache_key = f"comparison:{experiment_id}:{baseline_agent}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            comparator = ExperimentComparator(self.db)
            result = comparator.compare_experiment(
                experiment_id,
                baseline_agent=baseline_agent,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load comparison for {experiment_id}: {e}")
    
    def load_statistical(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
        confidence_level: float = 0.95,
    ) -> StatisticalAnalysisResult:
        """
        Load statistical significance test results.
        
        Args:
            experiment_id: ID of experiment to analyze
            baseline_agent: Baseline agent for comparison
            confidence_level: Confidence level for tests (default 0.95)
            
        Returns:
            StatisticalAnalysisResult with significance tests
            
        Raises:
            ExperimentNotFoundError: If experiment not found
        """
        cache_key = f"statistical:{experiment_id}:{baseline_agent}:{confidence_level}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = StatisticalAnalyzer(self.db)
            # Convert confidence level to alpha
            alpha = 1 - confidence_level
            result = analyzer.analyze_statistical_significance(
                experiment_id,
                baseline_agent=baseline_agent,
                alpha=alpha,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load statistical analysis for {experiment_id}: {e}")
    
    def load_timeseries(
        self,
        experiment_ids: List[str],
        agent_names: Optional[List[str]] = None,
    ) -> TimeSeriesAnalysisResult:
        """
        Load time-series analysis across experiments.
        
        Args:
            experiment_ids: List of experiment IDs (in chronological order)
            agent_names: Optional list of agents to analyze
            
        Returns:
            TimeSeriesAnalysisResult with trends and anomalies
            
        Raises:
            ExperimentNotFoundError: If experiments not found
        """
        cache_key = f"timeseries:{','.join(experiment_ids)}:{','.join(agent_names or [])}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = TimeSeriesAnalyzer(self.db)
            result = analyzer.analyze_multi_agent_trends(
                experiment_ids,
                agent_names=agent_names,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load time-series analysis: {e}")
    
    def load_cost(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> CostAnalysisResult:
        """
        Load cost analysis results.
        
        Args:
            experiment_id: ID of experiment to analyze
            baseline_agent: Baseline agent for comparison
            
        Returns:
            CostAnalysisResult with cost metrics and regressions
            
        Raises:
            ExperimentNotFoundError: If experiment not found
        """
        cache_key = f"cost:{experiment_id}:{baseline_agent}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = CostAnalyzer(self.db)
            result = analyzer.analyze_costs(
                experiment_id,
                baseline_agent=baseline_agent,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load cost analysis for {experiment_id}: {e}")
    
    def load_failures(
        self,
        experiment_id: str,
        agent_name: Optional[str] = None,
    ) -> FailureAnalysisResult:
        """
        Load failure pattern analysis.
        
        Args:
            experiment_id: ID of experiment to analyze
            agent_name: Optional agent to focus on
            
        Returns:
            FailureAnalysisResult with patterns and categories
            
        Raises:
            ExperimentNotFoundError: If experiment not found
        """
        cache_key = f"failures:{experiment_id}:{agent_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = FailureAnalyzer(self.db)
            result = analyzer.analyze_failures(
                experiment_id,
                agent_name=agent_name,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load failure analysis for {experiment_id}: {e}")
    
    def load_ir_analysis(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> IRAnalysisResult:
        """
        Load information retrieval metrics analysis.
        
        Args:
            experiment_id: ID of experiment to analyze
            baseline_agent: Baseline agent for comparison
            
        Returns:
            IRAnalysisResult with retrieval metrics
            
        Raises:
            ExperimentNotFoundError: If experiment not found
        """
        cache_key = f"ir:{experiment_id}:{baseline_agent}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = IRAnalyzer(self.db)
            result = analyzer.analyze_experiment(
                experiment_id,
                baseline_agent=baseline_agent,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            # IR analysis may not be available for all experiments
            logger.warning(f"IR analysis not available for {experiment_id}: {e}")
            return None
    
    def load_judge_results(
        self,
        experiment_id: str,
        baseline_agent: Optional[str] = None,
    ) -> LLMJudgeAnalysisResult:
        """
        Load LLM judge analysis results.
        
        Args:
            experiment_id: ID of experiment to analyze
            baseline_agent: Baseline agent for comparison
            
        Returns:
            LLMJudgeAnalysisResult with judge scores and comparisons
            
        Raises:
            ExperimentNotFoundError: If judge results not available
        """
        cache_key = f"judge:{experiment_id}:{baseline_agent}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            analyzer = LLMJudgeAnalyzer(self.db)
            result = analyzer.analyze_judge_scores(
                experiment_id,
                baseline_agent=baseline_agent,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            # Judge results may not be available for all experiments
            logger.warning(f"Judge results not available for {experiment_id}: {e}")
            return None
    
    def load_recommendations(
        self,
        experiment_id: str,
        agent_name: str,
    ) -> RecommendationPlan:
        """
        Load improvement recommendations for an agent.
        
        Args:
            experiment_id: ID of experiment
            agent_name: Agent to analyze
            
        Returns:
            RecommendationPlan with prioritized recommendations
            
        Raises:
            ExperimentNotFoundError: If data unavailable
        """
        cache_key = f"recommendations:{experiment_id}:{agent_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            engine = RecommendationEngine()
            
            # Load prerequisite analyses
            comparison = self.load_comparison(experiment_id)
            failures = self.load_failures(experiment_id, agent_name=agent_name)
            
            # Try to load IR analysis (may not be available)
            ir_analysis = None
            try:
                ir_analysis = self.load_ir_analysis(experiment_id)
            except:
                pass
            
            # Generate plan
            plan = engine.generate_plan(
                experiment_id,
                agent_name,
                comparison_result=comparison,
                failure_analysis=failures,
                ir_analysis=ir_analysis,
            )
            
            self._cache[cache_key] = plan
            return plan
        except Exception as e:
            raise ExperimentNotFoundError(f"Failed to load recommendations for {agent_name}: {e}")
    
    def clear_cache(self):
        """Clear result cache to force fresh loads."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        try:
            return self.db.get_stats()
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
