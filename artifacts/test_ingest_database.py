"""Tests for metrics database."""

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
def db(tmp_path):
    """Create a test database."""
    return MetricsDatabase(tmp_path / "test.db")


@pytest.fixture
def sample_harbor_result():
    """Create a sample Harbor result."""
    return HarborResult(
        task_id="test_task_001",
        task_metadata=HarborTaskMetadata(
            task_id="test_task_001",
            task_name="Test Task",
            category="information_retrieval",
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
            reward={"mrr": 0.95, "precision_at_10": 0.8},
            duration_seconds=10.2,
        ),
        passed=True,
        duration_seconds=55.7,
        model_name="claude-haiku",
        agent_name="strategic-deepsearch",
    )


def test_database_initialization(db):
    """Test database is initialized with correct schema."""
    assert db.db_path.exists()
    
    # Verify tables exist
    with db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        
        assert "harbor_results" in tables
        assert "tool_usage" in tables
        assert "experiment_summary" in tables


def test_store_harbor_result(db, sample_harbor_result):
    """Test storing a Harbor result."""
    db.store_harbor_result(sample_harbor_result, "exp001", "job001")
    
    # Verify it was stored
    result = db.get_harbor_result("test_task_001", "exp001", "job001")
    assert result is not None
    assert result["task_id"] == "test_task_001"
    assert result["passed"] == 1  # SQLite stores booleans as 0/1
    assert result["agent_name"] == "strategic-deepsearch"


def test_store_tool_usage(db, sample_harbor_result):
    """Test storing tool usage metrics."""
    metrics = TranscriptMetrics()
    metrics.total_tool_calls = 10
    metrics.mcp_calls = 5
    metrics.deep_search_calls = 1
    metrics.local_calls = 4
    metrics.successful_calls = 9
    metrics.failed_calls = 1
    metrics.success_rate = 0.9
    metrics.mcp_vs_local_ratio = 1.25
    metrics.unique_file_count = 5
    metrics.tool_calls_by_name = {"bash": 4, "grep": 1, "sg_search": 5}
    
    db.store_tool_usage(sample_harbor_result.task_id, metrics, "exp001", "job001")
    
    # Verify via database query
    with db._connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tool_usage WHERE task_id = ? AND experiment_id = ?",
            ("test_task_001", "exp001")
        )
        row = cursor.fetchone()
        
        assert row is not None
        assert row["total_calls"] == 10
        assert row["mcp_calls"] == 5
        assert row["deep_search_calls"] == 1


def test_get_experiment_results(db, sample_harbor_result):
    """Test retrieving all results for an experiment."""
    # Store multiple results
    for i in range(3):
        result = HarborResult(
            task_id=f"task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
            ),
            agent_output=HarborAgentOutput(exit_code=0),
            verifier_result=HarborVerifierResult(passed=i < 2),  # 2 pass, 1 fails
            passed=i < 2,
        )
        db.store_harbor_result(result, "exp001")
    
    results = db.get_experiment_results("exp001")
    assert len(results) == 3


def test_pass_rate_calculation(db, sample_harbor_result):
    """Test pass rate calculation."""
    # Store 3 results: 2 pass, 1 fail
    for i in range(3):
        result = HarborResult(
            task_id=f"task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
            ),
            agent_output=HarborAgentOutput(exit_code=0),
            verifier_result=HarborVerifierResult(passed=i < 2),
            passed=i < 2,
        )
        db.store_harbor_result(result, "exp001")
    
    pass_rate = db.get_pass_rate("exp001")
    assert pass_rate == pytest.approx(2/3, rel=0.01)


def test_experiment_summary(db):
    """Test experiment summary computation."""
    # Store some results
    for i in range(4):
        result = HarborResult(
            task_id=f"task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=30.0 + i,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 3,
                reward={"mrr": 0.8 + i * 0.05},
                duration_seconds=10.0,
            ),
            passed=i < 3,
            model_name="claude-haiku",
            agent_name="test-agent",
        )
        db.store_harbor_result(result, "exp002")
    
    # Update summary
    db.update_experiment_summary("exp002")
    
    # Verify summary was created
    summary = db.get_experiment_summary("exp002")
    assert summary is not None
    assert summary["total_tasks"] == 4
    assert summary["passed_tasks"] == 3


def test_get_stats(db):
    """Test comprehensive statistics."""
    # Store results
    for i in range(5):
        result = HarborResult(
            task_id=f"task_{i:03d}",
            task_metadata=HarborTaskMetadata(
                task_id=f"task_{i:03d}",
                task_name=f"Task {i}",
                category="test",
            ),
            agent_output=HarborAgentOutput(
                exit_code=0,
                duration_seconds=50.0,
            ),
            verifier_result=HarborVerifierResult(
                passed=i < 4,
                reward={"mrr": 0.9},
                duration_seconds=10.0,
            ),
            passed=i < 4,
        )
        db.store_harbor_result(result, "exp003")
    
    # Store tool usage
    for i in range(5):
        metrics = TranscriptMetrics()
        metrics.total_tool_calls = 20
        metrics.mcp_calls = 10
        metrics.deep_search_calls = 2
        metrics.local_calls = 8
        metrics.success_rate = 0.95
        db.store_tool_usage(f"task_{i:03d}", metrics, "exp003")
    
    stats = db.get_stats("exp003")
    
    assert stats["harbor"]["total_tasks"] == 5
    assert stats["harbor"]["passed_tasks"] == 4
    assert stats["harbor"]["pass_rate"] == 0.8
    assert stats["tool_usage"]["avg_mcp_calls"] == 10.0
    assert stats["tool_usage"]["avg_deep_search_calls"] == 2.0


def test_store_and_retrieve_empty_reward(db):
    """Test handling empty reward metrics."""
    result = HarborResult(
        task_id="no_reward",
        task_metadata=HarborTaskMetadata(
            task_id="no_reward",
            task_name="No Reward Task",
            category="test",
        ),
        agent_output=HarborAgentOutput(exit_code=0),
        verifier_result=HarborVerifierResult(
            passed=False,
            reward={},  # Empty reward
        ),
        passed=False,
    )
    
    db.store_harbor_result(result, "exp004")
    
    retrieved = db.get_harbor_result("no_reward", "exp004")
    assert retrieved is not None
    assert retrieved["reward_primary"] is None
