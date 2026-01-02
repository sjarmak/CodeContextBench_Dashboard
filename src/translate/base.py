"""Base translator interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.config.schemas import AgentConfig, MCPEndpoint


class AgentTranslator(ABC):
    """Base class for translating abstract configs to agent-specific formats."""
    
    agent_type: str = "base"
    
    @abstractmethod
    def translate(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
        output_dir: Path,
    ) -> dict[str, Path]:
        """
        Translate abstract config to agent-specific files.
        
        Args:
            config: Abstract agent configuration
            mcp_endpoints: Resolved MCP endpoint configurations
            output_dir: Directory to write output files
            
        Returns:
            Dict mapping file type to output path
        """
        pass
    
    @abstractmethod
    def get_harbor_agent_kwargs(
        self,
        config: AgentConfig,
        mcp_endpoints: list[MCPEndpoint],
    ) -> dict[str, Any]:
        """
        Get kwargs for Harbor agent instantiation.
        
        Returns configuration that can be passed to Harbor's agent system.
        """
        pass
