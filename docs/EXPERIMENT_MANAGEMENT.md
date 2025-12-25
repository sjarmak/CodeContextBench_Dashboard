# Experiment Management Guide

This guide establishes standards for organizing, naming, and documenting experiments in CodeContextBench.

---

## Directory Structure

```
jobs/
├── README.md                          # Index of experiments
├── history/                           # Archived logs and deprecated runs
│
├── <experiment-name>/                 # Organized experiment (preferred)
│   ├── MANIFEST.md                    # REQUIRED: Experiment description
│   ├── config.json                    # Experiment configuration
│   ├── REPORT.md                      # Results summary (generated)
│   ├── analysis.json                  # Metrics analysis (generated)
│   ├── <agent-variant>/               # Per-agent results
│   │   ├── metrics_report.json
│   │   └── <task-run-dir>/
│   └── *.log                          # Execution logs
│
└── YYYY-MM-DD__HH-MM-SS/              # Raw harbor output (auto-generated)
    ├── config.json
    ├── result.json
    ├── job.log
    └── <task-id>__<suffix>/           # Individual task runs
```

---

## Naming Conventions

### Experiment Names (Required)

Use descriptive, semantic names with date suffixes:

```
<experiment-type>-<focus>-<YYYYMMDD>[-<variant>]
```

**Examples:**
```
mcp-prompt-experiment-20251222          # Prompt strategy comparison
bigcode-comparison-20251220             # Big code benchmark comparison
dependeval-baseline-20251220            # DependEval with baseline agent
full-mcp-experiment-20251223            # All agents, all tasks
agent-ablation-deepsearch-20251223      # Deep Search ablation study
```

**BAD names (avoid):**
```
test-run-20251220                       # What was tested?
comparison-20251220-1254                # What's being compared?
2025-12-20__08-43-21                    # Raw timestamp only - no context
single-task-correct                     # Not dated, unclear purpose
```

### Agent Variant Names

Use consistent short names that map to agent classes:

| Short Name | Agent Class | File |
|------------|-------------|------|
| `baseline` | `BaselineClaudeCodeAgent` | `agents/claude_baseline_agent.py` |
| `aggressive` | `DeepSearchFocusedAgent` | `agents/mcp_variants.py` |
| `strategic` | `StrategicDeepSearchAgent` | `agents/mcp_variants.py` |
| `nodeep` | `MCPNonDeepSearchAgent` | `agents/mcp_variants.py` |
| `full-toolkit` | `FullToolkitAgent` | `agents/mcp_variants.py` |

---

## Experiment Manifest (MANIFEST.md)

**Every experiment directory MUST have a MANIFEST.md file.**

### Template

```markdown
# Experiment: <Title>

**Date:** YYYY-MM-DD
**Status:** Running | Complete | Failed | Abandoned
**Owner:** <name or agent session>

## Hypothesis

State what you're testing and what you expect to find.

## Configuration

- **Model:** anthropic/claude-haiku-4-5-20251001
- **Benchmark:** big_code_mcp (4 tasks) | github_mined (25 tasks) | etc.
- **Tasks:** [list specific tasks if not full benchmark]
- **Agents:** baseline, aggressive, strategic
- **Runs per config:** 1 | 3 | 5

## Variables

| Variable | Values Tested |
|----------|---------------|
| Prompt style | baseline, aggressive, strategic |
| Model | haiku-4-5 |
| Deep Search enabled | yes/no |

## Results Summary

| Agent | Success Rate | Avg Time | Notes |
|-------|--------------|----------|-------|
| baseline | 75% | 4:26 | No MCP |
| aggressive | 100% | 2:44 | 2 deep searches |
| strategic | 100% | 3:39 | 1 deep search |

## Key Findings

1. Finding 1
2. Finding 2

## Raw Outputs

- `config.json` - Experiment configuration
- `*/metrics_report.json` - Per-agent metrics
- `REPORT.md` - Auto-generated comparison report

## Follow-up

- [ ] Next experiment to run based on findings
- [ ] Issues to investigate
```

---

## Running Experiments

### Before Running

1. **Create experiment directory with MANIFEST.md:**
   ```bash
   mkdir -p jobs/my-experiment-20251223
   # Create MANIFEST.md with hypothesis and config
   ```

2. **Source credentials:**
   ```bash
   source .env.local
   export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
   ```

3. **Verify Docker space:**
   ```bash
   docker system df
   bash scripts/docker-cleanup.sh  # If needed
   ```

### Running with Scripts

**Full comparison experiment:**
```bash
./scripts/run_full_mcp_experiment.sh
# Creates: jobs/full-mcp-experiment-<timestamp>/
```

**Quick per-benchmark comparison:**
```bash
./scripts/run_mcp_comparison.sh benchmarks/big_code_mcp/big-code-vsc-001
```
Runs baseline + MCP variants with standardized logging under `results/` for faster iteration.

**Single task smoke test:**
```bash
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

### After Running

1. **Move raw output to experiment directory** (if harbor created timestamped dir):
   ```bash
   mv jobs/2025-12-23__* jobs/my-experiment-20251223/raw/
   ```

2. **Run analysis:**
   ```bash
   python3 scripts/analyze_mcp_experiment.py jobs/my-experiment-20251223
   ```

3. **Update MANIFEST.md** with results summary

4. **Clean up raw harbor directories** that weren't part of an experiment:
   ```bash
   # Move to history or delete if not needed
   mv jobs/2025-12-20__* jobs/history/
   ```

---

## Interpreting Results

### Key Metrics

| Metric | Location | Meaning |
|--------|----------|---------|
| `reward` | `result.json`, `metrics_report.json` | 1.0 = pass, 0.0 = fail |
| `duration_sec` | `metrics_report.json` | Time to complete task |
| `deep_search_calls` | `analysis.json`, logs | Number of deep search invocations |
| `success_rate` | `metrics_report.json` | % tasks passing |

### Result Files

| File | Contains | Use For |
|------|----------|---------|
| `result.json` | Aggregated pass/fail per task | Quick status check |
| `metrics_report.json` | Detailed per-agent stats | Quantitative comparison |
| `analysis.json` | Cross-agent analysis | Finding patterns |
| `REPORT.md` | Human-readable summary | Sharing results |
| `llm_judge_results.json` | LLM quality ratings | Code/retrieval quality |

### Reading Agent Logs

Agent output is in:
```
<experiment>/<agent>/<task-run>/agent/claude.txt
```

Look for:
- Tool calls and their results
- Deep Search queries and responses
- Error messages
- Time spent in different phases

---

## Cleanup & Archival

### Organizing Orphaned Runs

Raw harbor runs (timestamp-only dirs) should be:
1. **Moved to an experiment** if part of a planned experiment
2. **Moved to `jobs/history/`** if kept for reference
3. **Deleted** if debug/failed runs

```bash
# Find orphan timestamp directories
ls jobs/ | grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2}__"

# Move to history
mv jobs/2025-12-20__* jobs/history/
```

### What to Keep

**Keep:**
- Complete experiments with MANIFEST.md
- Successful comparison runs
- Runs with interesting failures to investigate

**Archive to history/:**
- Debug runs that succeeded
- Runs superseded by better experiments

**Delete:**
- Failed runs with known issues (after fixing)
- Duplicate runs
- Empty/incomplete runs

---

## Quick Reference

```bash
# List all experiments with manifests
find jobs -name "MANIFEST.md" -exec dirname {} \;

# List orphaned timestamp directories
ls jobs/ | grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2}__"

# Quick experiment status
for d in jobs/*/MANIFEST.md; do
  exp=$(dirname "$d")
  status=$(grep "Status:" "$d" | head -1)
  echo "$exp: $status"
done

# Find experiments by date
ls -d jobs/*20251222*

# Cleanup check
ls jobs/ | wc -l  # Should be reasonable (<20 active)
```
