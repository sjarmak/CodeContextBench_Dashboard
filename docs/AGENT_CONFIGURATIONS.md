# Agent Configurations for SWE-bench Testing

This document describes all agent configurations available for SWE-bench evaluation with Daytona.

## Quick Test

Test all configurations:
```bash
./scripts/test_swebench_agents.sh [task-name]
```

Default task: `astropy__astropy-12907` (known working oracle test)

## Agent Categories

### 1. Oracle Agent (Harbor Built-in)

**Purpose:** Golden solution baseline - always uses the correct patch from SWE-bench dataset.

| Agent | Import Path | MCP | Status |
|-------|-------------|-----|--------|
| Oracle | `oracle` | N/A | ✅ Tested (reward=1.0) |

**Usage:**
```bash
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent oracle \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

### 2. Harbor ClaudeCode (Built-in)

**Purpose:** Harbor's native ClaudeCode agent for baseline comparison.

| Agent | Import Path | MCP | Configuration |
|-------|-------------|-----|---------------|
| ClaudeCode Baseline | `claudecode` | None | Default |
| ClaudeCode + MCP | `claudecode` | Via config | TBD: Harbor MCP config |

**Usage:**
```bash
# Baseline (no MCP)
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent claudecode \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

**Note:** MCP configuration for built-in ClaudeCode needs Harbor-specific mechanism (not yet documented).

### 3. SWE-Agent Wrapper

**Purpose:** Wrap SWE-agent for Harbor compatibility with optional MCP integration.

| Agent | Import Path | MCP | Configuration |
|-------|-------------|-----|---------------|
| SWE-Agent Baseline | `agents.swe_agent_wrapper:SWEAgentBaselineAgent` | None | `enable_mcp=False` |
| SWE-Agent + MCP | `agents.swe_agent_wrapper:SWEAgentMCPAgent` | Sourcegraph | `enable_mcp=True` |

**Requirements:**
- SWE-agent installed at `~/SWE-bench_Pro-os/SWE-agent` (or set `SWE_AGENT_PATH`)
- For MCP: `SOURCEGRAPH_ACCESS_TOKEN` and `SOURCEGRAPH_URL` environment variables

**Usage:**
```bash
# Baseline (no MCP)
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.swe_agent_wrapper:SWEAgentBaselineAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# With Sourcegraph MCP
export SOURCEGRAPH_ACCESS_TOKEN="your-token"
export SOURCEGRAPH_URL="https://sourcegraph.com"
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.swe_agent_wrapper:SWEAgentMCPAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

### 4. Baseline ClaudeCode Agent (Our Custom)

**Purpose:** Our custom Claude Code agent with configurable MCP via environment variable.

| Agent | Import Path | MCP Type | Env Var |
|-------|-------------|----------|---------|
| Baseline (no MCP) | `agents.claude_baseline_agent:BaselineClaudeCodeAgent` | None | `BASELINE_MCP_TYPE=none` |
| + Sourcegraph | `agents.claude_baseline_agent:BaselineClaudeCodeAgent` | Full Sourcegraph | `BASELINE_MCP_TYPE=sourcegraph` |
| + Deep Search | `agents.claude_baseline_agent:BaselineClaudeCodeAgent` | Deep Search only | `BASELINE_MCP_TYPE=deepsearch` |

**Configuration:**
- `BASELINE_MCP_TYPE=none` - No MCP integration (pure baseline)
- `BASELINE_MCP_TYPE=sourcegraph` - Full Sourcegraph MCP (keyword, NLS, Deep Search)
- `BASELINE_MCP_TYPE=deepsearch` - Deep Search-only MCP endpoint

**Usage:**
```bash
# No MCP
BASELINE_MCP_TYPE=none harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# With Sourcegraph MCP
export SOURCEGRAPH_ACCESS_TOKEN="your-token"
BASELINE_MCP_TYPE=sourcegraph harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# Deep Search only
BASELINE_MCP_TYPE=deepsearch harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

### 5. MCP Variants (Our Custom)

**Purpose:** Specialized MCP configurations for ablation studies.

| Agent | Import Path | MCP Configuration |
|-------|-------------|-------------------|
| Strategic Deep Search | `agents.mcp_variants:StrategicDeepSearchAgent` | Full MCP with strategic Deep Search usage |
| Deep Search Focused | `agents.mcp_variants:DeepSearchFocusedAgent` | Deep Search-only endpoint |
| Non-Deep Search | `agents.mcp_variants:MCPNonDeepSearchAgent` | Keyword + NLS only (no Deep Search) |
| Full Toolkit | `agents.mcp_variants:FullToolkitAgent` | All MCP tools available |

**Requirements:**
- `SOURCEGRAPH_ACCESS_TOKEN` and `SOURCEGRAPH_URL` environment variables

**Usage:**
```bash
# Strategic Deep Search
export SOURCEGRAPH_ACCESS_TOKEN="your-token"
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# Deep Search Focused
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.mcp_variants:DeepSearchFocusedAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# Non-Deep Search (keyword/NLS only)
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.mcp_variants:MCPNonDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1

# Full Toolkit
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent agents.mcp_variants:FullToolkitAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

## Environment Variables Summary

### Required (All Agents)
- `ANTHROPIC_API_KEY` - Claude API key
- `DAYTONA_API_KEY` - Daytona cloud VMs access

### Optional (MCP Agents)
- `SOURCEGRAPH_ACCESS_TOKEN` - Sourcegraph API token
- `SOURCEGRAPH_URL` - Sourcegraph instance URL (default: https://sourcegraph.com)

### Agent-Specific
- `BASELINE_MCP_TYPE` - For BaselineClaudeCodeAgent (none|sourcegraph|deepsearch)
- `SWE_AGENT_PATH` - For SWE-agent wrapper (default: ~/SWE-bench_Pro-os/SWE-agent)

## Test Matrix

| Agent | No MCP | Sourcegraph MCP | Deep Search MCP |
|-------|--------|-----------------|-----------------|
| Oracle | ✅ (N/A) | N/A | N/A |
| Harbor ClaudeCode | ⏳ | ⏳ | ⏳ |
| SWE-Agent | ⏳ | ⏳ | N/A |
| Baseline ClaudeCode | ⏳ | ⏳ | ⏳ |
| Strategic Deep Search | N/A | ✅ (built-in) | N/A |
| Deep Search Focused | N/A | N/A | ✅ (built-in) |
| Non-Deep Search | N/A | ✅ (no DS) | N/A |
| Full Toolkit | N/A | ✅ (built-in) | N/A |

Legend:
- ✅ Tested and working
- ⏳ Pending test
- N/A Not applicable

## Running Tests

### Test Single Configuration
```bash
source .env.local
export ANTHROPIC_API_KEY DAYTONA_API_KEY SOURCEGRAPH_ACCESS_TOKEN

harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent <agent-import-path> \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona -n 1
```

### Test All Configurations
```bash
./scripts/test_swebench_agents.sh astropy__astropy-12907
```

### Check Results
```bash
# View all rewards
find jobs/swebench-agent-tests-* -name "reward.txt" -exec echo {} \; -exec cat {} \; -exec echo \;

# View specific test log
cat jobs/swebench-agent-tests-*/oracle/harbor.log
```

## Troubleshooting

### Agent Not Found
```
Error: Agent 'agents.foo:BarAgent' not found
```
**Solution:** Check import path and ensure agent class exists in the file.

### MCP Connection Failed
```
Error: Failed to connect to MCP server
```
**Solution:** Verify `SOURCEGRAPH_ACCESS_TOKEN` is set and valid.

### QEMU Segfault (Should Not Happen with Daytona)
```
qemu: uncaught target signal 11 (Segmentation fault)
```
**Solution:** Ensure `--env daytona` flag is used (not local Docker).

### Timeout
```
Error: Task timeout after 3600 seconds
```
**Solution:** SWE-bench tasks can be complex. Increase timeout if needed, or check agent logs for infinite loops.

## Performance Notes

- **Daytona:** 6x faster than local Docker, no QEMU issues
- **Oracle:** ~69 seconds for test task (golden solution)
- **Full agents:** Expect 5-30 minutes depending on task complexity
- **Deep Search:** Adds 1-5 minutes for code exploration

## Next Steps

1. Run `./scripts/test_swebench_agents.sh` to validate all configurations
2. Document test results in test matrix above
3. Update CLAUDE.md with preferred agent configurations
4. Create dashboard presets for common agent configurations
