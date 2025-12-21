# Development Guide

## Setup: Development & Benchmark Environments

CodeContextBench uses two separate Python environments:
1. **`.venv`** - Development environment (tests, utilities, analysis)
2. **`harbor/`** - Harbor environment (for running benchmarks with Daytona)

### Quick Start: Development

#### 1. Create Development Virtual Environment

```bash
cd CodeContextBench
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Install Dependencies

```bash
# Install CodeContextBench with dependencies
pip install -e .

# If testing NeMo integration, install from local source
pip install -e ~/NeMo-Agent-Toolkit/
```

#### 3. Python Version

- **Required**: Python 3.12.11
- Check with: `python --version`
- Set via: `pyenv local 3.12.11` (if using pyenv)

#### 4. Virtual Environment Management

All development and testing should use the `.venv` environment:

```bash
# Activate
source .venv/bin/activate

# Deactivate
deactivate

# View Python location
which python

# View installed packages
pip list
```

### Harbor Setup: Benchmarks with Daytona

To run benchmarks, use the **Harbor venv** instead of `.venv`:

```bash
# Activate Harbor environment (sets up Daytona credentials, DOCKER_HOST, PATH)
source harbor/bin/activate

# Run Harbor with Daytona backend
harbor run \
  --dataset swebench-verified@1.0 \
  --agent oracle \
  --env daytona \
  -n 1
```

See **infrastructure/PODMAN.md** for complete Harbor + Daytona setup and troubleshooting.

### Dependencies

#### Core

- pathlib, json, statistics (Python stdlib)

#### Observability

- **ManifestWriter**: Writes Harbor benchmark manifests
- **MetricsCollector**: Analyzes execution metrics
- **NeMoTraceParser**: Parses NeMo-Agent-Toolkit traces
- **ClaudeOutputParser**: Extracts token usage from Claude logs

#### Optional

- **NeMo-Agent-Toolkit**: For structured execution tracing
  - Install from ~/NeMo-Agent-Toolkit/
  - Provides structured trace format for agent execution

### Environment Variables

Optional environment variables:

```bash
# SRC_ACCESS_TOKEN for Sourcegraph Deep Search
export SRC_ACCESS_TOKEN=<your_token>

# ANTHROPIC_API_KEY for Claude
export ANTHROPIC_API_KEY=<your_key>

# Debug mode for extra logging
export DEBUG=1
```

## Development Commands

```bash
# Validate Python package
python setup.py check

# Run all tests
python -m pytest tests/ -q

# Run specific test
python -m pytest tests/test_mcp_agent_setup.py -v

# Format code
black agents/ runners/ observability/ tests/

# Type check
mypy agents/ runners/ observability/

# Smoke test infrastructure
python tests/smoke_test_10figure.py

# Agent environment injection test
python -m pytest tests/test_agent_env_injection.py -v

# With coverage
pytest tests/ --cov=src --cov=observability --cov=runners
```

## Common Development Tasks

### Run All Tests

```bash
pytest tests/ -q
```

### Run Specific Test

```bash
pytest tests/test_observability.py::TestNeMoTraceParser -v
```

### Extract NeMo Traces from Jobs

```bash
python runners/extract_nemo_traces.py --jobs-dir jobs/ --agent claude-baseline
```

### Generate Metrics Report

```bash
python -c "
from pathlib import Path
from observability import MetricsCollector

collector = MetricsCollector(Path('jobs'))
manifests = collector.load_manifests()
metrics = collector.extract_metrics(manifests)
report = collector.generate_report(metrics)
collector.print_report(report)
"
```

### Testing NeMo Integration

The NeMo integration requires NeMo-Agent-Toolkit to be installed:

```bash
# Install NeMo from local source
pip install -e ~/NeMo-Agent-Toolkit/

# Run NeMo-specific tests
pytest tests/test_observability.py::TestNeMoTraceParser -v

# Test trace extraction
python runners/extract_nemo_traces.py --jobs-dir jobs/ --all
```

## Troubleshooting Setup

### ModuleNotFoundError: No module named 'observability'

**Solution**: Make sure you're in the `.venv` and have installed CodeContextBench:

```bash
source .venv/bin/activate
pip install -e .
```

### Tests fail with "No such file or directory"

**Solution**: Run tests from the project root:

```bash
cd /Users/sjarmak/CodeContextBench
pytest tests/ -v
```

### NeMo-related imports fail

**Solution**: Install NeMo-Agent-Toolkit:

```bash
pip install -e ~/NeMo-Agent-Toolkit/
```

## Setting Up a New Agent Implementation

Agents extend Harbor's `ClaudeCode` class. See `agents/claude_sourcegraph_mcp_agent.py` for reference.

1. Create agent class in `agents/<agent_name>_agent.py`:

```python
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput

class MyAgent(ClaudeCode):
    """Custom agent extending ClaudeCode."""

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        """Override to customize Claude command and environment."""
        parent_commands = super().create_run_agent_commands(instruction)
        # Modify commands, add env vars, etc.
        return modified_commands

    def setup(self, env: BaseEnvironment, paths: EnvironmentPaths) -> None:
        """Optional: Run setup before agent execution (e.g., upload config files)."""
        super().setup(env, paths)
        # Custom setup logic
```

2. Key override methods:
   - `create_run_agent_commands()` - Modify Claude CLI command and environment
   - `setup()` - Upload files, configure container before agent runs

3. Enable implementation mode by injecting:
   - `FORCE_AUTO_BACKGROUND_TASKS=1` and `ENABLE_BACKGROUND_TASKS=1` env vars
   - `--permission-mode acceptEdits` flag
   - `--allowedTools Bash,Read,Edit,Write,Grep,Glob` flag

4. Write tests in `tests/test_<agent_name>_agent.py`

5. Run agent with Harbor:
```bash
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.<module>:<ClassName> \
  -n 1
```

## Executing a Benchmark Run

1. Verify environment: `python tests/smoke_test_10figure.py`
2. Run benchmark: `bash runners/harbor_benchmark.sh --benchmark 10figure --agent claude-baseline --tasks 10`
3. Monitor Harbor: Check job output in `jobs/` directory
4. Collect results: `bash runners/harbor_benchmark.sh --collect-results jobs/baseline-* jobs/treatment-*`
5. Aggregate results: `python runners/aggregator.py --runs jobs/ --output jobs/report.json`

## Comparing Agent Performance

```bash
# Run multiple agents on same benchmark
bash runners/harbor_benchmark.sh --benchmark 10figure --agent claude-baseline --tasks 50
bash runners/harbor_benchmark.sh --benchmark 10figure --agent claude-mcp --tasks 50

# Generate comparison report
python runners/compare_results.py jobs/claude-baseline-* jobs/claude-mcp-*
```

## Working with Benchmarks

### Generating Harbor Tasks from 10Figure YAML

```bash
python runners/gen_harbor_tasks.py \
  --input /path/to/10figure/tasks \
  --output benchmarks/10figure \
  --templates benchmarks/10figure/templates \
  --repo kubernetes \
  --corpus-root /10figure
```

### Task Structure Validation

Each task must have:
- `instruction.md` - Human-readable task description (type-specific)
- `task.toml` - Harbor metadata
- `task.yaml` - 10Figure task definition with fixed paths
- `environment/Dockerfile` - Container setup
- `tests/test.sh` - Validation script (rendered from Jinja2)

## Debugging

### Inspect task context
```bash
ls -la benchmarks/10figure/<task_id>/
cat benchmarks/10figure/<task_id>/instruction.md
cat benchmarks/10figure/<task_id>/task.yaml
```

### Check test results
```bash
ls -la jobs/run-*/
cat jobs/run-*/agent.log
cat jobs/run-*/reward.txt
```

### Validate result format
```bash
python tests/test_task_schema.py -v
```

## Code Quality Standards

- All new agent implementations must have unit tests
- All benchmark runners must validate task structure before execution
- All results must include execution metadata (agent_name, task_id, execution_time, tool_usage)
- Code must pass `black` formatting and `mypy` type checking
- Test coverage should remain above 80%


