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

### BasePatchAgent (agents/base.py)
Abstract base class for all CLI agents. Provides:
- Repository discovery (task.toml or /10figure/src/)
- Git diff capture (baseline → patch)
- Harbor integration
- Extensible environment/command customization

Subclasses implement `get_agent_command()` and `get_agent_env()` for:
- ClaudeCodeAgent (baseline, no Sourcegraph)
- ClaudeCodeSourcegraphMCPAgent (with MCP server)

## Datasets

- **10Figure-Codebases**: `/Users/sjarmak/10Figure-Codebases/` (~5GB, 23 repos)
- **Harbor Task Manifest**: `/Users/sjarmak/harbor-10figure-dataset/`

## Migration Status

✅ Directory skeleton created
✅ BasePatchAgent ported (generalized for multi-agent)
⏳ Agent implementations (Claude Code baseline)
⏳ Benchmark task loaders
⏳ Harbor configuration
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
