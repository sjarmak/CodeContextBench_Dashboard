"""Tests for Harbor result parser."""

import json
import pytest
from pathlib import Path
from src.ingest.harbor_parser import HarborResultParser, HarborResult


@pytest.fixture
def sample_harbor_result():
    """Sample Harbor result.json structure."""
    return {
        "task_id": "test_task_001",
        "metadata": {
            "task_name": "Test Task",
            "category": "information_retrieval",
            "difficulty": "medium",
            "tags": ["test", "ir"],
        },
        "agent": {
            "exit_code": 0,
            "duration_seconds": 45.5,
            "agent_type": "claude-code",
        },
        "verifier": {
            "passed": True,
            "duration_seconds": 10.2,
            "reward": {
                "mrr": 0.95,
                "precision_at_10": 0.8,
                "recall_at_10": 0.85,
            },
        },
        "model": "anthropic/claude-haiku-4-5-20251001",
        "passed": True,
    }


def test_harbor_parser_basic(sample_harbor_result):
    """Test basic parsing of Harbor result."""
    parser = HarborResultParser()
    result = parser.parse_dict(sample_harbor_result)
    
    assert result.task_id == "test_task_001"
    assert result.task_metadata.task_name == "Test Task"
    assert result.agent_output.exit_code == 0
    assert result.verifier_result.passed == True
    assert result.passed == True
    assert result.model_name == "anthropic/claude-haiku-4-5-20251001"


def test_harbor_parser_reward_extraction(sample_harbor_result):
    """Test reward metric extraction."""
    parser = HarborResultParser()
    result = parser.parse_dict(sample_harbor_result)
    
    assert result.verifier_result.reward["mrr"] == 0.95
    assert result.verifier_result.reward["precision_at_10"] == 0.8
    assert result.verifier_result.reward["recall_at_10"] == 0.85


def test_harbor_parser_duration_calculation(sample_harbor_result):
    """Test duration calculation."""
    parser = HarborResultParser()
    result = parser.parse_dict(sample_harbor_result)
    
    expected_duration = 45.5 + 10.2
    assert result.duration_seconds == expected_duration


def test_harbor_parser_pass_fail_logic():
    """Test pass/fail logic."""
    parser = HarborResultParser()
    
    # Passes when both exit_code == 0 and verifier passes
    passing_result = {
        "task_id": "pass",
        "metadata": {},
        "agent": {"exit_code": 0},
        "verifier": {"passed": True, "reward": {}},
    }
    result = parser.parse_dict(passing_result)
    assert result.passed == True
    
    # Fails when exit_code != 0
    failing_exit = {
        "task_id": "fail_exit",
        "metadata": {},
        "agent": {"exit_code": 1},
        "verifier": {"passed": True, "reward": {}},
    }
    result = parser.parse_dict(failing_exit)
    assert result.passed == False
    
    # Fails when verifier fails
    failing_verifier = {
        "task_id": "fail_verifier",
        "metadata": {},
        "agent": {"exit_code": 0},
        "verifier": {"passed": False, "reward": {}},
    }
    result = parser.parse_dict(failing_verifier)
    assert result.passed == False


def test_harbor_parser_missing_fields():
    """Test parsing with missing optional fields."""
    parser = HarborResultParser()
    
    minimal_result = {
        "task_id": "minimal",
    }
    
    result = parser.parse_dict(minimal_result)
    assert result.task_id == "minimal"
    assert result.task_metadata.task_name == "unknown"
    assert result.agent_output.exit_code == 0
    assert result.verifier_result.passed == False


def test_harbor_parser_to_dict():
    """Test conversion to dictionary."""
    parser = HarborResultParser()
    result = parser.parse_dict({
        "task_id": "test",
        "metadata": {"task_name": "Test"},
        "agent": {"exit_code": 0},
        "verifier": {"passed": True, "reward": {"score": 0.9}},
    })
    
    result_dict = result.to_dict()
    
    assert result_dict["task_id"] == "test"
    assert result_dict["task_metadata"]["task_name"] == "Test"
    assert result_dict["verifier_result"]["reward"]["score"] == 0.9
    assert result_dict["passed"] == True


def test_harbor_parser_with_file(tmp_path):
    """Test parsing from file."""
    result_file = tmp_path / "result.json"
    sample_data = {
        "task_id": "file_test",
        "metadata": {"task_name": "File Test"},
        "agent": {"exit_code": 0},
        "verifier": {"passed": True, "reward": {}},
    }
    
    result_file.write_text(json.dumps(sample_data))
    
    parser = HarborResultParser()
    result = parser.parse_file(result_file)
    
    assert result.task_id == "file_test"
    assert result.task_metadata.task_name == "File Test"
