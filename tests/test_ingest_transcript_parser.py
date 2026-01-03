"""Tests for transcript parser."""

import pytest
from pathlib import Path
from src.ingest.transcript_parser import (
    TranscriptParser,
    TranscriptMetrics,
    ToolCategory,
    AgentToolProfile,
)


@pytest.fixture
def sample_transcript():
    """Sample transcript with tool calls."""
    return """
    <function_calls>
    <invoke name="Bash">
    <parameter name="cmd">ls -la</parameter>
    </invoke>
    </function_calls>
    
    <function_calls>
    <invoke name="sg_keyword_search">
    <parameter name="query">authentication</parameter>
    </invoke>
    </function_calls>
    
    <function_calls>
    <invoke name="deepsearch">
    <parameter name="question">How does the auth system work?</parameter>
    </invoke>
    </function_calls>
    
    file: /Users/test/src/auth.ts
    """


def test_transcript_parser_basic(sample_transcript):
    """Test basic transcript parsing."""
    parser = TranscriptParser()
    metrics = parser.parse_text(sample_transcript)
    
    assert metrics.total_tool_calls == 3
    assert metrics.local_calls == 1
    assert metrics.mcp_calls == 1
    assert metrics.deep_search_calls == 1
    assert metrics.other_calls == 0


def test_transcript_parser_tool_categorization():
    """Test tool categorization."""
    parser = TranscriptParser()
    
    # Test MCP tool
    assert parser._categorize_tool("sg_keyword_search") == ToolCategory.MCP
    assert parser._categorize_tool("sourcegraph_search") == ToolCategory.MCP
    assert parser._categorize_tool("read_file") == ToolCategory.MCP
    
    # Test Deep Search
    assert parser._categorize_tool("deepsearch") == ToolCategory.DEEP_SEARCH
    assert parser._categorize_tool("deep_search") == ToolCategory.DEEP_SEARCH
    
    # Test Local tools
    assert parser._categorize_tool("bash") == ToolCategory.LOCAL
    assert parser._categorize_tool("grep") == ToolCategory.LOCAL
    assert parser._categorize_tool("find") == ToolCategory.LOCAL
    
    # Test Other
    assert parser._categorize_tool("custom_tool") == ToolCategory.OTHER


def test_transcript_parser_file_extraction(sample_transcript):
    """Test file path extraction."""
    parser = TranscriptParser()
    metrics = parser.parse_text(sample_transcript)
    
    assert metrics.unique_file_count == 1
    # File paths are normalized (leading / may be stripped)
    assert any("auth.ts" in f for f in metrics.files_accessed)


def test_transcript_parser_success_rate():
    """Test success rate calculation."""
    parser = TranscriptParser()
    
    transcript = """
    <function_calls>
    <invoke name="Bash">
    <parameter name="cmd">ls</parameter>
    </invoke>
    </function_calls>
    
    <function_calls>
    <invoke name="Bash">
    <parameter name="cmd">invalid_command</parameter>
    error occurred
    </invoke>
    </function_calls>
    """
    
    metrics = parser.parse_text(transcript)
    assert metrics.total_tool_calls == 2
    assert metrics.successful_calls == 1
    assert metrics.failed_calls == 1
    assert metrics.success_rate == 0.5


def test_transcript_parser_tool_counts():
    """Test tool call counting."""
    parser = TranscriptParser()
    
    transcript = """
    <function_calls>
    <invoke name="Bash">
    <parameter name="cmd">ls</parameter>
    </invoke>
    </function_calls>
    
    <function_calls>
    <invoke name="Bash">
    <parameter name="cmd">pwd</parameter>
    </invoke>
    </function_calls>
    
    <function_calls>
    <invoke name="sg_keyword_search">
    <parameter name="query">auth</parameter>
    </invoke>
    </function_calls>
    """
    
    metrics = parser.parse_text(transcript)
    
    assert metrics.total_tool_calls == 3
    assert metrics.tool_calls_by_name["Bash"] == 2
    assert metrics.tool_calls_by_name["sg_keyword_search"] == 1
    assert metrics.local_calls == 2
    assert metrics.mcp_calls == 1


def test_transcript_parser_mcp_vs_local_ratio():
    """Test MCP vs local ratio calculation."""
    parser = TranscriptParser()
    
    # All local
    transcript1 = """
    <invoke name="Bash"></invoke>
    <invoke name="Bash"></invoke>
    """
    metrics1 = parser.parse_text(transcript1)
    assert metrics1.mcp_vs_local_ratio == 0.0
    
    # All MCP
    transcript2 = """
    <invoke name="sg_keyword_search"></invoke>
    <invoke name="sg_keyword_search"></invoke>
    """
    metrics2 = parser.parse_text(transcript2)
    assert metrics2.mcp_vs_local_ratio == 999.0  # Inf is stored as 999
    
    # Mixed
    transcript3 = """
    <invoke name="sg_keyword_search"></invoke>
    <invoke name="Bash"></invoke>
    <invoke name="Bash"></invoke>
    """
    metrics3 = parser.parse_text(transcript3)
    assert metrics3.mcp_vs_local_ratio == pytest.approx(0.5)


def test_transcript_parser_from_file(tmp_path):
    """Test parsing from file."""
    transcript_file = tmp_path / "transcript.txt"
    content = """
    <invoke name="Bash"></invoke>
    <invoke name="sg_keyword_search"></invoke>
    """
    transcript_file.write_text(content)
    
    parser = TranscriptParser()
    metrics = parser.parse_file(transcript_file)
    
    assert metrics.total_tool_calls == 2
    assert metrics.local_calls == 1
    assert metrics.mcp_calls == 1


def test_agent_tool_profile():
    """Test agent tool profile analysis."""
    metrics = TranscriptMetrics(
        total_tool_calls=10,
        mcp_calls=7,
        deep_search_calls=2,
        local_calls=1,
        other_calls=0,
        tool_calls_by_name={"sg_keyword_search": 5, "deepsearch": 2, "Bash": 1},
        successful_calls=9,
        failed_calls=1,
        success_rate=0.9,
        mcp_vs_local_ratio=9.0,  # 9 MCP calls vs 1 local
    )
    
    profile = AgentToolProfile(metrics)
    
    # Check properties
    assert profile.is_mcp_heavy == True  # ratio 9.0 > 2.0
    assert profile.is_deep_search_strategic == True  # 2/10 = 20%, between 5-30%
    assert profile.tool_diversity > 0.0
    assert len(profile.top_tools) == 3


def test_agent_tool_profile_to_dict():
    """Test agent tool profile serialization."""
    metrics = TranscriptMetrics(
        total_tool_calls=5,
        mcp_calls=3,
        deep_search_calls=1,
        local_calls=1,
        other_calls=0,
        tool_calls_by_name={"sg_keyword_search": 3, "deepsearch": 1, "Bash": 1},
        successful_calls=5,
        failed_calls=0,
        success_rate=1.0,
        mcp_vs_local_ratio=4.0,  # 4 MCP calls vs 1 local
    )
    
    profile = AgentToolProfile(metrics)
    data = profile.to_dict()
    
    assert "metrics" in data
    assert "profile" in data
    assert data["metrics"]["total_tool_calls"] == 5
    assert data["profile"]["is_mcp_heavy"] == True  # 4.0 > 2.0
