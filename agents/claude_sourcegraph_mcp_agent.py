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
        then runs standard Claude Code setup.
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
        else:
            self.logger.warning(
                "⚠ Sourcegraph MCP not configured. Set SOURCEGRAPH_INSTANCE "
                "and SOURCEGRAPH_ACCESS_TOKEN environment variables."
            )
        
        # Run standard Claude Code setup
        await super().setup(environment)
