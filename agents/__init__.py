"""Harbor agents for CodeContextBench.

Production agents:
- BaselineClaudeCodeAgent: Control agent without MCP
- DeepSearchFocusedAgent: MCP with aggressive Deep Search prompting
- MCPNonDeepSearchAgent: MCP with keyword/NLS search only
- FullToolkitAgent: MCP with all tools available (neutral prompting)

Deprecated:
- ClaudeCodeSourcegraphMCPAgent: Use DeepSearchFocusedAgent instead
"""

def __getattr__(name):
    """Lazy imports to avoid Harbor dependency at module load time."""
    if name == "BaselineClaudeCodeAgent":
        from agents.claude_baseline_agent import BaselineClaudeCodeAgent
        return BaselineClaudeCodeAgent
    elif name == "DeepSearchFocusedAgent":
        from agents.mcp_variants import DeepSearchFocusedAgent
        return DeepSearchFocusedAgent
    elif name == "MCPNonDeepSearchAgent":
        from agents.mcp_variants import MCPNonDeepSearchAgent
        return MCPNonDeepSearchAgent
    elif name == "FullToolkitAgent":
        from agents.mcp_variants import FullToolkitAgent
        return FullToolkitAgent
    elif name == "ClaudeCodeSourcegraphMCPAgent":
        from agents.mcp_variants import DeepSearchFocusedAgent
        return DeepSearchFocusedAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BaselineClaudeCodeAgent",
    "DeepSearchFocusedAgent",
    "MCPNonDeepSearchAgent",
    "FullToolkitAgent",
    # Deprecated: kept for backward compatibility
    "ClaudeCodeSourcegraphMCPAgent",
]
