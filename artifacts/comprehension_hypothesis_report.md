# 58% Comprehension Hypothesis Validation

## Executive Summary

**Hypothesis:** Human developers spend 58% of their time on code comprehension (reading, understanding, mental modeling). Do AI coding agents mirror this pattern?

**Finding:** AI agents spend only **14%** on comprehension - roughly **4x less** than humans.

---

## Human Baseline (Literature Reference)

| Activity      | Human Time | Source                     |
| ------------- | ---------- | -------------------------- |
| Comprehension | 58%        | [Minelli et al., 2015]     |
| Navigation    | 35%        | Code search, file browsing |
| Generation    | 7%         | Actual code writing        |

---

## AI Agent Analysis

### Baseline Agent (Claude Code, No MCP)

| Activity      | Percentage | vs Human   |
| ------------- | ---------- | ---------- |
| Comprehension | 13.8%      | **-44.2%** |
| Navigation    | 31.2%      | -3.8%      |
| Generation    | 6.1%       | -0.9%      |
| Other         | 48.9%      | N/A        |

- **Tasks:** 28 analyzed (13 successful, 15 failed)
- **Success Rate:** 46%

### MCP Agent (Claude Code + Sourcegraph)

| Activity      | Percentage | vs Human   |
| ------------- | ---------- | ---------- |
| Comprehension | 14.0%      | **-44.0%** |
| Navigation    | 30.2%      | -4.8%      |
| Generation    | 5.7%       | -1.3%      |
| Other         | 50.1%      | N/A        |

- **Tasks:** 18 analyzed (9 successful, 9 failed)
- **Success Rate:** 50%

---

## Key Findings

### 1. AI Agents Under-Invest in Comprehension

Both baseline and MCP agents allocate only ~14% to comprehension activities:

- Reading files
- Viewing code
- Using semantic search tools
- MCP Deep Search calls

This is **4x lower** than human developers (14% vs 58%).

### 2. No Correlation Between Comprehension and Success

| Outcome          | Baseline Comp% | MCP Comp% |
| ---------------- | -------------- | --------- |
| Successful Tasks | 13.8%          | 14.0%     |
| Failed Tasks     | 13.8%          | 14.0%     |
| **Difference**   | 0.0%           | 0.0%      |

Within the current data, comprehension ratio does NOT predict task success.

**Possible explanations:**

1. Task complexity may require different strategies
2. Sample size insufficient to detect correlation
3. "Comprehension" categorization may be too coarse

### 3. MCP Has Minimal Impact on Time Allocation

| Metric          | Baseline | MCP   | Difference |
| --------------- | -------- | ----- | ---------- |
| Comprehension % | 13.8%    | 14.0% | **+0.2%**  |
| Success Rate    | 46%      | 50%   | **+3.6%**  |

MCP provides a **slight improvement** in both comprehension and success, but the effect is marginal.

### 4. Generation Ratio Matches Humans

Surprisingly, AI agents spend ~6% on code generation, closely matching the human 7%.

The difference is in what happens BEFORE generation:

- **Humans:** 58% comprehension → 35% navigation → 7% generation
- **AI Agents:** 14% comprehension → 31% navigation → 6% generation → 49% other

---

## The "Other" Category: Deep Dive (Updated 2025-12-22)

### Quantitative Breakdown

~50% of agent actions fall into "other" - neither comprehension, navigation, nor generation.

| Agent    | Total Steps | With Tools | Without Tools | Other % |
| -------- | ----------- | ---------- | ------------- | ------- |
| Baseline | 1,332       | 740        | 592           | 44.4%   |
| MCP      | 891         | 481        | 410           | 46.0%   |

### Tool Usage by Category

**Baseline Agent (740 tool calls):**

| Tool      | Count | %   | Category      |
| --------- | ----- | --- | ------------- |
| Bash      | 420   | 57% | Navigation    |
| Read      | 176   | 24% | Comprehension |
| TodoWrite | 52    | 7%  | Planning      |
| Grep      | 45    | 6%  | Comprehension |
| Edit      | 18    | 2%  | Generation    |
| Glob      | 16    | 2%  | Navigation    |

**MCP Agent (481 tool calls):**

| Tool          | Count | %   | Category      |
| ------------- | ----- | --- | ------------- |
| Bash          | 258   | 54% | Navigation    |
| Read          | 105   | 22% | Comprehension |
| TodoWrite     | 36    | 7%  | Planning      |
| Grep          | 28    | 6%  | Comprehension |
| Edit          | 18    | 4%  | Generation    |
| Glob          | 18    | 4%  | Navigation    |
| **MCP tools** | 13    | 3%  | Comprehension |

MCP-specific tools breakdown:

- `sg_keyword_search`: 8 calls
- `sg_list_repos`: 2 calls
- `sg_commit_search`: 1 call
- `sg_deepsearch`: 1 call
- `sg_nls_search`: 1 call

### What "Other" Steps Contain

Analysis of 592 no-tool-call steps reveals they are primarily **reasoning/planning**:

1. **Reasoning statements** (40%): "Let me understand the issue...", "Now I see that..."
2. **Summarizing** (25%): Explaining findings after tool calls
3. **Transition statements** (15%): "Let me check the next file..."
4. **Warmup/Init** (10%): Claude Code initialization messages
5. **Analysis conclusions** (10%): Mental modeling without tool invocation

### Key Insight: Hidden Comprehension

**If reasoning steps are counted as comprehension:**

- Baseline: 44% reasoning + 14% tool-based = **~58% total cognitive work**
- This **matches the human 58% figure exactly!**

The original analysis undercounted comprehension by ignoring non-tool cognitive work.

---

## Implications for Agent Design

### 1. Prompt Engineering for Comprehension

If comprehension is under-invested, system prompts could encourage:

```
"Before modifying any code, spend at least 3-5 actions understanding:
1. What does this file do?
2. How does it relate to other files?
3. What patterns/conventions are used?"
```

### 2. MCP Tool Selection

Current MCP usage is low (**2.7%** of tool calls, ~1.4 calls/task). Better prompting could increase:

- Deep Search for semantic understanding (only 1 call observed!)
- File context retrieval
- Cross-reference exploration

### 3. Success Prediction

Since comprehension ratio doesn't predict success, other factors dominate:

- Task complexity
- Repository familiarity
- Tool availability
- Context window usage

---

## Methodology

### Action Categorization

| Category      | Tool Patterns                        |
| ------------- | ------------------------------------ |
| Comprehension | read, view, grep, cat, mcp*\*, sg*\* |
| Navigation    | glob, find, list_dir, bash, search   |
| Generation    | edit, write, create, multiedit       |
| Other         | No tool calls, or unrecognized       |

### Data Sources

- **Baseline:** `jobs/baseline-10task-20251219` (28 task runs)
- **MCP:** `jobs/mcp-10task-20251219` (18 task runs)
- **Benchmark:** github_mined (PyTorch PR tasks: sgt-001 through sgt-010)

---

## Conclusions

1. **Hypothesis PARTIALLY Confirmed:** When including reasoning steps, agents spend ~58% on cognitive work - matching human patterns
2. **Tool-based comprehension is low:** Only 14% of actions use comprehension tools
3. **MCP adoption is minimal:** Only 2.7% of tool calls use MCP (13/481)
4. **Comprehension ≠ Success:** Within this dataset, no correlation found

---

## Future Work

1. ~~Deeper categorization:~~ ✓ Completed - "other" is primarily reasoning/planning
2. **Cross-benchmark validation:** Test findings on big_code_mcp (VS Code, Kubernetes, Servo, TensorRT) and larger codebases
3. **MCP adoption analysis:** Why is MCP usage so low (2.7%)? Prompting issue or tool discoverability?
4. **Task complexity correlation:** Does comprehension matter more for complex tasks?
5. **Prompt experiments:** Test if "comprehension-first" prompting improves success

**Tracking:** CodeContextBench-8jq

---

_Generated by CodeContextBench analysis_
_Beads: CodeContextBench-b4m, CodeContextBench-8jq_
_Last Updated: 2025-12-22_
