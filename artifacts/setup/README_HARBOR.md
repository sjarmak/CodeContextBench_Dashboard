# 🚀 Harbor Evaluations Dashboard

Standalone, simple Streamlit app for benchmarking OpenHands with different MCP configurations.

## Launch

```bash
cd CodeContextBench
streamlit run harbor_dashboard.py
```

## What It Does

Run Harbor evaluations with:
- **3 Agent Configurations**: Baseline, Sourcegraph MCP, Deep Search MCP
- **Multiple Models**: Haiku, Sonnet, Opus
- **Multiple Benchmarks**: SWE-bench, IR-SDLC, Aider, etc.
- **Automatic Telemetry**: Tokens, cost, time, success rate

## Structure

```
┌─────────────────────────────────────────┐
│  🚀 Harbor Evaluations Dashboard        │
├─────────────────────────────────────────┤
│                                         │
│  SIDEBAR: Configure                     │
│  • Agent (Baseline/SG/DS)               │
│  • Model (Haiku/Sonnet/Opus)            │
│  • Dataset (SWE-bench, IR-SDLC, etc)    │
│  • Advanced: filter, concurrency, etc   │
│                                         │
│  TABS:                                  │
│  ▶️  Run      → Execute evaluations     │
│  📊 Results  → View metrics             │
│  📈 Compare  → Cross-eval analysis      │
│                                         │
└─────────────────────────────────────────┘
```

## Quick Start

1. **Setup credentials** (`.env.local`):
   ```
   ANTHROPIC_API_KEY=...
   SOURCEGRAPH_URL=...
   SOURCEGRAPH_ACCESS_TOKEN=...
   ```

2. **Launch dashboard**:
   ```bash
   streamlit run harbor_dashboard.py
   ```

3. **Run a test**:
   - Baseline + Haiku + Hello World
   - Click START
   - Watch logs in real-time
   - View results in Results tab

## Files

| File | Purpose |
|------|---------|
| `harbor_dashboard.py` | Main app (380 lines) |
| `HARBOR_SETUP.md` | 2-minute setup guide |
| `HARBOR_QUICKSTART.md` | Detailed workflows |
| `TELEMETRY_SCHEMA.md` | Data reference |

## Key Features

✅ **Three MCP Configurations**
- 🔵 Baseline (no MCP)
- 🟢 Sourcegraph MCP (code search/navigation)
- 🟣 Deep Search MCP (semantic analysis)

✅ **Automatic Metrics**
- Reward (pass/fail)
- Cost (USD)
- Tokens (input+output)
- Time (execution)

✅ **Simple Workflow**
- Configure in sidebar
- Click START
- View results
- Compare across runs

✅ **Multiple Benchmarks**
- SWE-Bench Verified/Pro
- Aider Polyglot
- IR-SDLC (Multi-repo, Advanced, Gap-filling)
- Hello World (test)

## Example Workflows

### Baseline (5 min)
```
Baseline + Haiku + Hello World
→ Verify setup works
```

### Compare Agents (30 min)
```
Run: SWE-Bench + Python tasks
- Baseline
- Sourcegraph MCP
- Deep Search MCP
→ Measure MCP value
```

### Cost Analysis (20 min)
```
Run: Hello World with each model
- Haiku
- Sonnet
- Opus
→ Find cost/capability tradeoff
```

## Data

Results stored in `harbor_jobs/jobs/<timestamp>/`:
- Job aggregate results
- Per-trial metrics (tokens, cost, reward)
- Agent trajectories (step-by-step execution)
- Verification logs

All viewable in Results tab.

## Support

- **Setup issues**: See `HARBOR_SETUP.md`
- **How to use**: See `HARBOR_QUICKSTART.md`
- **Data schema**: See `TELEMETRY_SCHEMA.md`
- **Agent logs**: Check `harbor_jobs/jobs/<id>/<task>/agent/openhands.txt`

## That's It!

No complex integrations, no frankenstein code. Just:
1. `streamlit run harbor_dashboard.py`
2. Configure in sidebar
3. Click START
4. View results

Everything is self-contained and simple.
