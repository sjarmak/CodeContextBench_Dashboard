# Harbor Evaluations - Quick Start Guide

## What You Just Got

A **simple, powerful dashboard** for running systematic Harbor evaluations with:
- ✅ OpenHands agent (transparent, model-agnostic harness)
- ✅ Three MCP configurations (Baseline, Sourcegraph, Deep Search)
- ✅ Multiple benchmarks (SWE-bench, IR-SDLC, Aider, etc.)
- ✅ Automatic telemetry capture (tokens, cost, time, success)
- ✅ Real-time results dashboard with cross-evaluation comparison

---

## 🚀 5-Minute Setup

### 1. Ensure credentials are in `.env.local`

```bash
cat .env.local
```

Should contain:
```
ANTHROPIC_API_KEY=sk-ant-...
SOURCEGRAPH_URL=https://sourcegraph.sourcegraph.com
SOURCEGRAPH_ACCESS_TOKEN=sgp_...
```

If missing, add them:
```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env.local
echo "SOURCEGRAPH_URL=https://sourcegraph.sourcegraph.com" >> .env.local
echo "SOURCEGRAPH_ACCESS_TOKEN=sgp_..." >> .env.local
```

### 2. Launch the dashboard

```bash
cd CodeContextBench
streamlit run harbor_dashboard.py
```

That's it! The dashboard opens in your browser.

---

## 📖 Basic Workflow

### First Time: Verify Setup

**▶️ Run Evaluation tab:**
1. Agent: `Baseline (No MCP)`
2. Model: `Haiku (Fast, Cheap)`
3. Dataset: `Hello World (Test)`
4. Click **▶️ Start Evaluation**

Takes ~1 minute. If it succeeds:
✅ Your environment is ready
✅ Credentials are valid
✅ Harbor is working

**📊 Results tab:**
See the trial result with metrics:
- ✅ Task success (Reward = 1.0)
- Token usage
- Execution time
- Cost

---

## 🔍 Understanding the Three Agents

### Baseline (No MCP) 🔵
**What it is:** OpenHands with standard tools only
- `execute_bash` - run shell
- `str_replace_editor` - edit code
- `execute_ipython_cell` - Python

**When to use:**
- Baseline for comparison
- Simple tasks
- Cost-sensitive analysis

**Example run:**
```
Agent: Baseline
Model: Haiku
Dataset: hello-world@head
→ Should pass quickly
```

---

### Sourcegraph MCP 🟢
**What it is:** Code search, navigation, git history

**Tools it adds:**
- `sg_keyword_search` - Find code by keyword
- `sg_read_file` - Read any file in codebase
- `sg_go_to_definition` - Jump to definitions
- `sg_find_references` - Find all usages
- `sg_commit_search` - Search git history

**When to use:**
- Bug triage (find affected files)
- Code review (understand changes)
- Dependency analysis (find impacts)
- Architecture navigation

**Example run:**
```
Agent: Sourcegraph MCP
Model: Sonnet
Dataset: ir-sdlc-multi-repo@1.0
→ Should excel at multi-repo navigation
```

---

### Deep Search MCP 🟣
**What it is:** Semantic code understanding

**Tools it adds:**
- `deep_search` - Natural language semantic search
- Codebase reasoning and analysis
- Architecture understanding
- Cross-repo dependency analysis

**When to use:**
- Complex reasoning about code
- Architecture decisions
- Large-scale refactoring
- Understanding unfamiliar codebases

**Example run:**
```
Agent: Deep Search MCP
Model: Opus
Dataset: ir-sdlc-advanced-reasoning@1.0
→ Should handle complex reasoning
```

---

## 📊 Next Steps: Running Real Evaluations

### Step 1: Run SWE-Bench with Baseline

**Config:**
- Agent: `Baseline (No MCP)`
- Model: `Haiku`
- Dataset: `SWE-Bench Verified`
- Task Filter: `*python*` (just Python tasks)
- Concurrent: `2`
- Timeout: `1.5`

**Why:** Establishes baseline performance on real bug fixes

**Duration:** ~15-30 minutes (depends on task filter)

---

### Step 2: Run Same Tasks with Sourcegraph MCP

**Config:** Same as above, but
- Agent: `Sourcegraph MCP`

**Why:** Measure impact of code search on success rate

**Compare:**
- Which agent solved more tasks?
- How much did tokens/cost increase?
- Was the improvement worth it?

---

### Step 3: Run IR-SDLC Tasks

**Config:**
- Agent: Pick one (or try all three!)
- Model: `Sonnet` (better for IR tasks)
- Dataset: `ir-sdlc-multi-repo@1.0`
- Concurrent: `4`

**Why:** IR-SDLC tasks specifically test information retrieval

**Metrics:**
- Not just reward, but IR metrics:
  - Recall@10 (did it find relevant files?)
  - MRR (how high-ranked was first relevant result?)
  - Precision@10 (how many results were relevant?)

---

## 📈 Analyzing Results

### In the Dashboard

**▶️ Run Evaluation:** Start new evals
**📊 Results:** View latest eval in detail
**📈 Analysis:** Compare across evals

### Understanding Results Table

```
Task        Agent    Model   Reward  Tokens  Cost ($)  Time (s)
bug_123     baseline Haiku   1.0     12500   0.015     45
bug_124     baseline Haiku   0.0     18200   0.022     60
bug_125     baseline Haiku   1.0     15100   0.019     50
```

**Reward = 1.0**: Task passed ✅
**Reward = 0.0**: Task failed ❌

### Key Metrics

| Metric | Meaning | Good Range |
|--------|---------|------------|
| **Reward** | Success rate | 0.0-1.0 per task |
| **Input Tokens** | Context size | Lower is cheaper |
| **Output Tokens** | Model generation | Varies by task |
| **Cost ($)** | Estimated API cost | Lower is cheaper |
| **Time (s)** | Execution time | Varies by complexity |

---

## 💡 Quick Analysis Ideas

### Idea 1: Cost vs Performance
Run same benchmark with Haiku/Sonnet/Opus
→ See cost increase vs improvement

**Compare in Analysis tab:**
```
Model    Avg Reward    Avg Cost
Haiku    0.45          $0.02
Sonnet   0.62          $0.08
Opus     0.71          $0.15
```

**Question:** Is +26% performance worth 7.5x cost?

---

### Idea 2: MCP Value
Run same tasks with and without MCP

**Compare:**
```
Agent                  Success Rate   Tokens   Cost
Baseline              40%             15K      $0.02
+ Sourcegraph MCP     62%             28K      $0.04
+ Deep Search MCP     65%             32K      $0.05
```

**Question:** Is additional complexity worth it?

---

### Idea 3: Benchmark Difficulty
Run Haiku across different benchmarks

```
Benchmark              Success Rate   Avg Time
hello-world            100%           10s
aime (math)            5%             120s
swebench               12%            300s
ir-sdlc-simple         35%            90s
```

---

## 🛠️ Troubleshooting

### Dashboard won't load
```bash
# Check syntax
python -m py_compile dashboard/views/harbor_evaluations.py

# Check imports
streamlit run dashboard/app.py
```

### Missing credentials
```bash
# See what's loaded
cat .env.local | grep -E "ANTHROPIC|SOURCEGRAPH"

# Add missing ones
echo "ANTHROPIC_API_KEY=..." >> .env.local
```

### Evaluation fails immediately
Check agent logs:
```bash
tail -f CodeContextBench/harbor_jobs/jobs/*/*/agent/openhands.txt
```

### Jobs directory is huge
Clean up old results:
```bash
rm -rf CodeContextBench/harbor_jobs/jobs/2025-12-*
```

---

## 📚 Learn More

- **Full docs:** `dashboard/HARBOR_EVALUATIONS.md`
- **Configs:** `dashboard/harbor_configs.json`
- **Agent logs:** `harbor_jobs/jobs/<job_id>/<task>/agent/openhands.txt`
- **Trajectories:** `harbor_jobs/jobs/<job_id>/<task>/agent/trajectory.json`

---

## 🎓 Recommended Learning Path

1. **Understand:** Run hello-world with Baseline
2. **Measure:** Run SWE-bench with all 3 agents
3. **Optimize:** Run IR-SDLC with different models
4. **Analyze:** Compare results across all runs

Each step teaches you more about:
- How OpenHands works
- How MCP impacts performance
- How models compare
- How to instrument agent behavior

---

## 🚀 You're Ready!

Click "🚀 Harbor Evaluations" and start exploring! 

Questions? Check `HARBOR_EVALUATIONS.md` or look at agent logs in the Results tab.
