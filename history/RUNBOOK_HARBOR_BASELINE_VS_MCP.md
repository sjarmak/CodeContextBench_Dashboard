# Harbor: Baseline vs MCP Testing Runbook

**Date**: Dec 18, 2025  
**Updated**: After Harbor+MCP architecture fix  
**Status**: Ready to execute  

## Overview

Test whether Sourcegraph MCP improves Claude Code's performance on real coding tasks.

- **Baseline**: Claude Code with no Sourcegraph (native Harbor agent)
- **MCP**: Claude Code with Sourcegraph Deep Search via MCP (native Harbor agent + setup scripts)
- **Benchmark**: 25 PyTorch cross-module bug fixes (github_mined)

## Setup (One-Time)

```bash
cd /Users/sjarmak/CodeContextBench

# 1. Activate Harbor environment
source .venv-harbor/bin/activate

# 2. Load credentials
source infrastructure/load-env.sh

# 3. Verify you have required API keys
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "SRC_ACCESS_TOKEN: ${SRC_ACCESS_TOKEN:0:10}..."

# 4. Verify all tasks are updated with MCP setup
python3 tools/update_tasks_for_harbor_mcp.py
# Should show: "Results: 0 updated, 54 skipped" (all tasks already have sections)
```

## Running Tests

### Option 1: Interactive (Recommended)

```bash
# Terminal 1: Run baseline
./tools/harbor_test_commands.sh baseline

# Terminal 2: Run MCP (while baseline is running)
./tools/harbor_test_commands.sh mcp

# When both complete:
./tools/harbor_test_commands.sh compare
```

### Option 2: Manual Commands

**Baseline (no MCP):**
```bash
TIMESTAMP=$(date +%Y-%m-%d__%H-%M-%S)
JOB_DIR="jobs/claude-baseline-github_mined-$TIMESTAMP"

harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  --env daytona \
  -n 1 \
  --jobs-dir "$JOB_DIR"
```

**MCP (with Sourcegraph):**
```bash
TIMESTAMP=$(date +%Y-%m-%d__%H-%M-%S)
JOB_DIR="jobs/claude-mcp-github_mined-$TIMESTAMP"

harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  --env daytona \
  --ek SOURCEGRAPH_ACCESS_TOKEN="$SRC_ACCESS_TOKEN" \
  --ek SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com" \
  -n 1 \
  --jobs-dir "$JOB_DIR"
```

## Monitoring

While tests run:

```bash
# Watch job directory
watch -n 5 "ls -la jobs/ | tail -5"

# Monitor specific task (once it starts)
TASK_DIR=$(find jobs/claude-*/*/sgt-001__* -type d 2>/dev/null | head -1)
if [ -n "$TASK_DIR" ]; then
  watch -n 2 "ls -la $TASK_DIR/logs/ 2>/dev/null | head -10"
fi

# Check final results
ls -la $BASELINE_JOB_DIR/*/sgt-001__*/logs/verifier/
ls -la $MCP_JOB_DIR/*/sgt-001__*/logs/verifier/
```

## Validation Checklist

After both runs complete, verify:

- [ ] **Baseline created patch.diff** (> 0 bytes)
  ```bash
  find jobs/claude-baseline-*/*/sgt-001__*/logs/verifier -name "*.diff" -exec wc -c {} \;
  ```

- [ ] **MCP created patch.diff** (> 0 bytes)
  ```bash
  find jobs/claude-mcp-*/*/sgt-001__*/logs/verifier -name "*.diff" -exec wc -c {} \;
  ```

- [ ] **Both have reward scores**
  ```bash
  echo "Baseline reward:"; cat jobs/claude-baseline-*/*/sgt-001__*/logs/verifier/reward.txt
  echo "MCP reward:"; cat jobs/claude-mcp-*/*/sgt-001__*/logs/verifier/reward.txt
  ```

- [ ] **Both test outputs exist**
  ```bash
  diff <(ls -la jobs/claude-baseline-*/*/sgt-001__*/logs/verifier) \
       <(ls -la jobs/claude-mcp-*/*/sgt-001__*/logs/verifier)
  ```

- [ ] **Token counts are recorded** (in any manifest/metrics files)

## Expected Results

### Baseline Performance
- Completes: 30-40% (agent can read code but lacks context)
- Reward: 0.0-1.0 per task
- Code changes: Present, thread safety patterns may be missing

### MCP Performance (Target)
- Completes: 50-70% (Sourcegraph helps locate thread safety patterns)
- Reward: Higher average (0.5-1.0 per task)
- Code changes: Present, thread safety patterns more likely included
- Deep Search queries: Logged in Harbor stdout

## Post-Run Analysis

```bash
# Compare results side-by-side
BASELINE_DIR=$(ls -dt jobs/claude-baseline-github_mined-* | head -1)
MCP_DIR=$(ls -dt jobs/claude-mcp-github_mined-* | head -1)

echo "=== Baseline ==="
cat "$BASELINE_DIR/result.json" | python3 -m json.tool

echo "=== MCP ==="
cat "$MCP_DIR/result.json" | python3 -m json.tool

# Extract patch files for manual review
echo "=== Baseline patch ==="
find "$BASELINE_DIR"/*/sgt-*/logs/verifier -name "full.diff" -exec head -50 {} \;

echo "=== MCP patch ==="
find "$MCP_DIR"/*/sgt-*/logs/verifier -name "full.diff" -exec head -50 {} \;
```

## Troubleshooting

### No code changes (patch.diff = 0 bytes)

**Issue**: Agent ran but didn't modify files.

**Cause**: 
- Insufficient task context for agent to work
- Agent didn't use Deep Search or file exploration tools
- System prompt not applied correctly

**Fix**:
- Check Harbor logs for Claude Code output
- Verify system prompt in run output
- Check if Sourcegraph MCP is being used (look for Deep Search queries in stdout)

### AttributeError in results

**Issue**: Custom agent integration failed.

**Cause**: Old code trying to use ClaudeCodeSourcegraphMCPAgent (deprecated).

**Fix**: 
- Tasks already updated with proper setup scripts
- Don't use custom agents; only use `--agent claude-code`
- Verify task.toml has `[environment]` and `[environment.setup_scripts]` sections

### Tests hang or timeout

**Issue**: PyTorch clone takes 15+ minutes on first run.

**Cause**: Large repository (10GB+).

**Fix**:
- First run takes longer due to full clone (expected)
- Subsequent runs reuse cached Docker layers (faster)
- Use `-n 1` concurrency for initial testing
- Set reasonable timeout in task.toml (1800 sec = 30 min)

### MCP not being used

**Issue**: Harbor ran but Sourcegraph wasn't accessed.

**Cause**: 
- SOURCEGRAPH_ACCESS_TOKEN not set via --ek
- MCP setup script failed silently
- Claude Code didn't load mcp.json

**Fix**:
```bash
# Verify env var passed through
harbor run ... --ek SOURCEGRAPH_ACCESS_TOKEN="$SRC_ACCESS_TOKEN" ...

# Check setup script in container (after run)
docker exec <container> cat /root/.config/claude/mcp.json

# Look for Deep Search queries in stdout/logs
grep -r "deep.search\|sourcegraph\|mcp" jobs/claude-mcp-*/*/logs/
```

## Next Steps After Testing

1. **Analyze results**: Compare baseline vs MCP success rates
2. **Extract metrics**: Token usage, code quality, execution time
3. **File learnings**: Record patterns in AGENTS.md via Engram
4. **Plan Phase 5**: Multi-task benchmark with full dataset if MCP shows promise

## Reference

- **Architecture**: `history/HARBOR_MCP_APPROACH.md`
- **Setup script**: `tools/harbor_test_commands.sh`
- **Task updater**: `tools/update_tasks_for_harbor_mcp.py`
- **Quick check**: `tools/validate_tasks.py`
- **Deep Search**: `ds` CLI tool (reference: 8cfde179-ebf6-45e6-bb4a-1366075723cd)

## Key Commands Reference

```bash
# Setup
source .venv-harbor/bin/activate
source infrastructure/load-env.sh

# Run tests
./tools/harbor_test_commands.sh baseline
./tools/harbor_test_commands.sh mcp
./tools/harbor_test_commands.sh compare

# Verify results
python3 runners/compare_results.py jobs/claude-baseline-* jobs/claude-mcp-*

# Check specific task
TASK=$(ls -dt jobs/claude-baseline-*/*/sgt-001__* 2>/dev/null | head -1)
ls -la "$TASK/logs/verifier/"
```
