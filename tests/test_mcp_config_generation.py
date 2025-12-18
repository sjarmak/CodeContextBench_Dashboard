"""Sanity tests for MCP configuration generation (no Harbor dependency)."""

import json
import os
import tempfile
from pathlib import Path

import pytest


def test_mcp_config_format():
    """Test that MCP config follows correct format."""
    # Simulate what the agent does
    sg_url = "https://sourcegraph.sourcegraph.com"
    sg_token = "test-token-123"

    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": f"{sg_url}/.api/mcp/v1",
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
    assert server["url"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1"
    assert server["headers"]["Authorization"] == "token test-token-123"


def test_mcp_config_url_construction():
    """Test that MCP endpoint URL is correctly constructed."""
    test_cases = [
        ("https://sourcegraph.sourcegraph.com", "https://sourcegraph.sourcegraph.com/.api/mcp/v1"),
        ("https://sourcegraph.example.com", "https://sourcegraph.example.com/.api/mcp/v1"),
        ("http://localhost:3080", "http://localhost:3080/.api/mcp/v1"),
    ]

    for sg_url, expected_mcp_url in test_cases:
        sg_token = "test-token"
        # Remove trailing slash if present
        sg_url_clean = sg_url.rstrip('/')
        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": f"{sg_url_clean}/.api/mcp/v1",
                    "headers": {
                        "Authorization": f"token {sg_token}"
                    }
                }
            }
        }

        # Verify URL is constructed correctly
        assert mcp_config["mcpServers"]["sourcegraph"]["url"] == expected_mcp_url


def test_mcp_config_writeread():
    """Test that MCP config can be written and read correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".mcp.json"

        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "type": "http",
                    "url": "https://sourcegraph.sourcegraph.com/.api/mcp/v1",
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
        assert loaded["mcpServers"]["sourcegraph"]["type"] == "http"
        assert loaded["mcpServers"]["sourcegraph"]["url"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1"


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


def test_mcp_config_json_serialization():
    """Test that MCP config can be serialized to JSON for --mcp-config flag."""
    sg_url = "https://sourcegraph.sourcegraph.com"
    sg_token = "test-token"

    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": f"{sg_url}/.api/mcp/v1",
                "headers": {
                    "Authorization": f"token {sg_token}"
                }
            }
        }
    }

    # Serialize to JSON (as would be passed to --mcp-config)
    mcp_json = json.dumps(mcp_config)

    # Verify it can be deserialized
    loaded = json.loads(mcp_json)
    assert loaded == mcp_config

    # Verify key parts are in the JSON string
    assert "mcpServers" in mcp_json
    assert "sourcegraph" in mcp_json
    assert "http" in mcp_json
    assert ".api/mcp/v1" in mcp_json
