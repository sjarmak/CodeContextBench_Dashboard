"""DEPRECATED: Use agents.mcp_variants.DeepSearchFocusedAgent instead.

This module is kept for backward compatibility only. It imports and re-exports
ClaudeCodeSourcegraphMCPAgent as an alias to DeepSearchFocusedAgent.

Migration guide:
  OLD: --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent
  NEW: --agent-import-path agents.mcp_variants:DeepSearchFocusedAgent

See AGENTS.md for complete agent documentation and comparison.
"""

from agents.mcp_variants import DeepSearchFocusedAgent

# Compatibility alias - points to the new implementation
ClaudeCodeSourcegraphMCPAgent = DeepSearchFocusedAgent

__all__ = ["ClaudeCodeSourcegraphMCPAgent"]
