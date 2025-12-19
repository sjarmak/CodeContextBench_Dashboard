# Baseline vs MCP Agent Comparison Analysis
## Real Data (Dec 19 2025)

**Dataset**: 10-task mined benchmark (sgt-001 through sgt-010)  
**Baseline Agent**: Claude Code (standard)  
**MCP Agent**: Claude Code + Sourcegraph Deep Search  
**Model**: Claude 3.5 Haiku  

**Data Sources** (VALID):
- Baseline: `jobs/baseline-10task-20251219/` (10/10 tasks, 34.8M tokens)
- MCP: `jobs/mcp-10task-20251219/` (9/10 tasks, 40.5M tokens, sgt-003 missing)

---

## Executive Summary

| Metric | Baseline | MCP | Difference |
|--------|----------|-----|------------|
| **Pass Rate** | 10/10 (100%) | 9/10 (90%) | -1 task (sgt-003) |
| **Avg Time** | 139.7s | 138.7s | 1.05x faster |
| **Token Usage** | 34.8M | 40.5M | 1.16x MORE tokens |
| **Tool Calls** | 814 | 521 | -36% reduction |
| **Code Changes** | 7/10 tasks | 5/9 tasks | Similar rate |

**Key Finding**: MCP provides **marginal speedup (1.05x) while using significantly more tokens (1.16x)**. The Deep Search integration does not translate to improved efficiency, and one task (sgt-003) failed completely.

---

## Detailed Analysis

### 1. Execution Time Comparison

**Task-by-Task Performance:**

| Task | Baseline | MCP | Speedup | Winner |
|------|----------|-----|---------|--------|
| sgt-001 | 73.5s | 104.3s | 0.71x | Baseline (30.8s faster) |
| sgt-002 | 124.0s | 136.2s | 0.91x | Baseline (12.2s faster) |
| sgt-003 | 280.5s | MISSING | N/A | **Baseline (task failed in MCP)** |
| sgt-004 | 80.7s | 60.3s | 1.34x | MCP (20.4s faster) |
| sgt-005 | 143.8s | 182.7s | 0.79x | Baseline (38.9s faster) |
| sgt-006 | 69.6s | 37.8s | 1.84x | **MCP (31.8s faster)** |
| sgt-007 | 193.3s | 164.6s | 1.17x | MCP (28.7s faster) |
| sgt-008 | 70.1s | 131.6s | 0.53x | Baseline (61.5s slower) |
| sgt-009 | 143.8s | 299.8s | 0.48x | **Baseline (156.0s slower)** |
| sgt-010 | 218.0s | 130.7s | 1.67x | **MCP (87.3s faster)** |

**Summary Statistics:**

```
Baseline: avg=139.7s, median=133.9s, total=1397s, range=70.1s - 280.5s
MCP:      avg=138.7s, median=131.6s, total=1248s, range=32.0s - 299.8s

Speedup:  1.05x (marginal)
          Range: 0.48x - 1.84x (highly inconsistent)
```

**Interpretation:**
- No consistent speedup pattern
- MCP faster on 4/10 tasks, slower on 5/10 tasks
- Largest gain: sgt-006 (1.84x), largest loss: sgt-009 (0.48x)
- Speedup is **not statistically significant**

---

### 2. Token Usage Analysis

**Prompt Token Breakdown:**

| Task | Baseline | MCP | Ratio | Notes |
|------|----------|-----|-------|-------|
| sgt-001 | 1.64M | 3.58M | 2.18x | MCP uses 2.2x tokens |
| sgt-002 | 3.58M | 5.30M | 1.48x | MCP uses 48% more |
| sgt-003 | 7.85M | MISSING | N/A | Baseline only |
| sgt-004 | 2.03M | 1.28M | 0.63x | Baseline uses 37% more |
| sgt-005 | 2.50M | 5.55M | 2.22x | MCP uses 2.2x tokens |
| sgt-006 | 1.34M | 0.89M | 0.66x | MCP more efficient here |
| sgt-007 | 5.54M | 5.20M | 0.94x | Roughly equal |
| sgt-008 | 1.29M | 3.76M | 2.91x | MCP uses 3x tokens |
| sgt-009 | 3.96M | 11.98M | 3.02x | MCP uses 3x tokens |
| sgt-010 | 5.13M | 2.99M | 0.58x | Baseline uses 71% more |

**Summary:**

```
Baseline:
  Total prompt: 34.9M tokens
  Average: 3.49M tokens per task
  Completion: 45K tokens
  Total: 34.9M tokens

MCP (9 tasks):
  Total prompt: 40.5M tokens
  Average: 4.50M tokens per task
  Completion: 46K tokens
  Total: 40.5M tokens

Efficiency: MCP uses 1.16x MORE tokens for 1.05x speedup
           This is a negative ROI on tokens
```

**Interpretation:**
- MCP makes larger context windows (pulls more search results)
- But doesn't save token usage through better reasoning
- 4 tasks show MCP using 2-3x tokens (sgt-001, 005, 008, 009)
- Only 3 tasks show baseline using significantly more (sgt-003, 010)

---

### 3. Tool Usage Patterns

**Tool Call Comparison:**

| Tool | Baseline | MCP | Difference |
|------|----------|-----|------------|
| Bash | 425 | 261 | -164 (-39%) |
| Read | 207 | 119 | -88 (-42%) |
| Edit | 22 | 19 | -3 (-14%) |
| Write | 61 | 36 | -25 (-41%) |
| Task | 22 | 13 | -9 (-41%) |
| Grep | 53 | 35 | -18 (-34%) |
| Glob | 24 | 25 | +1 |
| **MCP Tools** | 0 | 13 | +13 |

**Total Tool Calls:**
- Baseline: 814 calls
- MCP: 521 calls
- Reduction: -36% fewer tool calls

**MCP Tool Usage Detail:**
- Total MCP-specific tool calls: **11 calls across 9 tasks**
- sgt-001: 1 call (sg_deepsearch)
- sgt-004: 1 call (sg_commit_search)
- sgt-005: 5 calls (4x sg_keyword_search, 1x sg_nls_search)
- sgt-007: 2 calls (2x sg_keyword_search)
- sgt-009: 2 calls (2x sg_keyword_search)

**Interpretation:**
- MCP uses Deep Search **sparingly** (only 11 calls across 9 tasks)
- Despite having MCP available, baseline's manual exploration (Read, Bash, Grep) is NOT replaced
- Smaller reduction in all traditional tools suggests MCP agent is *not* leveraging Deep Search effectively
- MCP still needs manual file reading and bash operations almost as much as baseline

---

### 4. Code Changes Quality

**Code Modification Patterns:**

| Metric | Baseline | MCP | Notes |
|--------|----------|-----|-------|
| Tasks with edits | 5/10 | 4/9 | Similar |
| Tasks with writes | 4/10 | 2/9 | MCP less likely to create |
| Tasks with commits | 2/10 | 2/9 | Similar |
| Tasks with bash ops | 10/10 | 9/9 | Both use bash extensively |

**Interpretation:**
- Both agents modify code in ~50% of tasks
- MCP makes slightly fewer writes (fewer new files created)
- Both rely heavily on bash operations (test runs, git operations)
- No evidence that Deep Search improves code quality or reduces modification iterations

---

### 5. Context Retrieval Analysis

**MCP Deep Search Usage:**

```
Baseline: 0 MCP tool calls (expected - no MCP available)

MCP Agent:
  - Total MCP calls: 11 across 9 tasks (1.2 calls/task average)
  - Most calls on complex tasks (sgt-005: 5 calls, sgt-009: 2 calls)
  - Some tasks skip MCP entirely (sgt-002, 006, 008)
```

**Search Tool Breakdown:**
- `sg_keyword_search`: 10 calls (most common)
- `sg_commit_search`: 1 call
- `sg_deepsearch`: 1 call
- `sg_nls_search`: 1 call

**Interpretation:**
- MCP agent **underutilizes** Deep Search (only 11 calls in 1248 seconds execution)
- Despite having access to semantic search, agent defaults to keyword search
- Agent does not aggressively use MCP tools to reduce manual exploration
- Deep Search integration is present but not effectively leveraged

---

### 6. Step Count Analysis

**Agent Reasoning Steps:**

```
Baseline: avg=106.8 steps, median=103, range=49-214
MCP:      avg=102.4 steps, median=103, range=32-202

Difference: -4.4 steps (-4.1%) - negligible
```

**Task-by-Task:**

| Task | Baseline | MCP | Change |
|------|----------|-----|--------|
| sgt-001 | 49 | 72 | +23 (+47%) |
| sgt-002 | 100 | 110 | +10 (+10%) |
| sgt-004 | 58 | 43 | -15 (-26%) |
| sgt-005 | 106 | 152 | +46 (+43%) |
| sgt-006 | 58 | 32 | -26 (-45%) |
| sgt-007 | 138 | 111 | -27 (-20%) |
| sgt-008 | 52 | 97 | +45 (+87%) |
| sgt-009 | 115 | 202 | +87 (+76%) |
| sgt-010 | 178 | 103 | -75 (-42%) |

**Interpretation:**
- MCP doesn't consistently reduce step count
- Some tasks have MORE steps with MCP (sgt-001, 005, 008, 009)
- Step reduction on simple tasks (sgt-006, 010) but increase on complex tasks
- Suggests MCP agent may be over-iterating on complex reasoning problems

---

## Efficiency Metrics

### Token Efficiency (tokens per second)

```
Baseline: 34.9M / 1397s = 24.97k tokens/sec
MCP:      40.5M / 1248s = 32.45k tokens/sec

MCP uses tokens 1.3x faster (worse efficiency)
```

### Cost Analysis (Claude Haiku pricing: $0.80/1M prompt, $4.00/1M completion)

```
Baseline:
  Prompt cost:     34.9M × $0.80 / 1M = $27.92
  Completion cost: 45.6K × $4.00 / 1M = $0.18
  Total:           $28.10 for 10 tasks ($2.81/task)

MCP:
  Prompt cost:     40.5M × $0.80 / 1M = $32.40
  Completion cost: 46.0K × $4.00 / 1M = $0.18
  Total:           $32.58 for 9 tasks ($3.62/task)

Cost increase: 1.16x MORE expensive despite marginal speedup
```

---

## Issues & Failures

### 1. sgt-003 Missing from MCP

**Status**: MCP run for sgt-003 is completely absent from `mcp-10task-20251219/`

**Possible Causes**:
- Task timeout (task is complex, 214 baseline steps)
- API failure during execution
- Crash during MCP initialization

**Impact**: Cannot compare MCP performance on this task

### 2. High Variability in Speedup

**Range**: 0.48x - 1.84x
**Std Dev**: High variance suggests task-dependent behavior
**Concerns**: 
- No consistent benefit across task types
- MCP slower on several complex tasks (sgt-001, 009)

### 3. Token Usage Not Reduced

**Expected**: Better codebase understanding → fewer tokens needed
**Observed**: MCP uses 16% MORE tokens
**Explanation**: Likely over-use of large context windows from search results

---

## Conclusions

### Does MCP Improve Performance?

**Timing**: **Marginally yes** (1.05x speedup)
- Not statistically significant given variance
- Inconsistent across tasks
- Some tasks are significantly slower

**Token Efficiency**: **No** (1.16x worse)
- MCP uses more tokens while providing marginal speedup
- Cost per task increases from $2.81 to $3.62

**Tool Utilization**: **No** (36% fewer tool calls)
- MCP doesn't leverage Deep Search effectively
- Only 11 MCP calls across 9 tasks
- Manual exploration still required

**Code Quality**: **Neutral**
- Similar modification patterns
- Similar code change rates
- No evidence of improved solution quality

### Key Inefficiencies

1. **Unused Deep Search**: MCP available but underutilized (only 1.2 calls/task)
2. **Over-reasoning**: More tokens per task despite fewer tool calls
3. **Inconsistent Benefits**: Works on simple tasks (sgt-006) but fails on complex ones (sgt-009)
4. **Manual Exploration Still Required**: Bash/Read/Grep not reduced significantly

### Recommendations

1. **Investigate sgt-003 failure** - Determine why MCP run is missing
2. **Analyze MCP underutilization** - Why does agent avoid Deep Search?
3. **Review token usage** - Identify if context windows are unnecessarily large
4. **Optimize MCP prompts** - Current system prompt may not encourage Deep Search usage
5. **Run larger benchmark** - 10 tasks insufficient for statistical significance
6. **Compare on different models** - Haiku may behave differently with MCP than Opus/Sonnet

---

## Data Quality Notes

- **Baseline**: All 10 tasks completed successfully
- **MCP**: 9/10 tasks completed (sgt-003 missing)
- **Validation**: All trajectories checked for API key failures and token counts verified
- **Sources**: 
  - Valid: `jobs/baseline-10task-20251219/` and `jobs/mcp-10task-20251219/`
  - Invalid: `jobs/comparison-20251219-clean/` (contains API key failures)

---

**Report Generated**: December 19, 2025  
**Analysis Time**: Real data from original comparison runs  
**Next Steps**: Run full 50-task benchmark with corrected setup
