"""Sanity tests for ClaudeCodeSourcegraphMCPAgent MCP configuration."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from agents.mcp_variants import DeepSearchFocusedAgent
    # Backward compat alias for deprecated agent path
    from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent
except ImportError as e:
    pytest.skip(f"Harbor not available: {e}", allow_module_level=True)


@pytest.mark.asyncio
async def test_mcp_config_in_commands():
    """Test that MCP config is injected via --mcp-config flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)

        # Set environment variables
        with patch.dict(os.environ, {
            "SOURCEGRAPH_URL": "https://sourcegraph.sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token-123"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

            # Mock the parent's create_run_agent_commands to return a simple claude command
            with patch.object(agent.__class__.__bases__[0], 'create_run_agent_commands') as mock_parent:
                from harbor.agents.installed.base import ExecInput
                mock_parent.return_value = [
                    ExecInput(command="claude -p 'test instruction'", env={})
                ]

                commands = agent.create_run_agent_commands("test instruction")

                # Verify --mcp-config flag was injected
                assert len(commands) > 0
                claude_cmd = commands[0].command
                assert "--mcp-config" in claude_cmd

                # Extract and verify the JSON config
                import re
                match = re.search(r"--mcp-config '({.*?})' ", claude_cmd)
                assert match, "MCP config not found in command"

                config = json.loads(match.group(1))
                assert "mcpServers" in config
                assert "sourcegraph" in config["mcpServers"]

                server = config["mcpServers"]["sourcegraph"]
                assert server["type"] == "http"
                assert server["url"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1"
                assert server["headers"]["Authorization"] == "token test-token-123"


@pytest.mark.asyncio
async def test_claude_md_uploaded_before_super_setup():
    """Test that CLAUDE.md is uploaded BEFORE calling super().setup()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)

        with patch.dict(os.environ, {
            "SOURCEGRAPH_URL": "https://sourcegraph.sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

            mock_env = AsyncMock()
            mock_env.upload_file = AsyncMock()

            setup_called = False

            async def mock_setup(env):
                nonlocal setup_called
                setup_called = True
                assert mock_env.upload_file.called, "upload_file() not called before super().setup()"

            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=lambda: mock_setup):
                await agent.setup(mock_env)

            assert setup_called, "super().setup() was not called"

            # Verify CLAUDE.md was uploaded
            upload_calls = [call for call in mock_env.upload_file.call_args_list
                           if "/workspace/CLAUDE.md" in str(call)]
            assert len(upload_calls) > 0, "CLAUDE.md not uploaded to /workspace"


@pytest.mark.asyncio
async def test_sourcegraph_url_to_mcp_endpoint():
    """Test that SOURCEGRAPH_URL is correctly converted to MCP endpoint URL."""
    test_cases = [
        ("https://sourcegraph.sourcegraph.com", "https://sourcegraph.sourcegraph.com/.api/mcp/v1"),
        ("https://sourcegraph.example.com", "https://sourcegraph.example.com/.api/mcp/v1"),
        ("http://localhost:3080", "http://localhost:3080/.api/mcp/v1"),
        ("sourcegraph.sourcegraph.com", "https://sourcegraph.sourcegraph.com/.api/mcp/v1"),  # Test protocol addition
    ]

    for sg_url, expected_mcp_url in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)

            with patch.dict(os.environ, {
                "SOURCEGRAPH_URL": sg_url,
                "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
            }):
                agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

                # Mock the parent's create_run_agent_commands
                with patch.object(agent.__class__.__bases__[0], 'create_run_agent_commands') as mock_parent:
                    from harbor.agents.installed.base import ExecInput
                    mock_parent.return_value = [
                        ExecInput(command="claude -p 'test'", env={})
                    ]

                    commands = agent.create_run_agent_commands("test")

                    # Extract config from command
                    import re
                    claude_cmd = commands[0].command
                    match = re.search(r"--mcp-config '({.*?})' ", claude_cmd)
                    config = json.loads(match.group(1))

                    # Verify MCP endpoint URL is constructed correctly
                    actual_url = config["mcpServers"]["sourcegraph"]["url"]
                    assert actual_url == expected_mcp_url, f"URL {sg_url} produced {actual_url}, expected {expected_mcp_url}"


@pytest.mark.asyncio
async def test_claude_md_created():
    """Test that CLAUDE.md is created with MCP instructions."""
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

            # Verify CLAUDE.md was created
            claude_path = logs_dir / "CLAUDE.md"
            assert claude_path.exists(), "CLAUDE.md not created"

            content = claude_path.read_text()
            assert "Sourcegraph MCP Available" in content
            assert "Deep Search" in content

            # Verify it was uploaded to workspace
            upload_calls = [call for call in mock_env.upload_file.call_args_list
                           if "/workspace/CLAUDE.md" in str(call)]
            assert len(upload_calls) > 0, "CLAUDE.md not uploaded to /workspace"


@pytest.mark.asyncio
async def test_missing_credentials_warning():
    """Test that agent skips MCP config when credentials missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)

        with patch.dict(os.environ, {"SOURCEGRAPH_URL": "", "SOURCEGRAPH_ACCESS_TOKEN": ""}):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)

            # Test create_run_agent_commands returns parent's commands unchanged
            with patch.object(agent.__class__.__bases__[0], 'create_run_agent_commands') as mock_parent:
                from harbor.agents.installed.base import ExecInput
                expected_commands = [ExecInput(command="claude -p 'test'", env={})]
                mock_parent.return_value = expected_commands

                commands = agent.create_run_agent_commands("test")

                # Should return parent's commands unchanged (no --mcp-config injection)
                assert commands == expected_commands
                assert "--mcp-config" not in commands[0].command

            # Test setup doesn't create files
            mock_env = AsyncMock()

            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                await agent.setup(mock_env)

            # Verify no CLAUDE.md was created
            assert not (logs_dir / "CLAUDE.md").exists()

            # Verify no upload calls
            assert not mock_env.upload_file.called
