"""Alias for BaselineClaudeCodeAgent to maintain backward compatibility.

This module provides a simple import alias so existing code using
'from agents.claude_agent import ClaudeCodeAgent' continues to work.
"""

from agents.claude_baseline_agent import BaselineClaudeCodeAgent

# Export as ClaudeCodeAgent for backward compatibility
ClaudeCodeAgent = BaselineClaudeCodeAgent

__all__ = ["ClaudeCodeAgent"]
