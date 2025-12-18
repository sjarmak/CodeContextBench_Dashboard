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
from typing import Dict, Optional, List

try:
    from harbor.agents.installed.base import BaseInstalledAgent, ExecInput
    from harbor.models.agent.context import AgentContext
    from harbor.environments.base import BaseEnvironment
except ImportError:
    # Fall back to stub implementation for development
    from ._harbor_base import BaseInstalledAgent, ExecInput, AgentContext
    BaseEnvironment = None  # Not needed in stub


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
    
    def create_run_agent_commands(self, instruction: str) -> List[ExecInput]:
        """Create commands to run agent and capture git diff patch.
        
        This method orchestrates:
        1. Repository directory discovery (from /task/task.toml or /workspace)
        2. Git baseline capture
        3. Agent execution with explicit system prompt requiring task completion
        4. Code changes validation (must be non-empty)
        5. Patch extraction via git diff
        
        Args:
            instruction: The task instruction to pass to the agent
            
        Returns:
            List of ExecInput commands for Harbor to execute
        """
        
        # System prompt: Explicit requirement that agent must complete task
        SYSTEM_PROMPT = """You are an expert coding agent. You MUST complete this coding task.

CRITICAL REQUIREMENTS:
1. This is NOT interactive - you cannot ask for approval or wait for human input
2. You MUST make actual code changes to solve the problem
3. Do NOT write placeholder code, pseudo-code, or incomplete solutions
4. Work until the task is complete, including validating your solution
5. Run tests to verify your implementation works
6. Do NOT say "here's what I would do" - actually DO it

Your goal is to implement the fix and pass all tests. Complete the task."""
        
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
        
        # Combine system prompt with instruction
        enhanced_instruction = f"{SYSTEM_PROMPT}\n\n---\n\n{instruction}"
        
        # Get agent-specific command
        agent_cmd = self.get_agent_command(enhanced_instruction, "$REPO_DIR")
        
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

# VALIDATE: Code changes must exist
if [ ! -s /logs/agent/patch.diff ]; then
    echo "ERROR: No code changes detected (patch.diff is empty)"
    echo "Agent execution did not produce code modifications"
    exit 1
fi

echo "✓ Patch saved to /logs/agent/patch.diff"
echo "✓ Code changes validated (non-empty)"
"""
        
        # Save system prompt for analysis
        prompt_cmd = f"""
mkdir -p /logs/agent
cat > /logs/agent/system_prompt.txt << 'EOF'
{SYSTEM_PROMPT}
EOF
"""
        
        return [
            ExecInput(
                command=prompt_cmd + "\n" + full_command,
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
