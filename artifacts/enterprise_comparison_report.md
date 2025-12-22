# Enterprise Metrics: Baseline vs MCP Comparison Report
**Date:** December 22, 2025  
**Dataset:** github_mined benchmark (PyTorch PRs)  
**Baseline:** Claude Code (standard)  
**MCP:** Claude Code + Sourcegraph MCP  

---

## Executive Summary

| Metric | Baseline | MCP | Delta | Insight |
|--------|----------|-----|-------|---------|
| **Tasks Completed** | 14 | 9 | -36% | MCP had more failures |
| **Avg Steps/Task** | 98.6 | 102.4 | +4% | Similar exploration depth |
| **Total Prompt Tokens** | 48.6M | 40.5M | -17% | MCP more token-efficient per-task |
| **Total Completion Tokens** | 67.6K | 46.0K | -32% | MCP generates less output |
| **MCP Tool Usage** | 0 | 13 calls | N/A | Low adoption rate |

## Key Findings

### 1. MCP Tool Underutilization
The MCP agent made only **13 Sourcegraph tool calls** across 9 tasks:
- `sg_keyword_search`: 8 calls
- `sg_list_repos`: 2 calls  
- `sg_deepsearch`: 1 call
- `sg_commit_search`: 1 call
- `sg_nls_search`: 1 call

**Average: 1.4 MCP calls per task** - extremely low for a code understanding benchmark.

### 2. Token Efficiency (Per Completed Task)

| Metric | Baseline | MCP | Interpretation |
|--------|----------|-----|----------------|
| Prompt tokens/task | 3.47M | 4.50M | MCP uses 30% more per task |
| Completion tokens/task | 4.8K | 5.1K | Similar generation |

Despite having fewer total tokens (due to fewer tasks), MCP uses **more tokens per task**. This suggests MCP retrieval adds context overhead without proportional benefit.

### 3. Code Navigation Patterns

| Tool Category | Baseline | MCP | Ratio |
|---------------|----------|-----|-------|
| Bash commands | 420 | 258 | 0.61x |
| File reads | 176 | 105 | 0.60x |
| Grep searches | 45 | 28 | 0.62x |
| Glob pattern matching | 16 | 18 | 1.12x |

**MCP agents use ~40% fewer local exploration tools**, but this hasn't translated to better outcomes.

### 4. Failure Analysis

**Baseline:** 14/14 tasks ran to completion (100%)  
**MCP:** 9/10 tasks ran to completion (90%)  

The MCP configuration introduced instability - one task (sgt-003) failed completely.

---

## Enterprise Productivity Lens

### Developer Time Allocation (Reference)
Industry research shows developers spend:
- 58% on code comprehension
- 35% on navigation/search
- 19% on external documentation

### How Do Agents Compare?

| Activity | Baseline Proxy | MCP Proxy | Enterprise Benchmark |
|----------|----------------|-----------|---------------------|
| Code comprehension | 176 file reads | 105 file reads | 58% of time |
| Navigation/search | 420 bash + 45 grep | 258 bash + 28 grep | 35% of time |
| Tool assistance | 0 semantic search | 13 semantic search | Variable |

**Observation:** Both agents spend proportionally more time on bash exploration (shell navigation) than on structured code reading, diverging from human patterns.

### Context Switching Indicators

No explicit context switching was measured. Future work should track:
- Time between file reads (recovery cost)
- Repeated file access patterns
- Search refinement sequences

---

## Tool Usage Effectiveness

### MCP Tool ROI Analysis

| MCP Tool | Calls | Est. Tokens Retrieved | Outcome Impact |
|----------|-------|----------------------|----------------|
| sg_keyword_search | 8 | ~80K (est) | Unclear |
| sg_list_repos | 2 | ~2K | Metadata only |
| sg_deepsearch | 1 | ~50K (est) | Low utilization |
| sg_commit_search | 1 | ~10K | Git history |
| sg_nls_search | 1 | ~30K | Natural language |

**Total MCP retrieval:** ~170K tokens estimated, representing ~0.4% of total token usage.

### Why Low MCP Adoption?

Possible explanations:
1. **Task type mismatch:** PyTorch PRs may be too localized for semantic search value
2. **Prompt insufficiency:** Agent not encouraged to use MCP tools
3. **Tool friction:** MCP tools require explicit invocation vs natural exploration
4. **Learning curve:** Agent defaulting to familiar bash/grep patterns

---

## Recommendations

### Immediate Actions

1. **Increase MCP prompting:** Add explicit instructions to use Sourcegraph for architecture understanding
2. **Track per-search ROI:** Measure if MCP searches lead to fewer subsequent file reads
3. **Test on larger codebases:** PyTorch is ~2GB, but tasks may be too localized

### Metrics to Add

1. **Search success rate:** Did search find relevant code on first try?
2. **Navigation efficiency:** Files read before making correct change
3. **Comprehension indicators:** Time reading files vs making changes
4. **Tool decision quality:** When should agent use MCP vs local search?

### Benchmark Improvements

1. **Design MCP-requiring tasks:** Tasks where local grep is insufficient
2. **Cross-module tasks:** Changes requiring understanding of distant code
3. **Architecture questions:** Tasks explicitly testing codebase comprehension

---

## Data Sources

- Baseline: `jobs/baseline-10task-20251219/` (14 trajectory files)
- MCP: `jobs/mcp-10task-20251219/` (9 trajectory files)
- Metrics: `artifacts/enterprise_metrics_comparison.json`
- Previous analysis: `artifacts/comparison_analysis_real_data.md`

---

## Conclusion

The current MCP integration shows **minimal productivity gains** on the github_mined benchmark:
- Token usage increased per task
- MCP tools severely underutilized (1.4 calls/task)
- Task completion rate decreased

**Key insight:** MCP value cannot be demonstrated on tasks where local exploration suffices. The benchmark needs tasks explicitly requiring semantic code search to validate the MCP hypothesis.

**Next steps:**
1. Fix big_code_mcp Docker infrastructure (CodeContextBench-dgt)
2. Design MCP-requiring tasks with cross-codebase dependencies
3. Re-run with explicit MCP usage prompts
