# CodeContextBench

Benchmark framework for evaluating how improved codebase understanding through Sourcegraph code intelligence tools improves coding agent performance.

## Quick Overview

- **Goal**: Measure ROI of Sourcegraph code search (via MCP) for coding agents
- **Primary Agent**: Claude Code (via Harbor CLI integration)
- **Task Corpus**: github_mined (25 real-world PyTorch tasks)
- **Framework**: Harbor (container orchestration) + Claude Code CLI
- **Evaluation**: Agent executes task → git diff captured → tests validate → reward score

## Directory Structure

```
agents/              # Agent implementations (Baseline + MCP variants)
benchmarks/          # Task sets (github_mined: 25 PyTorch tasks)
.beads/              # Issue tracking (auto-synced with git)

configs/             # Configuration files
docs/                # Project documentation (ARCHITECTURE, DEVELOPMENT, TROUBLESHOOTING)
infrastructure/      # Container setup, deployment configs
jobs/                # Harbor job outputs (auto-generated, git-ignored)
observability/       # Trace parsing, metrics collection
runners/             # Benchmark orchestration scripts
src/                 # Core library code (task schema, mining, benchmarking)
tests/               # Unit + integration tests
history/             # Temporary planning documents (git-ignored)
```

## Core Components

### Agent Implementations

#### BaselineClaudeCodeAgent (agents/claude_baseline_agent.py)
Claude Code baseline with autonomous implementation mode:
- Extends Harbor's built-in ClaudeCode agent
- Injects `FORCE_AUTO_BACKGROUND_TASKS=1` and `ENABLE_BACKGROUND_TASKS=1` (critical for autonomous operation)
- Enables tool access: Bash, Read, Edit, Write, Grep, Glob
- Requires: `ANTHROPIC_API_KEY`
- No Sourcegraph integration
- Fair baseline for MCP comparison

#### ClaudeCodeSourcegraphMCPAgent (agents/claude_sourcegraph_mcp_agent.py)
Claude Code with Sourcegraph MCP integration:
- Same autonomous env var injection as baseline
- Adds Sourcegraph Deep Search via MCP (Model Context Protocol)
- Creates `.mcp.json` configuration for Sourcegraph HTTP server
- Requires: `ANTHROPIC_API_KEY` + `SOURCEGRAPH_ACCESS_TOKEN` + `SOURCEGRAPH_URL`
- Provides intelligent codebase exploration vs manual grep
- Measures ROI of code intelligence on agent success rate

## Datasets

- **github_mined**: 25 real-world PyTorch tasks (Phase 3 baseline)
  - `benchmarks/github_mined/sgt-001` through `sgt-025`
  - Mixed difficulty levels, deterministic verification
  - Exact commit SHAs locked in Dockerfiles for reproducibility
- **10Figure-Codebases**: `/Users/sjarmak/10Figure-Codebases/` (~5GB, 23 repos, reference corpus)
- **terminal-bench**: Self-contained implementation tasks (future corpus)

## Phase Status

### Phase 1-2: Foundation & Mining (COMPLETE)
- Harbor integration with Claude Code CLI
- 25 github_mined PyTorch tasks (from Phase 2a mining)
- Task validation and reproducible execution

### Phase 3: Real Benchmarks (IN PROGRESS)
- Harbor framework fully operational
- Both agents with autonomous implementation mode enabled
- Single-task validation (sgt-001) shows agents can make code changes

### Phase 4: Single-Task Validation (IN PROGRESS - Dec 19, 2025)
- **Discovery**: Autonomous environment variables control Claude Code's operation mode
  - `FORCE_AUTO_BACKGROUND_TASKS=1` and `ENABLE_BACKGROUND_TASKS=1` enable headless implementation
  - Both baseline and MCP agents now have equal autonomous capability
- **Critical Issue Found** (CodeContextBench-mqz): Task environments must checkout code BEFORE fixes were merged
  - Current: Dockerfiles clone HEAD which already has fixes applied
  - Problem: Agents can't implement something already in the baseline
  - Solution: Update all task Dockerfiles to pre-fix commits
- **Next**: After environment fixes, re-run Phase 4 validation and compare results

See `.beads/issues.jsonl` for full task tracking.

## Contributing

- Use `bd ready` to find unblocked work
- Always close beads with `bd close` when work is complete
- Store AI planning docs in `history/` directory
- Always use `--json` flag for programmatic tools

## References

- AGENTS.md: Project-specific patterns and workflows
- docs/PAPER_DRAFT_121625.md: Research paper and motivation
- docs/LITERATURE_REVIEW.md: Related work survey
