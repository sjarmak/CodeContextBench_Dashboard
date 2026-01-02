"""Translator for OpenCode agent."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .base import AgentTranslator
from src.config.schemas import AgentConfig, MCPEndpoint


class OpenCodeTranslator(AgentTranslator):
    """Translate abstract config to OpenCode format."""
    
    agent_type: str = "opencode"
    
    def translate(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Generate opencode.jsonc and skills/ files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_files = {}
        
        # Generate opencode.jsonc
        opencode_config = self._generate_opencode_jsonc(config, mcp_endpoints)
        config_path = output_dir / "opencode.jsonc"
        config_path.write_text(json.dumps(opencode_config, indent=2))
        output_files["opencode_jsonc"] = config_path
        
        # Generate skills if prompts provided
        if config.prompts.claude_md:  # Reuse claude_md as skill content
            skills_dir = output_dir / "skills"
            skills_dir.mkdir(exist_ok=True)
            skill_path = skills_dir / "sourcegraph.md"
            skill_path.write_text(config.prompts.claude_md)
            output_files["skill"] = skill_path
        
        return output_files
    
    def _generate_opencode_jsonc(
        self,
        config: AgentConfig,
        endpoints: list[MCPEndpoint],
    ) -> dict:
        """Generate opencode.jsonc content."""
        opencode_config = {
            "$schema": "https://opencode.ai/schema/config.json",
            "model": self._map_model(config.default_model, config),
        }
        
        # Add MCP servers
        if endpoints:
            mcp_servers = {}
            for endpoint in endpoints:
                mcp_servers[endpoint.endpoint_id] = {
                    "type": "http",
                    "url": endpoint.url,
                }
            opencode_config["mcpServers"] = mcp_servers
        
        return opencode_config
    
    def _map_model(self, model: str, config: AgentConfig) -> str:
        """Map model name to OpenCode format."""
        opencode_overrides = config.overrides.get("opencode")
        if opencode_overrides and opencode_overrides.model_mapping:
            return opencode_overrides.model_mapping.get(model, model)
        
        # Default mappings
        default_mappings = {
            "anthropic/claude-haiku-4-5-20251001": "claude-3-5-haiku",
            "anthropic/claude-sonnet-4-20250514": "claude-sonnet-4",
        }
        return default_mappings.get(model, model)
    
    def get_harbor_agent_kwargs(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
    ) -> dict[str, Any]:
        """Get kwargs for Harbor OpenCode agent."""
        return {
            "model": self._map_model(config.default_model, config),
        }
