"""Harbor-compatible Claude Code agent with Sourcegraph Deep Search MCP support."""

import json
import os
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.environments.base import BaseEnvironment


class ClaudeCodeSourcegraphMCPAgent(ClaudeCode):
    """Claude Code with Sourcegraph MCP server pre-configured.
    
    Extends Harbor's built-in ClaudeCode agent to add Sourcegraph Deep Search
    via MCP (Model Context Protocol) server.
    
    Environment Variables:
    - SOURCEGRAPH_URL: Sourcegraph instance URL (e.g., https://sourcegraph.sourcegraph.com)
    - SOURCEGRAPH_ACCESS_TOKEN: Authentication token for Sourcegraph API

    The MCP server is configured to use HTTP transport via Sourcegraph's hosted MCP endpoint
    and will be available to Claude for Deep Search queries during task execution.
    """
    
    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Create Claude commands.

        MCP configuration is handled via /workspace/.mcp.json file created during setup().
        Claude Code will automatically discover and load this file when it starts.
        """
        # Just return parent's commands - MCP config is in .mcp.json file
        return super().create_run_agent_commands(instruction)

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup Claude Code environment.

        MCP configuration is handled in create_run_agent_commands() via --mcp-config flag.
        This method just creates CLAUDE.md instructions and runs parent setup.
        """

        # Get Sourcegraph credentials to check if MCP will be available
        sg_url = os.environ.get("SOURCEGRAPH_URL", "")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")

        if sg_url and sg_token:
            # Ensure URL has protocol
            if not sg_url.startswith(('http://', 'https://')):
                sg_url = f"https://{sg_url}"

            # Ensure URL doesn't end with trailing slash
            sg_url = sg_url.rstrip('/')

            # Create .mcp.json with Sourcegraph MCP configuration
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"{sg_url}/.api/mcp/v1",
                        "headers": {
                            "Authorization": f"token {sg_token}"
                        }
                    }
                }
            }

            mcp_config_path = self.logs_dir / ".mcp.json"
            with open(mcp_config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)

            # Upload .mcp.json to project root
            await environment.upload_file(
                source_path=mcp_config_path,
                target_path="/workspace/.mcp.json"
            )

            self.logger.info(f"✓ Created .mcp.json with Sourcegraph MCP configuration")

            # Create CLAUDE.md with instructions for using Sourcegraph MCP
            claude_instructions = """# Sourcegraph MCP Available

You have access to **Sourcegraph MCP** via the Sourcegraph server. Use it to understand the codebase instead of relying on grep or manual file exploration.

## How to Use

When you need to understand code patterns, find relevant files, or explore the repository structure:
1. Use the Sourcegraph MCP tools to query the codebase intelligently
2. Ask questions about code patterns, dependencies, and implementations
3. Leverage Deep Search for complex queries across the entire codebase

## Available Tools

The Sourcegraph MCP server provides tools for:
- Searching and exploring code
- Understanding code structure and dependencies
- Finding usage patterns and implementations
- Analyzing code relationships

This is much more efficient than grep for understanding large codebases.
"""

            instructions_path = self.logs_dir / "CLAUDE.md"
            with open(instructions_path, "w") as f:
                f.write(claude_instructions)

            # Upload CLAUDE.md to project root
            await environment.upload_file(
                source_path=instructions_path,
                target_path="/workspace/CLAUDE.md"
            )

            self.logger.info(f"✓ Created CLAUDE.md with Sourcegraph MCP instructions")
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_URL "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
