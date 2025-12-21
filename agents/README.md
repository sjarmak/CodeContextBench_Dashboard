# CodeContextBench Agents

This directory contains Harbor-compatible agent implementations for evaluating coding tasks with and without Sourcegraph MCP.

## Quick Reference

| Agent | Class | File | Purpose |
|-------|-------|------|---------|
| **Baseline** | `BaselineClaudeCodeAgent` | `claude_baseline_agent.py` | Claude Code in autonomous mode, NO MCP |
| **Deep Search Focused** | `DeepSearchFocusedAgent` | `mcp_variants.py` | MCP + aggressive Deep Search prompting |
| **MCP No Deep Search** | `MCPNonDeepSearchAgent` | `mcp_variants.py` | MCP with keyword/NLS search only |
| **Full Toolkit** | `FullToolkitAgent` | `mcp_variants.py` | MCP with all tools, neutral prompting |

## Usage

```bash
# Baseline (no MCP)
harbor run --task <path> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent

# Deep Search focused
harbor run --task <path> \
  --agent-import-path agents.mcp_variants:DeepSearchFocusedAgent

# No Deep Search (simpler MCP tools)
harbor run --task <path> \
  --agent-import-path agents.mcp_variants:MCPNonDeepSearchAgent

# Full toolkit (neutral prompting)
harbor run --task <path> \
  --agent-import-path agents.mcp_variants:FullToolkitAgent
```

## File Structure

```
agents/
├── claude_baseline_agent.py        # Baseline agent (NO MCP)
├── mcp_variants.py                 # 3 MCP variant agents
├── claude_sourcegraph_mcp_agent.py # DEPRECATED: Compatibility shim (→ DeepSearchFocusedAgent)
├── __init__.py                     # Module exports
└── README.md                       # This file
```

## Agent Implementations

### BaselineClaudeCodeAgent

**File:** `claude_baseline_agent.py`

Claude Code with autonomous implementation mode enabled but **without Sourcegraph MCP**.

**Key Features:**
- Extends Harbor's built-in `ClaudeCode` agent
- Enables autonomous operation via `FORCE_AUTO_BACKGROUND_TASKS=1` and `ENABLE_BACKGROUND_TASKS=1`
- Full tool access: Bash, Read, Edit, Write, Grep, Glob
- No MCP/Deep Search integration

**Use for:** Baseline comparison, measuring MCP value

### MCP Variants

**File:** `mcp_variants.py`

Three variant agents to isolate the value of different MCP tool combinations:

#### 1. DeepSearchFocusedAgent

Heavily emphasizes Deep Search tool usage via prompts.

- System prompt prioritizes `sg_deepsearch` for all code understanding
- CLAUDE.md contains aggressive guidance to use Deep Search first
- Measures: Does Deep Search prompting improve outcomes?

**Use for:** Testing if Deep Search is worth recommending to agents

#### 2. MCPNonDeepSearchAgent

MCP tools (keyword/NLS search) but explicitly avoids Deep Search.

- Uses `sg_keyword_search` and `sg_nls_search` only
- Prompts warn against using Deep Search
- Measures: Are simpler MCP tools sufficient?

**Use for:** Testing if keyword/NLS search is enough without semantic search

#### 3. FullToolkitAgent

All tools available with neutral prompting - no preference for any approach.

- Neutral system prompt listing all tools equally
- No preference for Deep Search vs other tools
- Measures: What does the agent naturally choose?

**Use for:** Control variant showing agent's natural tool choice

## Configuration

### Environment Variables

All agents require:
```bash
export ANTHROPIC_API_KEY="your-claude-key"
```

MCP agents additionally require:
```bash
export SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com"
export SOURCEGRAPH_ACCESS_TOKEN="your-sourcegraph-token"
```

### Agent-Specific Options

Each variant agent can be customized by modifying the system prompts:

**Deep Search Focused:**
- `DEEP_SEARCH_SYSTEM_PROMPT` - Controls the mandatory Deep Search guidance
- `DEEP_SEARCH_CLAUDE_MD` - Guidance file emphasizing Deep Search

**No Deep Search:**
- `NON_DEEPSEARCH_SYSTEM_PROMPT` - Recommends keyword/NLS only
- `NON_DEEPSEARCH_CLAUDE_MD` - Warns against Deep Search

**Full Toolkit:**
- `NEUTRAL_SYSTEM_PROMPT` - Lists all tools equally
- `NEUTRAL_CLAUDE_MD` - Describes available tools neutrally

## Running Benchmarks

See [benchmarks/README.md](../benchmarks/README.md) for benchmark-specific agent usage.

## Testing

```bash
# Verify agents load correctly
python -c "from agents import BaselineClaudeCodeAgent; print('✓ Baseline loaded')"
python -c "from agents.mcp_variants import DeepSearchFocusedAgent; print('✓ Deep Search loaded')"

# Run integration tests
pytest tests/test_mcp_agent_setup.py -v
```

## Backward Compatibility

**Deprecated:** `ClaudeCodeSourcegraphMCPAgent` (from `claude_sourcegraph_mcp_agent.py`)

This is now an alias to `DeepSearchFocusedAgent`. Old code using it will still work but should migrate to the new variant system.

**Migration:**
```bash
# OLD (still works, but deprecated)
--agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent

# NEW (recommended)
--agent-import-path agents.mcp_variants:DeepSearchFocusedAgent
```

## Adding New Agents

To create a new agent variant:

1. Create a new class in `mcp_variants.py` extending `ClaudeCode`
2. Define system prompts and guidance files as class attributes
3. Override `setup()` to configure MCP/prompts
4. Override `create_run_agent_commands()` to enable autonomous mode
5. Export in `__init__.py`
6. Document in this README

See existing variants for patterns.

## References

- [AGENTS.md](../AGENTS.md) - Agent framework and benchmarking guide
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Development setup
- [benchmarks/README.md](../benchmarks/README.md) - Benchmark usage
