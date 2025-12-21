# Scripts Reference Guide

Quick reference for which scripts to use for common tasks. Many scripts have overlapping functionality - this guide identifies the canonical versions.

## Comparison Analysis

**Use:** `runners/compare_results.py`

```bash
python runners/compare_results.py jobs/baseline-run jobs/mcp-run
```

Compares baseline vs MCP results from Harbor runs. Outputs reward metrics, timing, and pass rates.

**Alternatives (deprecated):**
- `scripts/analyze_comparison_results.py` - Hardcoded for 10 tasks, use compare_results.py instead
- `scripts/detailed_comparison_analysis.py` - Token/cost analysis, functionality should be merged into compare_results.py

---

## LLM Judge Evaluation

**Use:** `scripts/llm_judge_big_code.py` for big code tasks

```bash
python scripts/llm_judge_big_code.py --baseline jobs/baseline --mcp jobs/mcp --task vsc-001
```

Uses Claude as judge to evaluate code quality, test coverage, and architecture decisions.

**Alternatives (task-specific):**
- `scripts/llm_judge_evaluation.py` - General evaluation, less specific criteria
- `scripts/judge_vsc_rerun.py` - Three-way comparison for instruction impact studies
- `scripts/evaluate_vsc_001.py` - VSC-001 specific with cost analysis

**Note:** These scripts overlap significantly. Future consolidation planned (CodeContextBench-6rf).

---

## Metrics Collection

**Use:** `scripts/extract_enterprise_metrics.py` for baseline/MCP comparison data

```bash
python scripts/extract_enterprise_metrics.py jobs/comparison-run/
```

Extracts enterprise metrics: time allocation, tool usage patterns, file access.

**Alternatives:**
- `scripts/collect_metrics.py` - Enterprise baseline comparison (58% comprehension target)
- `scripts/comprehensive_metrics_analysis.py` - Multi-dimensional analysis (timing, tokens, tools)

**Note:** `comprehensive_metrics_analysis.py` has significant overlap with others. Consider deprecated.

---

## Result Validation

**Use:** `scripts/validate_comparison_results.py`

```bash
python scripts/validate_comparison_results.py jobs/baseline jobs/mcp
```

Validates that comparison results are complete and not corrupted (checks for API errors, token counts, task completeness).

---

## Task Generation

**Use:** `runners/gen_harbor_tasks.py`

```bash
python runners/gen_harbor_tasks.py --input /path/to/tasks --output benchmarks/output
```

Generates Harbor-compatible task directories from source task definitions.

---

## Benchmark Execution

**Use:** `runners/harbor_benchmark.sh`

```bash
bash runners/harbor_benchmark.sh --benchmark github_mined --agent claude-baseline --tasks 10
```

Primary benchmark runner. See `benchmarks/README.md` for detailed usage.

---

## Tool Usage Analysis

**Use:** `scripts/extract_tool_calls.py`

```bash
python scripts/extract_tool_calls.py jobs/run-directory/
```

Extracts and analyzes tool usage patterns from agent trajectories.

**Related:**
- `scripts/analyze_repoqa_tool_usage.py` - RepoQA-specific tool analysis

---

## Consolidation Status

| Category | Canonical Script | Deprecated/To Merge |
|----------|-----------------|---------------------|
| Comparison | `runners/compare_results.py` | analyze_comparison_results.py, detailed_comparison_analysis.py |
| LLM Judge | `scripts/llm_judge_big_code.py` | Others are task-specific |
| Metrics | `scripts/extract_enterprise_metrics.py` | comprehensive_metrics_analysis.py |
| Validation | `scripts/validate_comparison_results.py` | None |

Future work: Consolidate overlapping scripts into unified tools with config-driven behavior. See CodeContextBench-6rf.
