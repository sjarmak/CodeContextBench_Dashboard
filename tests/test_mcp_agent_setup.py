"""Sanity tests for ClaudeCodeSourcegraphMCPAgent MCP configuration."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent
except ImportError as e:
    pytest.skip(f"Harbor not available: {e}", allow_module_level=True)


@pytest.mark.asyncio
async def test_mcp_config_creation():
    """Test that MCP config is created with correct format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        
        # Set environment variables
        with patch.dict(os.environ, {
            "SOURCEGRAPH_INSTANCE": "sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token-123"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)
            
            # Create mock environment
            mock_env = AsyncMock()
            mock_env.exec = AsyncMock(return_value=MagicMock(return_code=0, stderr=""))
            mock_env.upload_file = AsyncMock()
            
            # Don't actually call super().setup(), just test our logic
            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                await agent.setup(mock_env)
            
            # Verify config file was created
            config_path = logs_dir / ".mcp.json"
            assert config_path.exists(), "MCP config file not created"
            
            # Verify config format
            with open(config_path) as f:
                config = json.load(f)
            
            assert "mcpServers" in config
            assert "sourcegraph" in config["mcpServers"]
            
            server = config["mcpServers"]["sourcegraph"]
            assert server["type"] == "http"
            assert server["url"] == "https://sourcegraph.com/.api/mcp/v1"
            assert server["headers"]["Authorization"] == "token test-token-123"


@pytest.mark.asyncio
async def test_mcp_config_uploaded_before_super_setup():
    """Test that MCP config is uploaded BEFORE calling super().setup()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        
        with patch.dict(os.environ, {
            "SOURCEGRAPH_INSTANCE": "sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)
            
            mock_env = AsyncMock()
            mock_env.exec = AsyncMock(return_value=MagicMock(return_code=0, stderr=""))
            mock_env.upload_file = AsyncMock()
            
            setup_called = False
            
            async def mock_setup(env):
                nonlocal setup_called
                setup_called = True
                assert mock_env.exec.called, "environment.exec() not called before super().setup()"
                assert mock_env.upload_file.called, "upload_file() not called before super().setup()"
            
            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=lambda: mock_setup):
                await agent.setup(mock_env)
            
            assert setup_called, "super().setup() was not called"
            
            # Verify exec was called to create the directory and file
            assert mock_env.exec.called
            exec_call_args = mock_env.exec.call_args[0][0]
            assert "mkdir -p /root/.claude" in exec_call_args
            assert "cat > /root/.claude/mcp.json" in exec_call_args


@pytest.mark.asyncio
async def test_mcp_config_no_double_https():
    """Test that Sourcegraph instance URL doesn't get double https://."""
    test_cases = [
        ("sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
        ("https://sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
        ("http://sourcegraph.com", "https://sourcegraph.com/.api/mcp/v1"),
    ]
    
    for instance_input, expected_url in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            
            with patch.dict(os.environ, {
                "SOURCEGRAPH_INSTANCE": instance_input,
                "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
            }):
                agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)
                
                mock_env = AsyncMock()
                mock_env.exec = AsyncMock(return_value=MagicMock(return_code=0, stderr=""))
                mock_env.upload_file = AsyncMock()
                
                with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                    await agent.setup(mock_env)
                
                config_path = logs_dir / ".mcp.json"
                with open(config_path) as f:
                    config = json.load(f)
                
                actual_url = config["mcpServers"]["sourcegraph"]["url"]
                assert actual_url == expected_url, f"Input {instance_input} produced {actual_url}, expected {expected_url}"


@pytest.mark.asyncio
async def test_claude_md_created():
    """Test that CLAUDE.md is created with MCP instructions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        
        with patch.dict(os.environ, {
            "SOURCEGRAPH_INSTANCE": "sourcegraph.com",
            "SOURCEGRAPH_ACCESS_TOKEN": "test-token"
        }):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)
            
            mock_env = AsyncMock()
            mock_env.exec = AsyncMock(return_value=MagicMock(return_code=0, stderr=""))
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
    """Test that agent logs warning when credentials missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logs_dir = Path(tmpdir)
        
        with patch.dict(os.environ, {"SOURCEGRAPH_INSTANCE": "", "SOURCEGRAPH_ACCESS_TOKEN": ""}):
            agent = ClaudeCodeSourcegraphMCPAgent(logs_dir=logs_dir)
            
            mock_env = AsyncMock()
            
            with patch.object(agent.__class__.__bases__[0], 'setup', new_callable=AsyncMock):
                await agent.setup(mock_env)
            
            # Verify no files were created
            assert not (logs_dir / ".mcp.json").exists()
            assert not (logs_dir / "CLAUDE.md").exists()
            
            # Verify no exec/upload calls
            assert not mock_env.exec.called
            assert not mock_env.upload_file.called
