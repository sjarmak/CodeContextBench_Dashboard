# Cleanup & Organization Action Plan

**Status**: Prioritized from CODE_REVIEW_FINDINGS.md  
**Target**: P0 (Critical) items this session, P1 (High) next session

---

## PHASE 1: CRITICAL FIXES (P0) - This Session

### 1. Update AGENTS.md - Add Benchmark Documentation
**File**: `AGENTS.md`  
**Current**: No benchmark documentation (references outdated Terminal-Bench)  
**Action**: 
- Add new section "Benchmarks & Comparison Matrix" after agent documentation
- Copy from benchmarks/README.md the 6-benchmark table
- Remove Terminal-Bench references
- Link to benchmarks/README.md

**Impact**: Fixes inconsistency in primary documentation

### 2. Fix Deprecated Agent References in Tests
**Files**:
- `tests/test_mcp_agent_setup.py` - Still imports old agent
- `tests/smoke_test_10figure.py` - Uses deprecated agent

**Action**:
- Update to import from `agents.mcp_variants:DeepSearchFocusedAgent`
- Verify tests still pass
- Confirm deprecation shim still works for backward compat

**Impact**: Tests use current agents

### 3. Update docs/MCP_SETUP.md
**File**: `docs/MCP_SETUP.md`  
**Issue**: Shows old import paths, outdated setup instructions  
**Action**:
- Replace deprecated agent imports with current paths
- Update agent configuration examples
- Add note that this doc is now superseded by agents/README.md
- Keep for reference but mark as "see agents/README.md for current info"

**Impact**: Reduces confusion for new users

### 4. Fix Runner Script Agent References
**Files** (7 total):
- `runners/validate_benchmark_setup.py`
- `runners/direct_benchmark.py`
- `runners/direct_benchmark_real.py`
- `runners/run_benchmark.py`
- `runners/run_pilot_benchmark.sh`
- `scripts/test_harbor_mcp.py`

**Action**: Update all to use current agents from mcp_variants  
**Impact**: Runner scripts work with current agent system

---

## PHASE 2: HIGH-PRIORITY (P1) - Next Session

### 5. Archive Stale Scripts & Runners
**Current State**: 34 scripts in runners/ + scripts/ appear stale  
**Action**:
- Audit each script (categorize: obsolete, deprecated, active)
- Move ~20 to history/archived_scripts/
- Keep 12-15 core scripts that are actively used
- Document purpose of kept scripts in `scripts/README.md`

**Candidates to Archive**:
```
runners/
- run_pilot_benchmark.sh (pilot, phase 2)
- harbor_benchmark.sh (old phase 2)
- gen_harbor_tasks.py (generator, rarely used)
- test_mcp_in_harbor.py (old test)
- capture_single_task_trace.py (observability, archived)

scripts/
- analyze_comparison_results.py (deprecated)
- comprehensive_metrics_analysis.py (deprecated)
- analyze_dependeval_comparison.py (phase 3 specific)
- run_*_comparison.sh (10 variants, consolidate to 1-2)
- test_*.py scripts (consolidate to tests/)
```

**Impact**: Cleaner, more navigable runner/scripts structure

### 6. Consolidate Documentation
**Current**: 18 docs with overlaps  
**Action**:
- Merge SETUP.md + DEVELOPMENT.md → DEVELOPMENT.md (one setup source)
- Merge METRICS_COLLECTION.md + OBSERVABILITY.md → OBSERVABILITY.md
- Deprecate MCP_SETUP.md (point to agents/README.md)
- Archive BENCHMARK_EXECUTION.md → history/ (use benchmarks/README.md instead)
- Consolidate BENCHMARKING_GUIDE.md + BENCHMARK_DESIGN_GUIDE.md

**Target**: Reduce docs/ from 18 → 12-14 files  
**Impact**: Single source of truth for each topic

### 7. Update ARCHITECTURE.md
**Issue**: References Terminal-Bench, references deprecated agent paths  
**Action**:
- Remove Terminal-Bench references
- Update agent section to show 4 agents + deprecation shim
- Update benchmark section to list 6 active benchmarks
- Add new section: "Agent Comparison Framework"

**Impact**: Architecture doc matches current system

---

## PHASE 3: NICE-TO-HAVE (P3) - When Time Permits

### 8. Update Observability
**Current**: 3 modules for trace parsing  
**Action**: Verify they work with new benchmark structure, update if needed

### 9. Update Infrastructure Configs
**Current**: Dockerfile, Podman, CI/CD configs  
**Action**: Verify they're up to date, document any local-only setups

### 10. Cleanup Old Artifacts
**Current**: artifacts/, results/, jobs/ may have old results  
**Action**: Archive old comparison results → history/

---

## Work Allocation

**This Session (Remaining)**:
- P0 items 1-4 (docs update + test fixes) - ~2 hours

**Next Session (Recommended)**:
- P1 items 5-7 (script archival + doc consolidation) - ~3 hours
- P3 items 8-10 if time - ~1 hour

---

## Files Generated
- `CODE_REVIEW_FINDINGS.md` - Full audit report
- `CLEANUP_ACTION_PLAN.md` - This file

---

## Success Criteria

✅ Codebase is ready for benchmarking when:
1. No broken deprecated agent references
2. AGENTS.md documents all 6 benchmarks
3. All docs point to correct files/paths
4. Runner scripts compile without errors
5. Tests pass with current agent setup
