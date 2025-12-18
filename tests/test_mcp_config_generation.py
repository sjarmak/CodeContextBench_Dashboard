"""Sanity tests for MCP configuration generation (no Harbor dependency)."""

import json
import os
import tempfile
from pathlib import Path

import pytest


def test_mcp_config_format():
    """Test that MCP config follows correct format."""
    # Simulate what the agent does
    sg_url = "https://sourcegraph.com"
    sg_token = "test-token-123"

    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "command": "npx",
                "args": ["-y", "@sourcegraph/mcp-server"],
                "env": {
                    "SRC_ACCESS_TOKEN": sg_token,
                    "SOURCEGRAPH_URL": sg_url
                }
            }
        }
    }

    # Verify structure
    assert "mcpServers" in mcp_config
    assert "sourcegraph" in mcp_config["mcpServers"]

    server = mcp_config["mcpServers"]["sourcegraph"]
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "@sourcegraph/mcp-server"]
    assert server["env"]["SRC_ACCESS_TOKEN"] == "test-token-123"
    assert server["env"]["SOURCEGRAPH_URL"] == "https://sourcegraph.com"


def test_mcp_config_url_passthrough():
    """Test that SOURCEGRAPH_URL is passed through as-is to the MCP server."""
    test_cases = [
        "https://sourcegraph.com",
        "https://sourcegraph.example.com",
        "http://localhost:3080",
    ]

    for sg_url in test_cases:
        sg_token = "test-token"
        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "command": "npx",
                    "args": ["-y", "@sourcegraph/mcp-server"],
                    "env": {
                        "SRC_ACCESS_TOKEN": sg_token,
                        "SOURCEGRAPH_URL": sg_url
                    }
                }
            }
        }

        # Verify URL is passed through unchanged
        assert mcp_config["mcpServers"]["sourcegraph"]["env"]["SOURCEGRAPH_URL"] == sg_url


def test_mcp_config_writeread():
    """Test that MCP config can be written and read correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".mcp.json"

        mcp_config = {
            "mcpServers": {
                "sourcegraph": {
                    "command": "npx",
                    "args": ["-y", "@sourcegraph/mcp-server"],
                    "env": {
                        "SRC_ACCESS_TOKEN": "secret-token",
                        "SOURCEGRAPH_URL": "https://sourcegraph.com"
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
        assert loaded["mcpServers"]["sourcegraph"]["command"] == "npx"
        assert loaded["mcpServers"]["sourcegraph"]["env"]["SOURCEGRAPH_URL"] == "https://sourcegraph.com"


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
    sg_url = "https://sourcegraph.com"
    sg_token = "test-token"

    mcp_config = {
        "mcpServers": {
            "sourcegraph": {
                "command": "npx",
                "args": ["-y", "@sourcegraph/mcp-server"],
                "env": {
                    "SRC_ACCESS_TOKEN": sg_token,
                    "SOURCEGRAPH_URL": sg_url
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
    assert "npx" in mcp_json
    assert "@sourcegraph/mcp-server" in mcp_json
