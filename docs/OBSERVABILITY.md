# Observability and Metrics Collection

CodeContextBench uses lightweight, JSON-based observability to track benchmark execution metrics without heavy dependencies like NeMo. The system captures tool usage, execution performance, and failure patterns for downstream analysis.

## Overview

Two main modules provide observability:

1. **ManifestWriter** - Writes `run_manifest.json` from Harbor benchmark runs
2. **MetricsCollector** - Collects and analyzes execution metrics across runs

## Key Concepts

### Run Manifest

Each benchmark run produces a `run_manifest.json` containing:

```json
{
  "timestamp": "2025-12-17T16:55:00",
  "harness": {
    "name": "harbor-v1",
    "version": "1.0",
    "framework": "harbor"
  },
  "execution": {
    "agent": "claude-baseline",
    "benchmark": "10figure",
    "job_dir": "/path/to/jobs/claude-baseline-10figure-20251217"
  },
  "tool_profile": {
    "tool_usage": {
      "sourcegraph_deep_search": {
        "tool_name": "sourcegraph_deep_search",
        "category": "code_search",
        "invocation_count": 5,
        "success_count": 4,
        "failure_count": 1,
        "avg_duration_sec": 2.5
      }
    },
    "total_tool_invocations": 5,
    "total_unique_tools": 1,
    "search_queries_count": 5,
    "file_operations_count": 0
  },
  "result": {
    "task_id": "cross_file_reasoning_01",
    "task_name": "cross_file_reasoning_01",
    "success": true,
    "reward": 0.85,
    "duration_sec": 15.5,
    "patch_size_bytes": 2048,
    "files_changed": 3,
    "error_type": null,
    "error_message": null
  },
  "retrieval_metrics": {
    "total_searches": 5,
    "total_file_ops": 0,
    "tools_used": ["sourcegraph_deep_search"],
    "tool_diversity": 1
  }
}
```

## Usage

### Writing Manifests

After a Harbor benchmark run completes, write a manifest:

```python
from pathlib import Path
from observability import ManifestWriter

job_dir = Path('jobs/claude-baseline-10figure-20251217/task-001')

writer = ManifestWriter(job_dir)
manifest_path = writer.write_manifest(
    harness_name='harbor-v1',
    agent_name='claude-baseline',
    benchmark_name='10figure'
)

print(f"Manifest written to: {manifest_path}")
```

### Collecting Metrics

Gather and analyze metrics from multiple runs:

```python
from pathlib import Path
from observability import MetricsCollector

collector = MetricsCollector(Path('jobs'))

# Load all manifests from jobs directory
manifests = collector.load_manifests()

# Extract structured metrics
metrics = collector.extract_metrics(manifests)

# Generate comprehensive report
report = collector.generate_report(metrics)

# Write JSON report
collector.write_report(report, Path('metrics_report.json'))

# Print human-readable report
collector.print_report(report)
```

### Regression Detection

Compare baseline and treatment runs for regressions:

```python
baseline_metrics = [m for m in metrics if 'baseline' in m.agent]
treatment_metrics = [m for m in metrics if 'treatment' in m.agent]

regression = collector.detect_regression(
    baseline_metrics,
    treatment_metrics,
    threshold_percent=10.0
)

print(f"Regressions: {len(regression['regressions'])}")
print(f"Improvements: {len(regression['improvements'])}")
```

## Tool Categories

Tools are categorized by type for analysis:

| Category | Examples | Purpose |
|----------|----------|---------|
| `code_search` | Sourcegraph Deep Search | Finding code patterns and context |
| `file_operation` | cat, grep, find, diff, patch | File manipulation |
| `code_generation` | Git operations, agent execution | Making changes |
| `verification` | Test scripts, validation | Validating results |

## Metrics Fields

### Result Summary

Extracted from Harbor `result.json`:

- `task_id` - Unique task identifier
- `task_name` - Human-readable task name
- `success` - Boolean success indicator (reward > 0)
- `reward` - Numerical reward score (0.0-1.0 range)
- `duration_sec` - Execution time in seconds
- `patch_size_bytes` - Size of generated patch
- `files_changed` - Number of modified files
- `error_type` - Type of error (if failed)
- `error_message` - Error description

### Tool Profile

Aggregated tool usage:

- `tool_usage` - Map of tool name to ToolUsage details
- `total_tool_invocations` - Sum of all tool calls
- `total_unique_tools` - Number of distinct tools used
- `search_queries_count` - Count of code search queries
- `file_operations_count` - Count of file operations

### Retrieval Metrics

Code retrieval effectiveness:

- `total_searches` - Total code search invocations
- `total_file_ops` - Total file operation invocations
- `tools_used` - List of tools that were used
- `tool_diversity` - Number of unique tools

## Report Structure

Generated reports contain:

```json
{
  "overall": {
    "total": 10,
    "successful": 8,
    "success_rate": 80.0,
    "avg_duration_sec": 14.5,
    "median_duration_sec": 14.0,
    "avg_patch_size_bytes": 2048,
    "avg_files_changed": 2.5,
    "avg_reward": 0.75,
    "max_reward": 1.0,
    "errors": {
      "TimeoutError": 2
    }
  },
  "per_agent": {
    "claude-baseline": { /* stats */ },
    "claude-mcp": { /* stats */ }
  },
  "per_benchmark": {
    "10figure": { /* stats */ },
    "terminal-bench": { /* stats */ }
  },
  "task_consistency": {
    "task-001": {
      "runs": 2,
      "success_rate": 100.0,
      "consistent": true
    }
  },
  "total_metrics": 10
}
```

## Integration with Benchmark Runner

The observability system integrates with `harbor_benchmark.sh`:

```bash
#!/bin/bash
# After Harbor completes, write manifests
python3 -c "
from pathlib import Path
from observability import ManifestWriter

for job_dir in Path('jobs/run-*').glob('**/task-*'):
    writer = ManifestWriter(job_dir)
    writer.write_manifest(
        harness_name='harbor-v1',
        agent_name='$AGENT',
        benchmark_name='$BENCHMARK'
    )
"
```

## Performance Characteristics

- **Memory**: Minimal - JSON-based, no in-memory aggregation
- **Speed**: Parse manifests in O(n) where n = number of runs
- **Dependencies**: Python stdlib only (json, pathlib, statistics)
- **Output**: JSON files suitable for further analysis

## Regression Detection

The `detect_regression()` method compares baseline and treatment metrics:

- **Success Rate**: Flags if treatment success rate drops >threshold_percent
- **Duration**: Flags if treatment execution becomes >threshold_percent slower
- **Improvements**: Reports cases where treatment outperforms baseline

Example output:

```json
{
  "regressions": [
    {
      "metric": "success_rate",
      "baseline": 80.0,
      "treatment": 60.0,
      "delta_percent": -20.0
    }
  ],
  "improvements": [
    {
      "metric": "avg_duration_sec",
      "baseline": 20.0,
      "treatment": 15.0,
      "delta_percent": -25.0
    }
  ],
  "baseline_stats": { /* ... */ },
  "treatment_stats": { /* ... */ }
}
```

## Testing

All observability modules are thoroughly tested:

```bash
pytest tests/test_observability.py -v
```

Tests cover:
- Manifest parsing and writing
- Tool usage extraction
- Metrics computation
- Regression detection
- Report generation
- Edge cases (empty results, missing files, etc.)

## See Also

- **docs/ARCHITECTURE.md** - System architecture
- **runners/harbor_benchmark.sh** - Benchmark execution
- **runners/aggregator.py** - Cross-benchmark aggregation
- **runners/compare_results.py** - Result comparison
