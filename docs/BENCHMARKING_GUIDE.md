# Benchmarking Guide: Running Tests with Agent Configurations

This guide documents how to run benchmark tests and task suites with different agent configurations, capture observability metrics, and compare results.

## Quick Start

### Run Baseline Agent (no Sourcegraph)

```bash
cd /Users/sjarmak/CodeContextBench
source .venv-harbor/bin/activate

harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/baseline-run \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003
```

### Run MCP Agent (with Sourcegraph Deep Search)

```bash
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/mcp-run \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003
```

## Detailed Workflow

### 1. Environment Setup

```bash
# Activate Harbor environment
source .venv-harbor/bin/activate

# Verify credentials are set
echo $ANTHROPIC_API_KEY  # Required for all agents
echo $SRC_ACCESS_TOKEN   # Required for MCP agent only

# Clean Docker cache (optional but recommended for fresh builds)
docker system prune -af --volumes
```

### 2. Single-Task Sanity Check

Always validate one task before running full suites:

```bash
# Baseline agent sanity check
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/sanity-baseline \
  --task-name sgt-001

# Check results
cat jobs/sanity-baseline/*/result.json | python3 -m json.tool

# Inspect agent output
find jobs/sanity-baseline -name "claude.txt" -exec head -50 {} \;

# Check if task passed
find jobs/sanity-baseline -name "reward.txt" | xargs cat
```

**Success indicators:**
- `result.json` exists with no errors
- `claude.txt` shows Claude Code executing the task
- `reward.txt` contains `1.0` (pass) or `0.0` (fail)

### 3. Subset Testing (5-10 Tasks)

Test with a subset before full suite to validate configuration:

```bash
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/mcp-subset \
  --task-name sgt-001 \
  --task-name sgt-002 \
  --task-name sgt-003 \
  --task-name sgt-004 \
  --task-name sgt-005
```

Expected runtime: 10-15 minutes per task (large PyTorch clones)

### 4. Full Suite Testing (All 25 Tasks)

```bash
# Run all 25 github_mined tasks
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/mcp-full \
  --task-name sgt-001 \
  --task-name sgt-002 \
  --task-name sgt-003 \
  --task-name sgt-004 \
  --task-name sgt-005 \
  --task-name sgt-006 \
  --task-name sgt-007 \
  --task-name sgt-008 \
  --task-name sgt-009 \
  --task-name sgt-010 \
  --task-name sgt-011 \
  --task-name sgt-012 \
  --task-name sgt-013 \
  --task-name sgt-014 \
  --task-name sgt-015 \
  --task-name sgt-016 \
  --task-name sgt-017 \
  --task-name sgt-018 \
  --task-name sgt-019 \
  --task-name sgt-020 \
  --task-name sgt-021 \
  --task-name sgt-022 \
  --task-name sgt-023 \
  --task-name sgt-024 \
  --task-name sgt-025
```

Expected runtime: 6-8 hours (25 tasks × 12-20 min each)

### 5. Monitor Execution

```bash
# Watch progress in real-time
watch -n 10 'ls -la jobs/mcp-full/*/sgt-*/reward.txt 2>/dev/null | wc -l'

# Check latest result aggregation
tail -50 jobs/mcp-full/*/result.json 2>/dev/null | python3 -m json.tool

# Look for failures in a specific task
find jobs/mcp-full -name "sgt-005*" -type d -exec ls -la {}/agent/ \;
```

## Capturing Observability Metrics

After a run completes, extract token usage, costs, and tool metrics:

```bash
python3 runners/capture_pilot_observability.py --baseline jobs/baseline-run

python3 runners/capture_pilot_observability.py --mcp jobs/mcp-run

python3 runners/capture_pilot_observability.py --all
```

**Output:**
- `artifacts/pilot-observability.json` - Full metrics including:
  - Per-task token counts and costs
  - Success rate
  - Tool usage patterns
  - Agent efficiency metrics

## Comparing Agent Configurations

### Side-by-Side Results

```bash
# Run baseline
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/compare-baseline \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003 --task-name sgt-004 --task-name sgt-005

# Run MCP
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/compare-mcp \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003 --task-name sgt-004 --task-name sgt-005

# Capture observability for both
python3 runners/capture_pilot_observability.py --baseline jobs/compare-baseline --mcp jobs/compare-mcp

# View combined metrics
cat artifacts/pilot-observability.json | python3 -m json.tool
```

### Metrics to Compare

1. **Success Rate**: `tasks_passed / tasks_total`
2. **Token Efficiency**: `total_tokens / tasks_passed`
3. **Cost**: `total_cost_usd` (cost-per-token varies by model)
4. **Tool Usage**: MCP agent should show `deep_search` calls in claude.txt

## Model Selection

Different models for different scenarios:

```bash
# Fast/cheap testing (haiku)
--model anthropic/claude-haiku-4-5

# Better quality (sonnet)
--model anthropic/claude-3-5-sonnet-20241022

# Best quality (opus)
--model anthropic/claude-opus-4-1
```

## Task Output Structure

Each task generates:

```
jobs/run-name/YYYY-MM-DD__HH-MM-SS/
├── result.json                          # Aggregated results
├── sgt-001__XXXXX/
│   ├── agent/
│   │   ├── claude.txt                   # Claude Code CLI output
│   │   ├── patch.diff                   # Git diff of changes
│   │   └── patch.stat                   # Git diff statistics
│   ├── reward.txt                       # 1.0 (pass) or 0.0 (fail)
│   ├── trial.log                        # Harbor execution log
│   └── run_manifest.json                # Observability metrics
├── sgt-002__XXXXX/
│   └── ...
```

## Troubleshooting

### Claude Code Not Found in Container

Check that Dockerfile installs Claude Code correctly:

```bash
# Verify installation
docker exec <container-id> which claude
docker exec <container-id> npm list -g @anthropic-ai/claude-code
```

### No Tokens Captured

Check `claude.txt` output:

```bash
find jobs/run-name -name "claude.txt" -exec head -200 {} \;
```

Look for Claude output format - token counts should be in JSON response.

### All Tasks Show 0.0 Reward

Check reward.txt files:

```bash
find jobs/run-name -name "reward.txt" -exec cat {} \;
```

If missing or empty, check that test harness properly generates rewards. Verify `tests/test.sh` in task directory.

### Out of Memory or Timeouts

PyTorch repo is large. Typical timings:

- First task: 15-20 min (full clone + install)
- Subsequent tasks: 12-15 min (cache reuse)

If timeouts occur, increase Harbor timeout:

```bash
harbor run ... --timeout-multiplier 2.0
```

## Best Practices

1. **Always sanity check first**: Run 1 task before suites
2. **Use consistent models**: Compare same models across agents
3. **Run in sequence**: Use `-n 1` for reliable results (no parallel)
4. **Clean Docker**: Run `docker system prune -af` between major runs
5. **Log everything**: Save `result.json` and `claude.txt` for analysis
6. **Capture metrics**: Always run `capture_pilot_observability.py` after benchmarks

## Example: Full A/B Test

```bash
#!/bin/bash
set -e

echo "=== A/B Test: Baseline vs MCP ==="

# Clean
docker system prune -af --volumes

# Run baseline
echo "Running baseline..."
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/ab-baseline \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003 --task-name sgt-004 --task-name sgt-005

# Run MCP
echo "Running MCP..."
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5 \
  -n 1 \
  --jobs-dir jobs/ab-mcp \
  --task-name sgt-001 --task-name sgt-002 --task-name sgt-003 --task-name sgt-004 --task-name sgt-005

# Capture metrics
echo "Capturing metrics..."
source .venv/bin/activate
python3 runners/capture_pilot_observability.py --baseline jobs/ab-baseline --mcp jobs/ab-mcp

echo "Complete! Results in artifacts/pilot-observability.json"
```

## Environment Variables

**Required for all agents:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Required for MCP agent only:**
```bash
export SRC_ACCESS_TOKEN="sgp_..."
export SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com"  # or your instance
```

Load from `.env.local`:
```bash
source infrastructure/load-env.sh
```
