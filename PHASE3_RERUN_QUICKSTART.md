# Phase 3 Rerun - Quick Start

**Status:** ✅ Ready to Execute  
**Duration:** ~2.5-3 hours  
**Requirements:** Docker, Harbor CLI, API credentials

---

## One-Command Start

```bash
# Setup credentials
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Run rerun
bash scripts/run_phase3_rerun_proper.sh
```

Output: `jobs/phase3-rerun-proper-YYYYMMDD-HHMM/`

---

## What Changed from Original Phase 3

| Aspect | Original | Rerun |
|--------|----------|-------|
| Baseline files | Empty stubs (❌ no code) | Pre-cloned repos (✅ full code) |
| MCP files | Pre-cloned repos | Pre-cloned repos |
| Fair? | ❌ NO (unequal access) | ✅ YES (equal access) |
| Measures | File access + search strategy | Search strategy only |
| Baseline score | 0.13-0.30 (no files) | 0.40-0.65 (expected, with files) |
| MCP score | 0.85-0.97 (expected similar) | 0.85-0.97 (semantic search) |
| Delta | 0.55-0.80 (inflated) | 0.30-0.50 (valid) |

---

## Results Analysis

After rerun completes:

```bash
# Extract token counts and metrics
python scripts/extract_big_code_metrics.py jobs/phase3-rerun-proper-YYYYMMDD-HHMM

# Run LLM judge for quality scores
python scripts/llm_judge_big_code.py jobs/phase3-rerun-proper-YYYYMMDD-HHMM
```

---

## Key Points

✅ **Both agents have identical file access** (repos pre-cloned)  
✅ **Baseline limited to grep/find/rg** (no MCP)  
✅ **MCP uses Sourcegraph semantic search** (+ local tools)  
✅ **Results will be valid and defensible** (equal starting point)  
✅ **All tasks expected to pass** (MCP > 0.70 threshold)

---

## Timeline

| Phase | Duration |
|-------|----------|
| Docker builds (4 repos) | ~35-40 min |
| Agent execution | ~70 min |
| Metrics extraction | ~5 min |
| Judge quality | ~5 min |
| **Total** | **~2.5-3 hours** |

---

## Documentation

- **[PHASE3_RERUN_GUIDE.md](PHASE3_RERUN_GUIDE.md)** - Complete guide with all details
- **[PHASE3_RERUN_SESSION_SUMMARY.md](PHASE3_RERUN_SESSION_SUMMARY.md)** - What was completed in this session
- **[PHASE3_RESULTS.md](PHASE3_RESULTS.md)** - Original Phase 3 (with caveat)
- **[PHASE3_FINAL_EVALUATION.md](PHASE3_FINAL_EVALUATION.md)** - Detailed analysis + VSC-001 rerun

---

Done. Ready to run Phase 3 Rerun whenever you are.
