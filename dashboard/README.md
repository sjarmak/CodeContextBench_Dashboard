# CodeContextBench Dashboard

Interactive Streamlit dashboard for CodeContextBench evaluation pipeline.

## Features

### 🏠 Home
- Quick stats (benchmarks, experiments, agents, manifests)
- Recent activity feed

### 📋 Benchmark Manifests
- Browse MANIFEST.json files
- View dataset information and hashes
- Inspect validation logs
- Environment fingerprints

### 📊 Experiment Results
- Browse evaluation_report.json data
- View individual agent runs
- LLM judge assessments
- Tool usage breakdowns
- REPORT.md rendering

### 🔍 Agent Comparison
- Side-by-side agent performance
- Success rate charts
- Token usage comparison
- Judge score radar charts
- Tool usage heatmaps
- Cost analysis

### 🔎 Deep Search Analytics
- MCP Deep Search usage patterns
- Tool distribution (deep_search vs keyword vs NLS vs local)
- Query analysis and export
- Per-agent breakdowns

### ▶️ Run Benchmarks
- Trigger benchmark lifecycle pipeline
- Launch profile runs
- Run post-process evaluation
- Preview commands with dry-run mode

## Installation

```bash
# Install dependencies
pip install -r dashboard/requirements.txt
```

## Quick Start

```bash
# Run dashboard
streamlit run dashboard/app.py
```

The dashboard will open in your browser at `http://localhost:8501`.

## Requirements

- Python 3.8+
- streamlit >= 1.29.0
- plotly >= 5.18.0
- pandas >= 2.1.0

## Usage

### Viewing Evaluation Results

1. First, run the post-process script on an experiment:
   ```bash
   python scripts/postprocess_experiment.py jobs/2025-12-23__11-13-40 \
       --benchmark repoqa \
       --judge
   ```

2. Open the dashboard and navigate to **Experiment Results** to view:
   - Summary metrics
   - Agent run details
   - Judge assessments
   - Generated reports

### Comparing Agents

1. Navigate to **Agent Comparison**
2. Select an experiment with multiple agents
3. View interactive charts comparing:
   - Success rates
   - Token usage
   - Judge scores
   - Tool usage patterns

### Triggering Runs

1. Navigate to **Run Benchmarks**
2. Choose a pipeline type:
   - **Benchmark Lifecycle**: Refresh adapters and validate
   - **Profile Runner**: Run agent matrices
   - **Post-Process**: Generate evaluation reports
3. Configure options and click **Run**

## Architecture

```
dashboard/
├── app.py                 # Main entry point
├── requirements.txt       # Dependencies
├── pages/
│   ├── manifests.py      # Benchmark manifest viewer
│   ├── results.py        # Experiment results browser
│   ├── comparison.py     # Agent comparison charts
│   ├── deep_search.py    # Deep Search analytics
│   └── run_triggers.py   # Pipeline trigger UI
```

## Integration with Evaluation Pipeline

The dashboard integrates with:

- **src/benchmark/evaluation_schema.py**: Loads evaluation_report.json
- **src/benchmark/metrics_extractor.py**: Processes Harbor results
- **src/benchmark/llm_judge.py**: Judge assessment data
- **scripts/postprocess_experiment.py**: Generates reports
- **configs/benchmark_pipeline.yaml**: Pipeline configuration
- **configs/benchmark_profiles.yaml**: Profile definitions

## Tips

- Use **Dry Run** mode when triggering pipelines to preview commands first
- Export query data from Deep Search Analytics for further analysis
- Check the **Raw JSON** views for debugging
- Monitor resource usage when running large experiments

## Troubleshooting

**Dashboard not loading:**
- Check that streamlit is installed: `pip install streamlit`
- Verify you're in the correct directory

**No data showing:**
- Run `postprocess_experiment.py` first to generate evaluation reports
- Check that `jobs/` directory exists and contains experiments

**Charts not rendering:**
- Install plotly: `pip install plotly>=5.18.0`
- Clear browser cache and refresh

**Run triggers failing:**
- Verify scripts exist in `scripts/` directory
- Check that you have execute permissions
- Review command output for errors
