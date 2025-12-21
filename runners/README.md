# CodeContextBench Runners

Harbor-based benchmark orchestration for evaluating coding agents with/without Sourcegraph code intelligence.

## Scripts

### harbor_benchmark.sh
Unified benchmark runner supporting multiple agents and benchmark sets.

**Usage:**
```bash
# Run baseline Claude on 10Figure, 50 tasks
./harbor_benchmark.sh --benchmark 10figure --agent claude-baseline --tasks 50

# Run Claude + Sourcegraph MCP with 10 concurrent executions
./harbor_benchmark.sh --benchmark terminal-bench --agent claude-mcp --concurrent 10

# Collect and compare results
./harbor_benchmark.sh --collect-results jobs/baseline-* jobs/treatment-*
```

**Options:**
- `--benchmark BENCH`: Benchmark dataset (terminal-bench, 10figure; default: terminal-bench)
- `--agent AGENT`: Agent implementation (claude-baseline, claude-mcp; default: claude-baseline)
- `--tasks N`: Number of tasks to run (default: 10)
- `--concurrent N`: Concurrent executions (default: 4)
- `--task-filter PATTERN`: Filter tasks by pattern (optional)
- `--jobs-dir DIR`: Harbor job output directory (default: ./jobs)
- `--collect-results`: Collect and compare results from job directories
- `--help`: Show help message

**Environment:**
```bash
# For Claude baseline
export ANTHROPIC_API_KEY="sk-..."

# For Claude + Sourcegraph MCP
export ANTHROPIC_API_KEY="sk-..."
export SRC_ACCESS_TOKEN="sgp_..."
export SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com"  # optional
```

### compare_results.py
Compare Harbor results between baseline and treatment runs.

**Usage:**
```bash
python3 compare_results.py jobs/baseline-20251217-161000 jobs/claude-mcp-20251217-161500
```

**Output:**
- Summary statistics (accuracy, timing, patch size)
- Error breakdown
- Task-by-task outcome differences

### aggregator.py
Cross-benchmark aggregation across multiple runs and agents.

**Usage:**
```bash
python3 aggregator.py --runs jobs/ --output cross-benchmark-report.json
```

**Output:**
- Overall accuracy and success rates
- Per-run performance breakdown
- Inconsistent tasks (vary across runs)
- Error summary
- JSON report for further analysis

## Workflow

### 1. Run baseline
```bash
./harbor_benchmark.sh --benchmark 10figure --agent claude-baseline --tasks 89
```

### 2. Run treatment
```bash
./harbor_benchmark.sh --benchmark 10figure --agent claude-mcp --tasks 89
```

### 3. Compare results
```bash
./harbor_benchmark.sh --collect-results jobs/claude-baseline-* jobs/claude-mcp-*
```

### 4. Cross-benchmark analysis
```bash
python3 aggregator.py --runs jobs/ --output analysis.json
```

## Supported Agents

### claude-baseline
Claude Code CLI without Sourcegraph tools (control).
- Requires: `ANTHROPIC_API_KEY`
- Import path: `agents:BaselineClaudeCodeAgent`

### claude-mcp
Claude Code with Sourcegraph MCP server for code intelligence.
- Requires: `ANTHROPIC_API_KEY`, `SRC_ACCESS_TOKEN`
- Import path: `agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent`

## Supported Benchmarks

### terminal-bench
Terminal-Bench 2.0 benchmark (89 tasks).
- Source: Terminal-based evaluation tasks
- Harbor dataset: `terminal-bench@2.0`

### 10figure
10Figure-Codebases real-world evaluation.
- Source: 23 real-world repositories
- Harbor dataset: `10figure@2.0`
- Dataset location: `/Users/sjarmak/10Figure-Codebases/`

## Result Structure

Harbor saves results with this structure:
```
jobs/
├── baseline-20251217-161000/
│   ├── jobs.json
│   └── <task-1>/
│       ├── task.json
│       ├── result.json
│       └── logs/
└── treatment-20251217-161500/
    └── ...
```

Each `result.json` contains:
- `task_name`: Task identifier
- `verifier_result.rewards.reward`: Success metric (>0 = success)
- `agent_execution.duration_sec`: Agent runtime
- `patch_info.size_bytes`: Generated patch size
- `exception_info`: Error details if execution failed

## Observability

Results are collected in JSON format:
- Raw Harbor output: `jobs/<run>/<task>/result.json`
- Comparison report: stdout from `compare_results.py`
- Aggregate report: `cross-benchmark-report.json`

## Tips

- Use `--tasks` to run smaller experiments first
- Use `--task-filter` to test specific task categories
- Use `--concurrent 1` for debugging
- Results are timestamped to avoid collisions
- Keep `jobs/` directory for future analysis
