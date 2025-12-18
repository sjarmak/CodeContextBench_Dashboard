"""Harbor-compatible Claude Code agent with Sourcegraph Deep Search MCP support."""

import json
import os
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment


class ClaudeCodeSourcegraphMCPAgent(ClaudeCode):
    """Claude Code with Sourcegraph MCP server pre-configured.
    
    Extends Harbor's built-in ClaudeCode agent to add Sourcegraph Deep Search
    via MCP (Model Context Protocol) server.
    
    Environment Variables:
    - SOURCEGRAPH_INSTANCE: Sourcegraph instance URL (e.g., sourcegraph.com)
    - SOURCEGRAPH_ACCESS_TOKEN: Authentication token for Sourcegraph API
    
    The MCP server is configured to use HTTP protocol and will be available
    to Claude for Deep Search queries during task execution.
    """
    
    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup Claude Code with Sourcegraph MCP configuration.
        
        Creates MCP configuration file and uploads it to the task environment,
        along with instructions for using the Sourcegraph MCP.
        Then runs standard Claude Code setup.
        """
        
        # Get Sourcegraph credentials from environment
        sg_instance = os.environ.get("SOURCEGRAPH_INSTANCE")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
        
        if sg_instance and sg_token:
            # Create MCP configuration for Sourcegraph
            mcp_config = {
                "mcpServers": {
                    "sourcegraph": {
                        "type": "http",
                        "url": f"https://{sg_instance}/.api/mcp/v1",
                        "headers": {
                            "Authorization": f"token {sg_token}"
                        }
                    }
                }
            }
            
            # Write config to logs directory
            config_path = self.logs_dir / ".mcp.json"
            with open(config_path, "w") as f:
                json.dump(mcp_config, f, indent=2)
            
            # Upload to task working directory
            await environment.upload_file(
                source_path=config_path,
                target_path="/app/.mcp.json"
            )
            
            self.logger.info(f"✓ Configured Sourcegraph MCP: {sg_instance}")
            
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
            
            # Upload to task working directory
            await environment.upload_file(
                source_path=instructions_path,
                target_path="/app/CLAUDE.md"
            )
            
            self.logger.info(f"✓ Created Sourcegraph MCP instructions")
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_INSTANCE "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
