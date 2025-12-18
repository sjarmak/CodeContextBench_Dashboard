"""Generate Sourcegraph MCP configuration file for Claude Code.

Creates a .mcp.json configuration that Claude Code auto-discovers and uses
to connect to Sourcegraph Deep Search via Model Context Protocol (MCP).

Usage in agent or Dockerfile:
    from agents.sourcegraph_mcp_config_generator import create_mcp_config
    
    # In agent
    config_path = create_mcp_config("/workspace")
    
    # In Dockerfile RUN command
    python3 -c "from agents.sourcegraph_mcp_config_generator import create_mcp_config; create_mcp_config('/workspace')"
"""

import json
import os
from pathlib import Path
from typing import Optional


def create_mcp_config(workspace_dir: str | Path = "/workspace") -> Optional[str]:
    """Create .mcp.json configuration for Sourcegraph MCP server.
    
    Reads Sourcegraph credentials from environment variables and writes
    .mcp.json to the workspace directory. Claude Code auto-discovers this
    file on startup and connects to the configured MCP server.
    
    Environment variables:
    - SOURCEGRAPH_MCP_URL: URL to Sourcegraph MCP endpoint
      (default: https://sourcegraph.sourcegraph.com/.api/mcp/v1)
    - SOURCEGRAPH_ACCESS_TOKEN: Sourcegraph API token for authentication
    
    Args:
        workspace_dir: Directory to write .mcp.json to (default: /workspace)
        
    Returns:
        Path to .mcp.json file if created successfully, None if MCP not configured
        
    Raises:
        FileNotFoundError: If workspace_dir doesn't exist
        PermissionError: If cannot write to workspace_dir
    """
    mcp_url = os.environ.get("SOURCEGRAPH_MCP_URL")
    mcp_token = os.environ.get("SOURCEGRAPH_ACCESS_TOKEN")
    
    # Silently skip if MCP not configured
    if not mcp_url or not mcp_token:
        print("ℹ️  Sourcegraph MCP not configured (SOURCEGRAPH_MCP_URL or SOURCEGRAPH_ACCESS_TOKEN missing)")
        return None
    
    workspace_path = Path(workspace_dir)
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    mcp_config_path = workspace_path / ".mcp.json"
    
    # Build MCP configuration
    config = {
        "mcpServers": {
            "sourcegraph": {
                "type": "http",
                "url": mcp_url,
                "headers": {
                    "Authorization": f"token {mcp_token}"
                }
            }
        }
    }
    
    # Write configuration
    mcp_config_path.write_text(json.dumps(config, indent=2) + "\n")
    
    print(f"✓ Created {mcp_config_path} for Sourcegraph MCP integration")
    return str(mcp_config_path)


if __name__ == "__main__":
    # Standalone execution: create_mcp_config in current directory
    config_path = create_mcp_config(".")
    if config_path:
        print(f"Configuration written to: {config_path}")
