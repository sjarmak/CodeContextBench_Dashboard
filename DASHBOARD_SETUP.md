# Dashboard Setup Guide

## Environment Setup

### Using Existing Python Environment (Recommended)

The dashboard uses your existing Python environment with mise. All dependencies are already installed:

```bash
# Verify dependencies
python -c "import streamlit, plotly, pandas; print('✅ Ready!')"
```

**Current Setup:**
- ✅ Python 3.12.11
- ✅ streamlit 1.51.0
- ✅ plotly 6.5.0
- ✅ pandas 2.3.3

### If Dependencies Are Missing

```bash
pip install streamlit plotly pandas
```

---

## Running the Dashboard

### Option 1: Quick Start Script (Easiest)

```bash
./run_dashboard.sh
```

### Option 2: Direct Streamlit Command

```bash
streamlit run dashboard/app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

---

## Running the Evaluation Pipeline

### Post-Process an Experiment

```bash
# Basic post-processing (no LLM judge)
python scripts/postprocess_experiment.py jobs/2025-12-23__11-13-40

# With benchmark manifest
python scripts/postprocess_experiment.py jobs/2025-12-23__11-13-40 \
    --benchmark repoqa

# With LLM judge evaluation (requires ANTHROPIC_API_KEY)
python scripts/postprocess_experiment.py jobs/2025-12-23__11-13-40 \
    --benchmark repoqa \
    --judge \
    --judge-model claude-haiku-4-5-20251001
```

### Outputs

After running postprocess, you'll get:
- `evaluation_report.json` - Complete metrics, judge assessments, tool usage
- `REPORT.md` - Human-readable markdown report

---

## Dashboard Features Overview

### 🏠 Home
- Quick stats dashboard
- Recent experiment activity
- Project overview

### 📋 Benchmark Manifests
- Browse MANIFEST.json files
- View dataset SHA-256 hashes
- Inspect validation logs
- Environment fingerprints

### 📊 Experiment Results
- Load evaluation_report.json
- View agent run details
- LLM judge assessments
- Tool usage breakdowns
- Interactive data exploration

### 🔍 Agent Comparison
- Success rate charts
- Token usage comparison
- Judge score radar charts
- Tool usage heatmaps
- Cost analysis

### 🔎 Deep Search Analytics
- MCP tool distribution
- Query analysis and export
- Per-agent breakdowns
- Search pattern insights

### ▶️ Run Benchmarks
- Trigger lifecycle pipeline
- Launch profile runs
- Run post-processing
- Dry-run mode available

---

## Workflow Example

### 1. Run a Benchmark Profile

```bash
# Run profile (creates experiment in jobs/)
python scripts/benchmark_profile_runner.py --profiles repoqa_smoke
```

### 2. Post-Process Results

```bash
# Process the experiment
python scripts/postprocess_experiment.py jobs/2025-12-25__10-30-00 \
    --benchmark repoqa \
    --profile repoqa_smoke \
    --judge
```

### 3. View in Dashboard

```bash
# Launch dashboard
./run_dashboard.sh

# Navigate to:
# - Experiment Results → Select your experiment
# - Agent Comparison → Compare agents side-by-side
# - Deep Search Analytics → Analyze MCP usage
```

---

## Troubleshooting

### Dashboard Won't Start

```bash
# Check streamlit installation
python -c "import streamlit; print(streamlit.__version__)"

# If missing, install
pip install streamlit plotly pandas
```

### No Data in Dashboard

**Problem:** Empty tables and "No experiments found"

**Solution:** Run postprocess script first:
```bash
python scripts/postprocess_experiment.py jobs/<experiment-dir> --benchmark <name>
```

The dashboard needs `evaluation_report.json` files in experiment directories.

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'benchmark'`

**Solution:** Run commands from project root:
```bash
cd /Users/sjarmak/CodeContextBench
python scripts/postprocess_experiment.py ...
```

### LLM Judge Fails

**Problem:** Judge evaluation throws API errors

**Solution:** Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your-key-here"
# Or add to .env.local
```

---

## Tips

1. **Use Dry-Run First**: When triggering pipelines from dashboard, use dry-run mode to preview commands

2. **Export Query Data**: From Deep Search Analytics, export queries as CSV for further analysis

3. **Monitor Costs**: Check the Agent Comparison page for token usage and cost metrics

4. **Batch Processing**: Post-process multiple experiments:
   ```bash
   for exp in jobs/2025-12-*/; do
       python scripts/postprocess_experiment.py "$exp" --benchmark repoqa
   done
   ```

5. **Judge Model Selection**:
   - `claude-haiku-4-5-20251001` - Fast and cheap (recommended)
   - `claude-sonnet-4-5-20250929` - Better quality, more expensive
   - `claude-opus-4-5-20251101` - Highest quality, most expensive

---

## Next Steps

- Read `dashboard/README.md` for detailed feature documentation
- Check `docs/BENCHMARK_LIFECYCLE.md` for pipeline details
- See `configs/benchmark_profiles.yaml` for profile examples
- Review `src/benchmark/` modules for API details
