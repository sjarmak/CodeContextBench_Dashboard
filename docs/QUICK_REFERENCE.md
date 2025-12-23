# SWEBench MCP Experiment - Quick Reference

## Status
**Experiment ID:** `swebench_comparison_20251222-220401`  
**Status:** RUNNING  
**Started:** 2025-12-22 22:04 UTC  
**Est. Completion:** 2025-12-22 22:44 UTC (~40 minutes)

## What's Running
4 agent variants against 5 SWEBench tasks from django, matplotlib, and astropy:
- **Baseline** (no MCP) - control group
- **Deep Search Focused** (MCP + explicit Deep Search)
- **MCP No Deep Search** (MCP keyword/NLS only)
- **Full Toolkit** (all MCP tools, neutral prompting)

## Quick Commands

### Monitor Progress
```bash
bash scripts/monitor_experiment.sh results/swebench_comparison_20251222-220401
```

### Analyze Results (after completion)
```bash
python3 scripts/aggregate_mcp_results.py results/swebench_comparison_20251222-220401
```

### Check Running Processes
```bash
ps aux | grep harbor | grep -v grep
```

### Kill Stuck Experiment
```bash
pkill -f "harbor run"
```

## Results Location
```
/Users/sjarmak/CodeContextBench/results/swebench_comparison_20251222-220401/
├── summary.json                  # Overall results
├── baseline.json                 # Baseline agent result
├── deep_search_focused.json      # Deep Search agent result
├── mcp_no_deep_search.json       # No Deep Search agent result
├── full_toolkit.json             # Full Toolkit agent result
├── baseline_stdout.log           # Execution logs
├── baseline_stderr.log
├── analysis_report.json          # Generated after completion
└── ...
```

## Key Hypothesis
**MCP code search tools provide 15-25% success improvement on complex multi-file tasks.**

Expected success rates:
- Baseline: 40-50%
- Deep Search Focused: 60-65%
- Full Toolkit: 55-65%
- MCP No Deep Search: 45-55%

## Documentation Files
- **Full Setup:** `/jobs/EXPERIMENT_SETUP_COMPLETE.md`
- **Detailed Plan:** `/jobs/swebench_mcp_experiment_plan.md`
- **Status & Troubleshooting:** `/jobs/swebench_mcp_experiment_status.md`
- **Summary:** `/SWEBENCH_EXPERIMENT_SUMMARY.txt`

## Selected Tasks
1. **django__django-11119** - Template engine rendering
2. **django__django-11532** - Email encoding (Unicode)
3. **django__django-12143** - Form prefix handling
4. **matplotlib__matplotlib-20859** - Legend rendering
5. **astropy__astropy-12907** - Separability matrix

All from Sourcegraph-indexed repos with multi-file complexity.

## Expected Next Steps
1. ✓ Baseline agent completes (~22:14)
2. → Deep Search Focused starts (~22:14)
3. → MCP No Deep Search starts (~22:24)
4. → Full Toolkit starts (~22:34)
5. → Analysis complete (~22:44)

## Key Metrics to Watch For
- ✓ Success rate per agent
- ✓ Task-by-task breakdown
- ✓ Tool usage patterns
- ✓ Execution time differences
- ✓ Improvement vs baseline (%)

## If Something Goes Wrong

### Experiment stuck/hanging?
```bash
pkill -f "harbor run"
# Then restart
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
python3 -u scripts/run_swebench_comparison.py
```

### Results incomplete?
```bash
# Check what was created
ls -la results/swebench_comparison_20251222-220401/

# Analyze partial results
python3 scripts/aggregate_mcp_results.py results/swebench_comparison_20251222-220401
```

### Need full details?
See `/jobs/swebench_mcp_experiment_status.md` troubleshooting section

---

**TL;DR:** Experiment comparing 4 agents on 5 SWEBench tasks to measure MCP code search value. Running now, ~40 min total. Results in `/results/swebench_comparison_20251222-220401/`.
