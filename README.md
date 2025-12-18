# CodeContextBench

Benchmark framework for evaluating how improved codebase understanding through Sourcegraph code intelligence tools improves coding agent performance.

## Quick Overview

- **Goal**: Measure ROI of Sourcegraph code search (via MCP) for coding agents
- **Primary Agent**: Claude Code (via CLI through Harbor)
- **Task Corpus**: github_mined (25 real-world PyTorch tasks, Phase 3 baseline)
- **Framework**: Harbor + Podman (reproducible container execution)
- **Evaluation**: Agent executes task → git diff captured → tests run → success/failure metrics

## Architecture

```
agents/              # Agent implementations (Claude Code baseline + variants)
benchmarks/          # Task sets (10figure, github_mined, terminal-bench)
configs/             # Repository configs, Harbor settings, tool profiles
infrastructure/      # Podman docs, dataset specs, container configs
observability/       # JSON logging + Harbor metrics (no NeMo complexity)
runners/             # Benchmark orchestration scripts
src/benchmark/       # Task schema, manifest writers, metrics collectors
tests/               # Unit + integration tests
tools/               # Utility scripts (task context, result validation)
artifacts/           # Ephemeral results, logs, job outputs
```

## Core Components

### Agent Implementations

#### BasePatchAgent (agents/base.py)
Abstract base class for all CLI agents. Provides:
- Repository discovery (task.toml or /10figure/src/)
- Git diff capture (baseline → patch)
- Harbor integration
- Extensible environment/command customization

Subclasses must implement:
- `get_agent_command(instruction, repo_dir)`: Shell command to run the agent
- `get_agent_env()`: Environment variables required by the agent
- `_install_agent_template_path`: Path to Jinja2 installation script

#### ClaudeCodeAgent (agents/claude_agent.py)
Claude Code baseline (no code search augmentation):
- Uses Claude Code CLI (`claude -p` print mode)
- JSON output format for structured results
- Requires `ANTHROPIC_API_KEY` environment variable
- Runs with `--dangerously-skip-permissions` for unattended execution
- Suitable for baseline evaluation without Sourcegraph tools

#### ClaudeCodeSourcegraphMCPAgent (agents/claude_sourcegraph_mcp_agent.py)
Claude Code with Sourcegraph MCP server integration:
- Inherits baseline Claude functionality
- Adds `SRC_ACCESS_TOKEN` and `SOURCEGRAPH_URL` credentials
- Enables Deep Search APIs via Model Context Protocol
- MCP server configuration handled via `--mcp-config` at runtime
- Measures ROI of Sourcegraph code intelligence on agent performance

## Datasets

- **github_mined**: 25 real-world PyTorch tasks (Phase 3 baseline)
  - `benchmarks/github_mined/sgt-001` through `sgt-025`
  - Mixed difficulty levels, deterministic verification
  - Exact commit SHAs locked in Dockerfiles for reproducibility
- **10Figure-Codebases**: `/Users/sjarmak/10Figure-Codebases/` (~5GB, 23 repos, reference corpus)
- **terminal-bench**: Self-contained implementation tasks (future corpus)

## Phase Status

### Phase 1: Foundation (COMPLETE)
✅ Directory skeleton and project structure
✅ BasePatchAgent + ClaudeCodeAgent + ClaudeCodeMCPAgent
✅ Installation templates and Harbor integration
✅ 25 Kubernetes reference tasks (10figure baseline)
✅ Agent tests (14 passing)

### Phase 2a: Mining (COMPLETE)
✅ Mined 50 real-world GitHub tasks (Kubernetes + PyTorch)
✅ 98% schema validation pass rate (49/50)
✅ All tasks multi-file, deterministic, ground-truth verified
✅ Harbor task generation & validation infrastructure
✅ See [docs/MINING_EXECUTION_REPORT.md](docs/MINING_EXECUTION_REPORT.md)

### Phase 3: Real Benchmarks (IN PROGRESS)
✅ Fixed Docker repo cloning (all 25 tasks)
🔄 Baseline pilot (10 tasks, claude-code agent) - RUNNING
⏳ MCP pilot (10 tasks, +Sourcegraph Deep Search)
⏳ Metric extraction and comparative analysis
⏳ Hypothesis validation (30-40% baseline, 70-90% with MCP)

See `.beads/issues.jsonl` for full task list.

## Contributing

- Use `bd ready` to find unblocked work
- Always close beads with `bd close` (triggers Engram learning)
- Run `en learn --beads <id>` manually if capturing learning without closure
- Store AI planning docs in `history/` directory
- Always use `--json` flag for programmatic tools

## References

- AGENTS.md: Project-specific patterns and workflows
- docs/PAPER_DRAFT_121625.md: Research paper and motivation
- docs/LITERATURE_REVIEW.md: Related work survey
