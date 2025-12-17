# Development Setup

CodeContextBench uses a dedicated Python virtual environment to manage dependencies, including integration with NeMo-Agent-Toolkit.

## Quick Start

### 1. Create Virtual Environment

```bash
cd CodeContextBench
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
# Install CodeContextBench with dependencies
pip install -e .

# If testing NeMo integration, install from local source
pip install -e ~/NeMo-Agent-Toolkit/
```

### 3. Run Tests

```bash
# All tests
pytest tests/ -q

# Specific test file
pytest tests/test_observability.py -v

# With coverage
pytest tests/ --cov=src --cov=observability --cov=runners
```

## Python Version

- **Required**: Python 3.12.11
- Check with: `python --version`
- Set via: `pyenv local 3.12.11` (if using pyenv)

## Dependencies

### Core

- pathlib, json, statistics (Python stdlib)

### Observability

- **ManifestWriter**: Writes Harbor benchmark manifests
- **MetricsCollector**: Analyzes execution metrics
- **NeMoTraceParser**: Parses NeMo-Agent-Toolkit traces
- **ClaudeOutputParser**: Extracts token usage from Claude logs

### Optional

- **NeMo-Agent-Toolkit**: For structured execution tracing
  - Install from ~/NeMo-Agent-Toolkit/
  - Provides structured trace format for agent execution

## Virtual Environment

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

## Testing NeMo Integration

The NeMo integration requires NeMo-Agent-Toolkit to be installed:

```bash
# Install NeMo from local source
pip install -e ~/NeMo-Agent-Toolkit/

# Run NeMo-specific tests
pytest tests/test_observability.py::TestNeMoTraceParser -v

# Test trace extraction
python runners/extract_nemo_traces.py --jobs-dir jobs/ --all
```

## Project Structure

```
CodeContextBench/
├── .venv/                 # Virtual environment (excluded from git)
├── .python-version        # Python version specification
├── observability/         # Observability modules
│   ├── __init__.py
│   ├── nemo_trace_parser.py
│   ├── manifest_writer.py
│   ├── metrics_collector.py
│   └── claude_output_parser.py
├── runners/               # Batch processing runners
│   ├── extract_nemo_traces.py
│   ├── collect_observability.py
│   └── aggregator.py
├── tests/                 # Test suite
├── docs/                  # Documentation
│   ├── SETUP.md          # This file
│   ├── OBSERVABILITY.md   # Observability guide
│   └── ARCHITECTURE.md    # System architecture
└── AGENTS.md              # Agent patterns and learnings
```

## Common Tasks

### Run all tests

```bash
pytest tests/ -q
```

### Run specific test

```bash
pytest tests/test_observability.py::TestNeMoTraceParser -v
```

### Extract NeMo traces from jobs

```bash
python runners/extract_nemo_traces.py --jobs-dir jobs/ --agent claude-baseline
```

### Generate metrics report

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

## Troubleshooting

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

## Environment Variables

Optional environment variables:

```bash
# SRC_ACCESS_TOKEN for Sourcegraph Deep Search
export SRC_ACCESS_TOKEN=<your_token>

# ANTHROPIC_API_KEY for Claude
export ANTHROPIC_API_KEY=<your_key>

# Debug mode for extra logging
export DEBUG=1
```

## See Also

- **docs/OBSERVABILITY.md** - Observability and metrics collection guide
- **docs/ARCHITECTURE.md** - System architecture and design
- **AGENTS.md** - Agent patterns and learned knowledge
