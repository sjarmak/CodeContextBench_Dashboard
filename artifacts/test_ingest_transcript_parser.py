"""Tests for transcript parser."""

import pytest
from src.ingest.transcript_parser import (
    TranscriptParser,
    TranscriptMetrics,
    AgentToolProfile,
    ToolCategory,
)


def test_transcript_parser_empty():
    """Test parsing empty transcript."""
    parser = TranscriptParser()
    metrics = parser.parse_text("")
    
    assert metrics.total_tool_calls == 0
    assert metrics.mcp_calls == 0
    assert metrics.deep_search_calls == 0
    assert metrics.success_rate == 0.0


def test_transcript_parser_tool_categorization():
    """Test tool categorization."""
    parser = TranscriptParser()
    
    # Test MCP categorization
    assert parser._categorize_tool("sourcegraph") == ToolCategory.MCP
    assert parser._categorize_tool("sg_keyword_search") == ToolCategory.MCP
    assert parser._categorize_tool("read_file") == ToolCategory.MCP
    
    # Test Deep Search categorization
    assert parser._categorize_tool("deepsearch") == ToolCategory.DEEP_SEARCH
    assert parser._categorize_tool("deep_search") == ToolCategory.DEEP_SEARCH
    
    # Test Local categorization
    assert parser._categorize_tool("bash") == ToolCategory.LOCAL
    assert parser._categorize_tool("grep") == ToolCategory.LOCAL
    assert parser._categorize_tool("find") == ToolCategory.LOCAL
    
    # Test other categorization
    assert parser._categorize_tool("unknown_tool") == ToolCategory.OTHER


def test_transcript_parser_mcp_calls():
    """Test parsing MCP tool calls."""
    transcript = """
<function_calls>
<invoke name="sourcegraph_keyword_search">
<parameter name="query">test query</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="sg_read_file">
<parameter name="path">file.py</parameter>
</invoke>
</function_calls>
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    assert metrics.total_tool_calls == 2
    assert metrics.mcp_calls == 2
    assert metrics.deep_search_calls == 0
    assert "sourcegraph_keyword_search" in metrics.tool_calls_by_name
    assert "sg_read_file" in metrics.tool_calls_by_name


def test_transcript_parser_deep_search_calls():
    """Test parsing Deep Search calls."""
    transcript = """
<function_calls>
<invoke name="deepsearch">
<parameter name="question">How does authentication work?</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="deepsearch">
<parameter name="question">Find token validation logic</parameter>
</invoke>
</function_calls>
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    assert metrics.total_tool_calls == 2
    assert metrics.deep_search_calls == 2
    assert metrics.mcp_calls == 0


def test_transcript_parser_local_calls():
    """Test parsing local tool calls."""
    transcript = """
<function_calls>
<invoke name="bash">
<parameter name="command">grep -r "function_name" .</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="find">
<parameter name="path">src/</parameter>
</invoke>
</function_calls>
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    assert metrics.total_tool_calls == 2
    assert metrics.local_calls == 2
    assert "bash" in metrics.tool_calls_by_name
    assert "find" in metrics.tool_calls_by_name


def test_transcript_parser_file_access():
    """Test parsing file access patterns."""
    transcript = """
Reading file: src/main.py
Opened: src/utils/helper.ts
Edited: tests/test_main.py
Created: new_file.json
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    # Should find at least some files
    assert metrics.unique_file_count >= 2  # main.py and helper.ts


def test_transcript_parser_mcp_vs_local_ratio():
    """Test MCP vs local ratio calculation."""
    transcript = """
<function_calls>
<invoke name="sg_keyword_search">
<parameter name="query">test</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="bash">
<parameter name="command">ls -la</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="bash">
<parameter name="command">grep test .</parameter>
</invoke>
</function_calls>
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    # 1 MCP call, 2 local calls
    assert metrics.mcp_vs_local_ratio == 0.5


def test_agent_tool_profile_mcp_heavy():
    """Test identifying MCP-heavy agents."""
    metrics = TranscriptMetrics()
    metrics.mcp_calls = 10
    metrics.local_calls = 2
    metrics.total_tool_calls = 12
    metrics.mcp_vs_local_ratio = 5.0
    
    profile = AgentToolProfile(metrics)
    assert profile.is_mcp_heavy == True


def test_agent_tool_profile_deep_search_strategic():
    """Test identifying strategic Deep Search usage."""
    metrics = TranscriptMetrics()
    metrics.total_tool_calls = 20
    metrics.deep_search_calls = 4  # 20% of calls
    metrics.mcp_calls = 8
    metrics.local_calls = 8
    
    profile = AgentToolProfile(metrics)
    assert profile.is_deep_search_strategic == True


def test_agent_tool_profile_top_tools():
    """Test getting top tools."""
    metrics = TranscriptMetrics()
    metrics.tool_calls_by_name = {
        "bash": 10,
        "sg_keyword_search": 5,
        "find": 3,
        "grep": 2,
        "deepsearch": 1,
    }
    
    profile = AgentToolProfile(metrics)
    top_tools = profile.top_tools
    
    assert len(top_tools) <= 5
    assert top_tools[0][0] == "bash"
    assert top_tools[0][1] == 10


def test_agent_tool_profile_to_dict():
    """Test converting profile to dictionary."""
    metrics = TranscriptMetrics()
    metrics.total_tool_calls = 10
    metrics.mcp_calls = 5
    metrics.deep_search_calls = 1
    metrics.local_calls = 4
    metrics.success_rate = 0.9
    metrics.tool_calls_by_name = {"bash": 4, "grep": 1, "sg_search": 5}
    metrics.unique_file_count = 5
    metrics.search_queries = ["query1", "query2"]
    
    profile = AgentToolProfile(metrics)
    profile_dict = profile.to_dict()
    
    assert profile_dict["metrics"]["total_tool_calls"] == 10
    assert profile_dict["metrics"]["mcp_calls"] == 5
    assert profile_dict["profile"]["tool_diversity"] > 0
    assert "top_tools" in profile_dict["profile"]


def test_transcript_parser_success_rate():
    """Test success rate calculation."""
    transcript = """
<function_calls>
<invoke name="bash">
<parameter name="command">valid command</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="bash">
<parameter name="command">failed with error</parameter>
</invoke>
</function_calls>

<function_calls>
<invoke name="bash">
<parameter name="command">another success</parameter>
</invoke>
</function_calls>
"""
    
    parser = TranscriptParser()
    metrics = parser.parse_text(transcript)
    
    # At least one should be marked as failed due to "error" keyword
    assert metrics.failed_calls >= 1
    assert metrics.total_tool_calls == 3
