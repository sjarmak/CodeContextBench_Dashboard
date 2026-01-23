# Development Guide

## Quick Start: Running the Dashboard

The simplest way to use CodeContextBench is via the dashboard:

```bash
# 1. Install dependencies
pip install -r dashboard/requirements.txt

# 2. Ensure your environment file is set up
# Copy .env.local.example to .env.local and fill in your API keys
cp .env.local.example .env.local

# 3. Start the dashboard
streamlit run dashboard/app.py

# 4. Open http://localhost:8501 in your browser
```

That's it! The dashboard handles all benchmark execution and result visualization.

---

## Development Environment Setup

For development work on the codebase (new agents, analysis tools, benchmarks, etc.):

### 1. Create Virtual Environment

```bash
cd CodeContextBench
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Install project in development mode
pip install -e .

# Install dashboard dependencies
pip install -r dashboard/requirements.txt

# Install testing tools
pip install pytest pytest-cov
```

### 3. Python Version

- **Required**: Python 3.12+ (tested on 3.12.11)
- Check: `python --version`
- Manage with: `pyenv local 3.12.11`

### 4. Environment Variables

Create `.env.local` with your credentials:

```bash
cp .env.local.example .env.local
# Edit to add your API keys:
# ANTHROPIC_API_KEY=<your-key>
# SOURCEGRAPH_ACCESS_TOKEN=<your-token>
# SOURCEGRAPH_URL=https://sourcegraph.com
```

The dashboard will automatically load and export these to Harbor subprocesses.

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
# SOURCEGRAPH_ACCESS_TOKEN for Sourcegraph Deep Search
export SOURCEGRAPH_ACCESS_TOKEN=<your_token>

# ANTHROPIC_API_KEY for Claude
export ANTHROPIC_API_KEY=<your_key>

# Debug mode for extra logging
export DEBUG=1
```

## Dashboard Development

### Adding a New Analysis View

1. Create new page in `dashboard/views/my_analysis.py`
2. Import in `dashboard/app.py`
3. Add to sidebar navigation
4. Use shared utilities from `dashboard/utils/`

Example:
```python
# dashboard/views/my_analysis.py
import streamlit as st
from dashboard.utils.common_components import create_header

def show_my_analysis():
    create_header("My Analysis", "description")
    # Your analysis code here

# In dashboard/app.py navigation:
if st.session_state.current_page == "My Analysis":
    from dashboard.views.my_analysis import show_my_analysis
    show_my_analysis()
```

### Accessing Experiment Results

Results are stored in `jobs/` directory. Use utility functions:

```python
from src.ingest.database import load_experiments
from src.analysis.llm_judge_analyzer import LLMJudgeAnalyzer

experiments = load_experiments('jobs/')
analyzer = LLMJudgeAnalyzer()
results = analyzer.analyze(experiment_id)
```

## Testing & Development Commands

```bash
# Run tests
pytest tests/ -q

# Run specific test
pytest tests/test_analysis_llm_judge.py -v

# Run tests with coverage
pytest tests/ --cov=src --cov=dashboard

# Start dashboard in development
streamlit run dashboard/app.py

# Validate agent implementations
python -c "from agents.mcp_variants import StrategicDeepSearchAgent; print('OK')"
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

Agents extend Harbor's `ClaudeCode` class. See `agents/mcp_variants.py` (e.g., `StrategicDeepSearchAgent`) for reference implementations.

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
  --model anthropic/claude-haiku-4-5-20251001 \
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

`claude-mcp` maps to `agents.mcp_variants:StrategicDeepSearchAgent`, so ensure `SOURCEGRAPH_ACCESS_TOKEN` and `SOURCEGRAPH_URL` are exported before invoking it.

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
