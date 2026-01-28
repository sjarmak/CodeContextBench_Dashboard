"""
Tests for LLM Judge analysis layer.
"""

import pytest
from pathlib import Path
import tempfile
import json

from src.ingest.database import MetricsDatabase
from src.analysis.llm_judge_analyzer import (
    LLMJudgeAnalyzer,
    LLMJudgeAnalysisResult,
    AgentJudgeMetrics,
    JudgeScores,
    JudgeDelta,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    db = MetricsDatabase(db_path)
    yield db
    
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def db_with_harbor_data(temp_db):
    """Populate database with Harbor results."""
    # Insert sample harbor results
    with temp_db._connect() as conn:
        cursor = conn.cursor()
        
        # Baseline agent results
        for i in range(5):
            cursor.execute("""
                INSERT INTO harbor_results
                (task_id, experiment_id, job_id, agent_name, model_name, passed, 
                 total_duration_seconds, reward_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"task_{i}", "exp_001", "job_baseline_{i}", "baseline", "claude-haiku",
                i < 4, 100.0 + i * 10, 0.8 if i < 4 else 0.0
            ))
        
        # Variant agent results
        for i in range(5):
            cursor.execute("""
                INSERT INTO harbor_results
                (task_id, experiment_id, job_id, agent_name, model_name, passed, 
                 total_duration_seconds, reward_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"task_{i}", "exp_001", "job_variant_{i}", "variant", "claude-haiku",
                i < 3, 120.0 + i * 10, 0.7 if i < 3 else 0.0
            ))
        
        conn.commit()
    
    return temp_db


@pytest.fixture
def db_with_judge_data(db_with_harbor_data):
    """Populate database with judge results."""
    db = db_with_harbor_data
    
    # Add judge results for baseline
    for i in range(5):
        judge_result = {
            "code_quality": 0.85 if i < 4 else 0.3,
            "correctness": 0.90 if i < 4 else 0.2,
            "completeness": 0.80 if i < 4 else 0.25,
            "quality": 0.85 if i < 4 else 0.3,
            "efficiency": 0.75 if i < 4 else 0.4,
            "overall_score": 0.83 if i < 4 else 0.29,
            "code_quality_reasoning": "Good code structure",
            "correctness_reasoning": "Correct logic",
            "completeness_reasoning": "All features implemented",
            "quality_reasoning": "Clean code",
            "efficiency_reasoning": "Minimal changes",
            "overall_reasoning": "Good solution" if i < 4 else "Failed solution",
            "judge_model": "claude-haiku",
            "tokens_used": 500,
        }
        db.store_judge_result(
            f"task_{i}",
            judge_result,
            experiment_id="exp_001",
            job_id=f"job_baseline_{i}",
            agent_name="baseline",
        )
    
    # Add judge results for variant
    for i in range(5):
        judge_result = {
            "code_quality": 0.75 if i < 3 else 0.25,
            "correctness": 0.80 if i < 3 else 0.15,
            "completeness": 0.70 if i < 3 else 0.20,
            "quality": 0.75 if i < 3 else 0.25,
            "efficiency": 0.80 if i < 3 else 0.35,
            "overall_score": 0.76 if i < 3 else 0.24,
            "code_quality_reasoning": "Decent code",
            "correctness_reasoning": "Mostly correct",
            "completeness_reasoning": "Some features missing",
            "quality_reasoning": "Acceptable quality",
            "efficiency_reasoning": "Some redundancy",
            "overall_reasoning": "Acceptable solution" if i < 3 else "Failed",
            "judge_model": "claude-haiku",
            "tokens_used": 480,
        }
        db.store_judge_result(
            f"task_{i}",
            judge_result,
            experiment_id="exp_001",
            job_id=f"job_variant_{i}",
            agent_name="variant",
        )
    
    return db


class TestJudgeScores:
    """Test JudgeScores dataclass."""
    
    def test_judge_scores_creation(self):
        """Test creating judge scores."""
        scores = JudgeScores(
            task_id="task_1",
            agent_name="baseline",
            code_quality=0.85,
            correctness=0.90,
            completeness=0.80,
            quality=0.85,
            efficiency=0.75,
            overall_score=0.83,
        )
        
        assert scores.task_id == "task_1"
        assert scores.agent_name == "baseline"
        assert scores.overall_score == 0.83
    
    def test_judge_scores_to_dict(self):
        """Test serialization to dict."""
        scores = JudgeScores(
            task_id="task_1",
            agent_name="baseline",
            code_quality=0.85,
            overall_score=0.83,
        )
        
        result = scores.to_dict()
        assert result["task_id"] == "task_1"
        assert result["scores"]["code_quality"] == 0.85
        assert result["scores"]["overall"] == 0.83


class TestAgentJudgeMetrics:
    """Test AgentJudgeMetrics aggregation."""
    
    def test_metrics_creation(self):
        """Test creating metrics."""
        metrics = AgentJudgeMetrics(
            agent_name="baseline",
            total_evaluations=5,
            mean_code_quality=0.85,
            mean_overall=0.83,
        )
        
        assert metrics.agent_name == "baseline"
        assert metrics.total_evaluations == 5
        assert metrics.mean_overall == 0.83
    
    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = AgentJudgeMetrics(
            agent_name="baseline",
            total_evaluations=5,
            mean_code_quality=0.85,
        )
        
        result = metrics.to_dict()
        assert result["agent_name"] == "baseline"
        assert result["total_evaluations"] == 5
        assert result["means"]["code_quality"] == 0.85


class TestJudgeDelta:
    """Test JudgeDelta comparison."""
    
    def test_delta_creation(self):
        """Test creating delta."""
        delta = JudgeDelta(
            baseline_agent="baseline",
            variant_agent="variant",
            overall_delta=0.07,  # variant is better
        )
        
        assert delta.baseline_agent == "baseline"
        assert delta.overall_delta == 0.07
    
    def test_delta_with_improvements(self):
        """Test delta with improvement areas."""
        delta = JudgeDelta(
            baseline_agent="baseline",
            variant_agent="variant",
            code_quality_delta=0.08,
            overall_delta=0.05,
            improvement_areas=["code_quality"],
        )
        
        assert "code_quality" in delta.improvement_areas
    
    def test_delta_with_regressions(self):
        """Test delta with regression areas."""
        delta = JudgeDelta(
            baseline_agent="baseline",
            variant_agent="variant",
            correctness_delta=-0.10,
            regression_areas=["correctness"],
        )
        
        assert "correctness" in delta.regression_areas


class TestLLMJudgeAnalyzer:
    """Test LLM judge analyzer."""
    
    def test_analyzer_initialization(self, temp_db):
        """Test analyzer initialization."""
        analyzer = LLMJudgeAnalyzer(temp_db)
        assert analyzer.db is temp_db
    
    def test_compute_agent_metrics(self, db_with_judge_data):
        """Test computing agent metrics."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        results = db_with_judge_data.get_judge_results_for_experiment(
            "exp_001", agent_name="baseline"
        )
        
        metrics = analyzer._compute_agent_metrics("baseline", results)
        
        assert metrics.agent_name == "baseline"
        assert metrics.total_evaluations == 5
        assert metrics.mean_overall > 0.5  # Most passed
        assert metrics.min_overall < 0.35  # One failed
        assert metrics.max_overall > 0.80
    
    def test_compute_delta(self, db_with_judge_data):
        """Test computing delta between agents."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        baseline_results = db_with_judge_data.get_judge_results_for_experiment(
            "exp_001", agent_name="baseline"
        )
        variant_results = db_with_judge_data.get_judge_results_for_experiment(
            "exp_001", agent_name="variant"
        )
        
        baseline_metrics = analyzer._compute_agent_metrics("baseline", baseline_results)
        variant_metrics = analyzer._compute_agent_metrics("variant", variant_results)
        
        delta = analyzer._compute_delta(baseline_metrics, variant_metrics)
        
        assert delta.baseline_agent == "baseline"
        assert delta.variant_agent == "variant"
        # Baseline is better overall
        assert delta.overall_delta < 0
    
    def test_analyze_judge_scores(self, db_with_judge_data):
        """Test full analysis."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001")
        
        assert result.experiment_id == "exp_001"
        assert result.baseline_agent == "baseline"
        assert "variant" in result.variant_agents
        assert len(result.individual_scores) == 10  # 2 agents * 5 tasks
        assert "baseline" in result.agent_metrics
        assert "variant" in result.agent_metrics
    
    def test_analyze_with_explicit_baseline(self, db_with_judge_data):
        """Test analysis with explicit baseline."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001", baseline_agent="variant")
        
        assert result.baseline_agent == "variant"
        assert "baseline" in result.variant_agents
    
    def test_identify_improvement_areas(self, db_with_judge_data):
        """Test identification of improvement areas."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001")
        
        # Should have improvement and regression areas
        # (depends on which agent is baseline)
        deltas = list(result.deltas.values())
        if deltas:
            delta = deltas[0]
            # Baseline should have improvements in some dimensions
            assert isinstance(delta.improvement_areas, list)
            assert isinstance(delta.regression_areas, list)
    
    def test_best_worst_agent(self, db_with_judge_data):
        """Test best/worst agent identification."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001")
        
        assert result.best_agent_overall
        assert result.worst_agent_overall
        
        best_metrics = result.agent_metrics[result.best_agent_overall]
        worst_metrics = result.agent_metrics[result.worst_agent_overall]
        
        assert best_metrics.mean_overall > worst_metrics.mean_overall
    
    def test_to_dict(self, db_with_judge_data):
        """Test result serialization."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001")
        result_dict = result.to_dict()
        
        assert result_dict["experiment_id"] == "exp_001"
        assert "agent_metrics" in result_dict
        assert "comparisons" in result_dict
        assert "summary" in result_dict
    
    def test_result_json_serializable(self, db_with_judge_data):
        """Test that result can be serialized to JSON."""
        analyzer = LLMJudgeAnalyzer(db_with_judge_data)
        
        result = analyzer.analyze_judge_scores("exp_001")
        result_dict = result.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(result_dict)
        assert json_str


class TestDatabaseIntegration:
    """Test database integration for judge results."""
    
    def test_store_judge_result(self, db_with_harbor_data):
        """Test storing judge result."""
        db = db_with_harbor_data
        
        judge_result = {
            "code_quality": 0.85,
            "correctness": 0.90,
            "completeness": 0.80,
            "quality": 0.85,
            "efficiency": 0.75,
            "overall_score": 0.83,
            "code_quality_reasoning": "Good",
            "judge_model": "claude-haiku",
            "tokens_used": 500,
        }
        
        db.store_judge_result(
            "task_0",
            judge_result,
            experiment_id="exp_001",
            job_id="job_baseline_0",
            agent_name="baseline",
        )
        
        # Verify stored
        retrieved = db.get_judge_result(
            "task_0", experiment_id="exp_001", job_id="job_baseline_0"
        )
        assert retrieved is not None
        assert retrieved["code_quality"] == 0.85
    
    def test_get_judge_results_for_experiment(self, db_with_judge_data):
        """Test retrieving judge results by experiment."""
        db = db_with_judge_data
        
        results = db.get_judge_results_for_experiment("exp_001")
        
        assert len(results) > 0
    
    def test_get_judge_results_by_agent(self, db_with_judge_data):
        """Test retrieving judge results by agent."""
        db = db_with_judge_data
        
        baseline_results = db.get_judge_results_for_experiment(
            "exp_001", agent_name="baseline"
        )
        variant_results = db.get_judge_results_for_experiment(
            "exp_001", agent_name="variant"
        )
        
        assert len(baseline_results) == 5
        assert len(variant_results) == 5
        assert all(r["agent_name"] == "baseline" for r in baseline_results)
        assert all(r["agent_name"] == "variant" for r in variant_results)


class TestErrorHandling:
    """Test error handling."""
    
    def test_analyze_empty_experiment(self, temp_db):
        """Test analyzing empty experiment."""
        analyzer = LLMJudgeAnalyzer(temp_db)
        
        with pytest.raises(ValueError, match="No judge results found"):
            analyzer.analyze_judge_scores("nonexistent_exp")
    
    def test_missing_scores_default_to_zero(self, db_with_harbor_data):
        """Test that missing scores default to zero."""
        db = db_with_harbor_data
        
        # Store result with missing scores
        judge_result = {
            "code_quality": None,
            "correctness": None,
            "judge_model": "claude-haiku",
        }
        
        db.store_judge_result(
            "task_0",
            judge_result,
            experiment_id="exp_001",
            job_id="job_baseline_0",
            agent_name="baseline",
        )
        
        # Should handle gracefully
        retrieved = db.get_judge_result(
            "task_0", experiment_id="exp_001", job_id="job_baseline_0"
        )
        assert retrieved is not None
