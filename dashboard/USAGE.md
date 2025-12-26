# Dashboard Usage Guide

## Starting the Dashboard

**IMPORTANT:** The dashboard needs access to environment variables (ANTHROPIC_API_KEY, etc.) to run evaluations.

### Recommended Method

Use the provided script that loads environment variables:

```bash
bash scripts/start_dashboard.sh
```

This script:
- Loads variables from `.env.local`
- Exports them so Harbor can access them
- Starts Streamlit on http://localhost:8501

### Manual Method

If you want to start manually:

```bash
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
streamlit run dashboard/app.py
```

**Why export?** Harbor runs as a subprocess and needs exported variables.

## Running Evaluations

### 1. Evaluation Runner

**To run a task evaluation:**

1. Navigate to **Evaluation Runner**
2. Select a benchmark (e.g., "Custom Big Code")
3. **Select at least one task** (e.g., "big-code-vsc-001")
4. Choose MCP configuration:
   - None (Pure Baseline) - No MCP tools
   - Sourcegraph MCP - Full Sourcegraph with all tools
   - Deep Search MCP - Deep Search only
5. Click **"Start Evaluation Run"**
6. On the monitoring page, click **"Start Run"** to execute

**Common mistakes:**
- ❌ Not selecting any tasks → run completes immediately with 0 tasks
- ❌ Forgetting to click "Start Run" → run stays in pending state
- ❌ Dashboard not started with environment variables → Harbor fails with exit code 1

### 2. Viewing Results

**To see LLM Judge and Task Reports:**

1. Navigate to **Run Results**
2. Select a completed run from dropdown
3. **Select a task** from the task dropdown
4. You'll see 4 tabs:
   - **Agent Trace** - Step-by-step agent actions
   - **Result Details** - Reward, verification output
   - **LLM Judge** - Evaluate with Claude (Haiku/Sonnet)
   - **Task Report** - Generate detailed analysis

**Why don't I see LLM Judge?**
- The run must have tasks (not 0 tasks)
- You must select a specific task (not just the run)
- The task must have completed (success or failure)

### 3. Oracle Validation

**To test a benchmark's tasks and verifiers:**

1. Navigate to **Benchmark Manager**
2. Select a benchmark
3. Select tasks to validate
4. Set timeout (default 300s)
5. Click **"Run Oracle Validation"**

This runs Harbor with the reference solution to verify the task is configured correctly.

## Troubleshooting

### "Run completed and failed"

Check the error message in Run Results. Common causes:

1. **Missing API key**
   - Error: "Harbor exited with code 1"
   - Fix: Restart dashboard with `bash scripts/start_dashboard.sh`

2. **Invalid task path**
   - Error: "Harbor exited with code 2"
   - Fix: Update to latest code (fixed in commit 2142499)

3. **Timeout**
   - Error: Task shows as failed after long run
   - Fix: Increase timeout in Evaluation Runner settings

### "I don't see the LLM Judge option"

LLM Judge only appears when:
- You're in **Run Results** view
- A run with tasks is selected
- A specific **task** is selected (not just the run)

If your run has 0 tasks:
- You didn't select tasks when creating the run
- Create a new run and check the task checkboxes

### Dashboard logs

To see what went wrong, check:

1. **Streamlit terminal** - Shows dashboard errors
2. **Harbor logs** - Saved to `jobs/<run-id>/<task>_<agent>_harbor.log`
3. **Database** - Error messages in run_tasks table

Example to check logs:
```bash
# Find latest run
ls -lt jobs/ | head -5

# Read Harbor log
cat "jobs/<run-id>/<task>_<agent>_harbor.log"
```

## Features

### LLM Judge Evaluation

Evaluate task results using Claude as a judge:

1. Select Haiku (fast/cheap) or Sonnet (detailed)
2. Click "Run LLM Judge Evaluation"
3. View:
   - Pass/Fail verdict
   - Detailed reasoning
   - Code quality assessment
   - Retrieval effectiveness (for MCP runs)

### Task Reports

Generate comprehensive task analysis:

1. Click "Generate Task Report"
2. View sections:
   - Task summary
   - Agent approach
   - Code changes
   - Quality metrics
   - Recommendations
3. Export as Markdown or JSON

### Comparison Table

Compare multiple runs across benchmarks:

1. Navigate to **Comparison Table**
2. View aggregated metrics
3. Filter by benchmark, agent, MCP configuration

## Tips

- **Oracle validation first** - Always validate a benchmark before running agent evaluations
- **Start with Haiku** - Use claude-haiku-4-5 for faster/cheaper iterations
- **Save logs** - Harbor logs are crucial for debugging failures
- **Check task selection** - Most common mistake is not selecting tasks
