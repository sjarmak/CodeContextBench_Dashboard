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


