"""Integration tests for the complete ingestion pipeline."""

import json
import pytest
from pathlib import Path
from src.ingest import HarborResultParser, TranscriptParser, MetricsDatabase


@pytest.fixture
def sample_experiment_dir(tmp_path):
    """Create a sample experiment directory structure."""
    exp_dir = tmp_path / "results" / "exp001"
    
    # Create job 1 - passing task with transcript
    job1_dir = exp_dir / "job001"
    job1_dir.mkdir(parents=True)
    
    result1 = {
        "task_id": "task_001",
        "metadata": {
            "task_name": "Retrieval Task 1",
            "category": "information_retrieval",
            "difficulty": "medium",
        },
        "agent": {
            "exit_code": 0,
            "duration_seconds": 45.0,
            "agent_type": "claude-code",
        },
        "verifier": {
            "passed": True,
            "reward": {"mrr": 0.95, "precision_at_10": 0.85},
            "duration_seconds": 10.0,
        },
        "model": "claude-haiku",
    }
    (job1_dir / "result.json").write_text(json.dumps(result1))
    
    transcript1 = """
<function_calls>
<invoke name="sg_keyword_search">
<parameter name="query">authentication</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="deepsearch">
<parameter name="question">How does token validation work?</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="bash">
<parameter name="command">grep -r "validate" src/</parameter>
</invoke>
</function_calls>
"""
    (job1_dir / "claude-code.txt").write_text(transcript1)
    
    # Create job 2 - failing task
    job2_dir = exp_dir / "job002"
    job2_dir.mkdir(parents=True)
    
    result2 = {
        "task_id": "task_002",
        "metadata": {
            "task_name": "Retrieval Task 2",
            "category": "information_retrieval",
            "difficulty": "hard",
        },
        "agent": {
            "exit_code": 1,
            "duration_seconds": 30.0,
        },
        "verifier": {
            "passed": False,
            "reward": {"mrr": 0.5},
            "duration_seconds": 5.0,
        },
        "model": "claude-haiku",
    }
    (job2_dir / "result.json").write_text(json.dumps(result2))
    
    transcript2 = """
<function_calls>
<invoke name="bash">
<parameter name="command">find . -name "*.py"</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="grep">
<parameter name="pattern">search term</parameter>
</invoke>
</function_calls>
"""
    (job2_dir / "claude-code.txt").write_text(transcript2)
    
    return exp_dir


def test_full_ingestion_pipeline(sample_experiment_dir):
    """Test the complete ingestion pipeline."""
    db_path = sample_experiment_dir.parent / "metrics.db"
    
    # Initialize components
    db = MetricsDatabase(db_path)
    harbor_parser = HarborResultParser()
    transcript_parser = TranscriptParser()
    
    # Find jobs
    jobs = list(sample_experiment_dir.iterdir())
    assert len(jobs) == 2
    
    # Process each job
    exp_id = sample_experiment_dir.name
    ingested = 0
    
    for job_dir in jobs:
        result_file = job_dir / "result.json"
        transcript_file = job_dir / "claude-code.txt"
        
        if not result_file.exists():
            continue
        
        # Parse result
        harbor_result = harbor_parser.parse_file(result_file)
        db.store_harbor_result(harbor_result, exp_id, job_dir.name)
        
        # Parse transcript if available
        if transcript_file.exists():
            metrics = transcript_parser.parse_file(transcript_file)
            db.store_tool_usage(harbor_result.task_id, metrics, exp_id, job_dir.name)
        
        ingested += 1
    
    assert ingested == 2
    
    # Verify data was stored
    results = db.get_experiment_results(exp_id)
    assert len(results) == 2
    
    # Verify first task (passing)
    result1 = results[0]
    assert result1["task_id"] == "task_001"
    assert result1["passed"] == 1
    
    # Verify second task (failing)
    result2 = results[1]
    assert result2["task_id"] == "task_002"
    assert result2["passed"] == 0


def test_ingestion_with_summary(sample_experiment_dir):
    """Test ingestion with experiment summary computation."""
    db_path = sample_experiment_dir.parent / "metrics.db"
    db = MetricsDatabase(db_path)
    
    harbor_parser = HarborResultParser()
    transcript_parser = TranscriptParser()
    
    # Ingest all jobs
    exp_id = sample_experiment_dir.name
    for job_dir in sample_experiment_dir.iterdir():
        result_file = job_dir / "result.json"
        transcript_file = job_dir / "claude-code.txt"
        
        if result_file.exists():
            harbor_result = harbor_parser.parse_file(result_file)
            db.store_harbor_result(harbor_result, exp_id, job_dir.name)
            
            if transcript_file.exists():
                metrics = transcript_parser.parse_file(transcript_file)
                db.store_tool_usage(harbor_result.task_id, metrics, exp_id, job_dir.name)
    
    # Update summary
    db.update_experiment_summary(exp_id)
    
    # Check summary
    summary = db.get_experiment_summary(exp_id)
    assert summary is not None
    assert summary["total_tasks"] == 2
    assert summary["passed_tasks"] == 1
    assert summary["pass_rate"] == 0.5


def test_ingestion_metrics_extraction(sample_experiment_dir):
    """Test that metrics are correctly extracted and stored."""
    db_path = sample_experiment_dir.parent / "metrics.db"
    db = MetricsDatabase(db_path)
    
    harbor_parser = HarborResultParser()
    transcript_parser = TranscriptParser()
    
    # Process job 1
    job1_dir = sample_experiment_dir / "job001"
    harbor_result = harbor_parser.parse_file(job1_dir / "result.json")
    metrics = transcript_parser.parse_file(job1_dir / "claude-code.txt")
    
    # Verify Harbor metrics
    assert harbor_result.task_id == "task_001"
    assert harbor_result.passed == True
    assert harbor_result.verifier_result.reward["mrr"] == 0.95
    assert harbor_result.duration_seconds == 55.0  # 45 + 10
    
    # Verify transcript metrics
    assert metrics.total_tool_calls == 3
    assert metrics.mcp_calls == 2  # sg_keyword_search + deepsearch
    assert metrics.deep_search_calls == 1
    assert metrics.local_calls == 1
    
    # Store in database
    db.store_harbor_result(harbor_result, "exp001", "job001")
    db.store_tool_usage(harbor_result.task_id, metrics, "exp001", "job001")
    
    # Verify retrieval
    stored = db.get_harbor_result("task_001", "exp001", "job001")
    assert stored is not None
    assert stored["passed"] == 1
    assert stored["agent_name"] is None  # Not in result.json


def test_ingestion_stats(sample_experiment_dir):
    """Test statistics computation from ingested data."""
    db_path = sample_experiment_dir.parent / "metrics.db"
    db = MetricsDatabase(db_path)
    
    harbor_parser = HarborResultParser()
    transcript_parser = TranscriptParser()
    
    # Ingest all jobs
    exp_id = sample_experiment_dir.name
    for job_dir in sample_experiment_dir.iterdir():
        result_file = job_dir / "result.json"
        transcript_file = job_dir / "claude-code.txt"
        
        if result_file.exists():
            harbor_result = harbor_parser.parse_file(result_file)
            db.store_harbor_result(harbor_result, exp_id, job_dir.name)
            
            if transcript_file.exists():
                metrics = transcript_parser.parse_file(transcript_file)
                db.store_tool_usage(harbor_result.task_id, metrics, exp_id, job_dir.name)
    
    # Get stats
    stats = db.get_stats(exp_id)
    
    assert "harbor" in stats
    assert "tool_usage" in stats
    
    # Harbor stats
    assert stats["harbor"]["total_tasks"] == 2
    assert stats["harbor"]["passed_tasks"] == 1
    assert stats["harbor"]["pass_rate"] == 0.5
    assert stats["harbor"]["avg_duration_seconds"] == 37.5  # (45+10+30+5) / 2
    
    # Tool usage stats
    assert stats["tool_usage"]["avg_mcp_calls"] == 1.0
    assert stats["tool_usage"]["avg_deep_search_calls"] == 0.5
    assert stats["tool_usage"]["avg_local_calls"] == 1.0


def test_ingestion_with_missing_transcript(tmp_path):
    """Test ingestion when transcript is missing."""
    exp_dir = tmp_path / "results" / "exp_no_transcript"
    job_dir = exp_dir / "job001"
    job_dir.mkdir(parents=True)
    
    # Only result.json, no transcript
    result = {
        "task_id": "task_001",
        "metadata": {"task_name": "Test"},
        "agent": {"exit_code": 0},
        "verifier": {"passed": True, "reward": {}},
    }
    (job_dir / "result.json").write_text(json.dumps(result))
    
    # Ingest
    db_path = tmp_path / "metrics.db"
    db = MetricsDatabase(db_path)
    parser = HarborResultParser()
    
    harbor_result = parser.parse_file(job_dir / "result.json")
    db.store_harbor_result(harbor_result, "exp_no_transcript", "job001")
    
    # Verify it was stored (without transcript metrics)
    stored = db.get_harbor_result("task_001", "exp_no_transcript", "job001")
    assert stored is not None
    
    # Tool usage table should not have entry (it's optional)
    # This is acceptable - we can have results without tool usage data
