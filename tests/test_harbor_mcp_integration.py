"""
Test Harbor + Daytona + Claude Code + Sourcegraph MCP integration.

Validates:
1. ClaudeCodeWithSourcegraphMCP agent can be imported
2. .mcp.json is correctly generated in workspace
3. Environment variables are properly read
4. Agent extends ClaudeCode correctly
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Import the custom agent
import sys
from pathlib import Path

# Add agents directory to path
agents_dir = Path(__file__).parent.parent / "agents"
if agents_dir not in sys.path:
    sys.path.insert(0, str(agents_dir))

try:
    from claude_code_with_sourcegraph_mcp import (
        ClaudeCodeWithSourcegraphMCP,
    )

    AGENT_AVAILABLE = True
except ImportError as e:
    AGENT_AVAILABLE = False
    print(f"Warning: Could not import agent: {e}")


class TestClaudeCodeWithSourcegraphMCP:
    """Test cases for ClaudeCodeWithSourcegraphMCP agent."""

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent module not available")
    def test_agent_imports(self):
        """Test that agent can be imported."""
        assert ClaudeCodeWithSourcegraphMCP is not None

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent module not available")
    def test_ensure_sourcegraph_mcp_creates_config(self):
        """Test that _ensure_sourcegraph_mcp creates .mcp.json correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)

            # Set environment variables
            os.environ["SOURCEGRAPH_MCP_URL"] = "https://sg.example.com/.api/mcp/v1"
            os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "token-secret-123"

            try:
                # Call the static method
                ClaudeCodeWithSourcegraphMCP._ensure_sourcegraph_mcp(workdir)

                # Verify .mcp.json was created
                mcp_path = workdir / ".mcp.json"
                assert mcp_path.exists(), ".mcp.json was not created"

                # Verify content
                config = json.loads(mcp_path.read_text())
                assert "mcpServers" in config
                assert "sourcegraph" in config["mcpServers"]

                sg_config = config["mcpServers"]["sourcegraph"]
                assert sg_config["type"] == "http"
                assert sg_config["url"] == "https://sg.example.com/.api/mcp/v1"
                assert "Authorization" in sg_config["headers"]
                assert sg_config["headers"]["Authorization"] == "token token-secret-123"

            finally:
                # Clean up environment
                os.environ.pop("SOURCEGRAPH_MCP_URL", None)
                os.environ.pop("SOURCEGRAPH_ACCESS_TOKEN", None)

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent module not available")
    def test_ensure_sourcegraph_mcp_skips_without_env_vars(self):
        """Test that config is not created if env vars are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)

            # Ensure env vars are NOT set
            os.environ.pop("SOURCEGRAPH_MCP_URL", None)
            os.environ.pop("SOURCEGRAPH_ACCESS_TOKEN", None)

            # Call the static method
            ClaudeCodeWithSourcegraphMCP._ensure_sourcegraph_mcp(workdir)

            # Verify .mcp.json was NOT created
            mcp_path = workdir / ".mcp.json"
            assert not mcp_path.exists(), ".mcp.json should not be created without env vars"

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent module not available")
    def test_ensure_sourcegraph_mcp_merges_existing_config(self):
        """Test that existing .mcp.json is preserved and merged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            mcp_path = workdir / ".mcp.json"

            # Create initial config with other MCP servers
            initial_config = {
                "mcpServers": {
                    "other_server": {
                        "type": "stdio",
                        "command": "some_command"
                    }
                }
            }
            mcp_path.write_text(json.dumps(initial_config))

            # Set environment variables
            os.environ["SOURCEGRAPH_MCP_URL"] = "https://sg.example.com/.api/mcp/v1"
            os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "token-secret-123"

            try:
                # Call the static method
                ClaudeCodeWithSourcegraphMCP._ensure_sourcegraph_mcp(workdir)

                # Verify config was merged (not replaced)
                config = json.loads(mcp_path.read_text())
                assert "other_server" in config["mcpServers"]
                assert "sourcegraph" in config["mcpServers"]

                # Verify other_server is unchanged
                assert config["mcpServers"]["other_server"]["command"] == "some_command"

            finally:
                os.environ.pop("SOURCEGRAPH_MCP_URL", None)
                os.environ.pop("SOURCEGRAPH_ACCESS_TOKEN", None)

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent module not available")
    def test_ensure_sourcegraph_mcp_handles_malformed_json(self):
        """Test that malformed existing .mcp.json is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workdir = Path(tmpdir)
            mcp_path = workdir / ".mcp.json"

            # Write malformed JSON
            mcp_path.write_text("{ invalid json }")

            # Set environment variables
            os.environ["SOURCEGRAPH_MCP_URL"] = "https://sg.example.com/.api/mcp/v1"
            os.environ["SOURCEGRAPH_ACCESS_TOKEN"] = "token-secret-123"

            try:
                # Call the static method (should not raise)
                ClaudeCodeWithSourcegraphMCP._ensure_sourcegraph_mcp(workdir)

                # Verify new config was written
                config = json.loads(mcp_path.read_text())
                assert "sourcegraph" in config["mcpServers"]

            finally:
                os.environ.pop("SOURCEGRAPH_MCP_URL", None)
                os.environ.pop("SOURCEGRAPH_ACCESS_TOKEN", None)
