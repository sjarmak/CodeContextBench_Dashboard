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
        assert "--dangerously-skip-permissions" in cmd
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
        """Test environment variables include Sourcegraph credentials."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        env = agent.get_agent_env()
        
        assert env["ANTHROPIC_API_KEY"] == "test-key"
        assert env["SRC_ACCESS_TOKEN"] == "sgp_test-token"
        assert env["SOURCEGRAPH_URL"] == "https://sourcegraph.sourcegraph.com"
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token",
        "SOURCEGRAPH_URL": "https://custom.sourcegraph.com"
    })
    def test_get_agent_env_custom_sourcegraph_url(self):
        """Test that custom SOURCEGRAPH_URL is respected."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        env = agent.get_agent_env()
        
        assert env["SOURCEGRAPH_URL"] == "https://custom.sourcegraph.com"
    
    def test_get_agent_env_missing_api_key(self):
        """Test that missing ANTHROPIC_API_KEY raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            agent = ClaudeCodeSourcegraphMCPAgent()
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                agent.get_agent_env()
    
    def test_get_agent_env_missing_src_token(self):
        """Test that missing SRC_ACCESS_TOKEN raises ValueError."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
            # Ensure SRC_ACCESS_TOKEN is not set
            if "SRC_ACCESS_TOKEN" in os.environ:
                del os.environ["SRC_ACCESS_TOKEN"]
            agent = ClaudeCodeSourcegraphMCPAgent()
            with pytest.raises(ValueError, match="SRC_ACCESS_TOKEN"):
                agent.get_agent_env()
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "SRC_ACCESS_TOKEN": "sgp_test-token"
    })
    def test_inherits_command_generation(self):
        """Test that MCP agent uses baseline command generation."""
        agent = ClaudeCodeSourcegraphMCPAgent()
        instruction = "Analyze the codebase"
        repo_dir = "/repo"
        
        cmd = agent.get_agent_command(instruction, repo_dir)
        
        # Should generate same command as baseline
        assert "claude -p" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--output-format json" in cmd
