"""
Abstract configuration schemas for agent, MCP, and experiment definitions.
These are framework-agnostic and get translated to agent-specific formats.
"""

from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class MCPEndpoint(BaseModel):
    """MCP endpoint definition."""
    endpoint_id: str
    display_name: str
    url: str
    auth_type: str = "token"
    auth_env_var: str = "SOURCEGRAPH_ACCESS_TOKEN"
    auth_header_format: str = "token {token}"
    tools: list[dict] = Field(default_factory=list)


class AgentPrompts(BaseModel):
    """Prompting configuration for an agent."""
    system: str = ""
    claude_md: str = ""


class AgentOverrides(BaseModel):
    """Agent-specific overrides."""
    env: dict[str, str] = Field(default_factory=dict)
    model_mapping: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Abstract agent configuration."""
    agent_id: str
    display_name: str
    description: str = ""
    extends: Optional[str] = None  # Base config to inherit from
    
    # MCP configuration
    mcp_endpoints: list[str] = Field(default_factory=list)  # References to MCP endpoint files
    mcp_tools: list[str] = Field(default_factory=list)  # Tool permissions
    
    # Prompting
    prompts: AgentPrompts = Field(default_factory=AgentPrompts)
    
    # Model configuration
    default_model: str = "anthropic/claude-haiku-4-5-20251001"
    allowed_models: list[str] = Field(default_factory=list)
    
    # Agent-specific overrides
    overrides: dict[str, AgentOverrides] = Field(default_factory=dict)


class BenchmarkTaskFilter(BaseModel):
    """Filter for selecting tasks from a benchmark."""
    limit: Optional[int] = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class BenchmarkConfig(BaseModel):
    """Benchmark configuration."""
    benchmark_id: str
    display_name: str
    description: str = ""
    source: str  # "harbor", "local", "ir-sdlc"
    
    # For Harbor datasets
    registry_url: Optional[str] = None
    dataset_name: Optional[str] = None
    dataset_version: str = "1.0"
    
    # For local benchmarks
    local_path: Optional[str] = None
    
    # Task filtering
    task_filter: BenchmarkTaskFilter = Field(default_factory=BenchmarkTaskFilter)


class ExperimentExecution(BaseModel):
    """Experiment execution settings."""
    n_attempts: int = 1
    timeout_multiplier: float = 1.0
    concurrent_trials: int = 1
    model: str = "anthropic/claude-haiku-4-5-20251001"


class ExperimentConfig(BaseModel):
    """Experiment configuration."""
    experiment_id: str
    name: str
    description: str = ""
    hypothesis: str = ""
    
    # What to compare
    agents: list[str] = Field(default_factory=list)  # References to agent configs
    benchmark: str = ""  # Reference to benchmark config
    
    # Execution settings
    execution: ExperimentExecution = Field(default_factory=ExperimentExecution)
    
    # Tracking
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    status: str = "pending"  # pending, running, completed, analyzed
