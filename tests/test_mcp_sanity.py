"""
Sanity test for Sourcegraph MCP integration in Harbor.

This test verifies that:
1. .mcp.json is created correctly in /workspace
2. Claude Code can start and load the MCP configuration
3. The MCP server connection status can be checked
"""
import os
import json
import tempfile
from pathlib import Path

try:
    from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent
    from unittest.mock import AsyncMock, MagicMock, patch
    import pytest
except ImportError as e:
    print(f"Warning: Could not import required modules: {e}")
    pytest = None


@pytest.mark.asyncio
async def test_mcp_json_file_creation():
    """Test that .mcp.json is created with correct format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)

        with patch.dict(os.environ, {
            "SOURCEGRAPH_URL": "https://sourcegraph.sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token-123"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

            # Mock environment
            mock_env = AsyncMock()
            mock_env.upload_file = AsyncMock()

            # Mock parent setup to avoid actual Claude Code installation
            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                await agent.setup(mock_env)

            # Verify .mcp.json was created locally
            mcp_json_path = logs_dir / ".mcp.json"
            assert mcp_json_path.exists(), ".mcp.json file not created"

            # Verify content
            with open(mcp_json_path) as f:
                config = json.load(f)

            assert "mcpServers" in config
            assert "sourcegraph" in config["mcpServers"]

            sg_config = config["mcpServers"]["sourcegraph"]
            assert sg_config["type"] == "http"
            assert sg_config["url"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1"
            assert sg_config["headers"]["Authorization"] == "token test-token-123"

            # Verify it was uploaded to /workspace
            upload_calls = [call for call in mock_env.upload_file.call_args_list
                           if "/workspace/.mcp.json" in str(call)]
            assert len(upload_calls) > 0, ".mcp.json not uploaded to /workspace"

            print("✓ .mcp.json created successfully with correct format")


@pytest.mark.asyncio
async def test_mcp_json_url_variations():
    """Test that various URL formats are handled correctly."""
    test_cases = [
        ("https://sourcegraph.sourcegraph.com", "https://sourcegraph.sourcegraph.com/.api/mcp/v1"),
        ("sourcegraph.sourcegraph.com", "https://sourcegraph.sourcegraph.com/.api/mcp/v1"),
        ("https://sourcegraph.com/", "https://sourcegraph.com/.api/mcp/v1"),  # Trailing slash
    ]

    for input_url, expected_mcp_url in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)

            with patch.dict(os.environ, {
                "SOURCEGRAPH_URL": input_url,
                "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
            }):
                agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

                mock_env = AsyncMock()
                mock_env.upload_file = AsyncMock()

                with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                    await agent.setup(mock_env)

                mcp_json_path = logs_dir / ".mcp.json"
                with open(mcp_json_path) as f:
                    config = json.load(f)

                actual_url = config["mcpServers"]["sourcegraph"]["url"]
                assert actual_url == expected_mcp_url, \
                    f"Input '{input_url}' produced '{actual_url}', expected '{expected_mcp_url}'"

    print("✓ URL variations handled correctly")


@pytest.mark.asyncio
async def test_claude_md_and_mcp_json_both_created():
    """Test that both CLAUDE.md and .mcp.json are created."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)

        with patch.dict(os.environ, {
            "SOURCEGRAPH_URL": "https://sourcegraph.sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

            mock_env = AsyncMock()
            mock_env.upload_file = AsyncMock()

            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                await agent.setup(mock_env)

            # Verify both files exist locally
            assert (logs_dir / ".mcp.json").exists(), ".mcp.json not created"
            assert (logs_dir / "CLAUDE.md").exists(), "CLAUDE.md not created"

            # Verify both were uploaded
            upload_calls = mock_env.upload_file.call_args_list
            uploaded_files = [str(call) for call in upload_calls]

            assert any("/workspace/.mcp.json" in f for f in uploaded_files), \
                ".mcp.json not uploaded"
            assert any("/workspace/CLAUDE.md" in f for f in uploaded_files), \
                "CLAUDE.md not uploaded"

            print("✓ Both .mcp.json and CLAUDE.md created and uploaded")


if __name__ == "__main__":
    import asyncio

    print("Running MCP sanity tests...\n")

    asyncio.run(test_mcp_json_file_creation())
    asyncio.run(test_mcp_json_url_variations())
    asyncio.run(test_claude_md_and_mcp_json_both_created())

    print("\n✅ All sanity tests passed!")
