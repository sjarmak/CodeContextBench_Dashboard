# CodeContextBench Architecture

CodeContextBench is a comprehensive benchmark evaluation framework for assessing how improved codebase understanding through Sourcegraph tools improves coding agent output. It supports multiple agent implementations (Claude Code baseline, Claude+MCP with Sourcegraph Deep Search) running against standardized benchmark task sets.

## Philosophy

- **Claude-first design**: Primary agents use Claude Code CLI (baseline + MCP variants)
- **Autonomous operation**: Claude Code must run in headless mode via environment variables
- **Fair benchmarking**: Both agents have equal autonomous capabilities for valid comparison
- **Continuous learning**: Engram framework captures execution patterns and improves future performance


## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CodeContextBench                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │  Benchmark Task  │      │  Benchmark Task  │                 │
│  │  (Terminal-Bench)│  ... │  (10Figure)      │                 │
│  └────────┬─────────┘      └────────┬─────────┘                 │
│           │                         │                            │
│           └────────────┬────────────┘                            │
│                        │                                          │
│                  ┌─────▼──────┐                                  │
│                  │   Harbor   │  (Container orchestration)       │
│                  │ + Podman   │                                  │
│                  └─────┬──────┘                                  │
│                        │                                          │
│        ┌───────────────┼───────────────┐                        │
│        │               │               │                        │
│   ┌────▼─────┐   ┌────▼──────┐  ┌────▼──────┐                 │
│   │ Claude   │   │ Claude    │  │ Future    │                 │
│   │Baseline  │   │ + MCP     │  │ Agents    │                 │
│   │(no tools)│   │(Deep Search)│  │(Cursor..) │                 │
│   └────┬─────┘   └────┬──────┘  └────┬──────┘                 │
│        │               │               │                        │
│        └───────────────┼───────────────┘                        │
│                        │                                          │
│                  ┌─────▼──────────┐                             │
│                  │  NeMo Tracing  │  (Structured metrics)       │
│                  │  + Observability│                             │
│                  └─────┬──────────┘                             │
│                        │                                          │
│                  ┌─────▼──────────┐                             │
│                  │  Results &     │                             │
│                  │  Manifests     │                             │
│                  └─────┬──────────┘                             │
│                        │                                          │
│        ┌───────────────┼───────────────┐                        │
│        │               │               │                        │
│   ┌────▼─────┐   ┌────▼──────┐  ┌────▼──────┐                 │
│   │Aggregation│   │Comparison  │  │Learning   │                 │
│   │& Analysis │   │& Reporting │  │(Engram)   │                 │
│   └──────────┘   └────────────┘  └───────────┘                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Execution Phases

### Phase 1: Setup ( Completed)
- Installed Harbor framework (harborai v0.1.25)
- Created isolated `.venv-harbor` environment
- All 25 github_mined tasks converted to Harbor format

### Phase 2: Docker Reproducibility ( Completed)
- Fixed critical issue: Dockerfiles weren't cloning PyTorch repo
- Updated all 25 Dockerfiles to include:
  - `git clone https://github.com/pytorch/pytorch.git /workspace`
  - `git checkout <commit>` (task-specific SHA or `main`)
  - `git submodule update --init --recursive`
- Single test validated: repo clones, Claude Code executes successfully

### Phase 3: Real Benchmarks ( In Progress)
- **Baseline Pilot** (10 tasks, claude-code agent)
  - Status: RUNNING
  - Model: claude-haiku-4-5 (faster testing)
  - Expected: 30-40% success rate
  - ETA: 1.5-2 hours (15 min/task × 10)
  
- **MCP Pilot** (next, 10 tasks with Sourcegraph)
  - Model: claude-haiku-4-5 with --mcp-config
  - Expected: 70-90% success rate
  - Hypothesis: +40-50% improvement from code search

### Phase 4: Analysis & Publication
- Extract metrics from Harbor job outputs
- Compare baseline vs MCP results
- Generate reproducibility documentation
- Validate improvement hypothesis

## Directory Structure

### Core Components

#### `agents/` - Agent Implementations

Both agents extend Harbor's built-in `ClaudeCode` and inject autonomous environment variables:

- **claude_baseline_agent.py** - Claude baseline (autonomous mode, no Sourcegraph)
  - Extends: `harbor.agents.installed.claude_code.ClaudeCode`
  - Injects: `FORCE_AUTO_BACKGROUND_TASKS=1`, `ENABLE_BACKGROUND_TASKS=1`
  - Tools: Bash, Read, Edit, Write, Grep, Glob
  - Purpose: Fair baseline for MCP comparison

- **claude_sourcegraph_mcp_agent.py** - Claude + Sourcegraph MCP (autonomous mode + Deep Search)
  - Extends: `harbor.agents.installed.claude_code.ClaudeCode`
  - Injects: Same autonomous env vars as baseline
  - Adds: `.mcp.json` configuration for Sourcegraph HTTP server
  - Tools: Same as baseline + Sourcegraph Deep Search
  - Purpose: Measure ROI of code intelligence

**Key Design**: 
- Both agents inject the same autonomous environment variables (critical for implementation mode)
- Differentiation happens via environment/MCP setup, not core command logic
- Allows fair A/B testing of Sourcegraph value

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

See [docs/MINING_EXECUTION_REPORT.md](MINING_EXECUTION_REPORT.md) for Phase 2a results.

#### `benchmarks/` - Task Sets

Standardized benchmark task sets with consistent format:

- **terminal-bench/** - Terminal-Bench 2.0 (89 self-contained implementation tasks)
- **10figure/** - 10Figure-Codebases (25 reference cross-file reasoning tasks)
- **github_mined/** - Real-world GitHub tasks (25 PyTorch tasks, Phase 3 baseline)
- **custom/** - Project-specific custom tasks

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
| `.env.local.example` | Template for credentials (ANTHROPIC_API_KEY, SRC_ACCESS_TOKEN) |
| `.python-version` | Python version specification (3.12.11) |
| `setup.py` | Python package configuration |
| `AGENTS.md` | Agent patterns, workflows, and learned knowledge |

## Data Flow: End-to-End

```
1. TASK SELECTION
   └─> bd ready → pick next benchmark task

2. ENVIRONMENT SETUP
   └─> source infrastructure/load-env.sh
       (loads ANTHROPIC_API_KEY, SRC_ACCESS_TOKEN, etc.)

3. AGENT INITIALIZATION
   └─> agents/claude_agent.py or claude_sourcegraph_mcp_agent.py
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

7. LEARNING (Engram)
   └─> bd close <bead-id>
       ├─> Auto-runs en learn
       ├─> Extracts patterns from execution traces
       ├─> Generates insights about failure modes, success patterns
       └─> Stores in .engram/engram.db for future reference
```

## Agent Design

### Claude Baseline

**File**: `agents/claude_agent.py`

- Uses Claude 3.5 Sonnet
- NO tools (vanilla command generation)
- Requires: ANTHROPIC_API_KEY
- For testing whether Deep Search helps or hurts

### Claude + MCP (With Sourcegraph Deep Search)

**File**: `agents/claude_sourcegraph_mcp_agent.py`

- Uses Claude 3.5 Sonnet
- Sourcegraph Deep Search via MCP
- Requires: ANTHROPIC_API_KEY + SRC_ACCESS_TOKEN
- MCP configuration at Harbor runtime (--mcp-config flag)
- NOT in agent code

### Why This Design?

Both agents use the same command generation logic. Differentiation happens at execution time:

1. **Base class** (`BasePatchAgent`) handles all common logic
2. **Subclasses** override only environment setup
3. **Harbor** applies MCP config at runtime via flags
4. **Result**: Easy to test impact of Deep Search without code duplication

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
   - Tool availability (SRC_ACCESS_TOKEN, ANTHROPIC_API_KEY)
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

## Knowledge Base: Engram

Every closed bead triggers Engram learning:

1. **Trace Capture**: Execution traces (test pass/fail, errors) stored in bead
2. **Pattern Extraction**: Engram analyzes traces to find patterns
3. **Insight Generation**: Creates insights about failure modes, success factors
4. **Knowledge Storage**: Stores in `.engram/engram.db` for reuse

Example insights:
- "NeMo metrics enable per-tool cost analysis" (helpful:1)
- "TypeScript build errors require running tsc before tests" (helpful:1)
- "Always validate user input before processing" (aggregated from 26 instances)

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

- **docs/DEVELOPMENT.md** - Development setup and workflows
- **docs/OBSERVABILITY.md** - Metrics and observability guide
- **docs/TROUBLESHOOTING.md** - Common issues and solutions
- **infrastructure/PODMAN.md** - Podman setup details
- **AGENTS.md** - Agent patterns and learned knowledge
