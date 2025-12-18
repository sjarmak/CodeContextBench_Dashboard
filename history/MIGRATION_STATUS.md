# CodeContextBench Migration Status

**Last Updated**: 2025-12-17

## Overview

Unified benchmark framework consolidating sg_benchmark and sourcegraph-benchmarks projects.

## Completed

 **Phase 1: Directory Skeleton** (CodeContextBench-swl)
- Created full directory structure
- Ported BasePatchAgent (generalized for multi-agent support)
- Added core modules: task_schema.py, metrics_collector.py, tool_profiles.py
- Configuration stubs: repos.yaml, tool_profiles.py
- Project README and setup.py

## In Progress

 **Agent Implementations** (3 tasks)
- CodeContextBench-ews: ClaudeCodeAgent (baseline)
- CodeContextBench-mk9: ClaudeCodeSourcegraphMCPAgent (with MCP)
- codegen task

 **Task Schema & Infrastructure** (4 tasks)
- CodeContextBench-6vn: Port task_schema.py
- CodeContextBench-81d: Port Harbor runners
- CodeContextBench-uzn: Port 10Figure task generator
- CodeContextBench-a2g: datasets.yaml

 **Observability & Docs** (2 tasks)
- CodeContextBench-4re: Observability (metrics_collector.py)
- CodeContextBench-qxh: Infrastructure docs
- CodeContextBench-7qs: AGENTS.md/ARCHITECTURE.md

## Architecture Summary

### Agents
- `agents/base.py`: Abstract base class (repo discovery, git diff capture)
- `agents/claude_agent.py`: Claude Code baseline (TBD)
- `agents/claude_sourcegraph_mcp_agent.py`: Claude + Sourcegraph MCP (TBD)

### Benchmarks
- `benchmarks/10figure/`: 10Figure-Codebases tasks (~5GB corpus, external)
- `benchmarks/github_mined/`: Real GitHub issues (future)
- `benchmarks/terminal-bench/`: Terminal-based tasks (future)

### Core Infrastructure
- `src/benchmark/task_schema.py`: Task TOML parsing
- `src/benchmark/metrics_collector.py`: JSON metrics + patch stats
- `configs/tool_profiles.py`: Tool capability profiles

### Runners
- `runners/harbor_benchmark.sh`: Main orchestrator (TBD)
- `runners/compare_results.py`: Agent comparison (TBD)
- `runners/aggregator.py`: Multi-benchmark reports (TBD)

## Key Design Decisions

1. **Claude Code as Primary Agent** (not Amp)
   - Reason: Better CLI integration, active development
   - Amp: Optional/legacy support via same BasePatchAgent

2. **Sourcegraph Tools via MCP** (not ds CLI)
   - Reason: Cleaner integration, supports multiple tools
   - ds CLI: Alternative implementation if needed

3. **Simple JSON Observability** (not NeMo-Agent-Toolkit)
   - Reason: Lower complexity, Harbor logs sufficient
   - Extensible for future metrics collection

4. **Harbor + Podman Framework**
   - Reason: Proven working in sourcegraph-benchmarks
   - Supports 10Figure corpus at /10figure/src/<repo>/

## Data & Datasets

- **10Figure-Codebases**: `/Users/sjarmak/10Figure-Codebases/` (~5GB)
  - 23 real-world repositories
  - 16,834 symbol/API task definitions
  - Reference via symlink in CodeContextBench

- **Harbor Task Manifest**: `/Users/sjarmak/harbor-10figure-dataset/`
  - Task specifications in Harbor format
  - Ready for benchmark runner integration

## Next Steps

1. Implement Claude Code agents (baseline + MCP variants)
2. Port task schema and Harbor runners
3. Setup 10Figure task loader
4. Create smoke tests
5. Run baseline benchmarks

## Related Files

- AGENTS.md: Project-specific patterns
- docs/PAPER_DRAFT_121625.md: Research motivation
- docs/LITERATURE_REVIEW.md: Related work survey
