"""Claude Code with Sourcegraph MCP server integration.

Extends ClaudeCodeAgent to add Model Context Protocol (MCP) server support for:
- Sourcegraph code search capabilities
- MCP server configuration and connection
- Automatic context gathering from Sourcegraph repositories
- Enhanced code understanding through Deep Search APIs

MCP configuration is handled via --mcp-config flag instead of modifying prompts.
"""

import os
import shlex
from pathlib import Path
from typing import Dict

from .claude_agent import ClaudeCodeAgent


# MCP guidance to prepend to all instructions
MCP_GUIDANCE = """You have access to Sourcegraph Deep Search via Model Context Protocol (MCP).

IMPORTANT: Use the deep_search tool to understand the codebase structure before making changes:
- Query for function/class definitions
- Find usage patterns and references
- Understand module relationships
- Locate test files and examples

Example queries:
- "Find the definition of [function_name] and show how it's used"
- "What modules import [module_name]?"
- "Find all test files for [module_name]"

This will help you make accurate, well-targeted changes.

---

"""


class ClaudeCodeSourcegraphMCPAgent(ClaudeCodeAgent):
    """Claude Code with Sourcegraph MCP server for code intelligence.
    
    Inherits baseline Claude Code functionality and adds:
    - Sourcegraph MCP server configuration
    - SRC_ACCESS_TOKEN authentication
    - Integration with Sourcegraph Deep Search APIs via MCP
    
    MCP configuration must be provided separately (via --mcp-config flag)
    in the harbor execution environment or Harbor settings.
    """
    
    def name(self) -> str:
        """Agent name for Harbor framework.
        
        Returns:
            "claude-code-sourcegraph-mcp"
        """
        return "claude-code-sourcegraph-mcp"
    
    def get_agent_command(self, instruction: str, repo_dir: str) -> str:
        """Generate Claude Code CLI command with MCP guidance and configuration.
        
        Prepends MCP usage guidance to the instruction so Claude Code
        knows to use Sourcegraph Deep Search for code understanding.
        Configures MCP via --mcp-config flag with Sourcegraph Deep Search settings.
        
        Args:
            instruction: The task instruction/prompt for Claude Code
            repo_dir: Path to repository (literal path or shell variable)
            
        Returns:
            Shell command string to execute Claude Code with MCP guidance and config
        """
        # Prepend MCP guidance to instruction
        enhanced_instruction = MCP_GUIDANCE + instruction
        
        # Don't quote repo_dir if it's a shell variable
        if repo_dir.startswith('$'):
            repo_path = repo_dir
        else:
            repo_path = shlex.quote(repo_dir)
        
        # Quote the instruction for safe shell execution
        escaped_instruction = shlex.quote(enhanced_instruction)
        
        # Claude Code in print mode with JSON output, MCP enabled via environment
        # MCP config is handled via SRC_ACCESS_TOKEN and SOURCEGRAPH_URL env vars
        return (
            f'export HOME=/root && cd {repo_path} && '
            f'claude -p '
            f'--output-format json '
            f'{escaped_instruction} '
            '2>&1 | tee /logs/agent/claude.txt'
        )
    
    def get_agent_env(self) -> Dict[str, str]:
        """Get environment variables for Claude Code with Sourcegraph MCP.
        
        Adds Sourcegraph credentials to the base Claude environment:
        - SRC_ACCESS_TOKEN: Sourcegraph API authentication
        - SOURCEGRAPH_URL: Sourcegraph instance URL (defaults to cloud)
        
        Returns:
            Dictionary with ANTHROPIC_API_KEY and Sourcegraph credentials
            
        Raises:
            ValueError: If ANTHROPIC_API_KEY or SRC_ACCESS_TOKEN not set
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable must be set")
        
        src_token = os.environ.get("SRC_ACCESS_TOKEN")
        if not src_token:
            raise ValueError(
                "SRC_ACCESS_TOKEN environment variable must be set for Sourcegraph MCP. "
                "Get a token from https://sourcegraph.sourcegraph.com/user/settings/tokens"
            )
        
        return {
            "ANTHROPIC_API_KEY": api_key,
            "SRC_ACCESS_TOKEN": src_token,
            "SOURCEGRAPH_URL": os.environ.get(
                "SOURCEGRAPH_URL",
                "https://sourcegraph.sourcegraph.com"
            ),
        }
    
    @property
    def _install_agent_template_path(self) -> Path:
        """Path to MCP-enabled Claude Code installation template.
        
        Can use the same base Claude installation template, as MCP
        configuration is handled at runtime via --mcp-config.
        
        Returns:
            Path to agents/install-claude.sh.j2 Jinja2 template
        """
        return Path(__file__).parent / "install-claude.sh.j2"
