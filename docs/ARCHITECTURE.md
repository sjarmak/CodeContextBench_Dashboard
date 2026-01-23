# CodeContextBench Architecture

CodeContextBench is a **benchmark evaluation platform** for measuring how Sourcegraph code intelligence improves coding agent performance. The system features:

- **Streamlit Dashboard**: Web UI for benchmark management, execution, and result analysis
- **VM Orchestration**: Harbor + Podman infrastructure running agents in isolated containers
- **Multiple Agent Variants**: Claude Code baseline + four MCP variants with different Sourcegraph tool configurations
- **Comprehensive Evaluation**: Automated metrics extraction, LLM judge assessment, and interactive visualization

## Design Philosophy

- **Dashboard-first UX**: Primary interaction through Streamlit web interface (no CLI required)
- **Reproducible Evaluation**: Deterministic task environments, isolated VM execution, captured metrics
- **Fair Comparison**: Baseline and MCP agents have identical autonomous capabilities
- **Extensible Framework**: New benchmarks, agents, and metrics can be added independently


## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    CodeContextBench Platform                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           Streamlit Dashboard (Web UI)                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐   │   │
│  │  │  Home    │ │Benchmark │ │Run Tasks │ │Results   │   │   │
│  │  │          │ │Manager   │ │& Monitor │ │& Charts  │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘   │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │ (triggers execution, displays results)   │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │         Harbor Orchestration + Podman VMs               │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │   │
│  │  │ Benchmark    │ │ Benchmark    │ │ Benchmark   │    │   │
│  │  │ Task VM      │ │ Task VM      │ │ Task VM     │    │   │
│  │  │ (Isolated)   │ │ (Isolated)   │ │ (Isolated)  │    │   │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬──────┘    │   │
│  │         │                │                │            │   │
│  │  ┌──────▼────────────────▼────────────────▼──────────┐ │   │
│  │  │      Agent Execution (Baseline/MCP Variants)      │ │   │
│  │  │  ┌───────────────┐  ┌───────────────────────┐    │ │   │
│  │  │  │ Claude Code   │  │ Sourcegraph MCP      │    │ │   │
│  │  │  │ (autonomous)  │  │ (Deep Search, etc)   │    │ │   │
│  │  │  └───────────────┘  └───────────────────────┘    │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │ (Harbor captures metrics)                │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │         Metrics & Analysis Pipeline                      │   │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────────────┐   │   │
│  │  │ Extraction │ │ LLM Judge  │ │ Visualization &  │   │   │
│  │  │ (Harbor)   │ │ Assessment │ │ Reporting        │   │   │
│  │  └────────────┘ └────────────┘ └───────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Core Components

### Dashboard (`dashboard/`)
Streamlit web application for benchmark management and analysis:
- **app.py**: Main entry point, page routing, session state
- **views/**: Page implementations (Home, Benchmark Manager, Run Benchmarks, Results, Analysis)
- **utils/**: Shared utilities (filters, navigation, analysis loaders)
- **components/**: Reusable UI components

### Agents (`agents/`)
Claude Code variants with different Sourcegraph configurations:
- **BaselineClaudeCodeAgent**: No MCP, pure Claude Code autonomous
- **StrategicDeepSearchAgent**: MCP with selective Deep Search usage (recommended)
- **DeepSearchFocusedAgent**: MCP with aggressive Deep Search prompting
- **MCPNonDeepSearchAgent**: MCP with keyword/NLS only (no Deep Search)
- **FullToolkitAgent**: MCP with all tools, neutral prompting

### Infrastructure (`infrastructure/`, `runners/`)
Harbor + Podman execution environment:
- **Podman VMs**: Isolated containers for each benchmark task execution
- **Harbor CLI**: Orchestrates agent execution, captures outputs and metrics
- **Custom Runners**: Benchmark lifecycle, profile execution, post-processing

### Metrics & Analysis (`src/analysis/`, `src/ingest/`)
Post-execution analysis pipeline:
- **Metrics Extraction**: Parses Harbor outputs for execution traces
- **LLM Judge**: Claude-based assessment of solution quality
- **Visualization**: Plotly charts, cost analysis, tool usage heatmaps

### Benchmarks (`benchmarks/`)
50+ task suites across multiple domains:
- **big_code_mcp** (4 tasks): Large codebases (VS Code, Kubernetes, Servo, TensorRT)
- **github_mined** (25 tasks): Real PyTorch PR tasks
- **dependeval** (9 tasks): Multi-file dependency reasoning
- **TAC** (9+ tasks): Agent company benchmark suite
- **repoqa**: Tool-sensitive code understanding
- Plus SWEBench, DIBench, Kubernetes Docs integrations

## Directory Structure

### Core Components

#### `agents/` - Agent Implementations

All agents extend Harbor's built-in `ClaudeCode` and inject autonomous environment variables:

- **claude_baseline_agent.py** - Claude baseline (autonomous mode, no Sourcegraph)
  - Extends: `harbor.agents.installed.claude_code.ClaudeCode`
  - Injects: `FORCE_AUTO_BACKGROUND_TASKS=1`, `ENABLE_BACKGROUND_TASKS=1`
  - Tools: Bash, Read, Edit, Write, Grep, Glob
  - Purpose: Fair baseline for MCP comparison

- **mcp_variants.py** - Strategic + experimental MCP agents (Sourcegraph Deep Search / keyword / neutral)
  - Contains: `StrategicDeepSearchAgent`, `DeepSearchFocusedAgent`, `MCPNonDeepSearchAgent`, `FullToolkitAgent`
  - Extends: `ClaudeCode` with identical autonomous command generation to the baseline
  - Adds: `.mcp.json` config upload + variant-specific prompts/cloude-md
  - Purpose: Measure MCP benefit across prompting strategies and tool combinations

- **claude_sourcegraph_mcp_agent.py** - Compatibility alias to `DeepSearchFocusedAgent`
  - Kept so older automation can still import `ClaudeCodeSourcegraphMCPAgent`

**Key Design**: 
- All agents inject the same autonomous environment variables (critical for implementation mode)
- Differentiation happens via environment/MCP setup and prompts, not core command logic
- Allows fair A/B testing of Sourcegraph value across multiple MCP prompting strategies

#### `src/task_mining/` - GitHub Task Mining

Automated pipeline for mining real-world tasks from GitHub repositories:

- **mine_tasks.py** - Main entry point (--repos, --days-back, --output, --limit flags)
- **github_client.py** - GitHub API client (REST v3, pagination, rate limiting)
- **task_generator.py** - Convert GitHub PRs/issues → TaskSpecification objects
- **task_filter.py** - Validate tasks against CodeContextBench eligibility criteria
- **repo_registry.py** - Repository definitions with language metadata

**Mining pipeline** (Phase 2a):
1. Query GitHub for merged PRs (≥2 files changed, test additions)
2. Filter by deterministic verification (test commands present)
3. Generate TaskSpecification objects with metadata
4. Validate schema (98% pass rate target)
5. Generate Harbor task directories ready for execution

**Output**: `benchmarks/github_mined/` with 50 Kubernetes + PyTorch tasks

See [history/MINING_EXECUTION_REPORT.md](../history/MINING_EXECUTION_REPORT.md) for Phase 2a results.

#### `benchmarks/` - Task Sets

Standardized benchmark task sets with consistent format:

- **big_code_mcp/** - Large Codebase MCP Comparison (4 tasks, high MCP value)
- **github_mined/** - Real-world GitHub tasks (25 PyTorch tasks, general capability)
- **dependeval_benchmark/** - Multi-File & Cross-Repo Tasks (9 tasks, dependency reasoning)
- **10figure/** - Legacy Codebase Challenges (4 tasks, large codebase understanding)
- **dibench/** - Dependency Inference Benchmark (variable tasks, language-diverse)
- **repoqa/** - Tool-Sensitive Code Understanding (variable tasks, MCP-sensitive)
- **kubernetes_docs/** - Kubernetes documentation regeneration tasks (doc.go, README reconstruction)

See [benchmarks/README.md](../benchmarks/README.md#benchmark-comparison-matrix) for comparison matrix and setup details.

Each task includes:
- `instruction.md` - Task description (includes commit SHA for reproducibility)
- `task.toml` / `task.yaml` - Task metadata with `version = "1.0"` (Harbor requirement)
- `environment/Dockerfile` - Container setup with repo clone
  - **Critical**: Must include `git clone` + `git checkout` for reproducible execution
  - Each task specifies exact commit (21 use `main`, 4 use specific SHAs extracted from instruction.md)
  - Submodules initialized: `git submodule update --init --recursive`
- `tests/test.sh` - Validation script with reward file output (`/logs/verifier/reward.txt`)

#### `runners/` - Benchmark Execution & Analysis

- **capture_single_task_trace.py** - Extract comprehensive execution traces (code changes, test results, metrics)
- **compare_results.py** - Comparative analysis (baseline vs MCP agent)
- **aggregator.py** - Cross-task result aggregation
- **collect_observability.py** - Gather metrics from Harbor job outputs
- **validate_tasks.py** - Verify task setup and configuration

#### `infrastructure/` - Container & Deployment

- **PODMAN.md** - Comprehensive Podman setup guide
- **docker-wrapper.sh** - Wrapper translating docker commands to podman
- **harbor-config.yaml** - Harbor orchestration settings (runtime, agents, timeouts)
- **datasets.yaml** - External dataset references (10Figure corpus)
- **load-env.sh** - Environment variable loader from .env.local

#### `observability/` - Metrics & Trace Parsing

Tools for extracting execution metrics from agent runs:

- **claude_output_parser.py** - Parse Claude CLI output for token counts and costs
- **metrics_collector.py** - Aggregate metrics across multiple runs
- **nemo_trace_parser.py** - Parse NeMo traces if available (future integration)

**Current Usage**:
- Extract token counts from Claude output
- Analyze success/failure rates
- Collect metrics for comparative analysis
- Support for structured trace formats

#### `tests/` - Testing Suite

- **test_observability.py** - NeMo parser, manifest writer, metrics tests
- **test_runners.py** - Benchmark runner and aggregation tests
- **test_agents.py** - Agent command generation and environment setup
- Comprehensive coverage of all core functionality

#### `.beads/` - Issue Tracking

- **issues.jsonl** - Issue database (auto-synced with git)
- Tracks all work items: bugs, features, tasks, epics
- Dependency-aware: tracks blockers and relationships
- Auto-populated from `bd` CLI commands

#### `.engram/` - Knowledge & Learning

- **engram.db** - SQLite database with learned patterns
- Populated automatically when beads are closed via `en learn`
- Stores execution traces, insights, bullets (formatted learnings)

### Configuration Files

| File | Purpose |
|------|---------|
| `.env.local.example` | Template for credentials (ANTHROPIC_API_KEY, SOURCEGRAPH_ACCESS_TOKEN) |
| `.python-version` | Python version specification (3.12.11) |
| `setup.py` | Python package configuration |
| `AGENTS.md` | Agent patterns, workflows, and learned knowledge |

## Data Flow: End-to-End

```
1. TASK SELECTION
   └─> bd ready → pick next benchmark task

2. ENVIRONMENT SETUP
   └─> source infrastructure/load-env.sh
       (loads ANTHROPIC_API_KEY, SOURCEGRAPH_ACCESS_TOKEN, etc.)

3. AGENT INITIALIZATION
    └─> agents/ (BaselineClaudeCodeAgent or MCP variant agents)
        ├─> Get installation template
        ├─> Get environment variables
        └─> Generate Harbor command

4. HARBOR EXECUTION
   └─> runners/harbor_benchmark.sh
       ├─> Parse task manifest
       ├─> Create container (podman via docker wrapper)
       ├─> Install agent
       ├─> Run task
       ├─> Collect result.json + logs
       └─> Optionally capture NeMo trace

5. METRICS COLLECTION
   └─> observability/
       ├─> NeMoTraceParser extracts tool metrics (if trace available)
       ├─> ClaudeOutputParser extracts tokens (fallback)
       ├─> ManifestWriter generates run_manifest.json
       └─> Result includes: tokens, cost, tool profile, success/reward

6. AGGREGATION & ANALYSIS
   └─> runners/aggregator.py
       ├─> Load all manifests from jobs/
       ├─> Compute per-agent and per-benchmark statistics
       ├─> Detect regressions (baseline vs treatment)
       └─> Generate reports

7. ISSUE TRACKING
   └─> bd close <bead-id>
       ├─> Updates .beads/issues.jsonl
       ├─> Syncs with git for version control
       └─> Provides audit trail of completed work
```

## Agent Design

Five benchmarking agents for A/B testing MCP impact:

### BaselineClaudeCodeAgent

**File**: `agents/claude_baseline_agent.py`  
**Import**: `agents.claude_baseline_agent:BaselineClaudeCodeAgent`

- **Purpose**: Control baseline for Claude Code autonomous capabilities
- **Features**: Claude Code CLI in autonomous mode, NO MCP tools
- **Environments**: ANTHROPIC_API_KEY only
- **Use Case**: Establish baseline performance without code intelligence

**Usage**:
```bash
harbor run --path <task_path> \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### StrategicDeepSearchAgent

**File**: `agents/mcp_variants.py`  
**Import**: `agents.mcp_variants:StrategicDeepSearchAgent`

- **Purpose**: Recommended MCP agent that uses Deep Search strategically for architecture/context discovery
- **Features**: Opinionated prompts that trigger Deep Search at task start and when encountering information gaps
- **Environments**: ANTHROPIC_API_KEY + SOURCEGRAPH_URL + SOURCEGRAPH_ACCESS_TOKEN
- **Use Case**: Balanced MCP runs that avoid overusing Deep Search while still gathering critical context

**Usage**:
```bash
harbor run --path <task_path> \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### DeepSearchFocusedAgent

**File**: `agents/mcp_variants.py`  
**Import**: `agents.mcp_variants:DeepSearchFocusedAgent`

- **Purpose**: Test the value of a dedicated deep-search-only MCP endpoint.
- **Features**: MCP with a dedicated deep-search-only endpoint and aggressive system prompts.
- **Environments**: ANTHROPIC_API_KEY + SOURCEGRAPH_ACCESS_TOKEN + SOURCEGRAPH_URL
- **Use Case**: Maximize Deep Search impact on task success

**Usage**:
```bash
harbor run --path <task_path> \
  --agent-import-path agents.mcp_variants:DeepSearchFocusedAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### MCPNonDeepSearchAgent

**File**: `agents/mcp_variants.py`  
**Import**: `agents.mcp_variants:MCPNonDeepSearchAgent`

- **Purpose**: Test if simpler search (keyword/NLS) is sufficient without Deep Search
- **Features**: MCP with keyword and natural language search only (Deep Search disabled)
- **Environments**: ANTHROPIC_API_KEY + SOURCEGRAPH_ACCESS_TOKEN + SOURCEGRAPH_URL
- **Use Case**: Measure Deep Search overhead vs simpler search strategies

**Usage**:
```bash
harbor run --path <task_path> \
  --agent-import-path agents.mcp_variants:MCPNonDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### FullToolkitAgent

**File**: `agents/mcp_variants.py`  
**Import**: `agents.mcp_variants:FullToolkitAgent`

- **Purpose**: Control for all-MCP tools with neutral prompting
- **Features**: MCP with all available tools, no task-specific prompts (baseline MCP)
- **Environments**: ANTHROPIC_API_KEY + SOURCEGRAPH_ACCESS_TOKEN + SOURCEGRAPH_URL
- **Use Case**: Measure agent's natural tool choices with all options available

**Usage**:
```bash
harbor run --path <task_path> \
  --agent-import-path agents.mcp_variants:FullToolkitAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

### Deprecated Shim

**File**: `agents/claude_sourcegraph_mcp_agent.py`  
**Alias for**: `DeepSearchFocusedAgent` (kept for backward compatibility)

This file is maintained for backward compatibility. New code should use:
```python
from agents.mcp_variants import DeepSearchFocusedAgent
```

### Agent Comparison Framework

The 4-agent design enables systematic MCP evaluation:

| Agent | MCP | Prompting | Purpose |
|-------|-----|-----------|---------|
| Baseline | No | N/A | Control: pure Claude Code |
| StrategicDeepSearch | Yes | Targeted Deep Search | Recommended MCP run (context-first) |
| DeepSearchFocused | Yes | Deep Search Only | Max Deep Search impact |
| MCPNonDeepSearch | Yes | Keyword/NLS only | Test Deep Search necessity |
| FullToolkit | Yes | Neutral | Control: all MCP tools |

**Testing Matrix**:
- **Baseline vs StrategicDeepSearch**: Strategic MCP vs no MCP
- **Baseline vs FullToolkit**: Total MCP value (all tools)
- **StrategicDeepSearch vs DeepSearchFocused**: Strategic vs aggressive Deep Search usage
- **StrategicDeepSearch vs MCPNonDeepSearch**: Deep Search necessity vs simpler search
- **FullToolkit vs DeepSearchFocused**: Prompting impact when all tools exist

**Design**:
- All agents use identical command generation logic (same base class)
- Differentiation happens via `.mcp.json` configuration and system prompts
- Environment variables injected at Harbor runtime (no code duplication)
- Fair comparison: all agents have equal autonomous capabilities

## Testing Strategy

1. **Unit Tests** (`tests/test_agents.py`)
   - Agent command generation
   - Environment variable handling
   - Installation template rendering

2. **Integration Tests** (`tests/test_runners.py`)
   - Harbor task discovery
   - Result parsing and validation
   - Cross-benchmark aggregation

3. **Observability Tests** (`tests/test_observability.py`)
   - NeMo trace parsing with realistic data
   - Manifest generation and schema validation
   - Metrics computation (latency, tokens, failure rates)

4. **Smoke Tests** (`smoke_test.sh`)
   - Environment availability (podman, harbor, python)
   - Tool availability (SOURCEGRAPH_ACCESS_TOKEN, ANTHROPIC_API_KEY)
   - Basic agent functionality

## Containerization: Harbor + Podman

- **Harbor**: Orchestration framework for running agents in containers
- **Podman**: Primary container runtime (rootless, no Docker Desktop needed)
- **Wrapper**: `infrastructure/docker-wrapper.sh` translates docker commands to podman
- **Config**: `infrastructure/harbor-config.yaml` defines runtime, timeouts, resource limits

See `infrastructure/PODMAN.md` for detailed setup.

## Execution Tracing & Metrics

### Current Approach

Metrics are extracted from Harbor job outputs and Claude CLI logs:

- **Code changes**: Captured via `git diff` in task containers
- **Test results**: Parsed from task validation scripts (reward.txt)
- **Token counts**: Extracted from Claude CLI output via `ClaudeOutputParser`
- **Execution time**: Recorded by Harbor

### Future: NeMo Integration

Full NeMo-Agent-Toolkit integration is planned for structured per-tool metrics (latency, failure analysis, cost breakdown). Currently using simplified metrics collection.

## Issue Tracking with Beads

All work is tracked in `.beads/issues.jsonl`:

1. **Issue Creation**: Use `bd create` with clear titles and descriptions
2. **Dependency Tracking**: Link related issues with `--deps discovered-from:<id>`
3. **Status Management**: Track with `in_progress` and `closed` states
4. **Git Sync**: Auto-synced with repository for version control
5. **Audit Trail**: Closed beads provide history of completed work

Best practices:
- Close beads immediately when work is complete
- Use priority levels (0-4) to guide work selection
- Link discovered issues to parent beads for traceability

## File Organization Principles

1. **Agents** (agents/):
   - One class per agent type
   - Shared base class for common logic
   - Separate install templates per agent

2. **Benchmarks** (benchmarks/):
   - One directory per benchmark set
   - Consistent task structure within each set
   - No hardcoded paths (use relative paths, env vars)

3. **Infrastructure** (infrastructure/):
   - Documentation (PODMAN.md)
   - Executable scripts (docker-wrapper.sh)
   - Configuration files (harbor-config.yaml, datasets.yaml)

4. **Observability** (observability/):
   - Modular: parser, writer, collector, parser can work independently
   - No external dependencies (json, pathlib, statistics only)
   - Structured data formats (JSON)

5. **Runners** (runners/):
   - Bash scripts for orchestration (harbor_benchmark.sh)
   - Python scripts for analysis (compare_results.py, aggregator.py)
   - Batch extraction (extract_nemo_traces.py)

## Key Design Decisions

### Why Claude-First?

- Claude has the best performance on code tasks
- MCP integration is production-ready
- Easy to compare baseline vs baseline+MCP

### Why NeMo Integration?

- Structured execution traces (not just logs)
- Per-tool metrics for debugging and optimization
- Failure analysis at granular level
- Cost breakdown for budget planning

### Why Engram Learning?

- Automatically improve future performance
- Don't repeat past mistakes
- Store patterns for cross-project learning
- Leverage execution traces as learning signals

### Why Podman-First?

- No Docker Desktop licensing
- Better security (rootless)
- CI/CD friendly
- Works in restricted environments

## See Also

- **docs/DEVELOPMENT.md** - Development environment setup, commands, and workflows
- **docs/OBSERVABILITY.md** - Metrics and observability guide
- **docs/TROUBLESHOOTING.md** - Common issues and solutions
- **infrastructure/PODMAN.md** - Podman setup details
- **AGENTS.md** - Agent patterns and learned knowledge
