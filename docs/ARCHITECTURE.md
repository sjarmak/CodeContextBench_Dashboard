# CodeContextBench Architecture

## Directory Structure

### Agent Development (`agents/`)
- **BasePatchAgent** in `base.py`: Abstract base class for all agent implementations
- Agent implementations should inherit from BasePatchAgent and implement required methods
- Installation templates (`install-*.sh.j2`) are Jinja2-based; use `jinja2` CLI for rendering

### Benchmark Task Sets (`benchmarks/`)
- **Terminal-Bench 2.0**: Original terminal-based tasks in `terminal-bench/`
- **10Figure-Codebases**: Real-world codebase evaluation tasks in `10figure/`
- **Custom tasks**: Project-specific benchmarks in `custom/`
- Task format: Each benchmark should include instruction.md, task.toml, task.yaml, environment/Dockerfile, tests/test.sh

### Benchmark Runners (`runners/`)
- **harbor_benchmark.sh**: Primary execution orchestrator (works with Harbor container system)
- **compare_results.py**: Comparative analysis across runs and agents
- **aggregator.py**: Cross-benchmark result aggregation and reporting
- **gen_harbor_tasks.py**: Converts 10Figure YAML to Harbor format

### Infrastructure (`infrastructure/`)
- **Podman-first approach**: Primary container system (see `PODMAN.md` for setup)
- **docker-wrapper.sh**: Docker compatibility layer for hybrid environments
- **Harbor config** (`harbor-config.yaml`): Container orchestration settings

### Observability (`observability/`)
- **nemo_observer.py**: Wraps agent execution for metrics capture
- **metrics_exporter.py**: Exports metrics to external systems (Prometheus, S3, etc.)

### Testing & Validation (`tests/`)
- **smoke_test_10figure.py**: Validates 10Figure task infrastructure
- **test_agent_comparison.py**: Compares Claude baseline vs Claude+MCP
- **test_claude_agents.py**: Tests agent command generation and environment setup
- **test_runners.py**: Tests benchmark result loading and aggregation

### Knowledge & Learning (`.engram/`)
- **engram.db**: SQLite database containing learned patterns, traces, insights, and bullets
- Populated automatically when beads are closed via `en learn`

## Key Files

| File | Purpose |
|------|---------|
| `agents/base.py` | Abstract base class and shared agent infrastructure |
| `agents/claude_agent.py` | Claude Code baseline agent (no tools) |
| `agents/claude_sourcegraph_mcp_agent.py` | Claude Code with Sourcegraph MCP integration |
| `runners/harbor_benchmark.sh` | Main benchmark orchestrator script |
| `docs/API.md` | Result format specification |
| `.beads/issues.jsonl` | Issue tracking and bead state (auto-synced) |
| `.engram/engram.db` | Learned patterns and execution traces |

## Data Flow

```
Benchmark Tasks
├── Terminal-Bench 2.0
├── 10Figure Codebases
└── Custom Tasks
    ↓
Harbor Container System
├── Agent Execution (Claude baseline or +MCP)
└── Patch Validation
    ↓
Result Collection
├── JSON results per task
├── Execution traces
└── Tool usage metrics
    ↓
Aggregation & Analysis
├── Per-run statistics
├── Cross-benchmark comparison
└── Error pattern analysis
    ↓
Learning (Engram)
├── Pattern extraction
├── Insight generation
└── Knowledge base update (.engram/engram.db)
```

## Agent Architecture

All agents inherit from `BasePatchAgent` and implement:
- `get_agent_command(instruction, repo_dir)` - Generate execution command
- `get_agent_env()` - Provide environment variables
- `_install_agent_template_path` - Path to installation template

**Claude Baseline** requires: `ANTHROPIC_API_KEY`
**Claude+MCP** requires: `ANTHROPIC_API_KEY` + `SRC_ACCESS_TOKEN`

MCP configuration is applied at Harbor runtime via `--mcp-config` flag, not in agent code.

## Testing Strategy

1. **Smoke tests**: Validate environment, tool availability, agent initialization
2. **Unit tests**: Agent command generation, environment setup, result parsing
3. **Integration tests**: Full benchmark run, result aggregation
4. **Learning tests**: Engram pattern extraction and knowledge storage
