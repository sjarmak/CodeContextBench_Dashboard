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
    - SOURCEGRAPH_INSTANCE: Sourcegraph instance URL (e.g., sourcegraph.com)
    - SOURCEGRAPH_ACCESS_TOKEN: Authentication token for Sourcegraph API
    
    The MCP server is configured to use HTTP protocol and will be available
    to Claude for Deep Search queries during task execution.
    """
    
    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Create Claude commands with MCP config injected via --mcp-config flag.
        
        Gets parent's commands and injects --mcp-config with Sourcegraph MCP config.
        """
        # Get Sourcegraph credentials
        sg_instance = os.environ.get("SOURCEGRAPH_INSTANCE", "").replace("https://", "").replace("http://", "")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")
        
        if not (sg_instance and sg_token):
            # No MCP config available, use parent's commands as-is
            self.logger.warning("⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_INSTANCE and SOURCEGRAPH_ACCESS_TOKEN.")
            return super().create_run_agent_commands(instruction)
        
        # Create MCP config
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
        
        mcp_config_json = json.dumps(mcp_config)
        
        # Get parent's commands
        parent_commands = super().create_run_agent_commands(instruction)
        
        # Inject --mcp-config flag into claude command
        modified_commands = []
        for cmd in parent_commands:
            if cmd.command and "claude" in cmd.command:
                # Find "claude" in the command and inject --mcp-config after it
                modified_cmd = cmd.command.replace(
                    "claude ",
                    f"claude --mcp-config '{mcp_config_json}' "
                )
                modified_commands.append(
                    ExecInput(
                        command=modified_cmd,
                        env=cmd.env or {},
                    )
                )
                self.logger.info(f"✓ Injected Sourcegraph MCP via --mcp-config flag")
            else:
                modified_commands.append(cmd)
        
        return modified_commands

    async def setup(self, environment: BaseEnvironment) -> None:
        """Setup Claude Code environment.
        
        MCP configuration is handled in create_run_agent_commands() via --mcp-config flag.
        This method just creates CLAUDE.md instructions and runs parent setup.
        """
        
        # Get Sourcegraph credentials to check if MCP will be available
        sg_instance = os.environ.get("SOURCEGRAPH_INSTANCE", "").replace("https://", "").replace("http://", "")
        sg_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN", "")
        
        if sg_instance and sg_token:
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
            
            # Upload to task working directory root
            await environment.upload_file(
                source_path=instructions_path,
                target_path="/workspace/CLAUDE.md"
            )
            
            self.logger.info(f"✓ Created CLAUDE.md with Sourcegraph MCP instructions")
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_INSTANCE "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
