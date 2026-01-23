# GCP VM Benchmark Execution Guide

This document covers running CodeContextBench benchmarks on GCP virtual machines. This is where the full evaluation matrix (baseline + 4 MCP agent variants) executes across all benchmark suites.

---

## Overview

**Local execution** (adapter verification) is small-scale and quick for validation.  
**GCP VM execution** (this guide) runs:
- Full benchmark suites (50+ tasks)
- All agent variants in parallel
- Extended timeouts for large codebases
- Comprehensive metrics collection

The GCP VM has pre-configured:
- Harbor framework and Podman container runtime
- Python 3.12 environment
- Sourcegraph and Anthropic credentials
- GCS bucket access for artifact/result storage

---

## VM Access & Credentials

### SSH Access to GCP VM

Use `gcloud compute ssh` to access the VM:

```bash
gcloud compute ssh <username>@<instance-name> \
  --zone <zone> \
  --project <project-id>
```

**Note**: Credentials and project details are sensitive. See project team for VM access.

### On-VM Credentials

The VM has pre-configured:
- `ANTHROPIC_API_KEY` - sourced from secure storage
- `SOURCEGRAPH_ACCESS_TOKEN` - sourced from secure storage
- GCS service account credentials for artifact/result upload

**Do NOT store credentials in code or logs.**

### VM Environment: Harbor & Podman

The VM is pre-configured with:

**Framework & Runtime:**
- Harbor framework for task orchestration
- Podman container runtime (no Docker Desktop required)
- Python 3.12 environment

**Verify Environment:**

```bash
# SSH into VM
gcloud compute ssh <username>@<instance-name> --zone <zone> --project <project-id>

# Check Harbor
harbor --version
harbor validate  # Verify framework setup

# Check Podman
podman --version
podman ps  # List containers (should be empty initially)

# Check environment
python --version  # Should be 3.12+
echo $ANTHROPIC_API_KEY | head -c 5  # Should show first 5 chars of key
echo $SOURCEGRAPH_ACCESS_TOKEN | head -c 5  # Should show first 5 chars of token
```

### Benchmark Adapters on VM

Adapters are deployed to the VM before execution.

**VM Directory Structure:**

```
/home/<username>/CodeContextBench/
├── benchmarks/          # Task definitions and adapters
│   ├── big_code_mcp/
│   ├── github_mined/
│   ├── dependeval/
│   └── tac_mcp_value/
├── agents/              # Agent implementations
├── src/                 # Core library
└── jobs/                # Execution results (populated during runs)
```

**Deployment via Git:**

```bash
# SSH into VM
gcloud compute ssh <username>@<instance-name> --zone <zone> --project <project-id>

# Clone or update repo (adapters come with the codebase)
cd ~/CodeContextBench
git pull origin main

# Verify adapters are present
ls -la benchmarks/
```

**Verification:**

```bash
# List available adapters
find benchmarks -name "task.toml" | wc -l  # Count tasks

# Validate a specific adapter
harbor validate --path benchmarks/github_mined
```

### Benchmark Execution Configuration

**TODO: Benchmark Setup & Agent Matrix (for another agent)**

Document the following for GCP VM benchmark runs:

- [ ] **Which benchmarks are tested** (big_code_mcp, github_mined, dependeval, tac_mcp_value, etc.)
- [ ] **Which agents tested on VM** (complete agent configuration):
  - `BaselineClaudeCodeAgent` (no Sourcegraph) — control group
  - `StrategicDeepSearchAgent` (MCP + selective Deep Search)
  - `DeepSearchFocusedAgent` (MCP + aggressive Deep Search)
  - `MCPNonDeepSearchAgent` (MCP + keyword/NLS only)
  - `FullToolkitAgent` (MCP + all tools)
- [ ] **Task selection strategy** (all tasks, subset, sampling method)
- [ ] **Timeout settings per benchmark type** (large codebase vs. small)
- [ ] **Agent-specific prompt configurations** (system prompts, tool guidance, etc.)
- [ ] **Expected duration per agent** (hours to complete full matrix)
- [ ] **Resource requirements** (CPU, memory, disk usage per agent/benchmark)
- [ ] **Parallelization strategy** (concurrent agents, sequential, batching)

### Benchmark Execution

Run benchmark evaluations using Harbor on the VM.

**Available Agents:**

- `BaselineClaudeCodeAgent` (no Sourcegraph) — control group
- `StrategicDeepSearchAgent` (MCP + selective Deep Search)
- `DeepSearchFocusedAgent` (MCP + aggressive Deep Search)
- `MCPNonDeepSearchAgent` (MCP + keyword/NLS only)
- `FullToolkitAgent` (MCP + all tools)

**Run a Benchmark:**

```bash
# SSH into VM
gcloud compute ssh <username>@<instance-name> --zone <zone> --project <project-id>

# Navigate to repo
cd ~/CodeContextBench

# Run a subset of tasks with baseline agent (fast verification)
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 5  # Run 5 tasks

# Results will be in:
ls -la jobs/
```

**Run Full Benchmark Suite:**

See **[Benchmark Execution Configuration](#benchmark-execution-configuration)** (above) for full details on which agents/benchmarks are tested. Once configured, run:

```bash
# Example: Run baseline + 4 MCP variants on github_mined benchmark
# (Exact commands depend on benchmark setup configuration)

for agent in baseline strategic aggressive nodeep full-toolkit; do
  harbor run \
    --path benchmarks/github_mined \
    --agent-import-path agents.mcp_variants:${agent} \
    --model anthropic/claude-haiku-4-5-20251001 \
    # Additional flags TBD based on benchmark configuration
done
```

**Monitor Execution:**

```bash
# Check running containers
podman ps

# View Harbor logs
tail -f jobs/<timestamp>/job.log

# Monitor disk usage
df -h
du -sh jobs/
```

**Expected Outputs:**

```
jobs/<timestamp>/
├── config.json          # Execution configuration
├── result.json          # Aggregated results
├── job.log              # Execution log
└── <task-id>_<suffix>/  # Per-task results
    ├── metrics.json     # Metrics (token usage, success, etc.)
    ├── trace.json       # Execution trace
    └── logs/            # Task-specific logs
```

### Execution Monitoring & Management

**On-VM Monitoring:**

```bash
# SSH into VM
gcloud compute ssh <username>@<instance-name> --zone <zone> --project <project-id>

# Monitor containers in real-time
watch podman ps -a --format "{{.ID}} {{.Status}} {{.Names}}"

# Check Harbor job status
tail -f ~/CodeContextBench/jobs/*/job.log

# Monitor disk usage (ensure enough space for benchmark artifacts)
watch df -h

# Monitor memory and CPU
free -h
top
```

**Stopping/Resuming Execution:**

```bash
# List running containers
podman ps -a

# Stop a specific container (graceful shutdown)
podman stop <container-id>

# Force stop (if stuck)
podman kill <container-id>

# Clean up stopped containers
podman system prune -f
```

**TODO: GCP Cloud Logging Integration**
- [ ] Configure Cloud Logging agent on VM
- [ ] Export Harbor logs to Cloud Logging
- [ ] Set up Cloud Monitoring alerts for resource usage
- [ ] Create dashboards for execution progress

### Results Retrieval & Storage

**Results Location on VM:**

```
~/CodeContextBench/jobs/<timestamp>/
├── config.json         # Run configuration
├── result.json         # Aggregated metrics
├── job.log             # Execution log
└── <task-dir>/         # Per-task outputs
    ├── metrics.json
    ├── trace.json
    └── logs/
```

**Download Results to Local Machine:**

```bash
# Copy entire experiment from VM to local
gcloud compute scp \
  --recurse \
  <username>@<instance-name>:~/CodeContextBench/jobs/<timestamp> \
  ./jobs/<timestamp> \
  --zone <zone> \
  --project <project-id>

# Or: Copy only metrics (smaller, faster)
gcloud compute scp \
  --recurse \
  <username>@<instance-name>:~/CodeContextBench/jobs/<timestamp>/ \
  ./jobs/<timestamp>/ \
  --zone <zone> \
  --project <project-id>
```

**Verify Downloaded Results:**

```bash
# Check directory structure
ls -la jobs/<timestamp>/

# Verify all metric files are present
find jobs/<timestamp> -name "metrics.json" | wc -l

# Validate JSON structure
python -m json.tool jobs/<timestamp>/config.json
python -m json.tool jobs/<timestamp>/result.json
```

**TODO: GCS Bucket Storage**
- [ ] Auto-upload completed runs to GCS bucket
- [ ] Archival and lifecycle policies
- [ ] Access controls and versioning

---

## Post-Execution Workflow

Once VM execution completes and results are downloaded locally:

### 1. Ingest Results into Dashboard

```bash
# Parse VM results and prepare for dashboard
python scripts/ingest_results.py jobs/<experiment-from-vm>

# Verify ingestion
python -c "from src.ingest.database import load_experiments; \
  print(load_experiments('jobs/'))"
```

### 2. Generate Analysis Reports

```bash
# Run LLM judge assessment
python scripts/postprocess_experiment.py jobs/<experiment> --judge

# Generate comparison reports
python scripts/analyze_mcp_experiment.py jobs/<experiment>
```

### 3. View Results in Dashboard

```bash
# Start dashboard
streamlit run dashboard/app.py

# Navigate to "Experiment Results" tab to view VM execution results
```

---

## Cost Optimization

**TODO: Document:**
- [ ] Instance sizing trade-offs (CPU vs. execution time vs. cost)
- [ ] Spot VM vs. on-demand considerations
- [ ] Batch execution strategy (group tasks to reduce startup overhead)
- [ ] Storage costs for benchmark artifacts and results
- [ ] Network egress costs

**Example cost estimation template (TODO: fill in):**
```
VM Instance Cost:
- Machine type: n1-standard-8
- Hourly rate: $0.35
- Expected duration per experiment: 6-8 hours
- Cost per full matrix run: ~$2.50-3.50

Storage Costs:
- Benchmark artifacts: ~50GB @ $0.02/GB/month = $1.00
- Results storage: ~100GB @ $0.02/GB/month = $2.00
- Total monthly: ~$3-5 (adjust based on retention)

Total cost per benchmark cycle: ~$5-10
```

---

## Troubleshooting

**Check Harbor & Podman:**

```bash
# SSH into VM
gcloud compute ssh <username>@<instance-name> --zone <zone> --project <project-id>

# Verify Harbor
harbor --version
harbor validate --path benchmarks/github_mined

# Check Podman runtime
podman ps -a  # List all containers
podman ps     # List running containers

# View container logs
podman logs <container-id>
```

**Common Issues:**

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| "Harbor not found" | Framework not installed | Contact team; VM should have Harbor pre-installed |
| Container exits immediately | Check pod logs: `podman logs <id>` | Review error, check agent implementation |
| "Out of disk space" | `df -h` shows 100% usage | Stop containers (`podman stop -a`), clean up old runs, expand disk |
| Credential errors | `echo $ANTHROPIC_API_KEY` shows empty | Credentials not loaded; verify VM environment setup |
| Network timeouts | Task hangs during execution | Check VM network, Sourcegraph availability, Internet connectivity |
| Metrics not captured | `metrics.json` missing from results | Verify Harbor is capturing metrics; check config |

**Manual Cleanup:**

```bash
# Stop all containers
podman stop -a

# Remove stopped containers
podman rm -a

# Prune unused images and volumes
podman system prune -a --volumes
```

**TODO: Extended Troubleshooting**
- [ ] Common Harbor errors and solutions
- [ ] Agent-specific failure patterns
- [ ] VM resource limit debugging
- [ ] Data corruption recovery

---

## References

**TODO: Link to:**
- [ ] GCP Cloud Computing documentation
- [ ] Harbor framework documentation
- [ ] Claude Code CLI setup guide
- [ ] Infrastructure-as-Code templates (Terraform/etc.)
- [ ] VM image/snapshot management

---

## Appendix: VM Deployment Checklist

- [ ] GCP project and credentials configured
- [ ] VM instance provisioned and accessible via SSH
- [ ] Harbor and required packages installed
- [ ] Benchmark adapters deployed to VM
- [ ] API keys configured (ANTHROPIC_API_KEY, SOURCEGRAPH_ACCESS_TOKEN)
- [ ] Disk space verified for benchmark corpus
- [ ] Artifact storage (GCS bucket or local) configured
- [ ] Monitoring and logging configured
- [ ] Test run with 1-2 small tasks succeeds
- [ ] Results successfully download to local machine
- [ ] Dashboard ingestion pipeline verified
