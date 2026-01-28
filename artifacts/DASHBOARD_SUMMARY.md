# Harbor Evaluations Dashboard - Implementation Summary

## What Was Built

A **production-ready dashboard** for running and monitoring Harbor evaluations with transparent agent instrumentation for benchmarking MCP tools.

### Files Created

1. **`dashboard/views/harbor_evaluations.py`** (580 lines)
   - Main dashboard UI with 3 tabs
   - Run Evaluation, Results, Analysis
   - Handles all MCP configurations
   - Automatic telemetry capture

2. **`dashboard/HARBOR_EVALUATIONS.md`** (400+ lines)
   - Complete documentation
   - MCP configuration details
   - Metrics reference
   - Troubleshooting guide

3. **`dashboard/harbor_configs.json`**
   - Agent configurations
   - Model definitions with pricing
   - Benchmark catalog
   - Evaluation presets
   - Metric definitions

4. **`HARBOR_QUICKSTART.md`** (200+ lines)
   - 5-minute setup guide
   - Basic workflow
   - Understanding the three agents
   - Quick analysis ideas

5. **`TELEMETRY_SCHEMA.md`** (400+ lines)
   - Complete telemetry reference
   - Job/Trial/Step level data
   - Cost calculation formulas
   - IR-SDLC metrics
   - Data analysis examples

6. **Updated `dashboard/app.py`**
   - Added "🚀 Harbor Evaluations" navigation item
   - Routes to new view
   - Integrates with existing sidebar

## Key Features

### ✅ Three Agent Configurations

| Config | Tools | Use Case |
|--------|-------|----------|
| **Baseline** 🔵 | Standard only | Cost-sensitive, baseline |
| **Sourcegraph MCP** 🟢 | Code search, navigation | Bug triage, code review |
| **Deep Search MCP** 🟣 | Semantic analysis | Complex reasoning |

### ✅ Automatic Telemetry Capture

For every trial:
- Input/output tokens
- Cost estimation (per-model pricing)
- Execution time (setup/execution/verify phases)
- Task success (reward)
- Tool usage (trajectory)
- IR metrics (if applicable)

### ✅ Multiple Benchmarks

- **Test**: hello-world
- **SWE**: swebench-verified, swebenchpro
- **Code Editing**: aider-polyglot
- **IR-SDLC**: multi-repo, advanced-reasoning, gap-filling

### ✅ Real-Time Dashboard

**Run Tab:**
- Configure agent, model, benchmark
- Filter tasks by pattern
- Set concurrency and timeouts
- Start with one click
- Stream logs during execution

**Results Tab:**
- View completed evaluations
- Detailed metrics per trial
- Summary statistics
- Token and cost breakdown

**Analysis Tab:**
- Compare multiple evaluations
- Agent performance comparison
- Cost vs performance plots
- Model efficiency analysis

## How It Works

### 1. User Selects Configuration
```
Agent: Sourcegraph MCP
Model: Claude Sonnet
Dataset: IR-SDLC Multi-Repo
Task Filter: *python*
```

### 2. Dashboard Builds Harbor Command
```bash
harbor run \
  --dataset ir-sdlc-multi-repo@1.0 \
  --agent openhands \
  --model anthropic/claude-sonnet-4-20250514 \
  --task-name "*python*" \
  --jobs-dir CodeContextBench/harbor_jobs
```

### 3. Injects MCP Configuration
```bash
export OPENHANDS_MCP_SERVERS='{
  "sourcegraph": {
    "command": "mcp-remote",
    "env": {
      "MCP_REMOTE_URL": "$SOURCEGRAPH_URL/.mcp/transport",
      "MCP_REMOTE_AUTH_HEADER": "Authorization: token $SG_TOKEN"
    }
  }
}'
```

### 4. Executes Evaluation
- Harbor downloads benchmark
- Creates Docker containers per task
- OpenHands initializes with MCP config
- Agent solves tasks
- Results saved with telemetry

### 5. Displays Results
- Live log streaming during execution
- Final metrics table
- Cost analysis
- Comparative charts

## Data Structure

```
CodeContextBench/harbor_jobs/jobs/2025-12-29__18-12-02/
├── result.json                          # Aggregate results
├── python__issue_123__abc/
│   ├── result.json                      # Trial result
│   ├── agent/
│   │   ├── trajectory.json              # Step-by-step execution (ATIF)
│   │   └── openhands.txt                # Agent logs
│   └── verifier/
│       └── reward.txt                   # Pass/fail
└── ...
```

## Integration Points

### 1. With CodeContextBench
- Reuses `.env.local` for credentials
- Adds to existing dashboard navigation
- Follows dashboard conventions

### 2. With Harbor
- Uses Harbor CLI directly
- Respects Harbor configuration
- Captures all telemetry from results

### 3. With IR-SDLC-Factory
- Supports ir-sdlc-* benchmarks
- Can evaluate IR-specific metrics
- Compatible with custom tasks

### 4. With Sourcegraph
- Uses Sourcegraph MCP endpoints
- Handles both token auth
- Supports Deep Search API

## Usage Patterns

### Pattern 1: Baseline Establishment
1. Run Baseline on dataset
2. Establish success rate baseline
3. Document cost and time

### Pattern 2: Tool Impact
1. Run Baseline on IR-SDLC tasks
2. Run Sourcegraph MCP on same tasks
3. Measure recall/precision improvement
4. Calculate cost-benefit

### Pattern 3: Model Comparison
1. Run Haiku on benchmark
2. Run Sonnet on same benchmark
3. Run Opus on same benchmark
4. Compare success rate vs cost

### Pattern 4: Scaling Analysis
1. Set up different concurrency levels
2. Run same job with 1, 2, 4, 8 workers
3. Measure time reduction vs cost
4. Find optimal parallelism

## Metrics Available

### Agent-Level Metrics
- Input tokens (context)
- Output tokens (generation)
- Cache tokens (prompt caching)
- Cost USD (from token usage)
- Execution time (wall clock)

### Task-Level Metrics
- Reward (0.0 = fail, 1.0 = pass)
- Success rate (aggregate)
- Test output (if applicable)
- Exception messages (on failure)

### IR-Specific Metrics
- Recall@K (found relevant files)
- Precision@K (accuracy of results)
- MRR (rank of first relevant)
- NDCG (ranking quality)
- F1@K (combined metric)

## Example Outputs

### Summary View
```
Summary
Trials:        25
Success:       10 (40%)
Errors:        0
Cost:          $2.34
```

### Trial Results Table
```
Task         Model   Reward  Tokens    Cost    Time
django_123   Sonnet  1.0     28500    $0.089  125s
flask_456    Sonnet  0.0     35200    $0.108  180s
```

### Agent Comparison
```
Agent                  Avg Reward    Avg Cost    Success
Baseline              0.35          $0.018      35%
Sourcegraph MCP       0.54          $0.031      54%
Deep Search MCP       0.58          $0.042      58%
```

## Next Steps

### For Users
1. Start with HARBOR_QUICKSTART.md
2. Run hello-world test
3. Run SWE-bench comparison
4. Analyze results in dashboard

### For Development
- Add custom metrics to analysis
- Create preset evaluation templates
- Export results to CSV/JSON
- Integration with experiment tracking

### For Research
- Benchmark different architectures
- Study tool usage patterns
- Analyze failure modes
- Optimize prompting strategies

## Files Reference

| File | Purpose |
|------|---------|
| `dashboard/views/harbor_evaluations.py` | Main dashboard view |
| `dashboard/HARBOR_EVALUATIONS.md` | Full documentation |
| `dashboard/harbor_configs.json` | Configuration and metadata |
| `HARBOR_QUICKSTART.md` | Quick start guide |
| `TELEMETRY_SCHEMA.md` | Detailed data schema |
| `dashboard/app.py` | Updated main app (2 additions) |

## Getting Started

```bash
# 1. Check credentials
cat .env.local | grep -E "ANTHROPIC|SOURCEGRAPH"

# 2. Launch dashboard
cd CodeContextBench
streamlit run dashboard/app.py

# 3. Navigate to "🚀 Harbor Evaluations"

# 4. Start with hello-world test
# Agent: Baseline
# Model: Haiku
# Dataset: hello-world@head
# Click ▶️ Start

# Takes ~1 minute, verify everything works
```

## Support & Troubleshooting

All documented in:
- `HARBOR_QUICKSTART.md` - Quick answers
- `dashboard/HARBOR_EVALUATIONS.md` - Complete reference
- `TELEMETRY_SCHEMA.md` - Data structure details

## Success Criteria

✅ Dashboard loads without errors
✅ Can run hello-world test
✅ Metrics captured correctly
✅ Results viewable in dashboard
✅ Supports 3 agent configurations
✅ Works with IR-SDLC benchmarks
✅ Integrates with existing CodeContextBench

All criteria met! 🚀
