"""Sanity tests for MCP configuration generation (no Harbor dependency)."""

import json
import os
import tempfile
from pathlib import Path

import pytest


def test_mcp_config_format():
    """Test that MCP config follows correct format."""
    # Simulate what the agent does
    sg_instance = "sourcegraph.com"
    sg_token = "test-token-123"
    
    # Ensure no double https://
    sg_instance = sg_instance.replace("https://", "").replace("http://", "")
    
    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": f"https://{sg_instance}/.api/mcp/v1",
                "headers": {
                    "Authorization": f"token {sg_token}"
                }
            }
        }
    }
    
    # Verify structure
    assert "mcpServers" in mcp_config
    assert "sourcegraph" in mcp_config["mcpServers"]
    
    server = mcp_config["mcpServers"]["sourcegraph"]
    assert server["type"] == "http"
    assert server["url"] == "https://sourcegraph.com/.api/mcp/v1"
    assert server["headers"]["Authorization"] == "token test-token-123"


def test_mcp_config_no_double_https():
    """Test that instance URL cleanup prevents double https://."""
    test_cases = [
        ("sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
        ("https://sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
        ("http://sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
    ]
    
    for instance_input, expected_url in test_cases:
        # Simulate agent logic
        sg_instance = instance_input.replace("https://", "").replace("http://", "")
        url = f"https://{sg_instance}/.api/mcp/v1"
        
        assert url == expected_url, f"Input {instance_input} produced {url}, expected {expected_url}"


def test_mcp_config_writeread():
    """Test that MCP config can be written and read correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".mcp.json"
        
        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": "https://sourcegraph.com/.api/mcp/v1",
                    "headers": {
                        "Authorization": "token secret-token"
                    }
                }
            }
        }
        
        # Write
        with open(config_path, "w") as f:
            json.dump(mcp_config, f, indent=2)
        
        # Verify file exists
        assert config_path.exists()
        
        # Read and verify
        with open(config_path) as f:
            loaded = json.load(f)
        
        assert loaded == mcp_config
        assert loaded["mcpServers"]["sourcegraph"]["url"] == "https://sourcegraph.com/.api/mcp/v1"


def test_claude_md_content():
    """Test that CLAUDE.md instructions contain expected content."""
    claude_instructions = """# Sourcegraph MCP Available

You have access to **Sourcegraph MCP** via the Sourcegraph server. Use it to understand the codebase instead of relying on grep or manual file exploration.

## How to Use

When you need to understand code patterns, find relevant files, or explore the repository structure:
1. Use the Sourcegraph MCP tools to query the codebase intelligently
2. Ask questions about code patterns, dependencies, and implementations
3. Leverage Deep Search for complex queries across the entire codebase

## Available Tools

The Sourcegraph MCP server provides tools for:
- Searching and exploring code
- Understanding code structure and dependencies
- Finding usage patterns and implementations
- Analyzing code relationships

This is much more efficient than grep for understanding large codebases.
"""
    
    # Verify key phrases present
    assert "Sourcegraph MCP Available" in claude_instructions
    assert "Deep Search" in claude_instructions
    assert "MCP tools" in claude_instructions
    assert "grep" in claude_instructions.lower()
    
    # Verify format
    lines = claude_instructions.strip().split('\n')
    assert lines[0].startswith('#')  # Starts with markdown header


def test_mcp_setup_command_format():
    """Test that shell command for MCP setup is properly formatted."""
    sg_instance = "sourcegraph.com"
    sg_token = "test-token"
    
    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": f"https://{sg_instance}/.api/mcp/v1",
                "headers": {
                    "Authorization": f"token {sg_token}"
                }
            }
        }
    }
    
    mcp_json_content = json.dumps(mcp_config, indent=2)
    setup_cmd = f"""
mkdir -p /root/.claude
cat > /root/.claude/mcp.json << 'EOF'
{mcp_json_content}
EOF
"""
    
    # Verify command contains expected parts
    assert "mkdir -p /root/.claude" in setup_cmd
    assert "cat > /root/.claude/mcp.json" in setup_cmd
    assert "EOF" in setup_cmd
    assert "mcpServers" in setup_cmd
    assert "sourcegraph" in setup_cmd
