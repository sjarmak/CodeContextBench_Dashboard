# CodeContextBench

**Benchmark adapter generation, verification, and result analysis platform.**

CodeContextBench generates benchmark task adapters, validates them locally with baseline agents, coordinates remote execution on GCP VMs, and ingests results into a Streamlit dashboard for visualization and comparative analysis.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                   CodeContextBench Workflow                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Adapter Generation (Local)                          │    │
│  │     ├─ Define benchmark task in benchmarks/             │    │
│  │     ├─ Generate Harbor-compatible adapters              │    │
│  │     └─ Validate adapter structure                       │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     │                                             │
│  ┌──────────────────▼──────────────────────────────────────┐    │
│  │  2. Baseline Verification (Local)                       │    │
│  │     ├─ Run sample tasks with BaselineClaudeCodeAgent    │    │
│  │     ├─ Verify metrics extraction works                  │    │
│  │     └─ Validate dashboard ingestion pipeline            │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     │                                             │
│  ┌──────────────────▼──────────────────────────────────────┐    │
│  │  3. GCP VM Benchmark Execution (Remote)                 │    │
│  │     ├─ Deploy adapters to GCP VM                        │    │
│  │     ├─ Run full agent/benchmark matrix                  │    │
│  │     ├─ Monitor execution via telemetry                  │    │
│  │     └─ Capture detailed metrics                         │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     │                                             │
│  ┌──────────────────▼──────────────────────────────────────┐    │
│  │  4. Results Ingestion & Visualization (Local)           │    │
│  │     ├─ Download VM run outputs                          │    │
│  │     ├─ Parse and normalize metrics                      │    │
│  │     ├─ Run LLM judge assessment                         │    │
│  │     └─ Ingest into Streamlit dashboard                  │    │
│  └──────────────────┬──────────────────────────────────────┘    │
│                     │                                             │
│  ┌──────────────────▼──────────────────────────────────────┐    │
│  │  5. Dashboard Analysis                                  │    │
│  │     ├─ Agent comparison charts                          │    │
│  │     ├─ Tool usage analytics                             │    │
│  │     ├─ Cost analysis                                    │    │
│  │     └─ LLM judge assessment reports                     │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Run Dashboard (Analyze Results)

```bash
# Install dashboard dependencies
pip install -r dashboard/requirements.txt

# Start Streamlit app
streamlit run dashboard/app.py
```

Open http://localhost:8501 to view experiment results, compare agents, and analyze benchmark metrics.

### Adapter Development (Local)

```bash
# 1. Create benchmark adapter in benchmarks/
# See benchmarks/README.md for structure

# 2. Verify with baseline agent locally
source .venv/bin/activate
harbor run \
  --path benchmarks/<your-benchmark> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# 3. Verify dashboard ingestion works
python scripts/ingest_results.py jobs/<timestamp>
```

### GCP VM Execution (Remote)

> **See [docs/GCP_BENCHMARK_EXECUTION.md](docs/GCP_BENCHMARK_EXECUTION.md)** for complete VM setup, execution, and monitoring guide.

Quick reference:
```bash
# 1. Deploy adapter to GCP VM (see GCP_BENCHMARK_EXECUTION.md)
# 2. Run benchmarks via VM orchestration
# 3. Download results to local machine
# 4. Ingest into dashboard (see step 3 above)
```

---

## Project Components

### Adapter Generation & Verification

- **`benchmarks/`** — Task definitions and Harbor-compatible adapters (50+ tasks)
- **`scripts/init_benchmarks.py`** — Generate and validate adapters
- **Local Harbor runs** — Baseline verification before GCP deployment

### Dashboard & Analysis

- **`dashboard/`** — Streamlit web UI for results visualization
  - Experiment browser, agent comparison, cost analysis, tool usage
  - Ingests results from `jobs/` directory
- **`src/analysis/`** — Metrics extraction and LLM judge assessment
- **`src/ingest/`** — Result parsing and database integration

### Agents

- **`agents/claude_baseline_agent.py`** — Claude Code without Sourcegraph (control)
- **`agents/mcp_variants.py`** — 4 MCP variants with different Deep Search configurations

### GCP VM Infrastructure

> **TODO** — Complete by another agent. See [docs/GCP_BENCHMARK_EXECUTION.md](docs/GCP_BENCHMARK_EXECUTION.md) placeholders.

- Infrastructure-as-code for VM provisioning
- Deployment scripts for adapters
- Monitoring and telemetry collection
- Results download and storage

---

## Workflow: Adapter → Verification → VM Execution → Analysis

### Phase 1: Adapter Development

1. Define benchmark task in TOML format (see `benchmarks/README.md`)
2. Run `scripts/init_benchmarks.py` to generate Harbor adapters
3. Validate structure: `python -m pytest tests/test_*_adapter.py`

### Phase 2: Baseline Verification (Local)

1. Execute adapter with `BaselineClaudeCodeAgent` locally:
   ```bash
   harbor run --path benchmarks/<name> \
     --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
     -n 1
   ```
2. Verify metrics extraction: Check `jobs/<timestamp>/metrics.json`
3. Verify dashboard ingestion: `python scripts/ingest_results.py jobs/<timestamp>`

### Phase 3: GCP VM Execution (Remote)

[**See docs/GCP_BENCHMARK_EXECUTION.md for:**](docs/GCP_BENCHMARK_EXECUTION.md)
- VM provisioning and SSH setup
- Adapter deployment via artifact upload
- Full agent matrix execution (baseline + 4 MCP variants)
- Monitoring and progress tracking
- Results download and storage

### Phase 4: Results Ingestion & Analysis (Local)

1. Download VM run outputs to local `jobs/` directory
2. Run ingestion pipeline:
   ```bash
   python scripts/ingest_results.py jobs/<vm-experiment>
   ```
3. Generate reports:
   ```bash
   python scripts/postprocess_experiment.py jobs/<vm-experiment> --judge
   ```
4. View in dashboard → Experiment Results tab

---

## Key Files

| Component | Location | Purpose |
|-----------|----------|---------|
| README (Benchmarks) | [benchmarks/README.md](benchmarks/README.md) | Task descriptions and adapters |
| Dashboard README | [dashboard/README.md](dashboard/README.md) | Dashboard features and usage |
| GCP Execution Guide | [docs/GCP_BENCHMARK_EXECUTION.md](docs/GCP_BENCHMARK_EXECUTION.md) | VM setup, deployment, monitoring |
| Development | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup and testing |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and component overview |
| Issue Tracking | [AGENTS.md](AGENTS.md) | Project patterns and workflows |

---

## Environment Setup

### Local Development

```bash
# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
pip install -r dashboard/requirements.txt

# Set credentials (create .env.local from example)
cp .env.local.example .env.local
# Edit to add: ANTHROPIC_API_KEY, SOURCEGRAPH_ACCESS_TOKEN, SOURCEGRAPH_URL
```

### GCP VM Setup

[**See docs/GCP_BENCHMARK_EXECUTION.md for:**](docs/GCP_BENCHMARK_EXECUTION.md)
- TODO: GCP project setup
- TODO: VM provisioning (instance type, image, sizing)
- TODO: Credential configuration
- TODO: Harbor/agent installation
- TODO: Network and storage setup
- TODO: Monitoring and alerting

---

## Contributing

1. Create a new benchmark adapter or improvement
2. Run baseline verification locally
3. File issue in `.beads/issues.jsonl` for tracking
4. Use `bd ready` to find unblocked work
5. Close issues with `bd close <id>` when complete

See [AGENTS.md](AGENTS.md) for full workflow and patterns.

---

## Status & Next Steps

### Completed ✅
- Adapter generation and validation framework
- Baseline agent verification (local)
- Dashboard with result visualization
- LLM judge assessment pipeline

### TODO 🚧

**GCP Infrastructure** (see [docs/GCP_BENCHMARK_EXECUTION.md](docs/GCP_BENCHMARK_EXECUTION.md)):
- [ ] VM provisioning and image setup
- [ ] Artifact deployment automation
- [ ] Execution monitoring dashboard
- [ ] Results download and storage
- [ ] Cost tracking and reporting

**Feature Improvements**:
- [ ] Expand benchmark suites (SWEBench, DIBench integration)
- [ ] Additional agent configurations
- [ ] Enhanced analysis and visualization
- [ ] Real-time VM execution monitoring

See `.beads/issues.jsonl` for current task tracking.
