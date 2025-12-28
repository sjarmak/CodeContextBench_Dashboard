# Running Mini SWE Agent with Local SWE-Bench Tasks

## Problem
Harbor's remote registry has a malformed JSON file, causing failures when using `--dataset swebench-verified`.

## Solution: Use Local Task Paths

### Quick Test (Single Task)

```bash
# Source environment
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# List available tasks
ls benchmarks/swebench_pro/tasks | head -5

# Run on first task with baseline agent
harbor trials start \
  --path benchmarks/swebench_pro/tasks/instance_ansible-ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2 \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentBaseline \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

### Run with Sourcegraph MCP

```bash
harbor trials start \
  --path benchmarks/swebench_pro/tasks/instance_ansible-ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2 \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentSourcegraphMCP \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

### Run Multiple Tasks

```bash
# Run first 5 tasks
for task in $(ls benchmarks/swebench_pro/tasks | head -5); do
  harbor trials start \
    --path benchmarks/swebench_pro/tasks/$task \
    --agent-import-path mini_swe_agent_mcp:MiniSweAgentBaseline \
    --model anthropic/claude-haiku-4-5-20251001 \
    -n 1 \
    --jobs-dir jobs/swe_baseline_run
done
```

## Using the Dashboard

### Via Evaluation Runner → Single Run Tab:

1. **Agent Type:** Select "Mini SWE Agent"
2. **Variant:** Choose your MCP configuration
3. **Benchmark:** If using local tasks, you'll need to add them to the database first

OR use the config files directly:

```bash
harbor trials start \
  -c swe_bench_configs/baseline.yaml \
  -p benchmarks/swebench_pro/tasks/instance_xxx
```

## Troubleshooting

### Error: "Dataset swebench-verified not found"
**Solution:** Use `--path` to local tasks, not `--dataset`

### Error: "JSONDecodeError"
**Solution:** Harbor registry is broken. Use local paths.

### Error: "No output generated"
**Solution:** Check `jobs/*/agent.log` for actual error. Usually means agent couldn't start.

### Error: "ANTHROPIC_API_KEY not set"
**Solution:** Run `export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL` after sourcing .env.local

## Task Structure

Each SWE-Bench task directory contains:
```
instance_xxx/
├── task.toml          # Task metadata
├── patches/           # Expected changes
└── setup/             # Environment setup
```

Harbor will:
1. Build Docker environment from task.toml
2. Run your agent inside container
3. Compare output to expected patches
4. Generate reward/score
