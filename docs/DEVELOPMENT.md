# Development Guide

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
```

## Setting Up a New Agent Implementation

1. Create agent class in `agents/<agent_name>_agent.py` inheriting from BasePatchAgent
2. Implement required methods:
   - `get_agent_command(instruction, repo_dir)` - Generate shell command
   - `get_agent_env()` - Return required environment variables
   - `_install_agent_template_path` - Path to Jinja2 installation template
3. Create installation template in `agents/install-<agent_name>.sh.j2` with Jinja2 variables
4. Add agent to `runners/harbor_benchmark.sh` execution loop
5. Write tests in `tests/test_<agent_name>_agent.py`
6. Run smoke tests: `python tests/smoke_test_10figure.py`

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


