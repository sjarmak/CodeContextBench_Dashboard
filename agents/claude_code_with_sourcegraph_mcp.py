"""
Claude Code agent with Sourcegraph MCP (Model Context Protocol) server integration.

This agent extends the built-in claude-code agent by injecting a Sourcegraph MCP
configuration (.mcp.json) into the task workspace before execution, enabling
Claude Code to access Sourcegraph Deep Search for improved codebase understanding.

Usage:
    harbor run \
      --path <task_path> \
      --env daytona \
      --agent-import-path agents.claude_code_with_sourcegraph_mcp:ClaudeCodeWithSourcegraphMCP \
      --model anthropic/claude-haiku-4-5 \
      -n 1

Environment variables:
    SOURCEGRAPH_MCP_URL: MCP server URL (e.g. https://sourcegraph.com/.api/mcp/v1)
    SOURCEGRAPH_ACCESS_TOKEN: Access token for Sourcegraph API
"""

import json
import os
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode


class ClaudeCodeWithSourcegraphMCP(ClaudeCode):
    """
    Claude Code agent with Sourcegraph MCP server for Deep Search integration.
    
    Injects a project-scoped .mcp.json configuration into the task workspace
    so Claude Code can access Sourcegraph Deep Search during execution.
    """

    def run(self, task, **kwargs):
        """
        Run task with Sourcegraph MCP configuration injected.
        
        Before calling the parent run() method, this ensures that .mcp.json
        exists in the task workspace with proper Sourcegraph credentials.
        """
        # Get the working directory where Claude Code will execute
        workdir = Path(kwargs.get("cwd", "."))
        
        # Inject Sourcegraph MCP configuration
        self._ensure_sourcegraph_mcp(workdir)
        
        # Execute the task with parent class
        return super().run(task, **kwargs)

    @staticmethod
    def _ensure_sourcegraph_mcp(workdir: Path) -> None:
        """
        Ensure Sourcegraph MCP server configuration exists in workspace.
        
        Creates or merges a project-scoped .mcp.json file in the working directory
        with Sourcegraph MCP server configuration, allowing Claude Code to access
        Deep Search capabilities.
        
        Configuration format follows Sourcegraph's documented .mcp.json schema:
        https://docs.sourcegraph.com/mcp/configuration
        
        Args:
            workdir: Path to the task workspace where .mcp.json should be written
        """
        # Get MCP configuration from environment
        url = os.environ.get("SOURCEGRAPH_MCP_URL")
        token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
        
        # Silently skip if not configured
        if not url or not token:
            return

        workdir = Path(workdir)
        mcp_path = workdir / ".mcp.json"
        
        # Read existing config if present, otherwise start with empty dict
        cfg = {}
        if mcp_path.exists():
            try:
                cfg = json.loads(mcp_path.read_text())
            except Exception:
                # If existing .mcp.json is malformed, start fresh
                cfg = {}

        # Ensure mcpServers section exists
        cfg.setdefault("mcpServers", {})
        
        # Add/update Sourcegraph MCP server configuration
        cfg["mcpServers"]["sourcegraph"] = {
            "type": "http",
            "url": url,
            "headers": {"Authorization": f"token {token}"},
        }
        
        # Write configuration to file (prettified JSON for readability)
        mcp_path.write_text(json.dumps(cfg, indent=2) + "\n")
