"""Translator for OpenHands agent."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .base import AgentTranslator
from src.config.schemas import AgentConfig, MCPEndpoint


class OpenHandsTranslator(AgentTranslator):
    """Translate abstract config to OpenHands format."""
    
    agent_type: str = "openhands"
    
    def translate(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
        output_dir: Path,
    ) -> dict[str, Path]:
        """Generate OpenHands config.toml."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_files = {}
        
        # Generate config.toml
        config_content = self._generate_config_toml(config, mcp_endpoints)
        config_path = output_dir / "config.toml"
        config_path.write_text(config_content)
        output_files["config_toml"] = config_path
        
        return output_files
    
    def _generate_config_toml(
        self,
        config: AgentConfig,
        endpoints: list[MCPEndpoint],
    ) -> str:
        """Generate config.toml content."""
        lines = [
            "[core]",
            f'workspace_base = "/workspace"',
            "",
            "[llm]",
            f'model = "{config.default_model}"',
            "",
        ]
        
        # Add MCP configuration if endpoints provided
        if endpoints:
            lines.append("[mcp]")
            for endpoint in endpoints:
                lines.append(f'[mcp.{endpoint.endpoint_id}]')
                lines.append(f'url = "{endpoint.url}"')
                lines.append(f'auth_env_var = "{endpoint.auth_env_var}"')
                lines.append("")
        
        # Add system prompt if provided
        if config.prompts.system:
            lines.append("[agent]")
            # Escape the system prompt for TOML
            escaped = config.prompts.system.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'system_prompt = """{escaped}"""')
        
        return "\n".join(lines)
    
    def get_harbor_agent_kwargs(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
    ) -> dict[str, Any]:
        """Get kwargs for Harbor OpenHands agent."""
        return {
            "model_name": config.default_model,
        }
