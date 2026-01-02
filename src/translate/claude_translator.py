"""Translator for Claude Code agent."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .base import AgentTranslator
from src.config.schemas import AgentConfig, MCPEndpoint


class ClaudeCodeTranslator(AgentTranslator):
    """Translate abstract config to Claude Code format."""
    
    agent_type: str = "claudecode"
    
    def translate(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Generate .mcp.json and CLAUDE.md files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_files = {}
        
        # Generate .mcp.json
        if mcp_endpoints:
            mcp_config = self._generate_mcp_json(mcp_endpoints)
            mcp_path = output_dir / ".mcp.json"
            mcp_path.write_text(json.dumps(mcp_config, indent=2))
            output_files["mcp_json"] = mcp_path
        
        # Generate CLAUDE.md
        if config.prompts.claude_md:
            claude_md_path = output_dir / "CLAUDE.md"
            claude_md_path.write_text(config.prompts.claude_md)
            output_files["claude_md"] = claude_md_path
        
        return output_files
    
    def _generate_mcp_json(self, endpoints: list[MCPEndpoint]) -> dict:
        """Generate .mcp.json content."""
        mcp_servers = {}
        
        for endpoint in endpoints:
            # The auth token will be injected at runtime from env var
            mcp_servers[endpoint.endpoint_id] = {
                "type": "http",
                "url": endpoint.url,
                "headers": {
                    "Authorization": f"token ${{env:{endpoint.auth_env_var}}}"
                }
            }
        
        return {"mcpServers": mcp_servers}
    
    def get_harbor_agent_kwargs(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
    ) -> dict[str, Any]:
        """Get kwargs for Harbor ClaudeCode agent."""
        kwargs = {}
        
        # Get Claude-specific overrides
        claude_overrides = config.overrides.get("claudecode")
        if claude_overrides:
            kwargs["env"] = claude_overrides.env
        
        # Add MCP tool permissions
        if config.mcp_tools:
            kwargs["mcp_tools"] = config.mcp_tools
        
        return kwargs
    
    def get_allowed_tools(self, config: AgentConfig) -> list[str]:
        """Get list of allowed MCP tools for --allowedTools flag."""
        tools = []
        for tool in config.mcp_tools:
            # Prefix with mcp__ for Claude Code
            if not tool.startswith("mcp__"):
                tools.append(f"mcp__sourcegraph__{tool}")
            else:
                tools.append(tool)
        return tools
