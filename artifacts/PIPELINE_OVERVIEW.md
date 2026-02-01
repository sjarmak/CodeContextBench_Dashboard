# CodeContextBench Pipeline Overview

CodeContextBench is an observability platform that measures whether MCP (Model Context Protocol) tools improve AI coding agent performance on software engineering tasks.

## Pipeline Flow

```
Benchmarks + Agents → Harbor Execution → Result Parsing → Metrics DB → Analysis → Insights
```

### 1. Execution Layer

**Harbor** runs agent variants against benchmark tasks in isolated containers:
- Tasks come from benchmark suites (SWE-bench, BigCode, custom)
- Agents use different MCP configurations (baseline, strategic deep search, full toolkit)
- Produces `result.json` (pass/fail, rewards) and `claude-code.txt` (tool usage transcript)

### 2. Ingestion Layer

**Parsers** extract structured metrics from raw outputs:
- `HarborResultParser`: Task metadata, pass/fail status, duration, rewards
- `TranscriptParser`: Tool calls, token counts, MCP usage patterns

**MetricsDatabase** (SQLite) stores everything in three tables:
- `harbor_results`: Task outcomes, agent info, timing
- `tool_usage`: Per-task tool calls, tokens, success rates
- `experiment_summary`: Aggregated experiment statistics

### 3. Analysis Layer

Six analyzers query the database to produce insights:

| Analyzer | Purpose | Key Output |
|----------|---------|------------|
| **ExperimentComparator** | Agent vs agent comparison | Pass rate deltas, best/worst agent |
| **IRAnalyzer** | Retrieval quality (for IR benchmarks) | MRR, precision, recall, NDCG |
| **FailureAnalyzer** | Failure pattern detection | Root causes, category-specific issues |
| **StatisticalAnalyzer** | Significance testing | P-values, effect sizes, power assessment |
| **TimeSeriesAnalyzer** | Trend detection across experiments | Improving/degrading/stable trends |
| **CostAnalyzer** | API spending and efficiency | Cost per task, cost per success, regressions |

**RecommendationEngine** synthesizes findings into prioritized action items.

### 4. Output Layer

**CLI Commands** (`ccb analyze <type>`) produce:
- Formatted terminal output with key metrics
- JSON artifacts in `artifacts/` for integration
- Rankings, deltas, and interpretations

## Key Metrics

| Category | Metrics |
|----------|---------|
| Performance | Pass rate, duration, reward scores |
| Tool Usage | MCP calls, Deep Search calls, local calls, MCP/local ratio |
| Cost | Tokens, USD cost, cost per success, efficiency score |
| Quality | Precision, recall, MRR, NDCG (for IR tasks) |

## Typical Workflow

```bash
# 1. Run experiment on VM
harbor run --path benchmarks/big_code_mcp/task-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent

# 2. Pull results
ccb sync pull --experiment exp001

# 3. Ingest to database
ccb ingest exp001

# 4. Analyze
ccb analyze compare exp001 --baseline baseline
ccb analyze cost exp001
ccb analyze statistical exp001
ccb analyze timeseries exp001,exp002,exp003
ccb analyze recommend exp001 --agent variant
```

## Design Principles

1. **Query-based aggregation**: All metrics computed from database queries
2. **Serializable results**: Every analyzer returns dataclasses with `to_dict()` for JSON export
3. **Interpretation layer**: Raw statistics paired with human-readable insights
4. **Confidence tracking**: P-values, R², and thresholds throughout
5. **Regression detection**: Automatic flagging of performance or cost degradation
