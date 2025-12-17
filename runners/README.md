# Benchmark Runners

Scripts for executing CodeContextBench tasks via Harbor framework.

## Scripts

- **harbor_benchmark.sh** - Main benchmark orchestrator (TBD: port from sourcegraph-benchmarks)
- **compare_results.py** - Comparative analysis between agent runs
- **aggregator.py** - Cross-benchmark result aggregation and reporting

## Architecture

All runners expect:
- Harbor CLI installed and configured
- Podman available (or docker-wrapper.sh for Docker)
- Task definitions in `benchmarks/*/` directories
- Agent implementations in `agents/` directory

## Common Workflows

### Run a single benchmark variant

```bash
bash runners/harbor_benchmark.sh --benchmark 10figure --agent claude-baseline
```

### Compare two agent variants

```bash
python runners/compare_results.py \
  --baseline results/claude-baseline/ \
  --treatment results/claude-sourcegraph-mcp/
```

### Aggregate multi-benchmark results

```bash
python runners/aggregator.py --runs results/ --output results/report.json
```

## Result Format

All results are standardized JSON (see `docs/API.md`):
- agent_name, task_id, status, timestamp
- elapsed_seconds, patch_stats
- test_passed, error_message
- tool_calls (if available)

Results are stored in `artifacts/results/<run_id>/` with one JSON per task.
