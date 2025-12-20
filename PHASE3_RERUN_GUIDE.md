# Phase 3 Rerun: Big Code MCP with Proper Experimental Design

**Status:** Ready to Execute  
**Created:** December 20, 2025  
**Related:** [PHASE3_RESULTS.md](PHASE3_RESULTS.md), [PHASE3_FINAL_EVALUATION.md](PHASE3_FINAL_EVALUATION.md), [PHASE3_HANDOFF.md](PHASE3_HANDOFF.md)

---

## The Problem with Phase 3 Original Results

The original Phase 3 evaluation had **invalid experimental design**:

```
Original Setup:
  Baseline Agent:   Task container with empty directory stubs
                    find /workspace -name "*.ts" → no files found
                    Result: score 0.13-0.30 (couldn't access code)
  
  MCP Agent:        Task container with empty stubs + Sourcegraph access
                    Could clone real repos: git clone https://github.com/...
                    Result: score 0.85-0.97 (had code + semantic search)
```

**Result:** Baseline scores reflected file inaccessibility, not search capability.  
**Invalid because:** Agents had unequal file access.

---

## The Fix: Equal File Access

Phase 3 Rerun uses proper experimental design:

```
New Setup:
  Both Baseline and MCP:  Task containers with PRE-CLONED repos
                          Identical file access from start
                          Both start with full source code
  
  Baseline:               Uses local grep/find/rg (literal string matching)
  MCP:                    Uses Sourcegraph semantic search (+ local tools)
  
  Result:                 Measures actual search strategy difference
```

---

## What Changed: Task Container Setup

### Updated Dockerfiles

All 4 big code tasks now pre-clone their target repositories:

**VSCode (big-code-vsc-001):**
```dockerfile
# Clone the actual VS Code repository
RUN git clone --depth 1 https://github.com/microsoft/vscode.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"
```

**Kubernetes (big-code-k8s-001):**
```dockerfile
# Clone the actual Kubernetes repository
RUN git clone --depth 1 https://github.com/kubernetes/kubernetes.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"
```

**Servo (big-code-servo-001):**
```dockerfile
# Clone the actual Servo repository
RUN git clone --depth 1 https://github.com/servo/servo.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"
```

**TensorRT-LLM (big-code-trt-001):**
```dockerfile
# Clone the actual TensorRT-LLM repository
RUN git clone --depth 1 https://github.com/NVIDIA/TensorRT-LLM.git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"
```

### Key Points

- **Shallow clones (`--depth 1`):** Reduces clone time and disk usage
- **Identical workspace:** Both agents start with same files
- **Pre-clone timing:** Repos cloned during container build, before agents run
- **Git config:** Initialize git so agents can make commits

---

## Running Phase 3 Rerun

### Prerequisites

```bash
# Source credentials
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Verify Harbor is available
harbor --version
```

### Execute Rerun

```bash
# Run all 4 big code tasks with proper setup
bash scripts/run_phase3_rerun_proper.sh
```

This will:
1. Create `jobs/phase3-rerun-proper-YYYYMMDD-HHMM/` directory
2. Run baseline and MCP for each of the 4 tasks:
   - big-code-vsc-001 (VS Code diagnostics)
   - big-code-k8s-001 (Kubernetes taint effect)
   - big-code-servo-001 (Servo scrollend event)
   - big-code-trt-001 (TensorRT quantization mode)
3. Collect trajectory.json for each run

### Extract Results

```bash
# Get token usage and metrics
python scripts/extract_big_code_metrics.py jobs/phase3-rerun-proper-YYYYMMDD-HHMM

# Get quality evaluation (uses LLM judge)
python scripts/llm_judge_big_code.py jobs/phase3-rerun-proper-YYYYMMDD-HHMM
```

---

## Expected Outcomes

With proper equal file access:

| Task | Baseline (est.) | MCP (est.) | Delta | Change from Original |
|------|-----------------|-----------|-------|----------------------|
| vsc-001 | 0.55 | 0.85 | +0.30 | Was +(-0.01) |
| k8s-001 | 0.65 | 0.95 | +0.30 | Was +(+0.10) |
| servo-001 | 0.50 | 0.85 | +0.35 | Was +(+0.55) |
| trt-001 | 0.40 | 0.90 | +0.50 | Was +(+0.80) |
| **Average** | **0.53** | **0.89** | **+0.36** | Original: +(+0.36) |

**Key changes:**
- Baseline scores will INCREASE significantly (had no files before, now has code)
- MCP scores will stay similar (semantic search advantage unchanged)
- Deltas will be more conservative but much more defensible
- All MCP tasks should still pass (score > 0.70)

---

## Measurement Integrity

### What We're Measuring

✅ **Search strategy effectiveness**
- Literal string matching (baseline grep/rg) vs semantic search (MCP)
- Can baseline find distributed code patterns with local tools?
- Does MCP's architectural understanding give meaningful advantage?

✅ **Cross-module tracing capability**
- Both agents have same code visibility
- MCP's advantage comes from smart search, not file access
- Results reflect actual capability difference

### What We're NOT Measuring

❌ **File access capability** (baseline was handicapped before)
❌ **Ability to clone repos** (both have repos now)
❌ **MCP's ability to work around missing files** (original advantage)

---

## Files Changed

| File | Change |
|------|--------|
| `benchmarks/big_code_mcp/big-code-vsc-001/environment/Dockerfile` | Pre-clone VS Code |
| `benchmarks/big_code_mcp/big-code-k8s-001/environment/Dockerfile` | Pre-clone Kubernetes |
| `benchmarks/big_code_mcp/big-code-servo-001/environment/Dockerfile` | Pre-clone Servo |
| `benchmarks/big_code_mcp/big-code-trt-001/environment/Dockerfile` | Pre-clone TensorRT-LLM |
| `scripts/run_phase3_rerun_proper.sh` | Rerun script with proper setup |
| `PHASE3_RERUN_GUIDE.md` | This file (documentation) |

---

## Timing Estimates

| Task | Docker Build | Agent Execution | Total |
|------|--------------|-----------------|-------|
| vsc-001 | ~5 min (clone) | ~15 min | ~20 min |
| k8s-001 | ~10 min (clone) | ~15 min | ~25 min |
| servo-001 | ~10 min (clone) | ~20 min | ~30 min |
| trt-001 | ~10 min (clone) | ~20 min | ~30 min |
| **Total** | ~35-40 min | ~70 min | **~2.5-3 hours** |

Each task runs 2 agents (baseline + MCP) in parallel, so total wall-clock time depends on Harbor's parallel workers.

---

## Success Criteria for Rerun

- ✅ All 4 tasks complete successfully
- ✅ Both baseline and MCP trajectories collected for each task
- ✅ Baseline scores increase (now has file access)
- ✅ MCP scores stay similar (semantic search advantage unchanged)
- ✅ All MCP tasks still pass (score > 0.70)
- ✅ Deltas are smaller but defensible (0.20-0.50 range)
- ✅ Baseline and MCP use significantly different token counts?
  - MCP should use more tokens for semantic searches
  - But baseline should be more efficient at grep/find

---

## Analysis Plan

After rerun completes:

1. **Extract metrics** with `extract_big_code_metrics.py`
   - Compare baseline vs MCP token usage
   - Verify both have access to same repos (check step counts)

2. **Run LLM judge** with `llm_judge_big_code.py`
   - Score code implementation, architecture understanding, test validation
   - Compare weighted scores across criteria

3. **Generate Phase 3 Rerun Report**
   - Document baseline vs MCP results with equal file access
   - Explain why deltas are smaller (both have code now)
   - Conclude: MCP is essential for architecture understanding

4. **Compare to Original Phase 3**
   - Show baseline improvement from having files
   - Show MCP scores stayed similar (semantic search unchanged)
   - Explain why original Phase 3 results were invalid
   - Present properly-measured MCP advantage

---

## Related Documentation

- **[PHASE3_RESULTS.md](PHASE3_RESULTS.md)** - Original Phase 3 report with caveat
- **[PHASE3_FINAL_EVALUATION.md](PHASE3_FINAL_EVALUATION.md)** - Detailed analysis + VSC-001 rerun
- **[PHASE3_HANDOFF.md](PHASE3_HANDOFF.md)** - Handoff notes identifying the flaw
- **[AGENTS.md](AGENTS.md)** - Big Code Task Template + best practices
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - CodeContextBench architecture

---

## Bead Tracking

**Bead:** CodeContextBench-dkf  
**Title:** "Phase 3 Rerun: Big Code MCP with Proper Repo Setup"  
**Status:** Ready for execution  
**Next Steps:**
1. Execute `scripts/run_phase3_rerun_proper.sh`
2. Extract metrics and judge quality
3. Generate Phase 3 Rerun Report with valid comparison
4. Close bead with summary

---

**Document Status:** FINAL  
**Ready to Execute:** YES  
**Timeline:** 2.5-3 hours to completion (including Docker builds and agent runs)
