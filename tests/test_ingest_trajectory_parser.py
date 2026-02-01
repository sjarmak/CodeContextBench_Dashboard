"""Tests for trajectory parser (ATIF format)."""

import pytest
import json
from pathlib import Path
from src.ingest.trajectory_parser import (
    TrajectoryParser,
    TrajectoryMetrics,
    TrajectoryStep,
)
from src.ingest.transcript_parser import ToolCategory, TranscriptMetrics


@pytest.fixture
def sample_trajectory_data():
    """Sample ATIF-v1.2 trajectory data."""
    return {
        "schema_version": "ATIF-v1.2",
        "session_id": "test-session-123",
        "agent": {
            "name": "claude-code",
            "version": "2.0.72",
            "model_name": "claude-haiku-4-5-20251001",
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-01-01T00:00:00Z",
                "source": "user",
                "message": "Test prompt",
            },
            {
                "step_id": 2,
                "timestamp": "2025-01-01T00:00:01Z",
                "source": "agent",
                "model_name": "claude-haiku-4-5-20251001",
                "message": "Response without tools",
                "metrics": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "cached_tokens": 0,
                },
            },
            {
                "step_id": 3,
                "timestamp": "2025-01-01T00:00:02Z",
                "source": "agent",
                "model_name": "claude-haiku-4-5-20251001",
                "message": "Using bash",
                "metrics": {
                    "prompt_tokens": 200,
                    "completion_tokens": 30,
                    "cached_tokens": 50,
                },
                "tool_calls": [
                    {
                        "tool_call_id": "toolu_1",
                        "function_name": "Bash",
                        "arguments": {"command": "ls"},
                    }
                ],
            },
            {
                "step_id": 4,
                "timestamp": "2025-01-01T00:00:03Z",
                "source": "agent",
                "model_name": "claude-haiku-4-5-20251001",
                "message": "Using Sourcegraph",
                "metrics": {
                    "prompt_tokens": 300,
                    "completion_tokens": 100,
                    "cached_tokens": 100,
                },
                "tool_calls": [
                    {
                        "tool_call_id": "toolu_2",
                        "function_name": "sg_keyword_search",
                        "arguments": {"query": "auth"},
                    }
                ],
            },
        ],
    }


@pytest.fixture
def sample_trajectory_multi_tool_step():
    """Trajectory data with multiple tools in one step."""
    return {
        "schema_version": "ATIF-v1.2",
        "session_id": "test-multi-tool",
        "agent": {
            "name": "claude-code",
            "version": "2.0.72",
            "model_name": "claude-haiku-4-5-20251001",
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2025-01-01T00:00:01Z",
                "source": "agent",
                "model_name": "claude-haiku-4-5-20251001",
                "message": "Using multiple tools",
                "metrics": {
                    "prompt_tokens": 600,
                    "completion_tokens": 120,
                    "cached_tokens": 60,
                },
                "tool_calls": [
                    {"tool_call_id": "toolu_1", "function_name": "Read", "arguments": {}},
                    {"tool_call_id": "toolu_2", "function_name": "Glob", "arguments": {}},
                    {"tool_call_id": "toolu_3", "function_name": "sg_keyword_search", "arguments": {}},
                ],
            },
        ],
    }


def test_trajectory_parser_basic(sample_trajectory_data):
    """Test basic trajectory parsing."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    assert metrics.schema_version == "ATIF-v1.2"
    assert metrics.session_id == "test-session-123"
    assert metrics.agent_name == "claude-code"
    assert metrics.model_name == "claude-haiku-4-5-20251001"


def test_trajectory_parser_token_totals(sample_trajectory_data):
    """Test total token counting."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    # Sum of all agent steps: 100+200+300 = 600 prompt, 50+30+100 = 180 completion
    assert metrics.total_prompt_tokens == 600
    assert metrics.total_completion_tokens == 180
    assert metrics.total_cached_tokens == 150  # 0+50+100


def test_trajectory_parser_tool_counts(sample_trajectory_data):
    """Test tool call counting."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    assert metrics.total_tool_calls == 2
    assert metrics.tool_call_counts["Bash"] == 1
    assert metrics.tool_call_counts["sg_keyword_search"] == 1


def test_trajectory_parser_token_attribution_single_tool(sample_trajectory_data):
    """Test token attribution for steps with single tool."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    # Step 3: Bash with 200 prompt, 30 completion, 50 cached
    assert metrics.tokens_by_tool["Bash"]["prompt"] == 200
    assert metrics.tokens_by_tool["Bash"]["completion"] == 30
    assert metrics.tokens_by_tool["Bash"]["cached"] == 50

    # Step 4: sg_keyword_search with 300 prompt, 100 completion, 100 cached
    assert metrics.tokens_by_tool["sg_keyword_search"]["prompt"] == 300
    assert metrics.tokens_by_tool["sg_keyword_search"]["completion"] == 100
    assert metrics.tokens_by_tool["sg_keyword_search"]["cached"] == 100


def test_trajectory_parser_token_attribution_no_tools(sample_trajectory_data):
    """Test token attribution for steps with no tools (OTHER category)."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    # Step 2: No tools, 100 prompt, 50 completion -> OTHER
    assert metrics.tokens_by_category[ToolCategory.OTHER]["prompt"] == 100
    assert metrics.tokens_by_category[ToolCategory.OTHER]["completion"] == 50


def test_trajectory_parser_token_attribution_multi_tool(sample_trajectory_multi_tool_step):
    """Test token attribution for steps with multiple tools (divide equally)."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_multi_tool_step)

    # 600 prompt / 3 = 200 each, 120 completion / 3 = 40 each, 60 cached / 3 = 20 each
    assert metrics.tokens_by_tool["Read"]["prompt"] == 200
    assert metrics.tokens_by_tool["Glob"]["prompt"] == 200
    assert metrics.tokens_by_tool["sg_keyword_search"]["prompt"] == 200

    assert metrics.tokens_by_tool["Read"]["completion"] == 40
    assert metrics.tokens_by_tool["Glob"]["completion"] == 40
    assert metrics.tokens_by_tool["sg_keyword_search"]["completion"] == 40


def test_trajectory_parser_category_attribution(sample_trajectory_data):
    """Test token attribution by category."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(sample_trajectory_data)

    # LOCAL: Bash - 200 prompt, 30 completion
    assert metrics.tokens_by_category[ToolCategory.LOCAL]["prompt"] == 200
    assert metrics.tokens_by_category[ToolCategory.LOCAL]["completion"] == 30

    # MCP: sg_keyword_search - 300 prompt, 100 completion
    assert metrics.tokens_by_category[ToolCategory.MCP]["prompt"] == 300
    assert metrics.tokens_by_category[ToolCategory.MCP]["completion"] == 100

    # OTHER: Step without tools - 100 prompt, 50 completion
    assert metrics.tokens_by_category[ToolCategory.OTHER]["prompt"] == 100
    assert metrics.tokens_by_category[ToolCategory.OTHER]["completion"] == 50


def test_trajectory_parser_tool_categorization():
    """Test tool categorization."""
    parser = TrajectoryParser(calculate_cost=False)

    # MCP tools
    assert parser._categorize_tool("sg_keyword_search") == ToolCategory.MCP
    assert parser._categorize_tool("sourcegraph_search") == ToolCategory.MCP
    assert parser._categorize_tool("mcp__deep_search") == ToolCategory.MCP
    assert parser._categorize_tool("nls_search") == ToolCategory.MCP

    # Deep Search
    assert parser._categorize_tool("deepsearch") == ToolCategory.DEEP_SEARCH
    assert parser._categorize_tool("deep_search") == ToolCategory.DEEP_SEARCH

    # Local tools
    assert parser._categorize_tool("Bash") == ToolCategory.LOCAL
    assert parser._categorize_tool("Read") == ToolCategory.LOCAL
    assert parser._categorize_tool("Write") == ToolCategory.LOCAL
    assert parser._categorize_tool("Edit") == ToolCategory.LOCAL
    assert parser._categorize_tool("Glob") == ToolCategory.LOCAL
    assert parser._categorize_tool("grep") == ToolCategory.LOCAL
    assert parser._categorize_tool("TodoWrite") == ToolCategory.LOCAL

    # Other
    assert parser._categorize_tool("unknown_tool") == ToolCategory.OTHER


def test_trajectory_parser_from_file(tmp_path, sample_trajectory_data):
    """Test parsing from file."""
    trajectory_file = tmp_path / "trajectory.json"
    trajectory_file.write_text(json.dumps(sample_trajectory_data))

    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_file(trajectory_file)

    assert metrics is not None
    assert metrics.total_tool_calls == 2


def test_trajectory_parser_invalid_json(tmp_path):
    """Test handling invalid JSON."""
    trajectory_file = tmp_path / "invalid.json"
    trajectory_file.write_text("not valid json")

    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_file(trajectory_file)

    assert metrics is None


def test_trajectory_parser_missing_file():
    """Test handling missing file."""
    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_file(Path("/nonexistent/file.json"))

    assert metrics is None


def test_trajectory_parser_sidechain_steps():
    """Test that sidechain (warmup) steps are counted but handled appropriately."""
    data = {
        "schema_version": "ATIF-v1.2",
        "session_id": "test",
        "agent": {"name": "claude-code", "version": "2.0", "model_name": "claude-haiku-4-5-20251001"},
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "timestamp": "2025-01-01T00:00:00Z",
                "message": "Warmup response",
                "metrics": {"prompt_tokens": 500, "completion_tokens": 10, "cached_tokens": 0},
                "extra": {"is_sidechain": True},
            },
            {
                "step_id": 2,
                "source": "agent",
                "timestamp": "2025-01-01T00:00:01Z",
                "message": "Real response",
                "metrics": {"prompt_tokens": 1000, "completion_tokens": 100, "cached_tokens": 500},
                "extra": {"is_sidechain": False},
            },
        ],
    }

    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(data)

    # Both steps counted for totals
    assert metrics.total_prompt_tokens == 1500
    assert metrics.total_completion_tokens == 110
    assert metrics.agent_steps == 2


def test_transcript_metrics_merge():
    """Test merging trajectory metrics into transcript metrics."""
    # Create transcript metrics with some data
    transcript_metrics = TranscriptMetrics(
        total_tool_calls=5,
        mcp_calls=2,
        local_calls=3,
        total_input_tokens=0,  # Will be updated
        total_output_tokens=0,  # Will be updated
    )

    # Create trajectory metrics
    trajectory_metrics = TrajectoryMetrics(
        total_prompt_tokens=5000,
        total_completion_tokens=1000,
        total_cached_tokens=2000,
        cost_usd=0.05,
        tokens_by_category={
            ToolCategory.MCP: {"prompt": 3000, "completion": 500, "cached": 1000},
            ToolCategory.LOCAL: {"prompt": 2000, "completion": 500, "cached": 1000},
        },
        tokens_by_tool={
            "sg_keyword_search": {"prompt": 3000, "completion": 500, "cached": 1000},
            "Bash": {"prompt": 2000, "completion": 500, "cached": 1000},
        },
    )

    # Merge
    transcript_metrics.merge_trajectory_metrics(trajectory_metrics)

    # Verify merged data
    assert transcript_metrics.total_input_tokens == 5000
    assert transcript_metrics.total_output_tokens == 1000
    assert transcript_metrics.cached_tokens == 2000
    assert transcript_metrics.cost_usd == 0.05
    assert "mcp" in transcript_metrics.tokens_by_category
    assert "local" in transcript_metrics.tokens_by_category
    assert "sg_keyword_search" in transcript_metrics.tokens_by_tool
    assert "Bash" in transcript_metrics.tokens_by_tool


def test_transcript_metrics_merge_null():
    """Test merging null trajectory metrics."""
    transcript_metrics = TranscriptMetrics(
        total_input_tokens=100,
        total_output_tokens=50,
    )

    # Merge None
    transcript_metrics.merge_trajectory_metrics(None)

    # Should not change
    assert transcript_metrics.total_input_tokens == 100
    assert transcript_metrics.total_output_tokens == 50


def test_trajectory_parser_cache_metrics():
    """Test extraction of detailed cache metrics."""
    data = {
        "schema_version": "ATIF-v1.2",
        "session_id": "test",
        "agent": {"name": "claude-code", "version": "2.0", "model_name": "claude-haiku-4-5-20251001"},
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "timestamp": "2025-01-01T00:00:00Z",
                "message": "Response",
                "metrics": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "cached_tokens": 800,
                    "extra": {
                        "cache_creation_input_tokens": 200,
                        "cache_read_input_tokens": 600,
                    },
                },
            },
        ],
    }

    parser = TrajectoryParser(calculate_cost=False)
    metrics = parser.parse_data(data)

    assert metrics.total_prompt_tokens == 1000
    assert metrics.total_cached_tokens == 800
    assert metrics.total_cache_creation_tokens == 200
    assert metrics.total_cache_read_tokens == 600


def test_trajectory_parser_cost_calculation():
    """Test cost calculation integration."""
    data = {
        "schema_version": "ATIF-v1.2",
        "session_id": "test",
        "agent": {"name": "claude-code", "version": "2.0", "model_name": "claude-haiku-4-5-20251001"},
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "timestamp": "2025-01-01T00:00:00Z",
                "message": "Response",
                "metrics": {
                    "prompt_tokens": 1000000,  # 1M tokens
                    "completion_tokens": 100000,  # 100K tokens
                    "cached_tokens": 0,
                },
            },
        ],
    }

    parser = TrajectoryParser(calculate_cost=True)
    metrics = parser.parse_data(data)

    # With cost calculation enabled, should have cost data
    # For claude-haiku-4-5: $0.80/M input, $4.00/M output
    # Expected: 1M * 0.80 + 0.1M * 4.00 = 0.80 + 0.40 = $1.20
    assert metrics.cost_usd is not None
    assert metrics.cost_usd > 0
