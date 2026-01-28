# Ingestion Pipeline Quick Start

Get raw Harbor results into the metrics database in 3 commands.

## Prerequisites

1. Results synced from VM: `./ccb sync pull`
2. Python environment with dependencies installed

## Quick Start

### 1. Ingest All Results
```bash
./ccb ingest
```

Processes all experiments in `data/results/` and stores metrics in `data/metrics.db`.

### 2. Ingest Specific Experiment
```bash
./ccb ingest exp001
```

### 3. Verbose Output (for debugging)
```bash
./ccb ingest exp001 -v
```

## Typical Output

```
Ingesting experiment: exp001

✓ job001
✓ job002
✓ job003
✗ job004

✓ Ingested 3/4 tasks

Database: /Users/sjarmak/CodeContextBench/data/metrics.db

Overall Stats:
  Pass rate: 75.0%
  Avg duration: 45.2s

Tool Usage:
  Avg MCP calls: 5.2
  Avg Deep Search calls: 1.3
  Avg Local calls: 3.8
```

## Expected Data Structure

The ingestion pipeline expects results from Harbor in this structure:

```
data/results/
├── exp001/                          # Experiment directory
│   ├── job001/                      # Job/task execution
│   │   ├── result.json              # Required: Harbor result
│   │   ├── claude-code.txt          # Optional: Agent transcript
│   │   └── logs/
│   │       └── verifier/
│   │           └── reward.json      # Optional: Additional rewards
│   ├── job002/
│   │   └── result.json
│   └── job003/
│       └── result.json
└── exp002/
    ├── job001/
    └── ...
```

## What Gets Extracted

### From result.json
- Task ID, name, category, difficulty
- Pass/fail status
- Execution duration (agent + verifier)
- Reward metrics (MRR, precision, recall, custom)
- Model and agent names

### From claude-code.txt
- Tool usage by category (MCP, Deep Search, local)
- Tool usage by name (bash, grep, sg_keyword_search, etc.)
- Success/failure rates
- Files accessed
- Search queries issued

## Database Location

Metrics are stored in: `data/metrics.db`

This is a standard SQLite database with 3 tables:
- `harbor_results`: Evaluation results and metrics
- `tool_usage`: Tool usage patterns
- `experiment_summary`: Aggregate statistics

## Query Examples

### Get results for an experiment
```python
from pathlib import Path
from src.ingest import MetricsDatabase

db = MetricsDatabase(Path("data/metrics.db"))
results = db.get_experiment_results("exp001")
for r in results:
    print(f"{r['task_id']}: {'✓' if r['passed'] else '✗'}")
```

### Get overall statistics
```python
stats = db.get_stats("exp001")
print(f"Pass rate: {stats['harbor']['pass_rate']:.1%}")
print(f"Avg MCP calls: {stats['tool_usage']['avg_mcp_calls']:.1f}")
```

### Get pass rate
```python
pass_rate = db.get_pass_rate("exp001")
print(f"Pass rate: {pass_rate:.1%}")
```

## Troubleshooting

### No experiments found
Ensure you've run `./ccb sync pull` to fetch results from the VM.

### Some tasks show errors
Results may be missing `result.json` or have malformed JSON. Use `-v` flag to see details.

### Database locked
Another process is using the database. Wait a moment and try again, or restart the Python process.

## Next: Analysis

Once results are ingested, use the analysis layer (Phase 3) to:
- Compare agents (baseline vs MCP configurations)
- Compute IR metrics (precision, recall, MRR)
- Run LLM-as-judge evaluation
- Detect failure patterns
- Get optimization recommendations

See `docs/INGESTION_PIPELINE.md` for full documentation.
