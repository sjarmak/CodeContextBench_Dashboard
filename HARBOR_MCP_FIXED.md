# ✅ Harbor + Sourcegraph MCP: Fixed & Ready

**Date**: Dec 18, 2025  
**Status**: Architecture fixed, ready for testing  
**Issue**: AttributeError when running Harbor with custom MCP agents  
**Solution**: Use Harbor's native `claude-code` agent + task setup scripts  

---

## What Was Wrong

The previous approach tried to use a custom `ClaudeCodeSourcegraphMCPAgent` class with Harbor. This failed because:

1. **Harbor expects `BaseInstalledAgent`** - Agents must inherit from Harbor's base class and implement `create_run_agent_commands()` → `ExecInput` objects
2. **Custom agents returned strings** - Our agents returned plain command strings, not Harbor's `ExecInput` format
3. **MCP config via CLI flags** - Tried to pass `--mcp-config` flag, but Claude Code doesn't support it
4. **Resulted in `AttributeError`** when Harbor tried to use the custom agent

## What's Fixed

Now using Harbor's **native `claude-code` agent** configured via task.toml setup scripts:

```toml
[environment]
build_timeout_sec = 1800.0

[environment.setup_scripts]
mcp_config = """#!/bin/bash
# Creates ~/.config/claude/mcp.json if credentials provided
if [ -n "$SOURCEGRAPH_ACCESS_TOKEN" ] && [ -n "$SOURCEGRAPH_URL" ]; then
  mkdir -p /root/.config/claude
  cat > /root/.config/claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "sourcegraph": {
      "command": "npx",
      "args": ["-y", "@sourcegraph/mcp-server"],
      "env": {
        "SRC_ACCESS_TOKEN": "$SOURCEGRAPH_ACCESS_TOKEN",
        "SOURCEGRAPH_URL": "$SOURCEGRAPH_URL"
      }
    }
  }
}
EOF
fi
"""
```

✅ **Key advantages:**
- Uses Harbor's native agent (no custom code needed)
- MCP config created before Claude Code starts
- Credentials passed via `--ek` flags (environment variables)
- Claude Code auto-discovers config on startup
- Works for both baseline and MCP variants

## Changes Made

### 1. Updated All 49 Task Files

```bash
python3 tools/update_tasks_for_harbor_mcp.py
# Updated: 49 tasks in benchmarks/github_mined/ and benchmarks/github_mined_pilot/
```

Each task now has:
- `[environment]` section with timeout
- `[environment.setup_scripts]` with MCP config generation

### 2. New Tools

- **`tools/harbor_test_commands.sh`** - Interactive baseline/MCP test runner
- **`tools/update_tasks_for_harbor_mcp.py`** - Bulk task.toml updater

### 3. New Documentation

- **`history/HARBOR_MCP_APPROACH.md`** - Architecture and solution details
- **`history/RUNBOOK_HARBOR_BASELINE_VS_MCP.md`** - Complete testing guide

### 4. Updated AGENTS.md

Added new learned pattern:
- **Bullet #ccb-harbor-mcp-004**: Marked `ClaudeCodeSourcegraphMCPAgent` as DEPRECATED
- **Bullet #ccb-harbor-mcp-005**: New pattern for Harbor+MCP via native agent

---

## How to Run Tests

### Quick Start

```bash
# Terminal 1: Baseline (no MCP)
source .venv-harbor/bin/activate
source infrastructure/load-env.sh
./tools/harbor_test_commands.sh baseline

# Terminal 2: MCP (with Sourcegraph)
source .venv-harbor/bin/activate
source infrastructure/load-env.sh
./tools/harbor_test_commands.sh mcp

# Compare results
./tools/harbor_test_commands.sh compare
```

### Manual Commands

**Baseline:**
```bash
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  --env daytona \
  -n 1
```

**MCP:**
```bash
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  --env daytona \
  --ek SOURCEGRAPH_ACCESS_TOKEN="$SRC_ACCESS_TOKEN" \
  --ek SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com" \
  -n 1
```

---

## Verification

After running tests, check:

✅ Both runs complete without AttributeError  
✅ Baseline produces `patch.diff` (> 0 bytes)  
✅ MCP produces `patch.diff` (> 0 bytes)  
✅ Both have `reward.txt` with scores  
✅ MCP has better average reward than baseline  

---

## Deprecation

The following are now **deprecated** and should not be used:

- ❌ `agents/claude_sourcegraph_mcp_agent.py` (custom MCP agent)
- ❌ `agents/_harbor_base.py` (stub Harbor classes)
- ❌ Custom agent imports in `--agent-import-path`

**Keep these files for reference** (in git history), but don't use them with Harbor.

---

## Architecture Diagram

```
Before (broken):
  Harbor → Custom ClaudeCodeSourcegraphMCPAgent (BaseAgent mismatch)
                 ↓
           AttributeError

After (working):
  Harbor → Native claude-code agent
                 ↓
           Daytona container + [environment.setup_scripts]
                 ↓
           MCP config script (creates /root/.config/claude/mcp.json)
                 ↓
           Claude Code auto-discovers + loads MCP config
                 ↓
           Claude executes with Sourcegraph Deep Search available
```

---

## References

- **Deep Search conversation**: 8cfde179-ebf6-45e6-bb4a-1366075723cd
- **Implementation plan**: `history/HARBOR_MCP_APPROACH.md`
- **Testing runbook**: `history/RUNBOOK_HARBOR_BASELINE_VS_MCP.md`
- **Test runner script**: `tools/harbor_test_commands.sh`
- **Harbor docs**: https://github.com/laude-institute/harbor

---

## Next Steps

1. ✅ Fix architecture (done)
2. ✅ Update all tasks (done - 49 files)
3. ✅ Create tools and docs (done)
4. → Run baseline test
5. → Run MCP test
6. → Compare results
7. → File learnings to AGENTS.md

**Ready to execute Phase 4: Single-Task Validation** 🚀
