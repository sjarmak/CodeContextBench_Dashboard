"""Tests for ingestion orchestrator."""

import json
import pytest
from pathlib import Path
from src.ingest.orchestrator import IngestionOrchestrator


@pytest.fixture
def sample_experiment_dir(tmp_path):
    """Create a sample experiment directory with results."""
    exp_dir = tmp_path / "exp_001"
    
    # Create job directories with result.json and transcript
    for i in range(2):
        job_dir = exp_dir / f"job_{i}"
        job_dir.mkdir(parents=True)
        
        # Create result.json
        result_data = {
            "task_id": f"task_{i}",
            "metadata": {
                "task_name": f"Task {i}",
                "category": "ir",
            },
            "agent": {"exit_code": 0, "duration_seconds": 30.0},
            "verifier": {"passed": True, "duration_seconds": 5.0, "reward": {"mrr": 0.9}},
            "model": "claude-haiku",
            "passed": True,
        }
        (job_dir / "result.json").write_text(json.dumps(result_data))
        
        # Create transcript
        transcript = f"""
        <function_calls>
        <invoke name="Bash">
        <parameter name="cmd">ls</parameter>
        </invoke>
        </function_calls>
        
        <function_calls>
        <invoke name="sg_keyword_search">
        <parameter name="query">auth</parameter>
        </invoke>
        </function_calls>
        """
        (job_dir / "claude-code.txt").write_text(transcript)
    
    return exp_dir


def test_orchestrator_initialization(tmp_path):
    """Test orchestrator initialization."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    assert orchestrator.db is not None
    assert db_path.exists()


def test_orchestrator_ingest_experiment(sample_experiment_dir, tmp_path):
    """Test ingesting a single experiment."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    stats = orchestrator.ingest_experiment(
        experiment_id="exp_001",
        results_dir=sample_experiment_dir,
    )
    
    assert stats["experiment_id"] == "exp_001"
    assert stats["results_processed"] == 2
    assert stats["transcripts_processed"] == 2
    assert stats["results_skipped"] == 0
    assert len(stats["errors"]) == 0


def test_orchestrator_stores_results(sample_experiment_dir, tmp_path):
    """Test that results are actually stored in the database."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    orchestrator.ingest_experiment(
        experiment_id="exp_001",
        results_dir=sample_experiment_dir,
    )
    
    # Verify results are in database
    results = orchestrator.get_experiment_results("exp_001")
    assert len(results) == 2
    assert all(r["experiment_id"] == "exp_001" for r in results)
    assert all(r["passed"] == True for r in results)


def test_orchestrator_handles_missing_transcript(tmp_path):
    """Test ingestion when transcript is missing."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    # Create result without transcript
    exp_dir = tmp_path / "exp_001"
    job_dir = exp_dir / "job_0"
    job_dir.mkdir(parents=True)
    
    result_data = {
        "task_id": "task_0",
        "metadata": {"task_name": "Task 0", "category": "ir"},
        "agent": {"exit_code": 0, "duration_seconds": 30.0},
        "verifier": {"passed": True, "duration_seconds": 5.0, "reward": {}},
        "passed": True,
    }
    (job_dir / "result.json").write_text(json.dumps(result_data))
    
    stats = orchestrator.ingest_experiment(
        experiment_id="exp_001",
        results_dir=exp_dir,
    )
    
    assert stats["results_processed"] == 1
    assert stats["transcripts_skipped"] == 1


def test_orchestrator_experiment_stats(sample_experiment_dir, tmp_path):
    """Test retrieving experiment statistics."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    orchestrator.ingest_experiment(
        experiment_id="exp_001",
        results_dir=sample_experiment_dir,
    )
    
    stats = orchestrator.get_experiment_stats("exp_001")
    
    assert "harbor" in stats
    assert "tool_usage" in stats
    assert stats["harbor"]["total_tasks"] == 2
    assert stats["harbor"]["passed_tasks"] == 2
    assert stats["harbor"]["pass_rate"] == 1.0
    assert stats["tool_usage"]["avg_mcp_calls"] > 0


def test_orchestrator_ingest_directory(tmp_path):
    """Test ingesting multiple experiments from directory."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    # Create two experiment directories
    for exp_num in range(2):
        exp_dir = tmp_path / f"exp_{exp_num:03d}"
        job_dir = exp_dir / "job_0"
        job_dir.mkdir(parents=True)
        
        result_data = {
            "task_id": f"task_{exp_num}",
            "metadata": {"task_name": f"Task {exp_num}", "category": "ir"},
            "agent": {"exit_code": 0, "duration_seconds": 30.0},
            "verifier": {"passed": True, "duration_seconds": 5.0, "reward": {}},
            "passed": True,
        }
        (job_dir / "result.json").write_text(json.dumps(result_data))
    
    all_stats = orchestrator.ingest_directory(tmp_path)
    
    assert len(all_stats["experiments"]) == 2
    assert all_stats["total_results"] == 2


def test_orchestrator_handles_invalid_result(tmp_path):
    """Test handling of invalid result files."""
    db_path = tmp_path / "metrics.db"
    orchestrator = IngestionOrchestrator(db_path)
    
    # Create result with minimal data
    exp_dir = tmp_path / "exp_001"
    job_dir = exp_dir / "job_0"
    job_dir.mkdir(parents=True)
    
    # Minimal valid result
    result_data = {"task_id": "task_0"}
    (job_dir / "result.json").write_text(json.dumps(result_data))
    
    stats = orchestrator.ingest_experiment(
        experiment_id="exp_001",
        results_dir=exp_dir,
    )
    
    # Should still process minimal result
    assert stats["results_processed"] == 1
    assert stats["results_skipped"] == 0


def test_orchestrator_job_id_extraction(tmp_path):
    """Test job ID extraction from paths."""
    orchestrator = IngestionOrchestrator(tmp_path / "metrics.db")
    
    # Test standard job pattern
    result_file = tmp_path / "jobs" / "job_123" / "result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    
    job_id = orchestrator._extract_job_id(result_file)
    assert job_id == "job_123"
    
    # Test experiment pattern
    result_file2 = tmp_path / "exp_001" / "job_456" / "result.json"
    result_file2.parent.mkdir(parents=True, exist_ok=True)
    
    job_id2 = orchestrator._extract_job_id(result_file2)
    assert job_id2 == "job_456"
