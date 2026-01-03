"""Tests for metrics database."""

import json
import pytest
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import (
    HarborResult,
    HarborTaskMetadata,
    HarborAgentOutput,
    HarborVerifierResult,
)
from src.ingest.transcript_parser import TranscriptMetrics


@pytest.fixture
def sample_harbor_result():
    """Sample HarborResult for testing."""
    return HarborResult(
        task_id="test_task_001",
        task_metadata=HarborTaskMetadata(
            task_id="test_task_001",
            task_name="Test Task",
            category="ir",
            tags=["test"],
            difficulty="medium",
        ),
        agent_output=HarborAgentOutput(
            exit_code=0,
            duration_seconds=45.5,
            agent_type="claude-code",
        ),
        verifier_result=HarborVerifierResult(
            passed=True,
            reward={"mrr": 0.95, "score": 0.9},
            duration_seconds=10.2,
        ),
        passed=True,
        duration_seconds=55.7,
        model_name="claude-haiku",
        agent_name="strategic-deepsearch",
    )


@pytest.fixture
def sample_transcript_metrics():
    """Sample TranscriptMetrics for testing."""
    return TranscriptMetrics(
        total_tool_calls=10,
        mcp_calls=6,
        deep_search_calls=2,
        local_calls=2,
        tool_calls_by_name={"sg_keyword_search": 5, "deepsearch": 1, "Bash": 4},
        successful_calls=9,
        failed_calls=1,
        success_rate=0.9,
        mcp_vs_local_ratio=4.0,
        unique_file_count=5,
        search_queries=["auth", "config"],
        transcript_length=5000,
    )


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_metrics.db"
    return MetricsDatabase(db_path)


def test_database_initialization(db):
    """Test database initialization."""
    assert db.db_path.exists()
    
    # Verify tables exist
    with db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert "harbor_results" in tables
        assert "tool_usage" in tables
        assert "experiment_summary" in tables


def test_store_harbor_result(db, sample_harbor_result):
    """Test storing a harbor result."""
    db.store_harbor_result(
        sample_harbor_result,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    # Verify it was stored
    result = db.get_harbor_result(
        task_id="test_task_001",
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    assert result is not None
    assert result["task_id"] == "test_task_001"
    assert result["passed"] == True
    assert result["model_name"] == "claude-haiku"
    assert result["agent_name"] == "strategic-deepsearch"


def test_store_tool_usage(db, sample_transcript_metrics):
    """Test storing tool usage metrics."""
    db.store_tool_usage(
        task_id="test_task_001",
        metrics=sample_transcript_metrics,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    # Verify it was stored
    with db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tool_usage WHERE task_id = ?",
            ("test_task_001",),
        )
        row = cursor.fetchone()
        
        assert row is not None
        assert row["mcp_calls"] == 6
        assert row["deep_search_calls"] == 2
        assert row["local_calls"] == 2


def test_get_experiment_results(db, sample_harbor_result):
    """Test retrieving experiment results."""
    # Store multiple results
    for i in range(3):
        result = HarborResult(
            task_id=f"task_{i}",
            task_metadata=sample_harbor_result.task_metadata,
            agent_output=sample_harbor_result.agent_output,
            verifier_result=sample_harbor_result.verifier_result,
            passed=(i % 2 == 0),
            duration_seconds=sample_harbor_result.duration_seconds,
            model_name=sample_harbor_result.model_name,
        )
        db.store_harbor_result(result, experiment_id="exp_001", job_id=f"job_{i}")
    
    # Retrieve all results
    results = db.get_experiment_results("exp_001")
    
    assert len(results) == 3
    assert all(r["experiment_id"] == "exp_001" for r in results)


def test_pass_rate_calculation(db, sample_harbor_result):
    """Test pass rate calculation."""
    # Store 2 passing and 1 failing result
    for i in range(3):
        result = HarborResult(
            task_id=f"task_{i}",
            task_metadata=sample_harbor_result.task_metadata,
            agent_output=sample_harbor_result.agent_output,
            verifier_result=HarborVerifierResult(
                passed=(i < 2),  # First two pass
                reward={},
            ),
            passed=(i < 2),
            duration_seconds=sample_harbor_result.duration_seconds,
        )
        db.store_harbor_result(result, experiment_id="exp_001", job_id=f"job_{i}")
    
    pass_rate = db.get_pass_rate(experiment_id="exp_001")
    
    assert pass_rate == pytest.approx(2.0 / 3.0)


def test_experiment_summary(db, sample_harbor_result, sample_transcript_metrics):
    """Test experiment summary generation."""
    # Store results and tool usage
    db.store_harbor_result(
        sample_harbor_result,
        experiment_id="exp_001",
        job_id="job_001",
    )
    db.store_tool_usage(
        task_id="test_task_001",
        metrics=sample_transcript_metrics,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    # Generate summary
    db.update_experiment_summary("exp_001")
    
    # Verify summary was created
    summary = db.get_experiment_summary("exp_001")
    
    assert summary is not None
    assert summary["experiment_id"] == "exp_001"
    assert summary["total_tasks"] == 1
    assert summary["passed_tasks"] == 1
    assert summary["pass_rate"] == 1.0


def test_stats_calculation(db, sample_harbor_result, sample_transcript_metrics):
    """Test comprehensive statistics calculation."""
    db.store_harbor_result(
        sample_harbor_result,
        experiment_id="exp_001",
        job_id="job_001",
    )
    db.store_tool_usage(
        task_id="test_task_001",
        metrics=sample_transcript_metrics,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    stats = db.get_stats(experiment_id="exp_001")
    
    assert "harbor" in stats
    assert "tool_usage" in stats
    
    # Harbor stats
    assert stats["harbor"]["total_tasks"] == 1
    assert stats["harbor"]["passed_tasks"] == 1
    assert stats["harbor"]["pass_rate"] == 1.0
    
    # Tool usage stats
    assert stats["tool_usage"]["avg_mcp_calls"] == 6


def test_reward_metrics_storage(db):
    """Test that reward metrics are properly stored as JSON."""
    result = HarborResult(
        task_id="test",
        task_metadata=HarborTaskMetadata("test", "Test", "ir"),
        agent_output=HarborAgentOutput(),
        verifier_result=HarborVerifierResult(
            reward={"mrr": 0.95, "precision": 0.87, "custom_metric": 42}
        ),
        passed=False,
        duration_seconds=0,
    )
    
    db.store_harbor_result(result, experiment_id="exp_001", job_id="job_001")
    
    # Retrieve and verify
    stored = db.get_harbor_result("test", "exp_001", "job_001")
    reward = json.loads(stored["reward_metrics"])
    
    assert reward["mrr"] == 0.95
    assert reward["precision"] == 0.87
    assert reward["custom_metric"] == 42


def test_replace_logic(db, sample_harbor_result):
    """Test that storing duplicate records replaces them."""
    # Store initial result
    db.store_harbor_result(
        sample_harbor_result,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    # Store updated result with same ID
    updated = HarborResult(
        task_id="test_task_001",
        task_metadata=sample_harbor_result.task_metadata,
        agent_output=sample_harbor_result.agent_output,
        verifier_result=HarborVerifierResult(
            passed=False,
            reward={"mrr": 0.5},
        ),
        passed=False,
        duration_seconds=100.0,
        model_name="claude-opus",
    )
    
    db.store_harbor_result(
        updated,
        experiment_id="exp_001",
        job_id="job_001",
    )
    
    # Verify update
    result = db.get_harbor_result("test_task_001", "exp_001", "job_001")
    assert result["passed"] == False
    assert result["total_duration_seconds"] == 100.0
    
    # Verify only one record exists
    with db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM harbor_results WHERE task_id = ? AND experiment_id = ? AND job_id = ?",
            ("test_task_001", "exp_001", "job_001"),
        )
        count = cursor.fetchone()[0]
        assert count == 1
