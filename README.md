# CodeContextBench

Unified benchmark framework for evaluating coding agents with/without Sourcegraph code intelligence tools. Migrates and consolidates sg_benchmark and sourcegraph-benchmarks projects.

## Quick Overview

- **Goal**: Measure ROI of Sourcegraph code search (via MCP) for coding agents
- **Primary Agent**: Claude Code (via CLI through Harbor)
- **Task Corpus**: 10Figure-Codebases (23 real-world repos, 16k+ symbol/API tasks)
- **Framework**: Harbor + Podman (proven working in sourcegraph-benchmarks)
- **Evaluation**: JSON patches + git diff → test pass/fail → effectiveness metrics

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

- **10Figure-Codebases**: `/Users/sjarmak/10Figure-Codebases/` (~5GB, 23 repos)
- **Harbor Task Manifest**: `/Users/sjarmak/harbor-10figure-dataset/`

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

### Phase 2b: Benchmark Execution (IN PROGRESS)
⏳ Pilot benchmark (10 tasks, both agents)
⏳ Full benchmark suite (50 + 4 10figure tasks × 2 agents)
⏳ Manifest generation and tool usage tracking

### Phase 2c: Analysis (READY FOR EXECUTION)
⏳ Comparative analysis (baseline vs +MCP)
⏳ Failure mode analysis by category/difficulty/language
⏳ Hypothesis validation report

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
