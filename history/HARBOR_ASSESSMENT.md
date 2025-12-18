# Harbor Framework Assessment (CodeContextBench-09h)

**Status**: ⚠️ PIVOT REQUIRED  
**Date**: 2025-12-17  
**Context**: Attempted to use official Harbor framework from harborframework.com for reproducible benchmark execution

---

## What Worked ✅

- ✅ Installed harborai package v0.1.25 successfully
- ✅ `harbor` CLI works without dependency conflicts
- ✅ Can load agent classes (ClaudeCodeAgent, ClaudeCodeSourcegraphMCPAgent)
- ✅ Harbor has clean typer integration (no compatibility issues like harbor-cli 0.3.0)

---

## What Doesn't Work ❌

**Harbor expects a specific task format:**
- Tasks must be defined in YAML configuration files (not task.toml + instruction.md)
- Harbor reads task specs from YAMLTask definitions with structured schemas
- Our github_mined benchmark has: `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`
- Harbor won't auto-discover local task directories

**Result**: Would need to:
1. Convert all 25 github_mined tasks to Harbor YAML format
2. Create adapter/registry entries
3. ~2-3 hours conversion work
4. Still need custom agent registration

---

## Why This Matters

Original hypothesis: "Use Harbor to run reproducible benchmarks"

**Reality**: Harbor is designed for:
- Terminal-Bench 2.0 (official benchmark)
- Published datasets from harborframework.com registry
- Cloud-scale execution (Daytona, Modal, etc.)

**What we need**: Local reproducible execution with our custom tasks

---

## Recommended Solution: Enhanced Direct Runner

Instead of shoehorning into Harbor, enhance `runners/direct_benchmark.py` to:

1. **Use real container execution** (not mocks)
   - Build Dockerfile from `task.environment/Dockerfile`
   - Mount task repo into container
   - Capture real git diffs and test results
   
2. **Maintain reproducibility**
   - Fixed task definitions (task.toml defines repo revision)
   - Deterministic agent execution (fixed seed, same input = same output)
   - Real artifact collection
   
3. **Keep dependencies minimal**
   - Podman (already have 5.6.2)
   - Python (already have 3.12)
   - No Harbor CLI needed

---

## Implementation Path (2 hours)

1. **Phase 1** (30 min): Modify `direct_benchmark.py` to use real container builds
   - Parse `task.environment/Dockerfile`
   - Build image: `podman build -t task-sgt-001:latest task/environment/`
   - Run: `podman run --rm -v /repo:/workspace task-sgt-001:latest <agent-cmd>`
   
2. **Phase 2** (30 min): Capture real artifacts
   - Mount shared volume for logs + diffs
   - Parse test output from container
   - Extract actual metrics (not random generation)
   
3. **Phase 3** (1 hour): Re-run pilot
   - Baseline: 10 github_mined tasks
   - MCP: 10 github_mined tasks
   - Verify results are deterministic (same task = same result)

---

## Decision

**Proceed with Enhanced Direct Runner** instead of Harbor conversion.

Rationale:
- Faster (2 hours vs 3-4 hours Harbor conversion)
- Same reproducibility goals
- Uses existing task format (no migration needed)
- Clearer path to publication (real execution, not framework-specific)
- Easier for others to replicate (just Podman + Python)

---

## Notes

- Keep `.venv-harbor/` installed (useful for other experiments)
- Document decision in AGENTS.md for future reference
- Mark harbor-fix bead as "deferred - use direct runner instead"
