# CodeContextBench

Benchmark framework for evaluating how improved codebase understanding through Sourcegraph code intelligence tools improves coding agent performance.

## Quick Overview

- **Goal**: Measure the ROI of Sourcegraph-assisted code understanding for coding agents
- **Agents**: Baseline Claude Code + four MCP variants (strategic/aggressive Deep Search, keyword-only, full toolkit)
- **Benchmarks**: `big_code_mcp`, `github_mined`, `dependeval_benchmark`, `10figure`, `dibench`, `repoqa`, `kubernetes_docs`
- **Execution**: Harbor CLI (`harbor run --path <task> --agent-import-path <agent> --model anthropic/claude-haiku-4-5-20251001`)
- **Evaluation**: Agent executes task → git diff captured → benchmark tests validate → reward score recorded in `jobs/`

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

#### BaselineClaudeCodeAgent (`agents/claude_baseline_agent.py`)
Claude Code baseline with autonomous implementation mode enabled:
- Extends Harbor's `ClaudeCode` agent and injects `FORCE_AUTO_BACKGROUND_TASKS=1`/`ENABLE_BACKGROUND_TASKS=1`
- Provides tool access (Bash, Read, Edit, Write, Grep, Glob) without MCP integrations
- Requires only `ANTHROPIC_API_KEY`
- Recommended command:
  ```bash
  harbor run \
    --path benchmarks/github_mined \
    --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
    --model anthropic/claude-haiku-4-5-20251001 \
    -n 1
  ```

#### MCP Variants (`agents/mcp_variants.py`)

- **StrategicDeepSearchAgent** *(recommended)* – Uses Sourcegraph Deep Search at critical checkpoints for context gathering.
- **DeepSearchFocusedAgent** – Uses a dedicated deep-search-only MCP endpoint and aggressively prompts the agent to use Deep Search for every question.
- **MCPNonDeepSearchAgent** – Enables Sourcegraph keyword/NLS search but keeps Deep Search disabled.
- **FullToolkitAgent** – Neutral MCP prompting; all Sourcegraph tools enabled with no guidance bias.

All MCP variants:
- Require `ANTHROPIC_API_KEY`, `SOURCEGRAPH_ACCESS_TOKEN`, and `SOURCEGRAPH_URL`
- Write `.mcp.json` configs that Harbor uploads into task containers
- Share the same autonomous command-generation logic as the baseline agent

Example (Strategic Deep Search):
```bash
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

> **Compatibility**: `agents/claude_sourcegraph_mcp_agent.py` remains as an alias to `DeepSearchFocusedAgent` for older automation that still references `ClaudeCodeSourcegraphMCPAgent`.

## Benchmarks

All benchmarks are self-contained in `benchmarks/` directory:

- **big_code_mcp**: 4 real large-codebase tasks (VS Code, Kubernetes, Servo, TensorRT)
- **github_mined**: 25 PyTorch real-world PR tasks
- **dependeval_benchmark**: 9 multi-file/cross-repo reasoning tasks
- **10figure**: 4 legacy codebase challenges (requires `~/10Figure-Codebases/` corpus)
- **dibench**: Multi-language dependency inference (Harbor adapter, variable task count)
- **repoqa**: Tool-sensitive code understanding tasks (Harbor adapter, newly completed)
- **kubernetes_docs**: 5 documentation-generation tasks that strip in-tree docs and compare baseline vs MCP retrieval

See [benchmarks/README.md](benchmarks/README.md) for detailed benchmark descriptions and usage.

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
- docs/ARCHITECTURE.md: System design and component overview
- docs/DEVELOPMENT.md: Development environment setup, commands, and agent implementation
- docs/BENCHMARK_DESIGN_GUIDE.md: Enterprise-informed benchmark design principles
