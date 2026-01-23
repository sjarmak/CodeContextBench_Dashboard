# GCP VM Benchmark Execution Guide

This document covers running SWE-bench Pro evaluations on the GCP VM, comparing **Baseline Claude Code** vs **Deep Search Hybrid MCP** agents.

**VM Instance**: `instance-20251230-155636`  
**Zone**: `us-central1-f`  
**Project**: `benchmarks-482815`  
**Working Directory**: `~/evals/custom_agents/agents/claudecode/`

---

## Table of Contents

1. [Overview](#overview)
2. [VM Access](#vm-access)
3. [Environment Setup](#environment-setup)
4. [Running Benchmarks](#running-benchmarks)
5. [Configuration Examples](#configuration-examples)
6. [Disk Management](#disk-management)
7. [Monitoring Execution](#monitoring-execution)
8. [Results Sync to Mac](#results-sync-to-mac)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The GCP VM runs SWE-bench Pro evaluations using:
- **Harbor Framework** for task orchestration
- **Docker** containers for isolated task execution  
- **Claude Opus 4.5** as the primary model
- **V2 Experiment Runner** (`bench-eval-v2`) for matrix expansion and canonical outputs

### Agent Variants

| Agent Mode | Description | MCP Enabled |
|------------|-------------|-------------|
| `baseline` | Pure Claude Code with all default tools, NO MCP | ❌ |
| `deepsearch_hybrid` | Claude Code + Deep Search MCP + all local tools | ✅ |
| `deepsearch` | Deep Search MCP only, local search blocked | ✅ |
| `sourcegraph` | Full Sourcegraph MCP v1, local search blocked | ✅ |

### Repository Mirroring (sg-benchmarks)

All benchmark repositories are mirrored at **https://github.com/sg-benchmarks/** with HEAD pinned to task-specific commits. This ensures Deep Search results match the agent's local working copy.

---

## VM Access

### SSH into the VM

```bash
gcloud compute ssh stephanie_jarmak@instance-20251230-155636 \
  --zone us-central1-f \
  --project benchmarks-482815
```

### Directory Structure

```
~/evals/custom_agents/agents/claudecode/
├── agents/                          # Agent implementations
│   ├── claude_baseline_agent.py     # Main agent with MCP toggle
│   ├── mcp_agents.py                # Alternative MCP agents
│   └── metrics_extractor.py         # Token/cost extraction
├── config/                          # V1 Harbor configs
│   ├── baseline_opus_50.yaml
│   ├── deepsearch_hybrid_opus_50.yaml
│   └── swebenchpro_50_tasks.txt     # Canonical 50-task list
├── configs_v2/                      # V2 experiment configs
│   ├── smoke_test.yaml
│   └── examples/
│       ├── minimal.yaml             # Single task test
│       ├── single.yaml              # Single agent test
│       └── swebenchpro_50_tasks_comparison.yaml  # Full 50-task
├── v2/                              # V2 runner implementation
├── jobs/                            # Harbor job outputs
├── eval_runs_v2/                    # V2 canonical outputs
├── logs/                            # Execution logs
├── bench-eval-v2                    # V2 CLI wrapper
├── run_comparison.sh                # V1 comparison script
└── cleanup.sh                       # Disk cleanup utility
```

---

## Environment Setup

### Load Credentials

```bash
# Source environment file
source ~/evals/.env.local

# CRITICAL: Export variables for subprocesses
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN

# Verify credentials are set
echo "Anthropic: ${ANTHROPIC_API_KEY:0:10}..."
echo "Sourcegraph: ${SOURCEGRAPH_ACCESS_TOKEN:0:10}..."
```

### Verify Harbor Installation

```bash
# Check Harbor is available
harbor --version

# Verify agent module
cd ~/evals/custom_agents/agents/claudecode
python -c "from agents.claude_baseline_agent import BaselineClaudeCodeAgent; print('✓ Agent loads')"
```

### Pre-Run Disk Cleanup

```bash
# Check disk usage
df -h

# Run cleanup if needed (threshold: 80%)
./cleanup.sh

# Force cleanup regardless of usage
./cleanup.sh --force
```

---

## Running Benchmarks

### V2 Runner (Recommended)

The V2 runner (`bench-eval-v2`) provides matrix expansion, deterministic IDs, and canonical outputs.

**Dry Run (Preview)**:
```bash
cd ~/evals/custom_agents/agents/claudecode
./bench-eval-v2 dry-run -c configs_v2/examples/minimal.yaml
```

**Run Experiment**:
```bash
# Single task test (fastest)
./bench-eval-v2 run -c configs_v2/examples/minimal.yaml

# Single MCP variant test
./bench-eval-v2 run -c configs_v2/examples/single.yaml

# Full 50-task comparison (production)
./bench-eval-v2 run -c configs_v2/examples/swebenchpro_50_tasks_comparison.yaml
```

**CLI Options**:
```bash
./bench-eval-v2 run -c <config.yaml> [OPTIONS]

Options:
  --jobs-dir DIR      Harbor jobs directory (default: jobs)
  --output-dir DIR    V2 output directory (default: eval_runs_v2)
  --force-rebuild     Force Docker environment rebuild
  -v, --verbose       Verbose output
```

### V1 Runner (Legacy)

For quick comparison runs without V2 features:

```bash
cd ~/evals/custom_agents/agents/claudecode

# Verify setup
./run_comparison.sh verify

# Run baseline (no MCP)
./run_comparison.sh baseline

# Run hybrid (MCP + local tools)
./run_comparison.sh hybrid

# Run both sequentially
./run_comparison.sh both
```

---

## Configuration Examples

### 1. Minimal Single-Task Ablation

**File**: `configs_v2/examples/minimal.yaml`  
**Use Case**: Quick testing, debugging  
**Duration**: 30-60 minutes  
**Tasks**: 1 (navidrome)

```yaml
experiment_name: minimal_v2_test
description: "Minimal v2 test: single task, baseline vs MCP"

benchmarks:
  - name: swebenchpro
    version: "1.0"
    task_selector:
      type: explicit
      task_ids:
        - "instance_navidrome__navidrome-bf2bcb12799b21069f137749e0c331f761d1f693"

models:
  - anthropic/claude-opus-4-5

mcp_modes:
  - baseline
  - deepsearch_hybrid

execution:
  concurrency: 1
  timeout_seconds: 3600

pairing:
  enabled: true
  baseline_mode: baseline
```

### 2. Single MCP Variant Test

**File**: `configs_v2/examples/single.yaml`  
**Use Case**: Test MCP without baseline comparison  
**Duration**: 30 minutes

```yaml
experiment_name: single_mcp_test
mcp_modes:
  - deepsearch_hybrid  # No baseline, MCP only

pairing:
  enabled: false
```

### 3. Full 50-Task Comparison

**File**: `configs_v2/examples/swebenchpro_50_tasks_comparison.yaml`  
**Use Case**: Production ablation study  
**Duration**: 24-48 hours  
**Tasks**: 50 across 10 repositories

```yaml
experiment_name: swebenchpro_50_tasks_baseline_vs_hybrid
description: "50-task ablation: Baseline (no MCP) vs Hybrid (Deep Search + local tools)"

benchmarks:
  - name: swebenchpro
    version: "1.0"
    task_selector:
      type: explicit
      task_ids:
        # 50 tasks across: ansible, element-web, flipt, vuls,
        # teleport, openlibrary, navidrome, NodeBB, webclients, tutanota

execution:
  concurrency: 2              # 2 concurrent trials (recommended)
  timeout_seconds: 7200       # 2 hours per task

pairing:
  enabled: true
  baseline_mode: baseline

tags:
  - 50-task-comparison
  - baseline-vs-hybrid
  - full-ablation
```

### Timeout Settings Reference

| Task Complexity | Timeout | Concurrency |
|-----------------|---------|-------------|
| Single task test | 600s (10min) | 1 |
| Standard task | 3600s (1hr) | 2-3 |
| Complex task | 7200s (2hr) | 2 |
| 50-task run | 7200s | 2 |

---

## Disk Management

The VM has limited disk space. Docker images and job artifacts accumulate quickly.

### Check Disk Usage

```bash
df -h
du -sh ~/evals/custom_agents/agents/claudecode/jobs/
docker system df
```

### Cleanup Script

```bash
# Automatic cleanup (runs if usage > 80%)
./cleanup.sh

# Force cleanup regardless of usage
./cleanup.sh --force

# Set custom threshold
./cleanup.sh --threshold 70
```

### Manual Docker Cleanup

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -af

# Full system prune (aggressive)
docker system prune -a -f --volumes
```

---

## Monitoring Execution

### Watch Logs

```bash
# V2 experiment logs
tail -f logs/*.log

# Harbor job logs
tail -f jobs/*/job.log

# Specific trial logs
tail -f jobs/<job_name>/<trial_name>/trial.log
```

### Check Docker Containers

```bash
# Running containers
docker ps

# All containers (including stopped)
docker ps -a

# Container resource usage
docker stats
```

### Check Experiment Status

```bash
# V2 status command
./bench-eval-v2 status -e <experiment_id>

# Or check manifest directly
cat eval_runs_v2/<experiment_id>/manifest.json | jq '.status'
```

### Check Task Results

```bash
# Count completed tasks
ls eval_runs_v2/<experiment_id>/runs/ | wc -l

# View task reward
jq '.verifier_result.rewards.reward' jobs/<job>/<trial>/result.json
```

---

## Results Sync to Mac

After experiments complete, sync results to your Mac for dashboard analysis.

### Sync Script (on Mac)

The sync script is at `~/evals/sync_script_targeted.sh`:

```bash
#!/bin/bash

# Tar the files on remote, copy tar, then extract locally
echo "Creating tar of target files on remote..."
gcloud compute ssh stephanie_jarmak@instance-20251230-155636 \
  --zone us-central1-f \
  --project benchmarks-482815 \
  --command "cd /home/stephanie_jarmak/evals/custom_agents/agents/claudecode/jobs && tar czf /tmp/sync.tar.gz ."

echo "Copying tar file..."
gcloud compute scp \
  --zone us-central1-f \
  --project benchmarks-482815 \
  stephanie_jarmak@instance-20251230-155636:/tmp/sync.tar.gz \
  /tmp/sync.tar.gz

echo "Extracting to local directory..."
cd ~/evals/custom_agents/agents/claudecode/jobs
tar xzf /tmp/sync.tar.gz

echo "Cleaning up..."
rm /tmp/sync.tar.gz
gcloud compute ssh stephanie_jarmak@instance-20251230-155636 \
  --zone us-central1-f \
  --project benchmarks-482815 \
  --command "rm /tmp/sync.tar.gz"

echo "Done!"
```

**Usage (on Mac)**:
```bash
cd ~/evals
./sync_script_targeted.sh
```

### Sync V2 Outputs

To also sync V2 canonical outputs:

```bash
# On Mac
gcloud compute ssh stephanie_jarmak@instance-20251230-155636 \
  --zone us-central1-f \
  --project benchmarks-482815 \
  --command "cd /home/stephanie_jarmak/evals/custom_agents/agents/claudecode/eval_runs_v2 && tar czf /tmp/eval_runs_v2.tar.gz ."

gcloud compute scp \
  --zone us-central1-f \
  --project benchmarks-482815 \
  stephanie_jarmak@instance-20251230-155636:/tmp/eval_runs_v2.tar.gz \
  /tmp/eval_runs_v2.tar.gz

cd ~/evals/custom_agents/agents/claudecode/eval_runs_v2
mkdir -p .
tar xzf /tmp/eval_runs_v2.tar.gz
rm /tmp/eval_runs_v2.tar.gz
```

### Key Files for Analysis

```
jobs/<job_name>/
├── result.json                        # Job-level aggregated results
├── config.json                        # Job configuration
└── <trial_name>/
    ├── result.json                    # Per-task result with reward
    └── agent/
        ├── claude-code.txt            # Full agent trace (JSON lines)
        ├── .mcp.json                  # MCP configuration used
        └── CLAUDE.md                  # Guidance document

eval_runs_v2/<experiment_id>/
├── manifest.json                      # Experiment metadata
├── index.json                         # Quick lookup indices
└── runs/<run_id>/
    └── results.json                   # Canonical run results
```

---

## Troubleshooting

### Common Issues

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| "Harbor not found" | `which harbor` returns nothing | Reinstall: `pip install harbor` |
| "Waiting for permission" hangs | Missing CLI flag | Verify `--dangerously-skip-permissions` in agent |
| Node.js installation fails | Docker install issue | Check `agents/install-claude-code.sh.j2` uses NodeSource |
| MCP not being used | Wrong env var | Ensure `BASELINE_MCP_TYPE=deepsearch_hybrid` is set |
| Task timeout | Insufficient time | Increase `timeout_seconds` in config |
| Out of disk space | Docker accumulation | Run `./cleanup.sh --force` |
| Version mismatch in Deep Search | Wrong repo searched | Verify `SWEBENCH_REPO_COMMIT` env var set |
| Token counts null in result.json | Harbor limitation | Parse `claude-code.txt` for token data |

### Debugging Steps

1. **Check agent trace**:
   ```bash
   cat jobs/<job>/<trial>/agent/claude-code.txt | head -100
   ```

2. **Check MCP config**:
   ```bash
   cat jobs/<job>/<trial>/agent/.mcp.json
   ```

3. **Check verifier output**:
   ```bash
   cat jobs/<job>/<trial>/verifier/test-stdout.txt
   ```

4. **Check CLAUDE.md was uploaded**:
   ```bash
   cat jobs/<job>/<trial>/agent/CLAUDE.md
   ```

### Extract Token Usage

Token usage is in `claude-code.txt` (JSON lines), not Harbor's result.json:

```bash
python agents/metrics_extractor.py jobs/<job>/<trial>/
```

Or manually:
```bash
grep '"usage"' jobs/<job>/<trial>/agent/claude-code.txt | tail -1
```

---

## Resource Requirements

### VM Specifications

| Resource | Current | Recommended |
|----------|---------|-------------|
| CPU | 8 vCPU | 8-16 vCPU |
| RAM | 32 GB | 32-64 GB |
| Disk | 200 GB | 200-500 GB SSD |

### Expected Durations

| Configuration | Tasks | Runs | Duration |
|---------------|-------|------|----------|
| `minimal.yaml` | 1 | 2 | 30-60 min |
| `single.yaml` | 1 | 1 | 15-30 min |
| `swebenchpro_50_tasks_comparison.yaml` | 50 | 2 | 24-48 hr |

### Parallelization Recommendations

- **Concurrency 1**: Sequential, lowest resource usage
- **Concurrency 2**: Recommended for production runs
- **Concurrency 3-4**: Faster but may cause resource contention

---

## Quick Reference

### Start a 50-Task Comparison

```bash
# SSH into VM
gcloud compute ssh stephanie_jarmak@instance-20251230-155636 \
  --zone us-central1-f \
  --project benchmarks-482815

# Setup
cd ~/evals/custom_agents/agents/claudecode
source ~/evals/.env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN

# Clean disk if needed
./cleanup.sh

# Run
./bench-eval-v2 run -c configs_v2/examples/swebenchpro_50_tasks_comparison.yaml
```

### Sync Results (on Mac)

```bash
cd ~/evals
./sync_script_targeted.sh
```

---

## Related Documentation

- [EVAL_FRAMEWORK.md](../swe_bench_configs/EVAL_FRAMEWORK.md) - Full framework documentation
- [SG_BENCHMARKS_UPDATE.md](https://github.com/sjarmak/CodeContextBench) - Repository mirroring details
- [Harbor Framework](https://harborframework.com/) - Task orchestration
- [sg-benchmarks Organization](https://github.com/sg-benchmarks/) - Mirrored repositories
