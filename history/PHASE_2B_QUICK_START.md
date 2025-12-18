# Phase 2b Quick Start (CodeContextBench-cy6)

**Status**: ✅ Ready for Pilot Execution  
**Infrastructure**: Validated (14/16 critical checks pass)  
**Tasks**: 25 mined (github_mined) + 6 baseline (10figure)  
**Agents**: claude-baseline (no search) vs claude-mcp (with Sourcegraph Deep Search)

---

## 1. Pre-Flight Check

```bash
# Verify everything is ready
python3 runners/validate_benchmark_setup.py
```

Should show: ✅ ALL CRITICAL CHECKS PASSED

---

## 2. Run Pilot (10 tasks, both agents)

### Baseline (no Sourcegraph)
```bash
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-baseline \
  --tasks 10 \
  --concurrent 2
```

**Expected**:
- Duration: 30-60 minutes
- Success rate: 30-40% (3-4 of 10 tasks)
- Cost: $2-3 USD

### MCP (with Sourcegraph Deep Search)
```bash
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-mcp \
  --tasks 10 \
  --concurrent 2
```

**Expected**:
- Duration: 30-60 minutes
- Success rate: 40-50% (4-5 of 10 tasks)
- Cost: $2-3 USD

---

## 3. Check Pilot Results

```bash
# After both pilot runs complete, aggregate results
python3 runners/extract_nemo_traces.py --jobs-dir jobs/ --all --json

# Look for:
# - Manifests written: 20 (10 per agent)
# - Success rate comparison: MCP > baseline
# - Per-task cost: <$0.50
# - Infrastructure errors: 0
```

---

## 4. Decision Point

**If pilot passes**:
- Success rates align with hypothesis (MCP >= baseline)
- Cost/efficiency reasonable
- 0 infrastructure failures
- → Proceed to Phase 2b-2 (full run, 50+4 tasks)

**If pilot fails**:
- Infrastructure errors? Check logs in `jobs/claude-*-pilot-*/`
- Success rates too low? Adjust difficulty filters
- Cost too high? Reduce concurrent workers
- → Fix issues, re-run pilot

---

## 5. Full Benchmark (if pilot passes)

Run all 50 github_mined + 4 10figure tasks on both agents:

```bash
# Baseline on github_mined
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-baseline \
  --tasks 50 \
  --concurrent 4

# MCP on github_mined
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-mcp \
  --tasks 50 \
  --concurrent 4

# Both agents on 10figure (4 tasks each)
./runners/harbor_benchmark.sh \
  --benchmark 10figure \
  --agent claude-baseline \
  --tasks 4 \
  --concurrent 2

./runners/harbor_benchmark.sh \
  --benchmark 10figure \
  --agent claude-mcp \
  --tasks 4 \
  --concurrent 2
```

**Expected**:
- Total: 108 task runs (54 × 2 agents)
- Duration: 8-12 hours wall time
- Cost: $25-35 USD
- Success rate: baseline 30-40%, MCP 40-55%

---

## 6. Aggregate & Analyze

```bash
# Extract all manifests and NeMo traces
python3 runners/extract_nemo_traces.py --jobs-dir jobs/ --all

# Output: artifacts/manifests_aggregate.json
# Contains: success rates, costs, tokens, tool usage per agent
```

---

## Key Files

| File | Purpose |
|------|---------|
| `runners/harbor_benchmark.sh` | Execute Harbor benchmarks |
| `runners/validate_benchmark_setup.py` | Pre-flight validation |
| `runners/extract_nemo_traces.py` | Aggregate manifests |
| `history/BENCHMARK_EXECUTION_PLAN.md` | Detailed strategy |
| `history/PHASE_2B_STARTUP.md` | Full startup summary |
| `benchmarks/github_mined/` | 25 mined tasks |
| `benchmarks/10figure/` | 6 baseline tasks |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Agent load error | Run `validate_benchmark_setup.py` to diagnose |
| Harbor CLI not found | Script uses Python wrapper; optional |
| Task timeout | Increase `--timeout-sec` in harbor-config.yaml |
| Cost too high | Reduce `--concurrent` workers |
| Success rate 0% | Tasks may be too hard; check pilot logs |
| Sourcegraph errors (MCP only) | Verify `SRC_ACCESS_TOKEN` in .env.local |

---

## Timeline

| Phase | Duration |
|-------|----------|
| Pilot | 1-2 hours |
| Decision/fix | 30 min |
| Full run | 8-12 hours |
| Aggregation | 1-2 hours |
| **Total** | **11-17 hours** |

---

## Success Criteria

✅ **Pilot**:
- Both agents complete 10 tasks without timeout
- Success rates: baseline 30-40%, MCP 40-50%
- Cost <$0.50/task

✅ **Full benchmark**:
- >90% tasks complete without errors
- MCP success > baseline by +10-15% (validates hypothesis)
- Cost $25-35 USD total

✅ **Analysis**:
- Stratified breakdown by task category, difficulty, language
- Failure modes categorized
- Report generated (JSON + HTML)

---

## Related Beads

- **wkb** (mining): ✅ COMPLETE — 50 tasks mined & validated
- **cy6** (execution): IN_PROGRESS — you are here
- **von** (analysis): OPEN — awaits cy6 results

---

**Bead**: CodeContextBench-cy6  
**Start time**: 2025-12-17 20:30 UTC  
**Status**: Ready for pilot execution  
**Next**: Run pilot, validate results, proceed to full benchmark
