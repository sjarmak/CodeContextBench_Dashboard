# Harbor Execution Checklist

**Critical issues that block task execution. Check these FIRST before running any benchmark.**

## Environment Variables (MANDATORY)

### 1. ANTHROPIC_API_KEY (REQUIRED FOR ALL AGENTS)

```bash
# Check if set
echo $ANTHROPIC_API_KEY

# If empty, load from .env.local
export ANTHROPIC_API_KEY=$(grep "ANTHROPIC_API_KEY=" .env.local | cut -d'=' -f2 | tr -d '"')

# Verify
echo $ANTHROPIC_API_KEY | head -c 20  # Should show your API key prefix
```

**KNOWN ISSUE**: Environment variables don't persist across command pipes or subshells. Always export in the same command before running `harbor run`.

**FIX**: 
```bash
# WRONG - API key lost between pipe
source .env.local
harbor run ...  # ❌ ANTHROPIC_API_KEY not available

# RIGHT - Export in same command
export ANTHROPIC_API_KEY=$(grep "ANTHROPIC_API_KEY=" .env.local | cut -d'=' -f2 | tr -d '"') && \
harbor run ...  # ✅ ANTHROPIC_API_KEY available
```

### 2. SOURCEGRAPH_ACCESS_TOKEN (REQUIRED FOR MCP AGENT ONLY)

For baseline agent: NOT required  
For MCP agent with Sourcegraph: REQUIRED

```bash
export SOURCEGRAPH_ACCESS_TOKEN=$(grep "SOURCEGRAPH_ACCESS_TOKEN=" .env.local | cut -d'=' -f2 | tr -d '"')
export SOURCEGRAPH_URL=$(grep "SOURCEGRAPH_URL=" .env.local | cut -d'=' -f2 | tr -d '"')
```

**Note**: Agents keep backward compatibility with `SRC_ACCESS_TOKEN`, but new automation should prefer `SOURCEGRAPH_ACCESS_TOKEN` + `SOURCEGRAPH_URL`.

## Model Selection

### Use anthropic/claude-haiku-4-5-20251001 (NOT claude-3-5-sonnet)

```bash
# WRONG - Too expensive and slow
--model anthropic/claude-3-5-sonnet-20241022

# RIGHT - Fast and cheap for testing
--model anthropic/claude-haiku-4-5-20251001
```

**Note**: The correct model name is `anthropic/claude-haiku-4-5-20251001`, NOT `claude-3-5-haiku`

**Why haiku?**
- 5x faster than sonnet
- 1/5 the cost
- Sufficient for code tasks
- Better for iteration and testing

## Baseline Agent Command

Complete working example:

```bash
export ANTHROPIC_API_KEY=$(grep "ANTHROPIC_API_KEY=" .env.local | cut -d'=' -f2 | tr -d '"') && \
harbor run \
  --path benchmarks/github_mined_pilot \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1 \
  --jobs-dir jobs/baseline-test \
  --task-name sgt-010
```

**What this does:**
1. Exports ANTHROPIC_API_KEY in same command (fixes env var persistence issue)
2. Uses `agents.claude_baseline_agent:BaselineClaudeCodeAgent` (Claude Code in autonomous mode, no MCP)
3. Uses haiku for speed/cost
4. Runs 1 task (`-n 1`)
5. Saves output to `jobs/baseline-test`
6. Tests task sgt-010

## Autonomous Implementation Mode

The baseline agent AUTOMATICALLY enables these settings:

```python
# In claude_baseline_agent.py:create_run_agent_commands()
env = {
    'FORCE_AUTO_BACKGROUND_TASKS': '1',
    'ENABLE_BACKGROUND_TASKS': '1'
}
```

**What this means:**
- Claude Code operates in headless/autonomous mode
- Automatically makes code changes instead of asking for approval
- No interactive prompts (required for automated benchmarks)
- These flags are injected by the agent itself - you don't need to set them

**You do NOT need to** manually export these variables - the agent injects them at runtime.

## Pre-Execution Checklist

Before running `harbor run`:

- [ ] ANTHROPIC_API_KEY exported (in same command as harbor run)
- [ ] Using `anthropic/claude-haiku-4-5-20251001` model (not sonnet)
- [ ] Task directory exists (e.g., `benchmarks/github_mined_pilot/sgt-010`)
- [ ] Jobs directory will be created (e.g., `jobs/baseline-test`)
- [ ] Docker daemon running (for task environment)

## Monitoring Execution

While task runs:

```bash
# Check if jobs directory was created
ls -la jobs/baseline-test/

# Monitor logs (after ~30 seconds)
find jobs/baseline-test -name "*.log" -exec tail -f {} \;

# Check for result file
find jobs/baseline-test -name "result.json"

# Expected files after completion:
# - result.json (task result)
# - reward.txt (0.0 or 1.0 - pass/fail)
# - claude.txt or similar (agent output)
```

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ANTHROPIC_API_KEY environment variable required` | API key not set | Export in same command: `export ANTHROPIC_API_KEY=... && harbor run ...` |
| `Task directory not found` | Wrong path | Use full path: `benchmarks/github_mined_pilot/sgt-010` |
| No files created in jobs directory | Harbor not running | Check Docker: `docker ps`, check logs: `docker logs` |
| `rate_limit_exceeded` error | API quota hit | Wait 60s, use haiku instead of sonnet |
| Task hangs for >30 minutes | Docker build timeout or network issue | Stop task (Ctrl+C), check Docker logs, try simpler task |

## Key Findings for Future Developers

1. **Environment variables don't persist**: Always export in the same bash command
2. **Autonomous mode is automatic**: Don't manually set FORCE_AUTO_BACKGROUND_TASKS
3. **Use haiku for testing**: Sonnet is too expensive for iteration
4. **Jobs directory auto-creates**: No need to mkdir beforehand
5. **Docker is required**: Ensure daemon is running
6. **Logs take time to appear**: Wait 20-30 seconds before checking

## References

- Full benchmarking guide: `docs/BENCHMARKING_GUIDE.md`
- Baseline agent implementation: `agents/claude_baseline_agent.py`
- Mining/task setup: `docs/MINING_EXECUTION_GUIDE.md`
