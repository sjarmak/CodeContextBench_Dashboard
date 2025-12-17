"""Claude Code with Sourcegraph MCP server integration.

Extends ClaudeCodeAgent to add Model Context Protocol (MCP) server support for:
- Sourcegraph code search capabilities
- MCP server configuration and connection
- Automatic context gathering from Sourcegraph repositories
- Enhanced code understanding through Deep Search APIs

MCP configuration is handled via --mcp-config flag instead of modifying prompts.
"""

import os
from pathlib import Path
from typing import Dict

from .claude_agent import ClaudeCodeAgent


class ClaudeCodeSourcegraphMCPAgent(ClaudeCodeAgent):
    """Claude Code with Sourcegraph MCP server for code intelligence.
    
    Inherits baseline Claude Code functionality and adds:
    - Sourcegraph MCP server configuration
    - SRC_ACCESS_TOKEN authentication
    - Integration with Sourcegraph Deep Search APIs via MCP
    
    MCP configuration must be provided separately (via --mcp-config flag)
    in the harbor execution environment or Harbor settings.
    """
    
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
