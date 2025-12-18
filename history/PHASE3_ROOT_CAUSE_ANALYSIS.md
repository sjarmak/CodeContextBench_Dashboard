# Phase 3 Results: Root Cause Analysis

## The Problem

We claimed:
- **Baseline**: 8/10 (80%) success
- **MCP**: 10/10 (100%) success  
- **Conclusion**: MCP improves success by 20 percentage points

**Reality**: Both are FAKE SUCCESS - tests don't validate actual code changes.

## Evidence

### sgt-001 Task
**What was supposed to happen:**
```
Task: Implement thread safety fix to ncclCommGetAsyncError
Files to modify: 3 (torch/csrc/distributed/c10d/NCCLUtils.cpp, NCCLUtils.hpp, torch/csrc/cuda/nccl.cpp)
Changes: 78 additions, 16 deletions
```

**What actually happened:**
```
1. Agent ran for 228.6 seconds, generated 12,407 tokens
2. Agent output: "I understand the issue. Here's a summary of changes needed..."
3. Agent made ZERO code changes (patch.diff is 0 bytes)
4. Test command: `make test` returned 0 (nothing to do)
5. Result: reward 1.0 (PASS) ✓ FAKE
```

### Why Test Passed Despite No Code Changes
```bash
$ make test
make: Nothing to be done for 'test'.
# make returns 0 (success)
# Test script interprets this as "✓ Tests passed"
```

### sgt-002 (Baseline Failed, MCP Passed)
**Baseline test output:**
```
✗ Tests failed
```

**But we don't know why** because:
1. We never capture actual test stderr/stdout
2. We don't see what code changes were attempted
3. `make test` has no real target, so it's a fake failure too

## Impact

**What we validated:**
- ✓ Agent can parse instructions and generate reasoning
- ✓ MCP guidance text is visible in instructions
- ✓ Token counting works

**What we CANNOT conclude:**
- ✗ Whether agents actually implement code changes
- ✗ Whether Deep Search actually helps solve problems
- ✗ Whether 100% vs 80% represents real improvement or measurement artifact

## The Core Issue

Tasks assume `make test` exists in PyTorch repo, but it doesn't.

Task Dockerfile clones PyTorch and runs agents, but there's NO VALIDATION that the right repo state is achieved.

## What We Need

1. **Real test commands per repo** (not `make test`)
   - PyTorch: pytest or CMake-based tests
   - Rust projects: `cargo test`
   - Python projects: `pytest`
   - etc.

2. **Validate code changes exist** before running tests
   - Check git diff is non-empty
   - Verify specific files were modified

3. **Actual test validation** - test must fail if code is wrong
   - Can be unit tests, integration tests, build tests
   - Must validate the FIX, not just "did code change"

4. **Single-task direct comparison**
   - Run sgt-001 with baseline agent
   - Run sgt-001 with MCP agent
   - Capture EVERYTHING:
     - Full multi-turn conversation
     - Deep Search queries and responses
     - Actual code changes
     - Real test results

5. **Explicit non-interactive system prompt**
   - Agent MUST complete task
   - No "awaiting approval" or "here's what I would do"
   - Must actually make code changes and validate them
