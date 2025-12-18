# Phase 2b Startup Summary (CodeContextBench-cy6)

**Status**:  Infrastructure Validated, Ready for Pilot Execution  
**Date**: 2025-12-17  
**Bead**: CodeContextBench-cy6

---

## Completed

### 1. Infrastructure Validation 
- [x] Agent implementations load (ClaudeCodeAgent, ClaudeCodeSourcegraphMCPAgent)
- [x] Environment variables configured (ANTHROPIC_API_KEY, SRC_ACCESS_TOKEN)
- [x] Tasks validated (25 github_mined + 6 10figure tasks ready)
- [x] Disk space sufficient (215 GB available)
- [x] Container runtime (Podman 5.6.2) available
- [x] Configuration files present (harbor-config.yaml, datasets.yaml)

**All 14/16 critical checks passed**. Two warnings are non-critical (Harbor CLI optional, docker wrapper optional).

### 2. Planning & Documentation 
- [x] Created BENCHMARK_EXECUTION_PLAN.md with detailed execution phases
- [x] Created run_pilot_benchmark.sh validation script
- [x] Created validate_benchmark_setup.py for pre-execution checks
- [x] Documented task structure, manifest format, result capture
- [x] Documented failure modes and abort criteria

### 3. Ready State 
All systems ready for **pilot benchmark execution**:
- 25 github_mined tasks (from Phase 2a mining, 98% validation pass rate)
- 6 10figure baseline tasks (canonical test set)
- 2 agents (baseline: no search, MCP: with Sourcegraph Deep Search)
- Harbor infrastructure configured
- Jobs directory prepared (/Users/sjarmak/CodeContextBench/jobs/)

---

## Next: Pilot Execution

### Phase 2b-1: Pilot (10 tasks, both agents)

**Commands**:
```bash
# Baseline (no Sourcegraph Deep Search)
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-baseline \
  --tasks 10 \
  --concurrent 2

# MCP (with Sourcegraph Deep Search)
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-mcp \
  --tasks 10 \
  --concurrent 2
```

**Expected outcomes**:
-  Baseline success: 30-40% (3-4 of 10 tasks)
-  MCP success: 40-50% (4-5 of 10 tasks)  
-  Per-task cost: <$0.50
-  0 infrastructure failures

**Success criteria**: Both agents complete 10 tasks without timeouts, success rate aligns with hypothesis direction (MCP ≥ baseline).

### After Pilot:
1. Review results for success rate & cost
2. If successful, proceed to Phase 2b-2 (full run: 50+4 tasks)
3. Aggregate manifests & NeMo traces
4. Hand off to cy6 for analysis

---

## Key Files

| File | Purpose |
|------|---------|
| `history/BENCHMARK_EXECUTION_PLAN.md` | Detailed execution strategy & phases |
| `history/MINING_PLAN.md` | Master strategy (hypothesis, task design, pipeline) |
| `docs/MINING_EXECUTION_REPORT.md` | Phase 2a results (50 tasks mined, 98% validation) |
| `runners/harbor_benchmark.sh` | Harbor CLI wrapper |
| `runners/validate_benchmark_setup.py` | Pre-execution validation |
| `runners/run_pilot_benchmark.sh` | Pilot bootstrap script |
| `infrastructure/harbor-config.yaml` | Harbor configuration |
| `infrastructure/datasets.yaml` | Dataset definitions |
| `agents/base.py` | BasePatchAgent base class |
| `agents/claude_agent.py` | ClaudeCodeAgent (baseline) |
| `agents/claude_sourcegraph_mcp_agent.py` | ClaudeCodeSourcegraphMCPAgent (MCP) |
| `benchmarks/github_mined/` | 25 mined tasks (sgt-001 through sgt-025) |
| `benchmarks/10figure/` | 6 baseline tasks |

---

## Hypothesis Being Tested

**"Sourcegraph code search (via MCP) improves agent success on multi-file, repository-scale tasks."**

### Agents Compared
- **Baseline**: Claude Code with file/git operations only (no code search)
- **Treatment**: Claude Code + Sourcegraph Deep Search via MCP

### Expected Results (Trevor-validated)
- Baseline success rate: 30-40%
- Treatment success rate: 40-55% (+ **10-15% improvement**)
- Difference validates hypothesis

### Tasks
- Real-world: 50 closed GitHub issues with merged PRs from Kubernetes + PyTorch
- Multi-file: Average 3.5 files per task
- Deterministic: All have test commands (make test, pytest, go test)
- Reproducible: Exact git revisions preserved

---

## Execution Matrix

```
Benchmarks:  github_mined (50 tasks) + 10figure (4 tasks) = 54 tasks
Agents:      claude-baseline + claude-mcp = 2 agents
Total runs:  54 × 2 = 108 task executions

Phase 2b-1 (Pilot):   10 tasks × 2 agents = 20 runs
Phase 2b-2 (Full):    50 tasks × 2 agents + 4 × 2 = 108 runs
```

---

## Cost & Timeline Estimates

| Phase | Duration | Cost |
|-------|----------|------|
| Pilot (10 tasks × 2 agents) | 1-2 hours | ~$2-3 USD |
| Full run (50+4 tasks × 2 agents) | 8-12 hours | ~$25-35 USD |
| Aggregation & analysis | 3-5 hours | $0 |
| **Total** | **12-20 hours** | **~$30-40 USD** |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Task timeouts | Set conservative timeouts (10-15 min/task) in pilot |
| Cost explosion | Monitor first 5 tasks; abort if >$1/task |
| Sourcegraph API rate limits | Stagger runs, use conversation IDs to cache |
| Non-deterministic tests | All tasks use standard test commands |
| Infrastructure failures | Retry failed containers, log all errors |

**Abort criteria**: >10% infrastructure failure, >$1/task cost, baseline success <20%.

---

## Bead Status

**ID**: CodeContextBench-cy6  
**Title**: Run Harbor benchmarks on 10figure + github_mined tasks  
**Status**: IN_PROGRESS (infrastructure validated, waiting for execution)  
**Priority**: 1 (critical path)  
**Depends on**: CodeContextBench-wkb (mining —  completed)  
**Blocks**: CodeContextBench-von (analysis — awaits Phase 2b-3 results)

---

## Glossary

- **Harbor**: Benchmark framework for evaluating agents on real-world tasks
- **Baseline**: Claude Code with no code search (control group)
- **MCP**: Model Context Protocol — enables Claude to call external tools (Sourcegraph)
- **NeMo traces**: Execution traces capturing token counts, latency, tool calls
- **Manifest**: JSON output containing metrics (success, tokens, cost, duration)
- **Task.toml**: Harbor task metadata (repo, language, difficulty, time limit)
- **Patch.diff**: Git diff output showing agent's changes

---

**Document maintainer**: CodeContextBench team  
**Last updated**: 2025-12-17  
**Next checkpoint**: Complete pilot, validate results before full run
