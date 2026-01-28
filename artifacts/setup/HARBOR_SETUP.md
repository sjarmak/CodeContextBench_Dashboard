# Harbor Evaluations Dashboard - Setup & Usage

## What You Have

A **simple, standalone Streamlit dashboard** for running Harbor evaluations with 3 MCP configurations.

**Files:**
- `harbor_dashboard.py` - The app (run this)
- `HARBOR_QUICKSTART.md` - Usage guide
- `TELEMETRY_SCHEMA.md` - Data reference

## Quick Start

```bash
cd CodeContextBench
streamlit run harbor_dashboard.py
```

Opens in browser. That's it.

## Three Agent Configurations

### 🔵 Baseline
No MCP tools. Standard OpenHands.
- Use for: Baseline comparison, cost analysis

### 🟢 Sourcegraph MCP
Code search, navigation, git history.
- Use for: Bug triage, code understanding

### 🟣 Deep Search MCP
Semantic code analysis and reasoning.
- Use for: Complex reasoning, architecture analysis

## How to Use

1. **Sidebar**: Select agent, model, dataset
2. **▶️ Run Tab**: Click START to run evaluation
3. **📊 Results Tab**: View completed evaluation metrics
4. **📈 Compare Tab**: Compare across multiple runs

## Metrics Captured

Per trial:
- ✅ Reward (0=fail, 1=pass)
- 🪙 Cost in USD
- 📊 Token usage (input+output)
- ⏱️ Execution time

All automatically saved and viewable in Results tab.

## Data Location

```
harbor_jobs/
└── jobs/
    └── <timestamp>/
        ├── result.json              # Aggregate results
        └── <task_id>/
            ├── result.json          # Trial result
            ├── agent/
            │   ├── trajectory.json  # Step-by-step
            │   └── openhands.txt    # Agent logs
            └── verifier/
                └── ...
```

## Example Runs

### Test Setup (1 minute)
```
Agent: Baseline
Model: Haiku
Dataset: Hello World
→ Verifies everything works
```

### SWE-Bench Comparison (30 minutes)
```
Agent: Baseline → Sourcegraph MCP
Model: Sonnet
Dataset: SWE-Bench Verified
Filter: *python*
→ Compare tool impact
```

### Cost Analysis (20 minutes)
```
Agent: Sourcegraph MCP
Model: Haiku → Sonnet → Opus
Dataset: Hello World
→ See cost vs capability tradeoff
```

## Troubleshooting

**Dashboard won't start:**
```bash
pip install streamlit pandas
```

**Missing credentials error:**
Add to `.env.local`:
```
ANTHROPIC_API_KEY=sk-ant-...
SOURCEGRAPH_URL=https://sourcegraph.sourcegraph.com
SOURCEGRAPH_ACCESS_TOKEN=sgp_...
```

**Evaluation fails immediately:**
Check `harbor_jobs/jobs/<id>/<task>/agent/openhands.txt`

## Next Steps

1. Run hello-world test
2. Check Results tab
3. Compare different agents on same benchmark
4. Analyze cost vs performance

See `HARBOR_QUICKSTART.md` for detailed workflows.
