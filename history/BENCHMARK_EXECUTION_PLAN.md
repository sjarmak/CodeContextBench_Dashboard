# Harbor Benchmark Execution Plan (Phase 2b: CodeContextBench-cy6)

**Status**: Infrastructure validated, ready for pilot execution  
**Date**: 2025-12-17  
**Task ID**: CodeContextBench-cy6

---

## Overview

Phase 2b executes Harbor benchmarks on **50 mined GitHub tasks** (benchmarks/github_mined/) plus **4 10figure baseline tasks** to test the hypothesis:

**"Sourcegraph code search (via MCP) improves agent success on multi-file, repository-scale tasks."**

Two agents are compared:
- **Baseline**: Claude Code with file/git operations only (no code search)
- **Treatment**: Claude Code + Sourcegraph Deep Search via MCP

---

## Execution Strategy

### Phase 2b-1: Pilot (10 tasks, both agents)
**Purpose**: Validate Harbor infrastructure, calibrate timeouts, estimate per-task cost

**Command**:
```bash
# Baseline (no Sourcegraph)
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-baseline \
  --tasks 10 \
  --concurrent 2

# MCP (with Sourcegraph Deep Search)
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-mcp \
  --tasks 10 \
  --concurrent 2
```

**Expected outcomes**:
- Baseline success: 30-40% (3-4 of 10 tasks)
- MCP success: 40-50% (4-5 of 10 tasks)
- Per-task cost: <$0.50
- Per-task duration: 5-30 minutes
- 0 infrastructure failures

**Success criteria**:
-  Both agents complete 10 tasks each without timeouts
-  Manifests captured for all 10 tasks per agent
-  Success rate consistent with hypothesis direction (MCP ≥ baseline)
-  Cost/efficiency reasonable for full run

### Phase 2b-2: Full Benchmark (50-54 tasks, both agents)
**Purpose**: Collect sufficient sample for statistical analysis

**Datasets**:
- `github_mined`: 50 real-world tasks (Kubernetes + PyTorch)
- `10figure`: 4 baseline tasks (canonical test set)
- **Optional**: 3 Trevor-validated tasks (sgt-005, sgt-006, sgt-007) for comparison

**Commands**:
```bash
# Run baseline on all 50 github_mined + 4 10figure
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-baseline \
  --tasks 50 \
  --concurrent 4

./runners/harbor_benchmark.sh \
  --benchmark 10figure \
  --agent claude-baseline \
  --tasks 4 \
  --concurrent 4

# Run MCP on same tasks
./runners/harbor_benchmark.sh \
  --benchmark github_mined \
  --agent claude-mcp \
  --tasks 50 \
  --concurrent 4

./runners/harbor_benchmark.sh \
  --benchmark 10figure \
  --agent claude-mcp \
  --tasks 4 \
  --concurrent 4
```

**Expected outcomes**:
- Total tasks: 54 × 2 agents = 108 runs
- Baseline success: 15-22 tasks (30-40%)
- MCP success: 24-30 tasks (40-55%) — **+10-15% improvement validates hypothesis**
- Total cost: ~$25-35 USD
- Total duration: 8-12 hours wall time
- >90% infrastructure success rate

### Phase 2b-3: Manifest Aggregation & Parsing
**Purpose**: Extract metrics from Harbor job outputs

**Command**:
```bash
# Extract NeMo traces or parse Claude logs, generate run_manifest.json
python3 runners/extract_nemo_traces.py \
  --jobs-dir jobs/ \
  --all \
  --output artifacts/manifests_aggregate.json
```

**Captured metrics**:
-  Task ID, agent name, benchmark name
-  Success/failure status
-  Execution time (seconds)
-  Input/output tokens (from NeMo traces or Claude logs)
-  Cost (calculated from tokens)
-  Tool usage (search queries, file operations, git operations)
-  Failure reason (if available)

**Output**: `artifacts/manifests_aggregate.json` (summary across all jobs)

---

## Agent Implementations

### BasePatchAgent (agents/base.py)
Shared functionality for all patch-based agents:
- Repository discovery (task.toml or /10figure/src)
- Git baseline capture (`git rev-parse HEAD`)
- Agent command execution
- Git diff extraction (`git diff > /logs/agent/patch.diff`)
- Optional post-run context population

### ClaudeCodeAgent (agents/claude_agent.py)
**Baseline agent** (no Sourcegraph):
- Command: `claude -p --dangerously-skip-permissions --output-format json "<instruction>"`
- Environment: `ANTHROPIC_API_KEY` only
- Tools: file operations (cat, ls, find, grep), git operations (diff, log)
- **No** code search capability

### ClaudeCodeSourcegraphMCPAgent (agents/claude_sourcegraph_mcp_agent.py)
**Treatment agent** (with Sourcegraph MCP):
- Command: Same as baseline, but with `--mcp-config` flag at runtime
- Environment: `ANTHROPIC_API_KEY`, `SRC_ACCESS_TOKEN`, `SOURCEGRAPH_URL`
- Tools: file operations, git operations **+** Sourcegraph Deep Search via MCP
- MCP configuration: Provided by Harbor at runtime

---

## Harbor Configuration

### harbor-config.yaml
```yaml
runtime:
  container_runtime: podman           # macOS uses podman machine
  timeout_sec: 3600                   # 1 hour per task
  network: bridge

agent_defaults:
  install_timeout_sec: 300            # 5 min to install agent
  memory_limit_gb: 4
  cpu_cores: 2

task_execution:
  parallel_workers: 4                 # Run 4 tasks concurrently
  result_format: json
  log_capture: true
  artifacts:
    - patch.diff
    - run_manifest.json
    - logs/
```

### datasets.yaml
```yaml
datasets:
  10figure:
    name: "10Figure Codebases"
    image: "harbor-10figure:base"
    env_var: "HARBOR_10FIGURE"
    corpus_path: "/10figure"
    validator: "/10figure/scripts/validate_patch.py"
```

---

## Task Structure (github_mined/)

Each Harbor task (sgt-001 through sgt-050) contains:

```
benchmarks/github_mined/sgt-NNN/
├── instruction.md              # Title, description, task, success criteria
├── task.toml                   # Metadata: id, language, difficulty, time_limit
├── environment/Dockerfile      # Language-specific base image
├── tests/test.sh              # Verification script (Jinja2 template)
└── repo_path                  # Path to repo in Harbor container

Example instruction.md:
  # Title
  Description of the task
  
  ## Task
  What to do...
  
  ## Success Criteria
  How to verify...

Example task.toml:
  [task]
  id = "sgt-001"
  language = "python"
  difficulty = "medium"
  category = "cross_module_bug_fix"
  time_limit = 600
  estimated_tokens = 8000
  
  [source]
  repo = "pytorch/pytorch"
  pr_url = "https://github.com/..."
  issue_url = "https://github.com/..."
```

---

## Result Capture & Analysis

### Per-Task Results
Each task produces:
- `/logs/agent/patch.diff` — Git diff output
- `/logs/agent/patch.stat` — Diff statistics
- `/logs/agent/claude.txt` — Agent execution logs (if available)
- `run_manifest.json` — Structured results (tokens, cost, duration)

### Manifest Structure (run_manifest.json)
```json
{
  "harness_name": "harbor-v1",
  "agent_name": "claude-baseline",
  "benchmark_name": "github_mined",
  "task_id": "sgt-001",
  "execution_time_sec": 245.3,
  "success": true,
  "tokens": {
    "input": 4200,
    "output": 1800,
    "total": 6000
  },
  "cost_usd": 0.0245,
  "tool_usage": {
    "search_queries": 0,
    "file_operations": 12,
    "git_operations": 3
  }
}
```

### Aggregated Metrics (manifests_aggregate.json)
```json
{
  "timestamp": "2025-12-17T20:00:00Z",
  "jobs_processed": 8,
  "total_tasks": 108,
  "total_manifests_written": 108,
  "total_traces_found": 54,
  "total_tokens": {
    "input": 432000,
    "output": 198000
  },
  "total_cost_usd": 18.45,
  "metrics_by_agent": {
    "claude-baseline": {
      "tasks_run": 54,
      "success_rate": 0.35,
      "avg_duration_sec": 320,
      "avg_tokens": 11500,
      "avg_cost_usd": 0.17
    },
    "claude-mcp": {
      "tasks_run": 54,
      "success_rate": 0.48,
      "avg_duration_sec": 380,
      "avg_tokens": 12800,
      "avg_cost_usd": 0.19
    }
  }
}
```

---

## Failure Modes & Mitigation

### Common Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Task timeouts (1 hour limit) | Medium | Set per-task limit 10-15 min in pilot; adjust based on results |
| Container resource limits (4GB RAM) | Low | Most tasks <1GB; monitor if issues arise |
| Sourcegraph API rate limits (MCP) | Medium | Stagger runs, cache search results, use conversation IDs |
| Non-deterministic test results | Low | All tasks use standard test commands (make test, pytest, go test) |
| Cost explosion | Low | Monitor first 5 tasks; abort if >$1/task |
| Flaky network (podman/Harbor) | Low | Retry failed containers; log all failures |

### Abort Criteria

Stop execution and troubleshoot if:
-  >10% infrastructure failure rate (Harbor container issues)
-  >$1.00 per task cost
-  Sourcegraph API errors affecting >5 tasks
-  Baseline success <20% (indicates task calibration issue)

---

## Timeline

| Phase | Work | Est. Duration | When |
|-------|------|---------------|------|
| **Pilot** | 10 tasks × 2 agents | 1-2 hours | Session 1 |
| **Validation** | Review pilot results, adjust if needed | 30 min | Session 1 |
| **Full Run** | 50 github_mined + 4 10figure × 2 agents | 8-12 hours | Session 2 (parallel) |
| **Aggregation** | Extract manifests, generate report | 1-2 hours | Session 3 |
| **Analysis** | Stratify by task type/difficulty, test hypothesis | 2-3 hours | Session 4 (cy6) |

---

## Next Steps

### Immediate (cy6 - this bead):
1.  Validate pilot infrastructure (agents load, tasks ready)
2.  Run 10-task pilot on baseline
3.  Run 10-task pilot on MCP
4.  Validate success rates align with hypothesis
5.  Document pilot results and any needed adjustments

### After Pilot:
- Run full benchmark (50+4 tasks × 2 agents) if pilot is successful
- Extract and aggregate manifests
- Pass results to cy6 (analysis phase)

### Long-term (von):
- Stratified analysis by task category, difficulty, language
- Generate comparative report
- Validate H1: +MCP success > baseline (+10-15% expected)

---

**Document maintainer**: CodeContextBench project team  
**Status**: Ready for pilot execution  
**Related beads**: cy6 (execution), von (analysis), wkb (mining - completed)
