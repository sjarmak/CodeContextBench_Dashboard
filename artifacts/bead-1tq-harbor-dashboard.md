# Bead CodeContextBench-1tq: Harbor Dashboard

**Status:** ✅ CLOSED  
**Priority:** P0  
**Type:** Task  
**Created:** 2025-12-29 18:42 UTC  
**Duration:** 2 hours  

## Summary

Successfully created a **clean, standalone Streamlit dashboard** for running and monitoring Harbor evaluations with different MCP configurations.

## What Was Built

### Main Application
- **File:** `harbor_dashboard.py` (380 lines)
- **Launch:** `streamlit run harbor_dashboard.py`
- **Framework:** Streamlit (simple, no complex integrations)

### Key Features

#### 1. Three Agent Configurations
- 🔵 **Baseline** - OpenHands without MCP (baseline for comparison)
- 🟢 **Sourcegraph MCP** - Code search, navigation, git history
- 🟣 **Deep Search MCP** - Semantic code analysis and reasoning

#### 2. Configuration Options
- **Models:** Haiku, Sonnet, Opus (with pricing info)
- **Datasets:** SWE-bench, IR-SDLC, Aider, Hello World
- **Advanced:** Task filtering, concurrency, timeout multiplier, retry attempts

#### 3. Three Main Tabs

**▶️ Run Tab**
- Configure agent, model, dataset in sidebar
- Real-time log streaming during execution
- One-click START button
- Automatic MCP configuration injection

**📊 Results Tab**
- View completed evaluations
- Detailed metrics per trial:
  - Reward (✅ pass / ❌ fail)
  - Token count (input+output)
  - Cost estimation in USD
  - Execution time
- Summary statistics (pass rate, total cost, avg time)

**📈 Compare Tab**
- Cross-evaluation analysis
- Agent comparison tables
- Model performance comparison
- Success rate analysis

#### 4. Automatic Telemetry Capture

Per trial:
- ✅ Task reward (0.0=fail, 1.0=pass)
- 🪙 Cost in USD (calculated from token usage)
- 📊 Token usage (input tokens + output tokens)
- ⏱️ Execution time (wall clock)
- 🛠️ Tool usage (via trajectory)

All data automatically captured and displayed.

### Documentation

| File | Purpose | Lines |
|------|---------|-------|
| `README_HARBOR.md` | Overview and quick reference | 100 |
| `HARBOR_SETUP.md` | 2-minute setup guide | 80 |
| `HARBOR_QUICKSTART.md` | Detailed usage workflows | 200 |
| `TELEMETRY_SCHEMA.md` | Complete data schema reference | 400 |

## Design Decisions

### ✅ What We Did Right

1. **Standalone App** - Not integrated with broken old dashboard
2. **Simple Codebase** - 380 lines, easy to maintain
3. **Clean Workflow** - Sidebar config → Click START → View results
4. **Automatic MCP** - Handles credential injection seamlessly
5. **Real Metrics** - Captures actual token/cost data from Harbor
6. **Multiple Benchmarks** - Supports SWE-bench, IR-SDLC, and more

### ❌ What We Avoided

- ❌ Integration with existing complex dashboard
- ❌ Custom state management (let Streamlit handle it)
- ❌ Pre-made evaluation templates (user configures instead)
- ❌ Database complexity (just read JSON files)

## Usage Examples

### Verify Setup (1 min)
```bash
streamlit run harbor_dashboard.py
# Sidebar: Baseline + Haiku + Hello World
# Click START
# Check Results tab
```

### Compare Agents (30 min)
```
Run 1: Baseline + Sonnet + SWE-bench (*python*)
Run 2: Sourcegraph MCP + Sonnet + SWE-bench (*python*)
Run 3: Deep Search MCP + Sonnet + SWE-bench (*python*)
→ Compare results in Compare tab
```

### Cost Analysis (20 min)
```
Run: Hello World with each model
- Haiku: $0.004
- Sonnet: $0.012
- Opus: $0.045
→ Find cost/capability tradeoff
```

## Data Flow

```
User Configuration (Sidebar)
        ↓
MCP Config Injection
        ↓
Harbor CLI Execution
        ↓
Result JSON Files
        ↓
Streamlit Display
```

## File Structure

```
CodeContextBench/
├── harbor_dashboard.py              # Main app
├── README_HARBOR.md                 # Overview
├── HARBOR_SETUP.md                  # Setup guide
├── HARBOR_QUICKSTART.md             # Workflows
├── TELEMETRY_SCHEMA.md              # Data reference
└── harbor_jobs/                     # Results (auto-created)
    └── jobs/
        └── <timestamp>/
            ├── result.json
            └── <task_id>/
                ├── result.json
                ├── agent/
                │   ├── trajectory.json
                │   └── openhands.txt
                └── verifier/
```

## Technical Details

### Dependencies
- streamlit - UI
- pandas - Tables
- subprocess - Harbor execution
- json - Data handling
- pathlib - File paths

### MCP Configuration
Dynamically builds and injects:
```python
OPENHANDS_MCP_SERVERS = {
    "sourcegraph": {
        "command": "mcp-remote",
        "env": {
            "MCP_REMOTE_URL": f"{SOURCEGRAPH_URL}/.mcp/transport",
            "MCP_REMOTE_AUTH_HEADER": f"Authorization: token {TOKEN}"
        }
    }
}
```

### Credential Handling
- Loads from `.env.local` on startup
- Validates credentials before execution
- Injects into subprocess environment
- No hardcoding, no insecurity

## Metrics Captured

### Standard Metrics
- **Reward**: Task success (0.0 or 1.0)
- **Input Tokens**: Context sent to LLM
- **Output Tokens**: Response from LLM
- **Cost USD**: Calculated from token usage
- **Execution Time**: Wall clock seconds

### Pricing (Anthropic Dec 2025)
```
Haiku:  $0.80/1M in, $4.00/1M out
Sonnet: $3.00/1M in, $15.00/1M out
Opus:   $15.00/1M in, $75.00/1M out
```

### IR-SDLC Specific
- Recall@K - Found relevant files
- Precision@K - Accuracy of results
- MRR - Mean Reciprocal Rank
- NDCG@K - Ranking quality
- F1@K - Combined metric

## Success Criteria Met

✅ Dashboard launches without errors  
✅ Can configure agent, model, dataset  
✅ Can execute Harbor evaluations  
✅ Real-time log streaming works  
✅ Results display correctly  
✅ Metrics captured and displayed  
✅ Supports 3 MCP configurations  
✅ Works with multiple benchmarks  
✅ Automatic MCP credential injection  
✅ Clean separation from old dashboard  
✅ Documentation complete  

## Known Limitations

- Only supports OpenHands agent (by design - transparent harness)
- Requires Harbor CLI installed
- Requires Docker for most benchmarks
- Results only viewable after completion (no streaming refresh)

## Future Enhancements

- CSV export of results
- Live metric updates (refresh Results tab)
- Preset evaluation templates
- Webhook integration for notifications
- Multi-job queuing

## How to Use

1. **Setup credentials** in `.env.local`:
   ```
   ANTHROPIC_API_KEY=...
   SOURCEGRAPH_URL=...
   SOURCEGRAPH_ACCESS_TOKEN=...
   ```

2. **Launch dashboard**:
   ```bash
   cd CodeContextBench
   streamlit run harbor_dashboard.py
   ```

3. **Configure & Run**:
   - Select agent, model, dataset in sidebar
   - Click START
   - Monitor logs in Run tab
   - View results in Results tab

4. **Compare**:
   - Run multiple evaluations
   - View cross-eval analysis in Compare tab

## Files Delivered

| File | Type | Size | Purpose |
|------|------|------|---------|
| harbor_dashboard.py | Python | 15KB | Main application |
| README_HARBOR.md | Markdown | 4KB | Overview |
| HARBOR_SETUP.md | Markdown | 2.6KB | Quick setup |
| HARBOR_QUICKSTART.md | Markdown | 7KB | Detailed guide |
| TELEMETRY_SCHEMA.md | Markdown | 12KB | Data reference |

## Integration Points

✅ Credentials from `.env.local`  
✅ Harbor CLI as subprocess  
✅ Results from `harbor_jobs/jobs/`  
✅ Sourcegraph MCP endpoints  
✅ IR-SDLC benchmarks  

## No Breaking Changes

- ✅ Old dashboard unchanged
- ✅ Old beads/data untouched
- ✅ Harbor installation unmodified
- ✅ Credentials not duplicated
- ✅ Completely separate application

## Lessons Learned

1. **Simplicity Wins**: Single file app beats integrated system
2. **Streamlit Works**: Perfect for this use case
3. **MCP Injection**: Easy to handle dynamically
4. **Harbor Results**: JSON output is straightforward to parse
5. **Separate Apps**: Better than integration nightmares

## Conclusion

Successfully delivered a **production-ready, simple, standalone dashboard** for Harbor evaluations. The app is clean, well-documented, and ready for use.

**Key Achievement:** Built this without touching the old broken dashboard system at all.
