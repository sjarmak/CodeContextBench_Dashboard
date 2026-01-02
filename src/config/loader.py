"""
Config loader for YAML configuration files.
Handles loading, validation, inheritance (extends), and reference resolution.
"""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import TypeVar, Type

from .schemas import AgentConfig, MCPEndpoint, BenchmarkConfig, ExperimentConfig

T = TypeVar('T')


class ConfigLoader:
    """Load and validate configuration files."""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self._cache: dict[str, dict] = {}
    
    def load_yaml(self, path: Path) -> dict:
        """Load a YAML file."""
        if str(path) in self._cache:
            return self._cache[str(path)]
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        self._cache[str(path)] = data
        return data
    
    def load_agent(self, agent_id: str) -> AgentConfig:
        """Load an agent configuration."""
        path = self.config_dir / "agents" / f"{agent_id}.yaml"
        data = self.load_yaml(path)
        
        # Handle inheritance
        if data.get("extends"):
            base = self.load_agent(data["extends"])
            data = self._merge_configs(base.model_dump(), data)
        
        return AgentConfig(**data)
    
    def load_mcp_endpoint(self, endpoint_id: str) -> MCPEndpoint:
        """Load an MCP endpoint configuration."""
        path = self.config_dir / "mcp" / f"{endpoint_id}.yaml"
        data = self.load_yaml(path)
        return MCPEndpoint(**data)
    
    def load_benchmark(self, benchmark_id: str) -> BenchmarkConfig:
        """Load a benchmark configuration."""
        path = self.config_dir / "benchmarks" / f"{benchmark_id}.yaml"
        data = self.load_yaml(path)
        return BenchmarkConfig(**data)
    
    def load_experiment(self, experiment_id: str) -> ExperimentConfig:
        """Load an experiment configuration."""
        path = self.config_dir / "experiments" / f"{experiment_id}.yaml"
        data = self.load_yaml(path)
        return ExperimentConfig(**data)
    
    def list_agents(self) -> list[str]:
        """List all available agent configurations."""
        agents_dir = self.config_dir / "agents"
        if not agents_dir.exists():
            return []
        return [p.stem for p in agents_dir.glob("*.yaml") if not p.stem.startswith("_")]
    
    def list_experiments(self) -> list[str]:
        """List all experiments."""
        exp_dir = self.config_dir / "experiments"
        if not exp_dir.exists():
            return []
        return [p.stem for p in exp_dir.glob("*.yaml")]
    
    def _merge_configs(self, base: dict, override: dict) -> dict:
        """Deep merge two config dicts, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key == "extends":
                continue  # Don't include extends in result
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
