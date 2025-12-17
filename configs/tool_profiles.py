"""Tool capability profiles for different agent configurations.

Defines which tools are available in different benchmark variants:
- baseline: No code search tools
- sourcegraph_mcp: With Sourcegraph MCP server integration
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ToolProfile:
    """Configuration for available tools in an agent setup."""
    
    name: str
    description: str
    tools: List[str]
    environment_vars: dict
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "environment_vars": self.environment_vars,
        }


# Baseline: No code search augmentation
BASELINE_PROFILE = ToolProfile(
    name="baseline",
    description="Claude Code without Sourcegraph tools",
    tools=[
        "file_read",
        "file_write",
        "file_list",
        "bash_execute",
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "",
        "SOURCEGRAPH_URL": "",
    },
)

# With Sourcegraph MCP
SOURCEGRAPH_MCP_PROFILE = ToolProfile(
    name="sourcegraph-mcp",
    description="Claude Code with Sourcegraph MCP server",
    tools=[
        "file_read",
        "file_write",
        "file_list",
        "bash_execute",
        "sourcegraph_search",  # Via MCP
        "sourcegraph_context",  # Via MCP
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "${SRC_ACCESS_TOKEN}",
        "SOURCEGRAPH_URL": "${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}",
    },
)

PROFILES = {
    "baseline": BASELINE_PROFILE,
    "sourcegraph-mcp": SOURCEGRAPH_MCP_PROFILE,
}


def get_profile(name: str) -> ToolProfile:
    """Get a tool profile by name.
    
    Args:
        name: Profile identifier ("baseline" or "sourcegraph-mcp")
        
    Returns:
        ToolProfile object
        
    Raises:
        ValueError: If profile not found
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name}. Available: {list(PROFILES.keys())}")
    return PROFILES[name]
