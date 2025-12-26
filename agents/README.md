# CodeContextBench Agents

This directory contains a single configurable Harbor agent for evaluating coding tasks with optional MCP support.

## Quick Reference

| Agent | Class | File | Purpose |
| --- | --- | --- | --- |
| **Baseline** | `BaselineClaudeCodeAgent` | `claude_baseline_agent.py` | Configurable agent with optional MCP support |

## Configuration

The baseline agent supports three MCP configurations via the `BASELINE_MCP_TYPE` environment variable:

| Mode | Value | MCP Config | CLAUDE.md | Use Case |
| --- | --- | --- | --- | --- |
| **Pure Baseline** | `none` (default) | No mcp.json | No CLAUDE.md | Local tools only, no MCP |
| **Sourcegraph MCP** | `sourcegraph` | Full Sourcegraph endpoint | All tools (keyword, NLS, Deep Search) | Full MCP access |
| **Deep Search MCP** | `deepsearch` | Deep Search endpoint | Deep Search only | Focused semantic search |

## Usage

### Pure Baseline (No MCP)

```bash
harbor run --path <task_path> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### With Sourcegraph MCP

```bash
export BASELINE_MCP_TYPE=sourcegraph
export SOURCEGRAPH_URL=https://sourcegraph.example.com
export SOURCEGRAPH_ACCESS_TOKEN=<your-token-here>

harbor run --path <task_path> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### With Deep Search MCP

```bash
export BASELINE_MCP_TYPE=deepsearch
export SOURCEGRAPH_URL=https://sourcegraph.example.com
export SOURCEGRAPH_ACCESS_TOKEN=<your-token-here>

harbor run --path <task_path> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

## File Structure

```
agents/
├── claude_baseline_agent.py   # Single configurable agent
├── __init__.py                 # Module exports
└── README.md                   # This file
```

## Implementation Details

### BaselineClaudeCodeAgent

**File:** `claude_baseline_agent.py`

Claude Code with autonomous implementation mode and optional MCP configuration.

**Key Features:**

- Extends Harbor's built-in `ClaudeCode` agent
- Enables autonomous operation via `FORCE_AUTO_BACKGROUND_TASKS=1` and `ENABLE_BACKGROUND_TASKS=1`
- Full tool access: Bash, Read, Edit, Write, Grep, Glob
- Configurable MCP support via environment variable

**MCP Configuration Details:**

**No MCP (`BASELINE_MCP_TYPE=none` or unset):**
- No mcp.json created
- No CLAUDE.md created
- Uses local tools only (Grep, Glob, Read, Edit, Write, Bash)

**Sourcegraph MCP (`BASELINE_MCP_TYPE=sourcegraph`):**
- Creates mcp.json pointing to `{SOURCEGRAPH_URL}/.api/mcp/v1`
- Creates CLAUDE.md with neutral instructions for all Sourcegraph tools:
  - `sg_keyword_search` - Fast exact string matching
  - `sg_nls_search` - Natural language semantic search
  - `sg_deepsearch` - Deep semantic search with context understanding

**Deep Search MCP (`BASELINE_MCP_TYPE=deepsearch`):**
- Creates mcp.json pointing to Deep Search endpoint
- Creates CLAUDE.md with focused Deep Search instructions
- Only `sg_deepsearch` available

## Archived Experimental Agents

Previous MCP variant agents with different prompting strategies have been archived to `archive/agents/mcp_variants.py`:
- `StrategicDeepSearchAgent` - Strategic Deep Search usage prompting
- `DeepSearchFocusedAgent` - Aggressive Deep Search prompting
- `MCPNonDeepSearchAgent` - MCP without Deep Search
- `FullToolkitAgent` - Neutral prompting with all tools

These were used for A/B testing different prompting approaches and are preserved for reference.
