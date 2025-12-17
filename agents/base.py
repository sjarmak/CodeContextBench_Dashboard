"""Base class for agents that produce git diff patches via Harbor framework.

This module provides common functionality for patch-based evaluation:
- cd into repository directory
- run agent command
- capture git diff as /logs/agent/patch.diff

Designed to be generalizable for any CLI agent (Claude Code, Amp, Copilot, Cursor).
"""

import os
import shlex
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Optional

from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
from harbor.models.agent.context import AgentContext
from harbor.environments.base import BaseEnvironment


class BasePatchAgent(BaseInstalledAgent, ABC):
    """Base class for CLI agents that produce git diff patches.
    
    Subclasses must implement:
    - get_agent_command(): Return the shell command to run the agent
    - get_agent_env(): Return environment variables for the agent
    - _install_agent_template_path: Path to the Jinja2 installation script
    """
    
    @abstractmethod
    def get_agent_command(self, instruction: str, repo_dir: str) -> str:
        """Get the shell command to run the agent.
        
        Args:
            instruction: The task instruction/prompt for the agent
            repo_dir: Path to the repository directory (can be literal path or shell variable)
            
        Returns:
            Shell command string to execute the agent
        """
        pass
    
    @abstractmethod
    def get_agent_env(self) -> Dict[str, str]:
        """Get environment variables for the agent.
        
        Returns:
            Dictionary of environment variables required by the agent
        """
        pass
    
    @property
    @abstractmethod
    def _install_agent_template_path(self) -> Path:
        """Path to the Jinja2 installation script template for this agent.
        
        Returns:
            Path object pointing to a .j2 template file
        """
        pass
    
    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Create commands to run agent and capture git diff patch.
        
        This method orchestrates:
        1. Repository directory discovery (from /task/task.toml or /workspace)
        2. Git baseline capture
        3. Agent execution
        4. Patch extraction via git diff
        
        Args:
            instruction: The task instruction to pass to the agent
            
        Returns:
            List of ExecInput commands for Harbor to execute
        """
        
        # Repo discovery shell script (supports Harbor's 10figure layout)
        repo_discovery_cmd = '''
# Extract repo_path from task.toml [environment] section
if [ -f /task/task.toml ]; then
    REPO_DIR=$(grep -A5 "\\[environment\\]" /task/task.toml | grep "repo_path" | cut -d'"' -f2 | tr -d "'" | head -1)
fi

# Fallback: detect from /10figure/src (Harbor's standard layout)
if [ -z "$REPO_DIR" ] && [ -d /10figure/src ]; then
    REPO_DIR=$(find /10figure/src -maxdepth 1 -type d | grep -v "^/10figure/src$" | head -1)
fi

# Final fallback to /workspace
if [ -z "$REPO_DIR" ]; then
    REPO_DIR="/workspace"
fi
'''
        
        # Get agent-specific command
        agent_cmd = self.get_agent_command(instruction, "$REPO_DIR")
        
        # Assemble full execution script
        full_command = f"""
{repo_discovery_cmd}
echo "Repository directory: $REPO_DIR"

if [ ! -d "$REPO_DIR" ]; then
    echo "ERROR: Repository directory not found: $REPO_DIR"
    exit 1
fi

cd "$REPO_DIR" || exit 1

# Capture git baseline
BASE_SHA=$(git rev-parse HEAD)
echo "Base commit SHA: $BASE_SHA"

# Run the agent
{agent_cmd}

# Capture git diff
cd "$REPO_DIR"
echo "Capturing git diff..."
mkdir -p /logs/agent
git diff --no-color --full-index "$BASE_SHA" > /logs/agent/patch.diff
git diff --stat "$BASE_SHA" > /logs/agent/patch.stat
echo "Patch saved to /logs/agent/patch.diff"
"""
        
        return [
            ExecInput(
                command=full_command,
                env=self.get_agent_env(),
                timeout_sec=3600,  # 1 hour timeout for long-running tasks
            )
        ]
    
    def populate_context_post_run(self, context: AgentContext) -> None:
        """Populate the agent context after execution.
        
        This is called by Harbor after the agent finishes running.
        Subclasses can override to parse agent-specific output formats.
        
        Args:
            context: The AgentContext object to populate (modified in-place)
        """
        # Default: Harbor's base class handles log collection
        # Subclasses can override to parse agent-specific output
        pass
