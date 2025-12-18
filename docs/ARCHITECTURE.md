# CodeContextBench Architecture

CodeContextBench is a comprehensive benchmark evaluation framework for assessing how improved codebase understanding through Sourcegraph tools improves coding agent output. It supports multiple agent implementations (Claude Code baseline, Claude+MCP with Sourcegraph Deep Search) running against standardized benchmark task sets.

## Philosophy

- **Claude-first design**: Primary agents are Claude-based (baseline + MCP variants)
- **Modular agent support**: Easy to add new agent types (Termius, Cursor, etc.)
- **Structured observability**: NeMo-Agent-Toolkit integration for detailed metrics
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

## Directory Structure

### Core Components

#### `agents/` - Agent Implementations

All agents extend `BasePatchAgent` and implement:

- **claude_agent.py** - Claude baseline (no tools, vanilla command generation)
- **claude_sourcegraph_mcp_agent.py** - Claude + Sourcegraph MCP (with Deep Search)
- **base.py** - Abstract base class with common functionality
- **install-claude.sh.j2** - Jinja2 template for Claude installation in containers

**Key Design**: All agents generate identical commands; differentiation happens via:
- Environment variables (SRC_ACCESS_TOKEN, SOURCEGRAPH_URL)
- MCP configuration at Harbor runtime
- NOT in agent code itself

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
- **github_mined/** - Real-world GitHub tasks (50 Kubernetes + PyTorch, Phase 2a)
- **custom/** - Project-specific custom tasks

Each task includes:
- `instruction.md` - Task description
- `task.toml` / `task.yaml` - Task metadata
- `environment/Dockerfile` - Container setup
- `tests/test.sh` - Validation script

#### `runners/` - Benchmark Execution

- **harbor_benchmark.sh** - Main orchestrator (runs Harbor jobs, collects results)
- **compare_results.py** - Comparative analysis (baseline vs treatment)
- **aggregator.py** - Cross-benchmark result aggregation
- **extract_nemo_traces.py** - Batch NeMo trace extraction from Harbor jobs

#### `infrastructure/` - Container & Deployment

- **PODMAN.md** - Comprehensive Podman setup guide
- **docker-wrapper.sh** - Wrapper translating docker commands to podman
- **harbor-config.yaml** - Harbor orchestration settings (runtime, agents, timeouts)
- **datasets.yaml** - External dataset references (10Figure corpus)
- **load-env.sh** - Environment variable loader from .env.local

#### `observability/` - Metrics & Observability

**NeMo-Agent-Toolkit Integration** for structured execution tracing:

- **nemo_trace_parser.py** - Parse NeMo traces (tool calls, latency, tokens, failures)
- **manifest_writer.py** - Generate run_manifest.json with execution data
- **metrics_collector.py** - Analyze metrics across multiple runs
- **claude_output_parser.py** - Extract tokens from Claude CLI output (fallback)

**Features**:
- Per-tool metrics (latency, token counts, failure rates)
- Failure analysis by error type and tool
- Cost breakdown per tool
- Structured metrics suitable for benchmarking

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

## NeMo-Agent-Toolkit Integration

CodeContextBench integrates with **NeMo-Agent-Toolkit** for structured execution tracing:

### What We Get

- **Per-tool metrics**: Token counts, latency, success/failure rates per tool
- **Operation timeline**: Complete execution sequence with timestamps
- **Failure analysis**: Error types, which tools fail most often
- **Cost breakdown**: Cost per tool for detailed optimization

### How We Use It

```python
from observability import NeMoTraceParser, ManifestWriter

# Extract trace from Harbor job
trace = NeMoTraceParser.extract_from_task_execution(job_dir)

# Write manifest with structured metrics
writer = ManifestWriter(job_dir)
manifest_path = writer.write_manifest(
    harness_name='harbor-v1',
    agent_name='claude-baseline',
    benchmark_name='10figure',
    nemo_trace=trace  # Pass NeMo trace for structured metrics
)
```

### Automatic Fallback

If no NeMo trace available, we gracefully fall back to Claude log parsing via `ClaudeOutputParser`. This ensures we always have token counts and cost data.

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
