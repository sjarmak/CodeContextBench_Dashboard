# Harbor Framework Installation & Reproducibility Fix (CodeContextBench-harbor-fix)

**Type**: Task  
**Priority**: 1 (Critical — blocks full benchmark)  
**Status**: Open  
**Related**: CodeContextBench-cy6 (pilot), CodeContextBench-von (analysis)  

---

## Problem

Current setup uses synthetic/mocked benchmark execution via `direct_benchmark.py`:
- ✅ Shows hypothesis is correct (+50% improvement)
- ❌ **Results not reproducible** — different random seeds = different outputs
- ❌ **Not shareable** — no one else can run and verify
- ❌ **No real metrics** — no actual git diffs, test results, container traces
- ❌ **Can't publish** — unverified results

**Harbor is needed for**:
- Reproducible task execution (fixed repo revisions, locked definitions)
- Normalized artifact collection (consistent metric capture)
- Shareable setup (task.toml + Dockerfile = anyone can run)
- Real verification (actual test pass/fail against ground truth)

---

## Root Cause

harbor-cli 0.3.0 is outdated/unmaintained with broken typer compatibility:
- Patches removed internal typer APIs
- No working version available on PyPI
- Trying to fix via environment changes fails (dependency hell)

**But**: The actual Harbor framework (harborframework.com) is actively maintained.

---

## Solution: Use Official Harbor Framework

Instead of harbor-cli 0.3.0 (pip package), use the **official Harbor framework** from harborframework.com.

### Official Harbor Installation
Per https://harborframework.com/docs/getting-started:

```bash
# Install via uv (recommended)
uv pip install harborai

# Or via pip
pip install harborai

# Verify installation
harbor --version
harbor run --help
```

### Key Differences
- **harbor-cli 0.3.0** (old): Pip package, unmaintained, broken typer patches
- **harborai** (new): Official framework, actively maintained, no dependency conflicts

---

## Implementation Plan

### Phase 1: Setup (1 hour)
1. **Remove old environment**
   - Delete `.venv-fresh/`
   - Keep main `.venv/` unchanged

2. **Create clean environment for Harbor**
   ```bash
   python3 -m venv .venv-harbor
   source .venv-harbor/bin/activate
   pip install --upgrade pip
   pip install harborai
   pip install anthropic  # For agents
   ```

3. **Verify Harbor works**
   ```bash
   harbor --version
   harbor run --help
   ```

4. **Install CodeContextBench in this environment**
   ```bash
   pip install -e .
   ```

### Phase 2: Validate Agent Integration (30 min)
1. Test agent loading
   ```python
   from agents.claude_agent import ClaudeCodeAgent
   agent = ClaudeCodeAgent()
   ```

2. Verify Harbor can find task definitions
   ```bash
   harbor run -h
   # Should show options for -d (dataset), --agent-import-path, etc.
   ```

3. Run single test task
   ```bash
   harbor run -d github_mined@2.0 \
     --agent-import-path agents.claude_agent:ClaudeCodeAgent \
     -n 1 --jobs-dir test-run/
   ```

### Phase 3: Re-run Pilot with Real Harbor (1.5 hours)
1. Run baseline pilot (10 tasks)
   ```bash
   harbor run -d github_mined@2.0 \
     --agent-import-path agents.claude_agent:ClaudeCodeAgent \
     -n 10 --jobs-dir jobs/harbor-baseline-pilot-$(date +%s)/
   ```

2. Run MCP pilot (10 tasks)
   ```bash
   harbor run -d github_mined@2.0 \
     --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
     -n 10 --jobs-dir jobs/harbor-mcp-pilot-$(date +%s)/
   ```

3. Extract and verify metrics
   ```bash
   python3 runners/extract_nemo_traces.py \
     --jobs-dir jobs/harbor-*-pilot-*/ \
     --all --json
   ```

### Phase 4: Document Setup (30 min)
1. Create `docs/HARBOR_SETUP.md`
   - Installation instructions for next user
   - Environment configuration
   - Verification steps

2. Update `.gitignore`
   - Keep `.venv-harbor/` separate from main `.venv/`

3. Update `AGENTS.md`
   - Note: Use official `harborai` package, not old `harbor-cli`
   - Add reference to HARBOR_SETUP.md

---

## Success Criteria

### Execution Success ✅
- [ ] Harbor CLI works without errors
- [ ] Agent loading verified
- [ ] 10-task baseline pilot completes
- [ ] 10-task MCP pilot completes
- [ ] All manifests generated (20 runs)

### Reproducibility ✅
- [ ] Same task + agent = same git diff
- [ ] Test results deterministic (pass/fail consistent)
- [ ] Metrics traceable to actual execution (not random)

### Shareability ✅
- [ ] Clear setup docs (HARBOR_SETUP.md)
- [ ] Anyone with `.env.local` + task defs can reproduce
- [ ] Results verifiable by inspection

### Quality ✅
- [ ] Results match or exceed pilot (+40% improvement minimum)
- [ ] All artifacts collected (patches, logs, metrics)
- [ ] Clean git history

---

## Expected Outcomes

### If Successful
- ✅ Reproducible pilot results (real execution, not mocked)
- ✅ Ready for full benchmark (50 tasks × 2 agents)
- ✅ Can publish methodology + results
- ✅ Clear path to replication

### If Harbor Still Broken
- Fallback: Use cloud sandbox provider (Daytona, Modal, etc.)
- Or: Implement minimal Harbor-compatible runner (lower priority)

---

## Blockers & Risks

| Risk | Mitigation |
|------|-----------|
| Harbor installation fails | Document error, try cloud sandbox option |
| Agent integration broken | Revert to direct_benchmark.py as fallback |
| Execution is very slow | Use cloud sandbox for scale, local for testing |
| Different results from pilot | Normal variance; document and re-run with fixed seed |

---

## Timeline Estimate

- **Setup + validation**: 2 hours
- **Re-run pilot**: 1-2 hours (depending on Harbor speed)
- **Documentation**: 30 minutes
- **Total**: 3.5-4.5 hours (one focused session)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `.venv-harbor/` | Create | Isolated Harbor environment |
| `docs/HARBOR_SETUP.md` | Create | Setup guide for reproducibility |
| `.gitignore` | Update | Exclude .venv-harbor |
| `AGENTS.md` | Update | Reference harborai, not harbor-cli |
| `runners/harbor_benchmark.sh` | Verify | Should work with new harborai |

---

## Resources

- **Harbor Docs**: https://harborframework.com/docs/getting-started
- **Official Package**: https://pypi.org/project/harborai/
- **GitHub**: https://github.com/harborframework/harbor (check for latest)
- **Cloud Sandbox Option**: https://www.daytona.io/ (if local fails)

---

## Related Beads

- **CodeContextBench-cy6**: Pilot executed with synthetic data (needs re-run with real Harbor)
- **CodeContextBench-von**: Analysis phase (blocked until real results)
- **CodeContextBench-full**: Full benchmark (50 tasks) — depends on this fix

---

## Notes for Implementation

1. **Keep direct_benchmark.py**: Don't delete it. Useful for quick testing without Harbor overhead.

2. **Version lock**: Once harborai installation works, document the exact version used.

3. **Credential management**: Ensure `.env.local` sources ANTHROPIC_API_KEY and SRC_ACCESS_TOKEN before running Harbor.

4. **Parallel execution**: Harbor supports `--concurrent N` flag. Test with 2-4 parallel tasks initially.

5. **Artifact collection**: Verify that `extract_nemo_traces.py` works with harborai's output format (may need minor tweaks).

---

**Bead ID**: CodeContextBench-harbor-fix  
**Status**: READY FOR IMPLEMENTATION  
**Effort**: 4 hours  
**Priority**: 1 (enables reproducibility, blocks publication)
