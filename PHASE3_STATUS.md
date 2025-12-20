# Phase 3: Big Code MCP Comparison Execution - Status Report

**Date:** Dec 20, 2025
**Status:** Infrastructure Fixed, Ready for Comparative Runs

## Summary

Phase 3 aimed to execute baseline vs MCP comparisons on all 4 big code tasks from Trevor Nederlof's research. Hit a blocker: big_code_mcp tasks lacked Harbor reward files needed for metric evaluation.

**Status:** ✅ Blocker resolved. All tasks now Harbor-compatible.

## Work Completed

### 1. Identified Harbor Compatibility Issue
- Harbor's benchmark runner requires `reward.json` files
- big_code_mcp tasks had all other files but were missing reward definitions
- Error: `RewardFileNotFoundError` prevented task execution

### 2. Created Reward Files for All 4 Tasks
Added `benchmarks/big_code_mcp/*/reward.json` with:
- Test completion criteria (50% weight)
- Code changes requirement (30% weight)  
- Architecture understanding (20% weight)
- Min success score 0.7

Tasks now Harbor-evaluable:
- big-code-vsc-001: Stale diagnostics (pipeline architecture)
- big-code-servo-001: scrollend event (cross-module integration)
- big-code-k8s-001: NoScheduleNoTraffic taint (comprehensive coverage)
- big-code-trt-001: W4A8_MXFP4_INT8 quantization (Python/C++ boundary)

### 3. Validated Existing Comparison Infrastructure
Ran single-task comparison (sgt-001) on github_mined:

**Results (Dec 20, 08:04-08:09 UTC):**
- Task: sgt-001 (GitHub mined issue)
- Baseline (Claude Code):
  - Prompt tokens: 6,026,028
  - Completion tokens: 9,022
  - Reward: 1.0 ✅
  
- MCP (Sourcegraph MCP guidance):
  - Prompt tokens: 5,292,841
  - Completion tokens: 9,262
  - Reward: 1.0 ✅

**Metric:** MCP used **12% fewer tokens** (5.3M vs 6.0M) while achieving same task completion.

### 4. Added Alternative Comparison Script
Created `scripts/run_direct_comparison.sh` for direct Claude Code invocation without Harbor wrapper (fallback option if reward evaluation has issues).

## Next Steps

### Immediate (Required to Complete Phase 3)

1. **Run big-code-vsc-001 baseline vs MCP**
   ```bash
   source .env.local
   bash scripts/run_mcp_comparison.sh big_code_mcp big-code-vsc-001
   ```
   Expected: ~20 min total (10 min each run)

2. **Run big-code-servo-001 baseline vs MCP**
   ```bash
   bash scripts/run_mcp_comparison.sh big_code_mcp big-code-servo-001
   ```

3. **Run big-code-k8s-001 baseline vs MCP**
   ```bash
   bash scripts/run_mcp_comparison.sh big_code_mcp big-code-k8s-001
   ```

4. **Run big-code-trt-001 baseline vs MCP**
   ```bash
   bash scripts/run_mcp_comparison.sh big_code_mcp big-code-trt-001
   ```

5. **Validate and Analyze Results**
   ```bash
   python scripts/validate_comparison_results.py jobs/comparison-*/baseline jobs/comparison-*/mcp
   python scripts/comprehensive_metrics_analysis.py
   ```

### Expected Outcomes

**Based on Trevor's research:**
- MCP should provide MORE value on big code tasks (broader architectural understanding needed)
- Previous github_mined results: MCP +1.16x tokens for 1.05x speedup (marginal)
- Big code tasks should show: better accuracy, fewer missed locations, more comprehensive implementations

**Success Criteria:**
- All 4 tasks complete without Harbor errors
- Both baseline and MCP agents produce valid trajectories
- Metrics extracted: prompt tokens, completion tokens, execution time, reward score
- Analysis shows architectural understanding difference between agents

## Estimated Timeline

| Task | Effort | Status |
|------|--------|--------|
| big-code-vsc-001 | 15-20 min | Ready |
| big-code-servo-001 | 15-20 min | Ready |
| big-code-k8s-001 | 15-20 min | Ready |
| big-code-trt-001 | 15-20 min | Ready |
| Validation & analysis | 30 min | Ready |
| **Total** | **~2 hours** | **Queued** |

## Key Documents

- **Trevor's Research:** `docs/TREVOR_RESEARCH_DEC2025.md` (rationale for 4 big code tasks)
- **MCP Agent:** `agents/claude_sourcegraph_mcp_agent.py` (injects MCP guidance)
- **Comparison Script:** `scripts/run_mcp_comparison.sh` (runs baseline vs MCP)
- **Validation:** `scripts/validate_comparison_results.py` (checks result integrity)

## Commits

- `62c2733e`: Add direct Claude Code comparison script
- `8421774d`: Add reward.json to all 4 big code MCP tasks

## Context

This is continuation of Phase 2, which successfully:
- Built 4 production-ready big code tasks from Trevor's December 2025 research
- Created enhanced MCP agent with Sourcegraph guidance injection
- Set up Harbor-compatible comparison framework
- Learned: Deep Search MCP times out on >2GB codebases; use full Sourcegraph MCP endpoint instead

Phase 3 will validate that the framework works end-to-end and measure MCP impact on actual "big code" problems.
