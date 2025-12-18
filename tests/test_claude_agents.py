"""Tests for Claude Code agent implementations."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agents.claude_agent import ClaudeCodeAgent
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent


class TestClaudeCodeAgent:
    """Tests for ClaudeCodeAgent baseline implementation."""
    
    def test_agent_initialization(self):
        """Test that ClaudeCodeAgent initializes properly."""
        agent = ClaudeCodeAgent()
        assert isinstance(agent, ClaudeCodeAgent)
    
    def test_installation_template_path_exists(self):
        """Test that installation template path is correct."""
        agent = ClaudeCodeAgent()
        template_path = agent._install_agent_template_path
        assert template_path.name == "install-claude.sh.j2"
        assert template_path.exists()
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_agent_env_with_api_key(self):
        """Test environment variables include ANTHROPIC_API_KEY."""
        agent = ClaudeCodeAgent()
        env = agent.get_agent_env()
        
        assert env["ANTHROPIC_API_KEY"] == "test-key"
        assert env["SRC_ACCESS_TOKEN"] == ""
        assert env["SOURCEGRAPH_URL"] == ""
    
    def test_get_agent_env_missing_api_key(self):
        """Test that missing ANTHROPIC_API_KEY raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            agent = ClaudeCodeAgent()
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                agent.get_agent_env()
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_agent_command_with_literal_path(self):
        """Test command generation with absolute repository path."""
        agent = ClaudeCodeAgent()
        instruction = "Fix the bug in main.py"
        repo_dir = "/workspace/repo"
        
        cmd = agent.get_agent_command(instruction, repo_dir)
        
        assert "cd /workspace/repo" in cmd
        assert "claude -p" in cmd
        assert "--output-format json" in cmd
        assert "'Fix the bug in main.py'" in cmd
        assert "tee /logs/agent/claude.txt" in cmd
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_agent_command_with_shell_variable(self):
        """Test command generation with shell variable for repo path."""
        agent = ClaudeCodeAgent()
        instruction = "Implement feature X"
        repo_dir = "$REPO_DIR"
        
        cmd = agent.get_agent_command(instruction, repo_dir)
        
        # Shell variable should not be quoted
        assert "cd $REPO_DIR" in cmd
        assert "claude -p" in cmd
        assert "'Implement feature X'" in cmd
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_get_agent_command_handles_special_characters(self):
        """Test command generation with special characters in instruction."""
        agent = ClaudeCodeAgent()
        instruction = 'Fix the bug: add error handling for $PATH=="error"'
        repo_dir = "/repo"
        
        cmd = agent.get_agent_command(instruction, repo_dir)
        
        # Instruction should be properly quoted
        assert "claude -p" in cmd
        assert "cd /repo" in cmd


class TestClaudeCodeSourcegraphMCPAgent:
    """Tests for ClaudeCodeSourcegraphMCPAgent with MCP support."""
    
    def test_agent_initialization(self):
        """Test that MCP agent initializes properly."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        assert isinstance(agent, ClaudeCodeSourcegraphMCPAgent)
    
    def test_inherits_from_claude_code_agent(self):
        """Test that MCP agent inherits from baseline."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        assert isinstance(agent, ClaudeCodeAgent)
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token"
    })
    def test_get_agent_env_with_sourcegraph(self):
        """Test environment variables include Sourcegraph MCP credentials."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        env = agent.get_agent_env()
        
        assert env["ANTHROPIC_API_KEY"] == "test-key"
        assert env["SOURCEGRAPH_ACCESS_TOKEN"] == "sgp_test-token"
        assert env["SOURCEGRAPH_MCP_URL"] == "https://sourcegraph.sourcegraph.com/.api/mcp/v1"
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token",
        "SOURCEGRAPH_MCP_URL": "https://custom.sourcegraph.com/.api/mcp/v1"
    })
    def test_get_agent_env_custom_mcp_url(self):
        """Test that custom SOURCEGRAPH_MCP_URL is respected."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        env = agent.get_agent_env()
        
        assert env["SOURCEGRAPH_MCP_URL"] == "https://custom.sourcegraph.com/.api/mcp/v1"
    
    def test_get_agent_env_missing_api_key(self):
        """Test that missing ANTHROPIC_API_KEY raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            agent = ClaudeCodeSourcegraphMCPAgent()
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                agent.get_agent_env()
    
    def test_get_agent_env_missing_sourcegraph_token(self):
        """Test that missing SRC_ACCESS_TOKEN raises ValueError."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            agent = ClaudeCodeSourcegraphMCPAgent()
            with pytest.raises(ValueError, match="SRC_ACCESS_TOKEN"):
                agent.get_agent_env()
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token"
    })
    def test_mcp_guidance_prepended_to_instruction(self):
        """Test that MCP guidance is prepended to instructions."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        instruction = "Fix the bug"
        repo_dir = "/repo"
        
        cmd = agent.get_agent_command(instruction, repo_dir)
        
        # Should include MCP guidance in the command
        assert "Model Context Protocol" in cmd
        assert "USE THE MCP TOOLS" in cmd
        assert "claude -p" in cmd
        assert "--output-format json" in cmd
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token"
    })
    def test_create_mcp_setup_script_generates_config(self):
        """Test that _create_mcp_setup_script generates valid shell script."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        script = agent._create_mcp_setup_script()
        
        # Script should create .mcp.json
        assert ".mcp.json" in script
        assert "mcpServers" in script
        assert "sourcegraph" in script
        assert "Authorization" in script
