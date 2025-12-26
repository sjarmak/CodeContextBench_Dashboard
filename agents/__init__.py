"""Harbor agents for CodeContextBench.

Single configurable agent:
- BaselineClaudeCodeAgent: Configurable agent with optional MCP support
  - Configure via BASELINE_MCP_TYPE env var: none, sourcegraph, deepsearch
  - No MCP: Pure baseline with local tools only
  - Sourcegraph MCP: Full Sourcegraph MCP with all tools
  - Deep Search MCP: Deep Search-only MCP endpoint

SWE-agent wrapper:
- SWEAgentMCPAgent: SWE-agent with Sourcegraph MCP integration
- SWEAgentBaselineAgent: Pure SWE-agent baseline

Archived experimental agents:
- MCP variants with different prompting strategies archived to archive/agents/mcp_variants.py
"""


def __getattr__(name):
    """Lazy imports to avoid Harbor dependency at module load time."""
    if name == "BaselineClaudeCodeAgent":
        from agents.claude_baseline_agent import BaselineClaudeCodeAgent

        return BaselineClaudeCodeAgent
    if name in ("SWEAgentWrapper", "SWEAgentMCPAgent", "SWEAgentBaselineAgent"):
        from agents import swe_agent_wrapper
        return getattr(swe_agent_wrapper, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaselineClaudeCodeAgent",
    "SWEAgentMCPAgent",
    "SWEAgentBaselineAgent",
]
