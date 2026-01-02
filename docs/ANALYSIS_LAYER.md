# Phase 3: Analysis Layer - Complete Implementation

The analysis layer provides comprehensive evaluation, comparison, and optimization tools for CodeContextBench. It analyzes ingested metrics from `data/metrics.db` to drive continuous improvement of agent configurations.

## Architecture Overview

```
Ingested Metrics (data/metrics.db)
  ↓
  ├─→ ExperimentComparator (Agent vs Agent comparison)
  ├─→ IRAnalyzer (Retrieval quality analysis)
  ├─→ FailureAnalyzer (Failure pattern detection)
  └─→ RecommendationEngine (Generate improvement suggestions)
  
  ↓
Output Artifacts (data/artifacts/)
  ├─ comparison_<exp_id>.json
  ├─ failures_<exp_id>_<agent>.json
  ├─ ir_analysis_<exp_id>.json
  └─ recommendations_<exp_id>_<agent>.json
```

## Components

### 1. ExperimentComparator

Compares agent performance across experiments.

**Purpose**: Measure if MCP tools improve agent performance and by how much.

**Key Classes**:
- `AgentMetrics`: Aggregated metrics for a single agent (pass rate, duration, tool usage, rewards)
- `ComparisonDelta`: Differences between two agents
- `ComparisonResult`: Complete comparison with metrics and deltas

**Capabilities**:
- Compares multiple agents in an experiment
- Computes pass rate deltas, duration deltas, tool usage deltas
- Interprets impact of MCP usage
- Assesses efficiency improvements/degradations

**Example Usage**:
```python
from src.ingest.database import MetricsDatabase
from src.analysis.comparator import ExperimentComparator

db = MetricsDatabase(Path("data/metrics.db"))
comparator = ExperimentComparator(db)

result = comparator.compare_experiment(
    "exp001",
    baseline_agent="baseline"
)

print(f"Best agent: {result.best_agent}")
print(f"Pass rate delta: {result.deltas['baseline__variant'].pass_rate_delta:+.1%}")
```

### 2. IRAnalyzer

Analyzes information retrieval metrics for IR-SDLC benchmarks.

**Purpose**: Evaluate how well agents retrieve relevant code for understanding tasks.

**Key Classes**:
- `IRMetricsAggregate`: Aggregated IR metrics (precision, recall, MRR, NDCG)
- `IRDelta`: IR metric differences between agents
- `IRAnalysisResult`: Complete IR analysis with rankings

**Metrics Analyzed**:
- Precision@1, @5, @10, @20
- Recall@1, @5, @10, @20
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- File-level recall
- Cross-module coverage
- Context efficiency

**Example Usage**:
```python
from src.analysis.ir_analyzer import IRAnalyzer

analyzer = IRAnalyzer(db)
result = analyzer.analyze_experiment("exp001")

print(f"MRR improvement: {result.deltas['baseline__variant'].mrr_delta:+.3f}")
print(f"Best recall agent: {result.best_recall_agent}")
```

### 3. FailureAnalyzer

Detects patterns in task failures to identify root causes.

**Purpose**: Identify systematic issues in agent behavior.

**Key Classes**:
- `FailurePattern`: A detected failure pattern with affected tasks and suggestions
- `FailureAnalysisResult`: Complete failure analysis with patterns and insights

**Detected Patterns**:
1. **High-Difficulty Failures**: Agent struggles with harder tasks
2. **Category-Specific Failures**: Agent fails predominantly on certain task types
3. **Duration-Related Failures**: Agent times out or exceeds limits
4. **Low-Quality Solutions**: Agent produces low-reward solutions

**Example Usage**:
```python
from src.analysis.failure_analyzer import FailureAnalyzer

analyzer = FailureAnalyzer(db)
result = analyzer.analyze_failures("exp001", agent_name="variant")

for pattern in result.patterns:
    print(f"{pattern.pattern_name}: {pattern.frequency} failures")
    print(f"  Recommendation: {pattern.suggested_fix}")
```

### 4. RecommendationEngine

Synthesizes analysis results into actionable recommendations.

**Purpose**: Suggest concrete configuration changes to improve performance.

**Key Classes**:
- `Recommendation`: A single actionable suggestion
- `RecommendationPlan`: Prioritized set of recommendations

**Recommendation Categories**:
- **Prompting**: System prompt improvements, task understanding
- **Tools**: MCP configuration, Deep Search usage patterns
- **Config**: Model parameters, execution settings
- **Experiment**: Benchmark selection, task difficulty

**Priority Levels**:
- **High**: Large impact + Easy to implement (Quick Wins)
- **Medium**: Medium impact, medium effort
- **Low**: Small impact or high effort

**Example Usage**:
```python
from src.analysis.recommendation_engine import RecommendationEngine

engine = RecommendationEngine()
plan = engine.generate_plan(
    "exp001",
    "variant",
    comparison_result=comparison,
    failure_analysis=failures,
)

for rec in plan.quick_wins:
    print(f"✓ {rec.title}")
    print(f"  Implementation: {rec.implementation_details}")
```

## CLI Commands

### Compare Agents
```bash
ccb analyze compare exp001 [--baseline baseline_agent] [-v]
```

Compare all agents in an experiment against a baseline.

**Output**:
- Pass rates and pass rate deltas
- Execution durations
- Tool usage breakdown
- Detailed JSON results

### Analyze Failures
```bash
ccb analyze failures exp001 [--agent agent_name] [-v]
```

Detect failure patterns and root causes.

**Output**:
- Failure rate statistics
- Detected patterns with affected tasks
- Top failing categories and difficulties
- Recommendations per pattern

### Analyze IR Metrics
```bash
ccb analyze ir exp001 [--baseline baseline_agent] [-v]
```

Evaluate information retrieval metrics for IR-SDLC benchmarks.

**Output**:
- MRR, Precision, Recall, NDCG by agent
- File-level and module-level metrics
- Context efficiency analysis
- Best agents by metric

### Generate Recommendations
```bash
ccb analyze recommend exp001 --agent agent_name [-v]
```

Generate improvement recommendations based on all analyses.

**Output**:
- Quick wins (high impact, low effort)
- High-priority issues
- Medium/low priority improvements
- Implementation details and config changes

## Data Flow

```
Harbor Result → Parse result.json → Extract metrics
                   ↓
Agent Transcript → Parse claude-code.txt → Extract tool usage
                   ↓
            Store in metrics.db
                   ↓
         ┌─────────┼─────────┬─────────┐
         ↓         ↓         ↓         ↓
      Compare   Failures    IR     Recommend
      agents    patterns  metrics    changes
         ↓         ↓         ↓         ↓
         └─────────┴─────────┴─────────┘
                   ↓
         Generate artifacts (JSON)
                   ↓
       Feed back into config optimization
```

## Analysis Workflow

### 1. Run Experiment
```bash
# On VM
harbor run --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

### 2. Pull Results
```bash
ccb sync pull --experiment exp001
```

### 3. Ingest Metrics
```bash
ccb ingest exp001
```

### 4. Run Analysis
```bash
# Compare agents
ccb analyze compare exp001 --baseline baseline

# Check failures
ccb analyze failures exp001 --agent variant

# Analyze IR quality
ccb analyze ir exp001

# Get recommendations
ccb analyze recommend exp001 --agent variant
```

### 5. Apply Recommendations
Update `configs/agents/` with suggested changes and repeat.

## Key Insights

### MCP Impact Measurement

The comparator measures MCP value through:
- **Pass rate delta**: Do more MCP calls improve success?
- **Duration delta**: Is there a time cost to MCP usage?
- **Tool ratio delta**: How much are MCP calls increasing?
- **Efficiency impact**: Are gains worth the time cost?

### Failure Patterns

The failure analyzer categorizes failures into:
- **Capability gaps**: Agent lacks skills (hard problems)
- **Strategy errors**: Wrong approach taken
- **Tool misuse**: Inefficient tool selection
- **Implementation issues**: Code quality problems

### IR Quality Analysis

For retrieval-based tasks, IR analyzer measures:
- **Recall**: Are correct files found?
- **Precision**: Are irrelevant files filtered?
- **Efficiency**: Is context window used effectively?
- **Module coverage**: Are cross-module dependencies discovered?

## Integration Points

### With Dashboard
- Comparison results feed into agent performance charts
- Failure patterns appear in issue summary
- IR metrics shown in retrieval quality section
- Recommendations surfaced in improvement suggestions

### With Recommendation Engine
- Failure patterns → prompting recommendations
- Comparison deltas → tool usage recommendations
- IR analysis → search strategy recommendations
- All combined → prioritized action plan

### With Config Optimization
- Recommendations directly translate to YAML config changes
- Quick wins prioritized for immediate experimentation
- High-priority issues inform design decisions
- Historical patterns prevent regressions

## Testing

All analysis components include comprehensive tests:

```bash
pytest tests/test_analysis_comparator.py -v
pytest tests/test_analysis_failure_analyzer.py -v
pytest tests/test_analysis_ir_analyzer.py -v
pytest tests/test_analysis_recommendation_engine.py -v
```

Test coverage includes:
- Basic functionality (parsing, aggregation)
- Edge cases (empty results, single agent, no rewards)
- Data integrity (serialization, round-trips)
- Business logic (interpretation, recommendations)

## Performance

- Single experiment comparison: < 500ms
- Failure pattern detection: < 1s
- IR metrics analysis: < 500ms
- Recommendation generation: < 2s
- Database queries: < 100ms

## Phase 4.2: Time-Series Analysis (Complete)

### TimeSeriesAnalyzer Component

Provides trend detection and metric tracking across experiment iterations.

**Purpose**: Track how metrics improve/degrade over experiment iterations to validate optimization efforts.

**Key Features**:
- Linear regression trend detection with confidence scoring
- Multi-agent comparison over time
- Automatic anomaly detection (z-score method)
- Direction classification (improving, degrading, stable)
- Serializable results for JSON export

**Usage**:
```python
analyzer = TimeSeriesAnalyzer(db)
result = analyzer.analyze_multi_agent_trends(
    ["exp001", "exp002", "exp003"],
    agent_names=["baseline", "variant"],
)

for metric, trends in result.trends.items():
    for agent, trend in trends.items():
        print(f"{agent}: {trend.direction.value} ({trend.confidence:.0%})")
```

**CLI Command**:
```bash
ccb analyze timeseries exp001,exp002,exp003 [--agents baseline,variant] [-v]
```

**Test Coverage**:
- 14 test cases covering all components
- Scenarios: improving, degrading, stable trends
- Anomaly detection, multi-agent analysis
- Serialization/deserialization

---

## Phase 4.1: Statistical Testing (Complete)

### StatisticalAnalyzer Component

Provides rigorous statistical significance testing for experiment comparisons.

**Purpose**: Distinguish real performance differences from random variation.

**Key Features**:
- **T-tests**: For continuous metrics (duration, rewards)
- **Chi-square tests**: For categorical metrics (pass/fail)
- **Mann-Whitney U test**: For non-normal distributions
- **Effect size computation**: Cohen's d, Cramér's V, rank-biserial correlation
- **Power assessment**: Evaluates statistical reliability (underpowered, adequate, well-powered)
- **P-value interpretation**: Human-readable significance assessment

**Usage**:
```python
analyzer = StatisticalAnalyzer(db)
result = analyzer.analyze_comparison(
    "exp001",
    baseline_agent="baseline",
    confidence_level=0.95,
)

for metric in result.significant_metrics:
    tests = result.tests[metric]
    for test in tests:
        print(f"{test.metric_name}: {test.interpretation}")
```

**CLI Command**:
```bash
ccb analyze statistical <exp_id> [--baseline agent] [--confidence 0.95] [-v]
```

### Test Coverage
- 15 comprehensive tests covering all statistical tests
- Realistic scenarios with significant and non-significant differences
- Effect size validation
- Power assessment accuracy

## Future Enhancements

### Phase 4.5 (Planned)
- Time-series analysis (improvement tracking)
- Cost analysis (API spending, resource usage)

### Phase 5 (Planned)
- Automated config generation
- A/B testing framework
- Multi-experiment meta-analysis
- Regression detection

## Troubleshooting

### "No results found for experiment"
- Ensure experiment was ingested: `ccb ingest exp001`
- Check database exists: `ls -la data/metrics.db`

### Missing IR metrics
- IR analyzer requires reward metrics in harbor results
- Some benchmarks may not have IR-specific metrics
- Fall back to basic comparison if IR data unavailable

### Inconsistent recommendations
- Recommendations based on statistical patterns
- Small sample sizes (< 5 tasks) produce unreliable patterns
- Run larger experiments (10+ tasks) for confidence

## See Also

- `docs/INGESTION_PIPELINE.md` - Data collection
- `docs/REFACTOR_PROPOSAL.md` - Architecture overview
- `AGENTS.md` - CLI command reference
