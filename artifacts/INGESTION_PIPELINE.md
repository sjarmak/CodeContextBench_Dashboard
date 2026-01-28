# Ingestion Pipeline - Phase 2

The ingestion pipeline processes Harbor evaluation results and agent transcripts, extracting metrics and storing them in a SQLite database for analysis and visualization.

## Architecture

### Pipeline Stages

```
Raw Results (data/results/<exp_id>/)
    ↓
[Harbor Parser] - Parse result.json files
    ↓
[Transcript Parser] - Extract tool usage from transcripts
    ↓
[Database] - Store metrics in SQLite
    ↓
Processed Metrics (data/metrics.db)
```

### Data Flow

1. **Pull results from VM** via `ccb sync pull`
2. **Ingest results** via `ccb ingest [<experiment_id>]`
3. **Results are parsed and stored** in `data/metrics.db`
4. **Dashboard queries database** for analysis and visualization

## Components

### 1. HarborResultParser (`src/ingest/harbor_parser.py`)

Parses `result.json` files from Harbor task evaluations.

**Extracts:**
- Task metadata (ID, name, category, difficulty, tags)
- Agent execution info (exit code, duration, agent type)
- Verifier results (passed/failed status, reward metrics)
- Model and agent names

**Usage:**
```python
from src.ingest.harbor_parser import HarborResultParser

parser = HarborResultParser()
result = parser.parse_file(Path("data/results/exp001/job001/result.json"))

print(f"Task: {result.task_id}")
print(f"Passed: {result.passed}")
print(f"Reward metrics: {result.verifier_result.reward}")
```

**Data Structures:**
- `HarborResult`: Complete evaluation result
- `HarborTaskMetadata`: Task information
- `HarborAgentOutput`: Agent execution details
- `HarborVerifierResult`: Test/verifier results with metrics

### 2. TranscriptParser (`src/ingest/transcript_parser.py`)

Extracts tool usage patterns from agent transcripts (claude-code.txt).

**Extracts:**
- Total tool call count
- Breakdown by category: MCP, Deep Search, local, other
- Tool usage by name (bash, grep, sg_keyword_search, etc.)
- Success/failure rates
- MCP vs local tool ratio (effectiveness metric)
- Files accessed
- Search queries issued

**Usage:**
```python
from src.ingest.transcript_parser import TranscriptParser, AgentToolProfile

parser = TranscriptParser()
metrics = parser.parse_file(Path("data/results/exp001/job001/claude-code.txt"))

print(f"Total calls: {metrics.total_tool_calls}")
print(f"MCP calls: {metrics.mcp_calls}")
print(f"Deep Search calls: {metrics.deep_search_calls}")

profile = AgentToolProfile(metrics)
print(f"Is MCP heavy: {profile.is_mcp_heavy}")
print(f"Deep Search strategy: {profile.is_deep_search_strategic}")
```

**Tool Categories:**
- **MCP**: Sourcegraph integration tools (sg_keyword_search, sg_read_file, etc.)
- **Deep Search**: Sourcegraph Deep Search for semantic code understanding
- **Local**: Shell commands (bash, grep, find, etc.)
- **Other**: Miscellaneous tools

**Metrics:**
- `mcp_vs_local_ratio`: Ratio of MCP calls to local tool calls
  - `< 0.5`: Local-heavy (prefers shell tools)
  - `0.5-2.0`: Balanced
  - `> 2.0`: MCP-heavy (prefers Sourcegraph tools)
- `success_rate`: % of tool calls that succeeded
- `tool_diversity`: How many different tools were used

### 3. MetricsDatabase (`src/ingest/database.py`)

SQLite database for storing and querying metrics.

**Tables:**
- `harbor_results`: Task evaluation results and metrics
- `tool_usage`: Agent tool usage patterns
- `experiment_summary`: Aggregate statistics per experiment

**Usage:**
```python
from pathlib import Path
from src.ingest.database import MetricsDatabase
from src.ingest.harbor_parser import HarborResult

db = MetricsDatabase(Path("data/metrics.db"))

# Store results
db.store_harbor_result(harbor_result, exp_id="exp001", job_id="job001")
db.store_tool_usage(task_id, transcript_metrics, exp_id="exp001", job_id="job001")

# Query results
results = db.get_experiment_results("exp001")
pass_rate = db.get_pass_rate("exp001")
stats = db.get_stats("exp001")

# Print summary stats
print(f"Pass rate: {stats['harbor']['pass_rate']:.1%}")
print(f"Avg MCP calls: {stats['tool_usage']['avg_mcp_calls']:.1f}")
```

**Database Schema:**

**harbor_results:**
```sql
task_id              TEXT PRIMARY KEY
experiment_id        TEXT
job_id               TEXT
task_name            TEXT
task_category        TEXT
task_difficulty      TEXT
agent_name           TEXT
model_name           TEXT
passed               BOOLEAN
exit_code            INTEGER
agent_duration_seconds REAL
verifier_duration_seconds REAL
total_duration_seconds REAL
reward_metrics       JSON  -- All reward metrics
reward_primary       REAL  -- Primary metric (MRR, score, etc.)
evaluated_at         TEXT  -- ISO timestamp
ingested_at          TEXT  -- When ingested into DB
```

**tool_usage:**
```sql
task_id              TEXT PRIMARY KEY
experiment_id        TEXT
job_id               TEXT
total_calls          INTEGER
mcp_calls            INTEGER
deep_search_calls    INTEGER
local_calls          INTEGER
other_calls          INTEGER
tool_calls_by_name   JSON  -- {tool_name: count}
total_input_tokens   INTEGER
total_output_tokens  INTEGER
avg_tokens_per_call  REAL
successful_calls     INTEGER
failed_calls         INTEGER
success_rate         REAL
mcp_vs_local_ratio   REAL
unique_files_accessed INTEGER
search_query_count   INTEGER
transcript_length    INTEGER
ingested_at          TEXT
```

**experiment_summary:**
```sql
experiment_id        TEXT PRIMARY KEY
total_tasks          INTEGER
completed_tasks      INTEGER
passed_tasks         INTEGER
agent_name           TEXT
model_name           TEXT
pass_rate            REAL
avg_duration_seconds REAL
avg_mcp_calls        REAL
avg_deep_search_calls REAL
avg_local_calls      REAL
created_at           TEXT
updated_at           TEXT
```

## CLI Usage

### Ingest All Experiments
```bash
./ccb ingest
```

Processes all experiments in `data/results/` and stores metrics in `data/metrics.db`.

### Ingest Specific Experiment
```bash
./ccb ingest exp001
```

Processes only the specified experiment.

### Verbose Output
```bash
./ccb ingest exp001 --verbose
```

Shows detailed error messages for debugging.

### Expected Output Structure

Results directory structure:
```
data/results/
├── exp001/
│   ├── job001/
│   │   ├── result.json           ← Parsed by HarborResultParser
│   │   ├── claude-code.txt       ← Parsed by TranscriptParser
│   │   ├── logs/
│   │   │   └── verifier/
│   │   │       ├── reward.json
│   │   │       └── reward.txt
│   │   └── *.patch               ← Agent-generated patches
│   └── job002/
│       └── ...
└── exp002/
    └── ...
```

## Metrics and KPIs

### Harbor Metrics
- **Pass Rate**: % of tasks where agent solution passed tests
- **Avg Duration**: Average task execution time
- **Primary Reward**: Main metric from verifier (MRR for IR tasks, etc.)

### Tool Usage Metrics
- **MCP Calls**: Number of Sourcegraph tool invocations
- **Deep Search Calls**: Dedicated Deep Search queries
- **Local Calls**: Shell command executions (grep, bash, etc.)
- **MCP vs Local Ratio**: Preference for MCP vs local tools
- **Success Rate**: % of tool calls that succeeded
- **Tool Diversity**: Number of unique tools used

### Agent Profiles
Three main usage patterns identified:

1. **MCP-Heavy** (ratio > 2.0)
   - Heavily relies on Sourcegraph tools
   - Good for semantic understanding tasks
   - May be overkill for simple file access

2. **Deep Search Strategic** (5-30% of calls)
   - Uses Deep Search at critical checkpoints
   - Balances sophisticated understanding with efficiency
   - Recommended for most coding tasks

3. **Local-Heavy** (ratio < 0.5)
   - Prefers shell commands (grep, find)
   - Lean, fast execution
   - May miss architectural insights

## Integration Points

### With Dashboard
- Dashboard queries `data/metrics.db` for visualization
- Uses `experiment_summary` table for quick stats
- Uses `harbor_results` + `tool_usage` for detailed analysis

### With Config Optimization
- Failure patterns from `harbor_results` inform prompt adjustments
- Tool usage patterns guide MCP endpoint configuration
- Pass rates drive recommendation engine decisions

### With IR-SDLC Integration
- IR metrics (precision@k, recall@k, MRR) stored in `reward_metrics` JSON
- File-level ground truth matches stored for retrieval analysis
- Cross-tool comparison helps evaluate Deep Search value

## Error Handling

The ingestion pipeline gracefully handles:
- Missing `result.json` files (warns but continues)
- Missing `claude-code.txt` transcripts (skips tool analysis)
- Malformed JSON (logs error with context)
- Missing reward metrics (uses None/0 defaults)

Run with `--verbose` to see detailed error traces.

## Performance

- Typical ingestion: ~100 tasks/minute on modern hardware
- Database queries: <100ms for single experiment
- Aggregation queries: <1s for large experiments (1000+ tasks)

## Testing

Run tests for ingestion components:
```bash
pytest tests/test_ingest_harbor_parser.py -v
pytest tests/test_ingest_transcript_parser.py -v
pytest tests/test_ingest_database.py -v
```

## Next Steps (Phase 3)

The analysis layer will build on these metrics:
- **Comparator**: Baseline vs MCP comparison
- **LLM Judge**: Quality evaluation beyond pass/fail
- **Failure Analyzer**: Pattern detection from failures
- **Config Optimizer**: Suggestion engine for improvements
