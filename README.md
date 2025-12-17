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

## Migration Status

✅ Directory skeleton created
✅ BasePatchAgent ported (generalized for multi-agent)
✅ ClaudeCodeAgent (baseline, no code search)
✅ ClaudeCodeSourcegraphMCPAgent (with Sourcegraph tools)
✅ Installation templates (install-claude.sh.j2)
✅ Tests for agent implementations (14 passing)
⏳ Benchmark task runners
⏳ Harbor configuration & integration
⏳ 10Figure task generator
⏳ Smoke tests

See `.beads/issues.jsonl` for full task list (14 beads total).

## Contributing

- Use `bd ready` to find unblocked work
- All changes require `en learn` before closing beads
- Store AI planning docs in `history/` directory
- Always use `--json` flag for programmatic tools

## References

- AGENTS.md: Project-specific patterns and workflows
- docs/PAPER_DRAFT_121625.md: Research paper and motivation
- docs/LITERATURE_REVIEW.md: Related work survey
