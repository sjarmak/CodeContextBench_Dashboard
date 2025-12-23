# MCP Prompt Experiment Results

## Task: big-code-vsc-001
**VS Code Stale Diagnostics Fix** - Handle stale diagnostics after git branch switching

## Results Summary

| Agent | Reward | Time | Deep Search Calls | Other MCP |
|-------|--------|------|-------------------|-----------|
| Strategic | 1.0 ✅ | 3:39 | 6 | 2 |
| Aggressive | 1.0 ✅ | 2:44 | 14 | 0 |
| Baseline (no MCP) | 1.0 ✅ | 4:26 | 0 | 0 |

## Key Observations

### 1. All agents succeeded
All three agents achieved reward = 1.0, successfully implementing the fix.

### 2. Aggressive agent was fastest
The DeepSearchFocusedAgent (2:44) was actually faster than both:
- Strategic (3:39) - 55 seconds slower
- Baseline (4:26) - 102 seconds slower

### 3. Deep Search usage correlates with speed
- Aggressive: 14 calls → 2:44 (fastest)
- Strategic: 6 calls → 3:39
- Baseline: 0 calls → 4:26 (slowest)

## Interpretation

For this task (VS Code codebase, ~2M lines):
- MCP tools provide meaningful speedup (~35-40% faster than baseline)
- More aggressive Deep Search use correlated with faster completion
- The "strategic" approach (fewer calls) was still better than baseline

## Hypothesis
On large codebases, aggressive Deep Search may be more effective because:
1. Each search provides context that would take multiple grep/read operations
2. The cost of "over-searching" is lower than the cost of missing context
3. The agent can make better-informed decisions with more context

## Next Steps
1. Run on kubernetes (k8s-001) task for comparison
2. Test on smaller codebase where baseline might be competitive
3. Count total tool calls (not just MCP) to understand time allocation
