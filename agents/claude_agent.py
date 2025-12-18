"""Claude Code baseline agent (no Sourcegraph tools).

Extends BasePatchAgent with Claude Code CLI integration for:
- Command generation using `claude` CLI with `-p` (print) mode
- API key management (ANTHROPIC_API_KEY)
- Structured JSON output for programmatic parsing
- Harbor-compatible installation and execution

Does not include Sourcegraph code search tools.
"""

import os
import shlex
from pathlib import Path
from typing import Dict

from .base import BasePatchAgent


class ClaudeCodeAgent(BasePatchAgent):
    """Claude Code baseline agent (no Sourcegraph augmentation).
    
    Executes coding tasks using Claude Code CLI in print mode with:
    - JSON output format for structured results
    - Permission skipping for unattended execution
    - Standard environment variables (no Sourcegraph credentials)
    """
    
    def name(self) -> str:
        """Agent name for Harbor framework.
        
        Returns:
            "claude-code"
        """
        return "claude-code"
    
    def get_agent_command(self, instruction: str, repo_dir: str) -> str:
        """Generate Claude Code CLI command for task execution.
        
        Uses `-p` (print) mode with JSON output for:
        - Non-interactive, deterministic behavior
        - Structured output parsing
        - Script-friendly execution in Harbor containers
        
        Args:
            instruction: The task instruction/prompt for Claude Code
            repo_dir: Path to repository (literal path or shell variable like $REPO_DIR)
            
        Returns:
            Shell command string to execute Claude Code
        """
        # Don't quote repo_dir if it's a shell variable
        if repo_dir.startswith('$'):
            repo_path = repo_dir
        else:
            repo_path = shlex.quote(repo_dir)
        
        # Quote the instruction for safe shell execution
        escaped_instruction = shlex.quote(instruction)
        
        # Claude Code in print mode with JSON output
        # In Docker (running as root), use HOME=/root to fix permission issues
        return (
            f'export HOME=/root && cd {repo_path} && '
            f'claude -p '
            f'--output-format json '
            f'{escaped_instruction} '
            '2>&1 | tee /logs/agent/claude.txt'
        )
    
    def get_agent_env(self) -> Dict[str, str]:
        """Get environment variables for Claude Code baseline.
        
        Returns:
            Dictionary with ANTHROPIC_API_KEY and empty Sourcegraph credentials
            
        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set")
        
        return {
            "ANTHROPIC_API_KEY": api_key,
            "SRC_ACCESS_TOKEN": "",
            "SOURCEGRAPH_URL": "",
        }
    
    @property
    def _install_agent_template_path(self) -> Path:
        """Path to Claude Code installation template.
        
        Returns:
            Path to agents/install-claude.sh.j2 Jinja2 template
        """
        return Path(__file__).parent / "install-claude.sh.j2"
