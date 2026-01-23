# CodeContextBench

Benchmark evaluation platform for measuring how Sourcegraph code intelligence improves coding agent performance. Features an interactive **Streamlit dashboard** for managing, monitoring, and analyzing agent evaluations running in isolated VM environments.

## Quick Overview

- **Dashboard**: Streamlit web UI for benchmark management, execution, result analysis, and agent comparison
- **Execution**: Benchmarks run in isolated VMs via **Harbor + Podman** orchestration
- **Agents**: Baseline Claude Code + four MCP variants (strategic/aggressive Deep Search, keyword-only, full toolkit)
- **Benchmarks**: 6+ benchmark suites (big_code_mcp, github_mined, dependeval, TAC, etc.) with 50+ total tasks
- **Evaluation**: Automated execution → metrics extraction → LLM judge assessment → results visualization
- **Results**: Interactive charts, cost analysis, tool usage patterns, agent comparison reports

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

## Running Evaluations

### Dashboard (Recommended)

1. **Start the dashboard**:
   ```bash
   streamlit run dashboard/app.py
   ```
   Opens at `http://localhost:8501`

2. **Navigate to "Run Benchmarks"** to:
   - Select benchmark suite and tasks
   - Choose agent variants to evaluate
   - Configure model and parameters
   - Preview commands before execution
   - Monitor execution progress

3. **View results** in:
   - **Experiment Results**: Per-task and per-agent metrics
   - **Agent Comparison**: Side-by-side performance analysis
   - **Deep Search Analytics**: MCP tool usage patterns
   - **Cost Analysis**: Token usage and cost tracking

### Command Line (Advanced)

For automated workflows, use Harbor CLI directly:

```bash
# Source environment and export credentials
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Run benchmark
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

## Agent Implementations

### BaselineClaudeCodeAgent (`agents/claude_baseline_agent.py`)
Claude Code without Sourcegraph integrations:
- Extends Harbor's `ClaudeCode` agent with autonomous environment variables
- Tools: Bash, Read, Edit, Write, Grep, Glob (no MCP/Deep Search)
- Use as control group for MCP value measurement
- Requires: `ANTHROPIC_API_KEY` only

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

## Current State

### Infrastructure (Complete)
- ✅ Harbor + Podman VM orchestration fully operational
- ✅ 6+ benchmark suites with 50+ tasks ready for evaluation
- ✅ Streamlit dashboard for UI-driven benchmark execution
- ✅ Automated metrics extraction and LLM judge assessment
- ✅ Results visualization with Plotly charts

### Dashboard Features (Complete)
- ✅ Home: Quick stats and activity feed
- ✅ Benchmark Manager: Browse and filter available benchmarks
- ✅ Run Benchmarks: Execute evaluations with preview and dry-run modes
- ✅ Experiment Results: View per-task metrics and judge assessments
- ✅ Agent Comparison: Side-by-side performance analysis with interactive charts
- ✅ Deep Search Analytics: Tool usage patterns and cost analysis

### Active Development
- Expanding benchmark coverage (TAC suite, SWEBench integration)
- Enhancing analysis visualizations and reporting
- Refining agent configurations and prompt strategies

See `.beads/issues.jsonl` for current work tracking.

## Contributing

- Use `bd ready` to find unblocked work
- Always close beads with `bd close` when work is complete
- Store AI planning docs in `history/` directory
- Always use `--json` flag for programmatic tools

## Documentation

**Getting Started:**
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) - Setup, dependencies, and development workflow
- [dashboard/README.md](dashboard/README.md) - Dashboard features and usage guide
- [benchmarks/README.md](benchmarks/README.md) - Available benchmarks and descriptions

**Reference:**
- [AGENTS.md](AGENTS.md) - Project patterns, workflows, and issue tracking
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design, component overview, and data flow
- [docs/EXPERIMENT_MANAGEMENT.md](docs/EXPERIMENT_MANAGEMENT.md) - Experiment naming and organization
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) - Metrics collection and tracing
