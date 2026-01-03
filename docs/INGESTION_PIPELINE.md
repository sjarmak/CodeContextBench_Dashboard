# Ingestion Pipeline

The ingestion pipeline processes Harbor evaluation results and Claude Code transcripts to extract metrics for dashboard analysis.

## Components

### 1. HarborResultParser
Parses Harbor `result.json` files to extract:
- Task metadata (ID, name, category, difficulty)
- Agent output (exit code, duration, type)
- Verifier results (pass/fail, reward metrics, duration)
- Model and agent names

**Features:**
- Handles missing fields gracefully
- Extracts reward metrics from multiple locations
- Infers pass/fail from various sources
- Supports custom reward files

**Usage:**
```python
from src.ingest import HarborResultParser
from pathlib import Path

parser = HarborResultParser()
result = parser.parse_file(Path("result.json"))
```

### 2. TranscriptParser
Extracts tool usage patterns from Claude Code transcripts:
- Tool categorization (MCP, Deep Search, Local, Other)
- Tool call counts and frequencies
- Success rates and effectiveness
- File access patterns
- Search query extraction

**Features:**
- Regex-based tool pattern detection
- MCP vs local tool ratio calculation
- Tool diversity metrics
- File path normalization

**Usage:**
```python
from src.ingest import TranscriptParser

parser = TranscriptParser()
metrics = parser.parse_file(Path("claude-code.txt"))
# Or parse text directly
metrics = parser.parse_text(transcript_content)
```

### 3. MetricsDatabase
SQLite database for storing and querying metrics:

**Tables:**
- `harbor_results`: Evaluation results (task, agent, model, pass/fail, duration, rewards)
- `tool_usage`: Tool usage patterns (tool counts, success rates, MCP ratios)
- `experiment_summary`: Aggregated statistics per experiment

**Features:**
- UPSERT logic for duplicate handling
- Indexed queries for performance
- Foreign key constraints
- Comprehensive statistics queries

**Usage:**
```python
from src.ingest import MetricsDatabase
from pathlib import Path

db = MetricsDatabase(Path("metrics.db"))

# Store results
db.store_harbor_result(result, experiment_id="exp_001", job_id="job_001")
db.store_tool_usage(task_id, metrics, experiment_id="exp_001", job_id="job_001")

# Query
results = db.get_experiment_results("exp_001")
stats = db.get_stats("exp_001")
pass_rate = db.get_pass_rate("exp_001")
```

### 4. IngestionOrchestrator
Coordinates the full pipeline:
- Discovers Harbor result files and transcripts
- Parses and stores results
- Handles errors gracefully
- Updates experiment summaries
- Generates ingestion statistics

**Features:**
- Single experiment ingestion
- Batch directory ingestion
- Flexible path discovery
- Detailed error tracking
- Progress logging

**Usage:**
```python
from src.ingest import IngestionOrchestrator
from pathlib import Path

orchestrator = IngestionOrchestrator(
    db_path=Path("metrics.db"),
    results_dir=Path("results/"),
)

# Ingest single experiment
stats = orchestrator.ingest_experiment(
    experiment_id="exp_001",
    results_dir=Path("results/exp_001/"),
)

# Batch ingest directory
all_stats = orchestrator.ingest_directory(Path("results/"))

# Query results
results = orchestrator.get_experiment_results("exp_001")
stats = orchestrator.get_experiment_stats("exp_001")
```

## Directory Structure

Assumes the following layout for Harbor results:

```
results/
├── exp_001/
│   ├── job_001/
│   │   ├── result.json
│   │   └── claude-code.txt
│   ├── job_002/
│   │   ├── result.json
│   │   └── claude-code.txt
│   └── ...
├── exp_002/
│   └── ...
```

## Data Schema

### harbor_results table
```
task_id TEXT
experiment_id TEXT
job_id TEXT
task_name TEXT
task_category TEXT
task_difficulty TEXT
task_tags TEXT (JSON)
agent_name TEXT
model_name TEXT
passed BOOLEAN
exit_code INTEGER
agent_duration_seconds REAL
verifier_duration_seconds REAL
total_duration_seconds REAL
reward_metrics TEXT (JSON)
reward_primary REAL
evaluated_at TEXT (ISO 8601)
ingested_at TEXT (ISO 8601)
```

### tool_usage table
```
task_id TEXT
experiment_id TEXT
job_id TEXT
total_calls INTEGER
mcp_calls INTEGER
deep_search_calls INTEGER
local_calls INTEGER
other_calls INTEGER
tool_calls_by_name TEXT (JSON)
total_input_tokens INTEGER
total_output_tokens INTEGER
avg_tokens_per_call REAL
successful_calls INTEGER
failed_calls INTEGER
success_rate REAL
mcp_vs_local_ratio REAL
unique_files_accessed INTEGER
search_query_count INTEGER
transcript_length INTEGER
ingested_at TEXT (ISO 8601)
```

### experiment_summary table
```
experiment_id TEXT UNIQUE
total_tasks INTEGER
completed_tasks INTEGER
passed_tasks INTEGER
agent_name TEXT
model_name TEXT
pass_rate REAL
avg_duration_seconds REAL
avg_mcp_calls REAL
avg_deep_search_calls REAL
avg_local_calls REAL
created_at TEXT (ISO 8601)
updated_at TEXT (ISO 8601)
```

## Error Handling

The orchestrator handles common errors gracefully:
- Missing result.json files are skipped with warning
- Missing transcripts log as skipped but don't block ingestion
- Invalid JSON is logged and skipped
- Database errors include detailed messages

All errors are collected in the returned statistics object.

## Performance

- Uses SQLite for reliable, queryable storage
- Indexed on experiment_id, passed status, model for fast queries
- UPSERT logic prevents duplicate processing
- Batch operations for multiple experiments
- Logging includes progress indicators

## Integration with Dashboard

The ingestion pipeline feeds data to the dashboard:

1. **Real-time tracking**: Experiment summaries updated after ingestion
2. **Metrics queries**: Dashboard queries harbor_results and tool_usage tables
3. **Filtering**: Indexes enable fast filtering by experiment, model, status
4. **Aggregation**: Experiment summaries pre-computed for dashboard views

Example dashboard query:
```python
# Get pass rate by agent for experiment
results = db.get_experiment_results("exp_001")
by_agent = defaultdict(list)
for r in results:
    by_agent[r["agent_name"]].append(r)

for agent, results in by_agent.items():
    pass_count = sum(1 for r in results if r["passed"])
    pass_rate = pass_count / len(results)
```

## Testing

Comprehensive test suite (36 tests):
- **Harbor parsing**: Reward extraction, duration, metadata, missing fields
- **Transcript parsing**: Tool categorization, file extraction, success rates
- **Database**: Storage, retrieval, aggregation, summaries
- **Orchestrator**: Single/batch ingestion, error handling, statistics

Run tests:
```bash
python -m pytest tests/test_ingest_*.py -v
```
