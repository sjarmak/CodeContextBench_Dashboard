# Observability and Enterprise Metrics Collection

CodeContextBench provides structured observability through **NeMo-Agent-Toolkit integration** and comprehensive enterprise-informed metrics. The system captures per-tool metrics, execution performance, failure patterns, cost analysis, and detailed developer activity patterns (comprehension, navigation, implementation) for downstream benchmarking and optimization.

## Overview

Three main modules provide observability:

1. **NeMoTraceParser** - Parse NeMo-Agent-Toolkit structured execution traces
2. **ManifestWriter** - Writes `run_manifest.json` from Harbor benchmark runs (with NeMo trace support)
3. **MetricsCollector** - Collects and analyzes execution metrics across runs

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
        "avg_duration_sec": 2.5,
        "input_tokens": 1000,
        "output_tokens": 500
      }
    },
    "total_tool_invocations": 5,
    "total_unique_tools": 1,
    "search_queries_count": 5,
    "file_operations_count": 0,
    "total_input_tokens": 12345,
    "total_output_tokens": 4567,
    "total_tokens": 16912
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
    "error_message": null,
    "tokens": {
      "input_tokens": 12345,
      "output_tokens": 4567,
      "total_tokens": 16912
    },
    "cost_usd": 0.087
  },
  "retrieval_metrics": {
    "total_searches": 5,
    "total_file_ops": 0,
    "tools_used": ["sourcegraph_deep_search"],
    "tool_diversity": 1
  }
}
```

## NeMo-Agent-Toolkit Integration

CodeContextBench now integrates with **NeMo-Agent-Toolkit** for structured execution tracing. When NeMo traces are available, the system automatically extracts:

- **Per-tool metrics**: Token counts, latency, success/failure rates for each tool
- **Operation timeline**: Complete execution sequence with timestamps
- **Failure analysis**: Error types, failure modes, tools with highest failure rates
- **Cost breakdown**: Cost per tool for granular cost analysis

### When to Use NeMo Traces

NeMo traces should be used when:
- Running agents built with NeMo-Agent-Toolkit (ReAct, Tool-Calling, ReWOO agents)
- You need detailed per-tool performance metrics
- You want failure analysis at the tool level
- You need accurate token counts per tool call

### Automatic Trace Extraction

```bash
# Extract NeMo traces from Harbor jobs and generate manifests
python runners/extract_nemo_traces.py --jobs-dir jobs/ --agent claude-baseline

# Or process all jobs
python runners/extract_nemo_traces.py --jobs-dir jobs/ --all

# Output JSON summary
python runners/extract_nemo_traces.py --jobs-dir jobs/ --json --output trace_summary.json
```

The runner automatically:
1. Finds all NeMo trace files (`logs/nemo/trace.json`, `logs/trace.json`, etc.)
2. Parses structured tool call data
3. Falls back to Claude log parsing if no traces found
4. Writes `run_manifest.json` with full metrics

### Manual NeMo Trace Processing

```python
from pathlib import Path
from observability import NeMoTraceParser, NeMoMetricsExtractor, ManifestWriter

job_dir = Path('jobs/claude-baseline-10figure-20251217/task-001')

# Extract NeMo trace
trace = NeMoTraceParser.extract_from_task_execution(job_dir)

if trace:
    print(f"Tool calls: {trace.tool_call_count}")
    print(f"Tokens: {trace.total_input_tokens} input, {trace.total_output_tokens} output")
    print(f"Failure rate: {trace.failure_rate:.1f}%")
    
    # Per-tool breakdown
    print(f"Tool call counts: {trace.tool_call_count_by_tool}")
    print(f"Avg latency per tool: {trace.tool_latency_by_tool}")
    print(f"Failures by tool: {trace.failure_rate_by_tool}")
    
    # Write manifest with NeMo metrics
    writer = ManifestWriter(job_dir, model='anthropic/claude-haiku-4-5-20251001')
    manifest_path = writer.write_manifest(
        harness_name='harbor-v1',
        agent_name='claude-baseline',
        benchmark_name='10figure',
        nemo_trace=trace  # Pass NeMo trace for structured metrics
    )
```

### NeMo Trace Structure

```json
{
  "workflow_name": "my_agent",
  "start_time": "2025-12-17T16:00:00.000Z",
  "end_time": "2025-12-17T16:00:15.000Z",
  "duration_sec": 15.0,
  "tool_calls": [
    {
      "tool_name": "sourcegraph_deep_search",
      "invocation_id": "tc_001",
      "duration_sec": 2.5,
      "input_tokens": 1000,
      "output_tokens": 500,
      "success": true,
      "timestamp": "2025-12-17T16:00:01.000Z"
    }
  ],
  "total_input_tokens": 1000,
  "total_output_tokens": 500,
  "success": true
}
```

### NeMo Metrics in Manifests

When written with a NeMo trace, manifests include a `nemo_metrics` section:

```json
{
  "nemo_metrics": {
    "workflow_name": "my_agent",
    "total_duration_sec": 15.0,
    "tool_call_count": 3,
    "failed_tool_calls": 0,
    "failure_rate_percent": 0.0,
    "tool_latency_by_tool": {
      "sourcegraph_deep_search": 2.5,
      "git_operations": 1.5
    },
    "failure_analysis": {
      "total_failures": 0,
      "failure_rate_percent": 0.0,
      "failures_by_type": {},
      "failures_by_tool": {},
      "failure_rate_by_tool": {}
    }
  }
}
```

## Usage

### Writing Manifests with NeMo Traces (Preferred)

After a Harbor benchmark run completes, the observability system automatically extracts token counts from Claude CLI output logs:

```python
from pathlib import Path
from observability import ManifestWriter, ClaudeOutputParser

job_dir = Path('jobs/claude-baseline-10figure-20251217/task-001')

# Initialize writer (specifies model for cost calculation)
writer = ManifestWriter(job_dir, model='anthropic/claude-haiku-4-5-20251001')

# Automatically extract token counts from Claude output logs
# Searches logs/agent/claude.txt and other standard log locations
token_usage = ClaudeOutputParser.extract_from_task_execution(job_dir)

manifest_path = writer.write_manifest(
    harness_name='harbor-v1',
    agent_name='claude-baseline',
    benchmark_name='10figure',
    input_tokens=token_usage.input_tokens,
    output_tokens=token_usage.output_tokens
)

print(f"Manifest written to: {manifest_path}")
print(f"Tokens: {token_usage.input_tokens} input, {token_usage.output_tokens} output")
print(f"Cost: ${writer.calculate_cost(token_usage.input_tokens, token_usage.output_tokens):.6f}")
```

### Token Extraction from Claude CLI Output

The `ClaudeOutputParser` class handles extracting token usage from Claude's JSON output:

```python
from pathlib import Path
from observability import ClaudeOutputParser

task_dir = Path('jobs/claude-baseline-10figure-20251217/task-001')

# Extracts tokens from logs/agent/claude.txt and other log locations
token_usage = ClaudeOutputParser.extract_from_task_execution(task_dir)

print(f"Input tokens: {token_usage.input_tokens}")
print(f"Output tokens: {token_usage.output_tokens}")
print(f"Total tokens: {token_usage.total_tokens}")
print(f"Model: {token_usage.model}")
```

**Token extraction supports multiple formats:**

1. **Claude JSON Output** (preferred):
   ```json
   {
     "usage": {
       "input_tokens": 1234,
       "output_tokens": 567
     },
     "model": "claude-3-5-sonnet-20241022"
   }
   ```

2. **Human-readable text format**:
   ```
   input_tokens: 1234
   output_tokens: 567
   model: claude-3-5-sonnet-20241022
   ```

3. **Key-value format**:
   ```
   input_tokens=1234, output_tokens=567
   ```

#### Log File Locations

ClaudeOutputParser searches these locations in order:
- `logs/agent/claude.txt`
- `logs/agent/stdout.log`
- `logs/agent/output.json`
- `logs/agent.txt`
- `logs/stdout.txt`

### Batch Manifest Collection

The `collect_observability.py` runner automatically collects manifests and extracts tokens:

```bash
# Collect manifests from all job directories
python runners/collect_observability.py collect --jobs-dir jobs/

# Filter by agent
python runners/collect_observability.py collect --jobs-dir jobs/ --agent claude-baseline
```

This will:
1. Scan for all `result.json` files
2. Extract token counts from Claude logs
3. Write `run_manifest.json` with token and cost data
4. Print summary showing tokens and costs for each run

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
- `tokens.input_tokens` - Number of input tokens consumed
- `tokens.output_tokens` - Number of output tokens generated
- `tokens.total_tokens` - Sum of input and output tokens
- `cost_usd` - Calculated cost in USD based on model pricing

### Tool Profile

Aggregated tool usage:

- `tool_usage` - Map of tool name to ToolUsage details (includes per-tool token counts)
- `total_tool_invocations` - Sum of all tool calls
- `total_unique_tools` - Number of distinct tools used
- `search_queries_count` - Count of code search queries
- `file_operations_count` - Count of file operations
- `total_input_tokens` - Aggregate input tokens across all tools
- `total_output_tokens` - Aggregate output tokens across all tools
- `total_tokens` - Sum of input and output tokens

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

## Enterprise Metrics Collection

### Overview

This system implements comprehensive metrics collection based on research from developer activity patterns:
- **58% developer time on comprehension** (vs agent actual)
- **35% on navigation** (vs agent actual)
- **23min context switch recovery**
- Build/test feedback loop impacts
- Navigation efficiency patterns

### Components

#### 1. Metrics Schema (`schemas/enterprise_metrics_schema.json`)

JSON Schema defining the complete metrics structure with 11 main sections:
- `metadata`: Task and run identification
- `execution`: Basic timing and event counts
- `tokens`: Token usage by phase
- `time_allocation`: Comprehension/navigation/implementation %
- `navigation`: File access patterns and efficiency
- `tool_usage`: Tool call patterns including MCP detection
- `build_test`: Build and test cycle tracking
- `comprehension`: Indicators of understanding quality
- `implementation`: Code editing patterns
- `context_switching`: File switching and thrashing detection
- `quality_indicators`: Outcome metrics
- `errors`: Error patterns and resolution

#### 2. Collector Module (`src/metrics/enterprise_collector.py`)

Core `EnterpriseMetricsCollector` class with:
- ✅ Post-hoc trajectory analysis
- ✅ Real-time event processing
- ✅ Automatic phase detection (comprehension/navigation/implementation/testing)
- ✅ MCP tool detection (sg_* tools)
- ✅ Build/test cycle tracking
- ✅ Context switch detection
- ✅ Think time calculation
- ✅ Error categorization

**Phase Detection Logic:**
```python
Read tool → Comprehension (if before first edit) or Navigation (after)
Search/MCP tools → Navigation
Write/Edit tools → Implementation
Bash (test/build) → Testing
Bash (grep/find) → Navigation
Bash (cat/ls) → Comprehension
```

#### 3. CLI Tool (`scripts/collect_metrics.py`)

Command-line interface for metrics collection:

```bash
# Single trajectory
python scripts/collect_metrics.py trajectory.jsonl

# Directory (auto-finds session files)
python scripts/collect_metrics.py jobs/phase3-rerun/

# Compare baseline vs MCP
python scripts/collect_metrics.py \
  baseline.jsonl \
  mcp.jsonl \
  --compare --verbose

# Custom output directory
python scripts/collect_metrics.py trajectory.jsonl --output results/metrics
```

#### 4. Legacy Extraction Script (`scripts/extract_enterprise_metrics.py`)

Original script used for Phase 3 retrospective analysis. **Deprecated** in favor of new collector.

### Enterprise Metrics Usage

#### Post-Hoc Analysis

```python
from src.metrics import EnterpriseMetricsCollector
from pathlib import Path

collector = EnterpriseMetricsCollector()
metrics = collector.process_trajectory(
    Path('trajectory.jsonl'),
    task_metadata={'task_id': 'my-task', 'agent_type': 'baseline'}
)

print(f"Comprehension: {metrics['time_allocation']['comprehension_pct']:.1f}%")
print(f"Gap from research: {metrics['time_allocation']['baseline_comparison']['comprehension_gap']:.1f} points")
```

#### Real-Time Collection

```python
from src.metrics import EnterpriseMetricsCollector

# Initialize
collector = EnterpriseMetricsCollector(
    realtime=True,
    task_metadata={'task_id': 'my-task', 'agent_type': 'mcp'}
)

# Process events as they arrive
for event in agent_event_stream:
    collector.on_event(event)

# Finalize when complete
metrics = collector.finalize()
```

#### Integration with Harbor

**Option 1: Post-Processing (Recommended)**

After running Harbor tasks, collect metrics from generated trajectory files:

```bash
python scripts/collect_metrics.py results/harbor_run_*/*/agent/sessions/**/*.jsonl
```

**Option 2: Real-Time Hook (Future)**

Modify Harbor agent to emit metrics during execution:

```python
# In harbor agent code
from src.metrics import EnterpriseMetricsCollector

class HarborAgent:
    def __init__(self):
        self.metrics_collector = EnterpriseMetricsCollector(realtime=True)

    def on_event(self, event):
        # Normal Harbor processing
        self.process_event(event)

        # Collect metrics
        self.metrics_collector.on_event(event)

    def finalize(self):
        metrics = self.metrics_collector.finalize()
        self.save_metrics(metrics)
```

### Metrics Interpretation

#### Time Allocation

**Research Baseline (Real Developers):**
- 58% Comprehension
- 35% Navigation
- ~7% Implementation

**Typical AI Agent (Observed):**
- 21-41% Comprehension (**17-37 point gap**)
- 13-41% Navigation
- 17-57% Implementation

**What it Means:**
- Large gap → Agent rushing to implementation
- Small gap → Agent more methodical (like humans)
- Negative comprehension gap = insufficient understanding

#### Navigation Efficiency

**Metric:** `file_reads / file_writes`

**Interpretation:**
- **0-0.5**: Very low exploration, jumping straight to edits
- **0.5-1.5**: Balanced, some exploration before changes
- **1.5-3.0**: High exploration, methodical comprehension
- **>3.0**: Possible over-exploration or confusion

**Task-Dependent:**
- Simple tasks: Low navigation OK (0.5-1.0)
- Complex distributed systems: Need high navigation (2.0-3.0)

#### MCP Searches

**Expected:**
- Baseline: 0 (no MCP tools)
- MCP: 10-50+ (depending on task complexity)

**Red Flag:**
- MCP agent with 0 searches → MCP tools not working!

#### Context Switching

**Metrics:**
- `file_switches`: Total switches
- `rapid_switches`: Switches < 30sec apart
- `thrashing_detected`: >5 rapid switches

**Interpretation:**
- High rapid switches → Agent confused, searching without direction
- Thrashing → Red flag for task difficulty or agent capability

#### Build/Test Cycles

**Metric:** `cycles_to_success`

**Research Context:**
- 68% of developers cite slow feedback as burnout factor
- Flaky tests: ~40% false positive rate (PayPal)

**Interpretation:**
- 1-3 cycles: Good comprehension, targeted fix
- 4-10 cycles: Trial-and-error, moderate comprehension
- >10 cycles: Poor comprehension, thrashing

### Example Enterprise Metrics Output

```json
{
  "metadata": {
    "task_id": "big-code-vsc-001",
    "agent_type": "baseline",
    "timestamp": "2025-12-20T18:36:04.366Z",
    "version": "1.0.0"
  },
  "execution": {
    "total_duration": 157.5,
    "total_events": 112
  },
  "tokens": {
    "total": 2043706,
    "total_input": 2043458,
    "total_output": 248
  },
  "time_allocation": {
    "comprehension_pct": 21.7,
    "navigation_pct": 13.3,
    "implementation_pct": 16.7,
    "baseline_comparison": {
      "comprehension_gap": -36.3,
      "navigation_gap": -21.7
    }
  },
  "navigation": {
    "navigation_efficiency": 0.62,
    "file_reads": 5,
    "file_writes": 8,
    "unique_files_read": 5,
    "unique_files_written": 8,
    "reread_ratio": 0.4
  },
  "tool_usage": {
    "tool_calls": {
      "Bash": 63,
      "Read": 5,
      "Write": 8
    },
    "mcp_searches": 0
  },
  "context_switching": {
    "file_switches": 11,
    "rapid_switches": 3,
    "thrashing_detected": false
  }
}
```

### Enterprise Metrics Validation

**Tested on:**
- ✅ Phase 3 baseline trajectories (vsc-001, k8s-001)
- ✅ Phase 3 MCP trajectories (vsc-001, k8s-001)
- ✅ Comparison mode (baseline vs MCP)

**Key Findings:**
- Time allocation gaps validated: -36.3 to -37.6 points
- Navigation efficiency: 0.25-2.38 reads/write
- MCP tool detection: Working (found 0 in Phase 3 = validated absence)

### Enterprise Metrics Troubleshooting

#### "No events processed"
- Check file format: Must be JSONL (one JSON object per line)
- Check for 'timestamp' field in events
- Verify it's a Claude Code trajectory file

#### "MCP searches: 0" when expecting MCP usage
- Verify MCP tools are configured (`sg_*` tools)
- Check tool_timeline in detailed metrics JSON
- Validate Sourcegraph MCP server is running

#### "Time allocation all 0%"
- No tool calls detected
- Check if trajectory file is truncated
- Verify events have 'message' > 'content' > 'tool_use'

#### "baseline_comparison missing"
- Old collector version
- Update to latest: `git pull origin main`
- Re-run collection

## See Also

- **docs/ARCHITECTURE.md** - System architecture
- **docs/ENTERPRISE_CODEBASES.md** - Research foundations
- **docs/EXPERIMENT_PLAN.md** - Experimental design
- **runners/harbor_benchmark.sh** - Benchmark execution
- **runners/aggregator.py** - Cross-benchmark aggregation
- **runners/compare_results.py** - Result comparison
- **schemas/enterprise_metrics_schema.json** - Full schema
