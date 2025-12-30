# Verifier QEMU Segfault Analysis

## Issue
Evaluation runs on ARM64 Macs return `reward=0` due to a segmentation fault in the test verifier, even when all tests pass successfully.

**Error observed:**
```
qemu: uncaught target signal 11 (Segmentation fault) - core dumped
/tests/test.sh: line 151: 13151 Segmentation fault      (core dumped) uv run parser.py
```

## Root Cause
This is **NOT a code issue** but a **system-level infrastructure problem** when running SWE-bench verifications on Apple Silicon (ARM64) Macs with QEMU x86_64 emulation.

### Technical Details

1. **QEMU Emulation Layer**: Harbor runs x86_64 Docker/Podman containers on ARM64 Macs using QEMU translation
2. **Numpy Binary Incompatibility**: Tests run with warning:
   ```
   RuntimeWarning: numpy.ndarray size changed, may indicate binary incompatibility. 
   Expected 80 from C header, got 96 from PyObject
   ```
3. **Post-Test Parser Failure**: After pytest completes successfully (15/15 tests pass), the verification parser crashes
4. **QEMU Translation Race Condition**: The transition from high-intensity test execution to the parser phase triggers a crash in the QEMU translation layer due to memory layout mismatches

## Evidence

**Test execution succeeded:**
```
astropy/modeling/tests/test_separable.py ...............                 [100%]
==================================== PASSES ====================================
PASSED astropy/modeling/tests/test_separable.py::test_coord_matrix
PASSED astropy/modeling/tests/test_separable.py::test_cdot
... (15 total tests passed)
============================== 15 passed in 0.65s ==============================
```

**But verifier crashed during result parsing:**
```
qemu: uncaught target signal 11 (Segmentation fault)
```

The segfault happens in the parser cleanup phase (line 151 of test.sh), not during actual test execution.

## Impact on Different Agents

This issue affects **ALL agents** running SWE-bench verifications on ARM64 Macs:
- ✗ OpenHands + QEMU = parser segfault → reward=0
- ✗ Claude Code + QEMU = parser segfault → reward=0
- ✓ Any agent + Daytona = no QEMU, no segfault → correct reward

The previous assumption that OpenHands had dependency issues was partially correct, but the reward=0 was ultimately caused by this QEMU/numpy problem, not agent-specific failures.

## Solution

**Use Daytona environment instead of local Docker:**

```bash
# FAILS on ARM64 Mac (QEMU segfault)
harbor run --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# WORKS on ARM64 Mac (no QEMU)
harbor run --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  -n 1
```

**Benefits of Daytona:**
- Real x86_64 cloud VMs (no QEMU emulation)
- 6x faster than local Docker
- Consistent environment across all machines
- Correct numpy/C extension ABI compatibility
- No post-test parser segfaults

## Documentation References

- `CLAUDE.md` lines 61-65: Daytona requirement for SWE-bench
- `docs/AGENT_CONFIGURATIONS.md` lines 246-250: QEMU segfault solution
- `swe_bench_configs/TEST_RESULTS.md` lines 47-60: ARM64 QEMU issues documentation

## Recommendations

1. **Update Dashboard**: Switch to `--env daytona` by default for all SWE-bench runs
2. **Update CLI Scripts**: Add environment detection to recommend Daytona on ARM64
3. **Add Troubleshooting Section**: Document QEMU issue and Daytona solution in TROUBLESHOOTING.md
4. **Consider Local Testing**: For fast iteration on code fixes without verifier, use direct pytest instead of SWE-bench harness

## Not a Code Issue

The separability matrix fix itself is **correct** (all tests pass). The reward=0 is a false negative caused by verifier infrastructure failure, not code failure.
