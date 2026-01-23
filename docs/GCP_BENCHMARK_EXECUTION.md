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
- Cost tracking and optimization

---

## TODO: Complete These Sections

### VM Provisioning & Setup

**TODO: Provide:**
- [ ] GCP project ID and organization
- [ ] Recommended instance type (CPU, memory, disk)
- [ ] Base image (Container-Optimized OS, Ubuntu, custom?)
- [ ] Disk size calculations for benchmark tasks
- [ ] Network configuration (VPC, subnets, firewall rules)
- [ ] SSH key setup and authentication
- [ ] Service account configuration for artifact storage

**Example Template (update):**
```bash
# TODO: Fill in your GCP project details
GCP_PROJECT_ID="your-project-id"
GCP_ZONE="your-zone"
VM_NAME="codebench-executor-01"
MACHINE_TYPE="n1-standard-8"  # 8 vCPU, 30GB RAM - adjust based on needs
BOOT_DISK_SIZE="200GB"        # Adjust for benchmark corpus

# TODO: Create VM with your configuration
gcloud compute instances create $VM_NAME \
  --project=$GCP_PROJECT_ID \
  --zone=$GCP_ZONE \
  --machine-type=$MACHINE_TYPE \
  --boot-disk-size=$BOOT_DISK_SIZE \
  # TODO: Add remaining configuration
```

### VM Environment Configuration

**TODO: Document:**
- [ ] Harbor installation and configuration
- [ ] Claude Code CLI setup
- [ ] Podman/Docker runtime configuration
- [ ] Storage mounting for benchmark artifacts
- [ ] Environment variables and secrets management
- [ ] Telemetry and monitoring agent installation

**Example template:**
```bash
# SSH into VM
gcloud compute ssh $VM_NAME --zone=$GCP_ZONE

# TODO: Install dependencies
# - Python 3.12+
# - Harbor framework
# - Docker/Podman
# - Required Python packages

# TODO: Configure credentials
# - ANTHROPIC_API_KEY
# - SOURCEGRAPH_ACCESS_TOKEN
# - SOURCEGRAPH_URL
# - GCS credentials for results upload

# TODO: Verify installation
harbor --version
# Should show version info
```

### Artifact Deployment

**TODO: Specify:**
- [ ] How adapters are copied to VM (GCS, git, artifact registry?)
- [ ] Directory structure on VM for benchmarks
- [ ] Verification steps before benchmark execution
- [ ] Versioning strategy for deployed adapters

**Example workflow:**
```bash
# TODO: Choose deployment method and document
# Option A: Copy from GCS bucket
# Option B: Clone from git repository
# Option C: Upload via gcloud compute scp

# Example: GCS-based deployment (TODO: implement)
gsutil -m cp -r gs://your-bench-bucket/benchmarks/* /vm/benchmarks/

# Verify deployment
ls -la /vm/benchmarks/
```

### Benchmark Execution

**TODO: Document:**
- [ ] Command structure for running agent matrix
- [ ] Task grouping/batching strategy
- [ ] Timeout configurations per task type
- [ ] Parallel execution settings
- [ ] Progress monitoring and logging
- [ ] Failure recovery and retry logic

**Example execution template (TODO: complete):**
```bash
# TODO: SSH into VM and run benchmarks

# TODO: Configure execution parameters
AGENTS=("baseline" "strategic" "aggressive" "nodeep" "full-toolkit")
BENCHMARKS=("big_code_mcp" "github_mined" "dependeval" "tac_mcp_value")
TASKS_PER_BENCHMARK=5  # Adjust based on VM capacity

# TODO: Run full matrix (update with actual commands)
for benchmark in ${BENCHMARKS[@]}; do
  for agent in ${AGENTS[@]}; do
    harbor run \
      --path benchmarks/$benchmark \
      --agent-import-path agents.mcp_variants:${agent} \
      --model anthropic/claude-haiku-4-5-20251001 \
      # TODO: Add remaining flags for VM execution
  done
done

# TODO: Document expected outputs
# - jobs/<timestamp>/ directories
# - Metrics files
# - Log files
# - Error tracking
```

### Execution Monitoring

**TODO: Provide:**
- [ ] VM metrics to monitor (CPU, memory, disk I/O, network)
- [ ] Agent execution progress tracking
- [ ] Real-time log aggregation
- [ ] Alert thresholds for failures
- [ ] Dashboard for live execution status

**Example monitoring (TODO: implement):**
```bash
# Monitor VM resources during execution
watch -n 5 'gcloud compute ssh $VM_NAME --zone=$GCP_ZONE -- \
  "free -h && df -h /vm && ps aux | grep harbor"'

# TODO: Set up centralized logging
# - Cloud Logging integration
# - Custom metrics export
# - Alerting policies

# TODO: Document how to track job progress
```

### Results Retrieval & Storage

**TODO: Specify:**
- [ ] Where results are stored on VM (`jobs/` directory structure?)
- [ ] Results upload to GCS bucket
- [ ] Archival strategy for old runs
- [ ] Results download to local machine
- [ ] Storage lifecycle policies (retention, deletion)

**Example retrieval (TODO: implement):**
```bash
# Option 1: Download from VM via SSH
gcloud compute scp \
  --recurse \
  $VM_NAME:/vm/jobs/<experiment> \
  ./jobs/<experiment>

# Option 2: Download from GCS bucket
gsutil -m cp -r gs://your-bench-bucket/results/<experiment> ./jobs/

# TODO: Document verification steps
# - Check all task results present
# - Verify metrics files
# - Validate JSON structure
```

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

**TODO: Document solutions for:**
- [ ] Harbor connection failures
- [ ] Agent crashes or timeouts
- [ ] Disk space issues during execution
- [ ] Network connectivity problems
- [ ] Credential/authentication failures
- [ ] Results upload/download failures

**Example troubleshooting template:**
```bash
# SSH into VM
gcloud compute ssh $VM_NAME --zone=$GCP_ZONE

# Check Harbor status
harbor --version
harbor validate  # TODO: verify this command exists

# Check agent installation
python -c "from agents.mcp_variants import StrategicDeepSearchAgent"

# Monitor resource usage
df -h /vm
free -h
ps aux | grep harbor

# TODO: Document specific error messages and solutions
```

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
