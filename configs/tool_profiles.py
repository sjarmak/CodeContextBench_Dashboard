"""Tool capability profiles for different agent configurations.

Defines which tools are available in different benchmark variants:
- none: Minimal tools (file operations only)
- search_only: Basic file + search without code intelligence
- code_intel: File + search with code intelligence features
- deep_search: Full Sourcegraph Deep Search integration via MCP
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ToolProfile:
    """Configuration for available tools in an agent setup."""
    
    name: str
    description: str
    tools: List[str]
    environment_vars: Dict[str, str]
    mcp_enabled: bool = False
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "environment_vars": self.environment_vars,
            "mcp_enabled": self.mcp_enabled,
        }


# Profile 1: None (baseline, minimal tools)
NONE_PROFILE = ToolProfile(
    name="none",
    description="Baseline: Claude Code without any code search or intelligence tools",
    tools=[
        "file_read",      # cat, head, tail
        "file_write",     # echo to files
        "file_list",      # ls, find
        "bash_execute",   # bash, sh command execution
        "git_operations", # git diff, git log, git status
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "",
        "SOURCEGRAPH_URL": "",
    },
    mcp_enabled=False,
)

# Profile 2: Search Only (basic search without code intelligence)
SEARCH_ONLY_PROFILE = ToolProfile(
    name="search_only",
    description="File operations + basic code search (no code intelligence)",
    tools=[
        "file_read",      # cat, head, tail
        "file_write",     # echo to files
        "file_list",      # ls, find
        "bash_execute",   # bash, sh command execution
        "git_operations", # git diff, git log, git status
        "basic_search",   # Pattern matching, grep-like search
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "${SRC_ACCESS_TOKEN}",
        "SOURCEGRAPH_URL": "${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}",
    },
    mcp_enabled=False,
)

# Profile 3: Code Intel (search + code intelligence features)
CODE_INTEL_PROFILE = ToolProfile(
    name="code_intel",
    description="File operations + search + code intelligence (symbol search, definitions, references)",
    tools=[
        "file_read",           # cat, head, tail
        "file_write",          # echo to files
        "file_list",           # ls, find
        "bash_execute",        # bash, sh command execution
        "git_operations",      # git diff, git log, git status
        "basic_search",        # Pattern matching, grep-like search
        "symbol_search",       # Find symbol definitions and references
        "code_navigation",     # Jump to definition, find references
        "semantic_search",     # Semantic code search (type-aware, scope-aware)
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "${SRC_ACCESS_TOKEN}",
        "SOURCEGRAPH_URL": "${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}",
    },
    mcp_enabled=True,
)

# Profile 4: Deep Search (full Sourcegraph Deep Search via MCP)
DEEP_SEARCH_PROFILE = ToolProfile(
    name="deep_search",
    description="Full Sourcegraph Deep Search integration via MCP server",
    tools=[
        "file_read",              # cat, head, tail
        "file_write",             # echo to files
        "file_list",              # ls, find
        "bash_execute",           # bash, sh command execution
        "git_operations",         # git diff, git log, git status
        "basic_search",           # Pattern matching, grep-like search
        "symbol_search",          # Find symbol definitions and references
        "code_navigation",        # Jump to definition, find references
        "semantic_search",        # Semantic code search (type-aware, scope-aware)
        "sourcegraph_deep_search", # MCP: Advanced Deep Search with context
        "sourcegraph_context",     # MCP: Gather codebase context
        "sourcegraph_insights",    # MCP: Code quality insights
    ],
    environment_vars={
        "SRC_ACCESS_TOKEN": "${SRC_ACCESS_TOKEN}",
        "SOURCEGRAPH_URL": "${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}",
        "MCP_CONFIG": "${MCP_CONFIG:-/etc/mcp/config.json}",
    },
    mcp_enabled=True,
)

# Registry of all profiles
PROFILES = {
    "none": NONE_PROFILE,
    "search_only": SEARCH_ONLY_PROFILE,
    "code_intel": CODE_INTEL_PROFILE,
    "deep_search": DEEP_SEARCH_PROFILE,
}


def get_profile(name: str) -> ToolProfile:
    """Get a tool profile by name.
    
    Args:
        name: Profile identifier ("none", "search_only", "code_intel", "deep_search")
        
    Returns:
        ToolProfile object
        
    Raises:
        ValueError: If profile not found
    """
    if name not in PROFILES:
        available = list(PROFILES.keys())
        raise ValueError(f"Unknown profile: {name}. Available: {available}")
    return PROFILES[name]


def list_profiles() -> List[str]:
    """List all available profile names.
    
    Returns:
        Sorted list of profile identifiers
    """
    return sorted(PROFILES.keys())


def get_profile_info(name: str) -> dict:
    """Get detailed information about a profile.
    
    Args:
        name: Profile identifier
        
    Returns:
        Dictionary with profile name, description, tools, and MCP status
        
    Raises:
        ValueError: If profile not found
    """
    profile = get_profile(name)
    return {
        "name": profile.name,
        "description": profile.description,
        "tools": profile.tools,
        "tool_count": len(profile.tools),
        "mcp_enabled": profile.mcp_enabled,
        "environment_vars": list(profile.environment_vars.keys()),
    }


def get_mcp_profiles() -> List[str]:
    """Get list of profiles that have MCP enabled.
    
    Returns:
        List of profile names with MCP support
    """
    return [name for name, profile in PROFILES.items() if profile.mcp_enabled]


if __name__ == "__main__":
    # Example usage
    import json
    
    print("Available Tool Profiles:")
    print("=" * 60)
    
    for profile_name in list_profiles():
        info = get_profile_info(profile_name)
        print(f"\n{profile_name.upper()}")
        print(f"  Description: {info['description']}")
        print(f"  Tools ({info['tool_count']}): {', '.join(info['tools'])}")
        print(f"  MCP Enabled: {info['mcp_enabled']}")
        print(f"  Env Vars: {', '.join(info['environment_vars'])}")
    
    print("\n" + "=" * 60)
    print(f"MCP-Enabled Profiles: {', '.join(get_mcp_profiles())}")
