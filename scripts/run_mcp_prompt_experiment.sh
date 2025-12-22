#!/bin/bash
# MCP Prompt Experiment: Strategic vs Aggressive Deep Search
# Reference: CodeContextBench-6pl
#
# Tests three agents on the same task:
# 1. StrategicDeepSearchAgent - Strategic context-gathering
# 2. DeepSearchFocusedAgent - Aggressive "use for every question"
# 3. BaselineClaudeCodeAgent - No MCP (control)
#
# Usage:
#   ./scripts/run_mcp_prompt_experiment.sh <task-path>
#
# Example:
#   ./scripts/run_mcp_prompt_experiment.sh benchmarks/big_code_mcp/big-code-vsc-001

set -e

TASK_PATH="${1:-benchmarks/big_code_mcp/big-code-vsc-001}"
MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
JOBS_DIR="jobs/mcp-prompt-experiment-${TIMESTAMP}"

# Check required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Run: source .env.local && export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL"
    exit 1
fi

if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "WARNING: SOURCEGRAPH_ACCESS_TOKEN not set - MCP agents will fail"
fi

echo "============================================"
echo "MCP Prompt Experiment"
echo "============================================"
echo "Task: $TASK_PATH"
echo "Model: $MODEL"
echo "Output: $JOBS_DIR"
echo "============================================"
echo ""

mkdir -p "$JOBS_DIR"

# Run 1: Strategic Deep Search Agent
echo ">>> Running StrategicDeepSearchAgent..."
harbor run \
    --path "$TASK_PATH" \
    --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
    --model "$MODEL" \
    -n 1 \
    --jobs-dir "$JOBS_DIR/strategic" \
    --job-name "strategic-${TIMESTAMP}" \
    2>&1 | tee "$JOBS_DIR/strategic.log"

echo ""
echo ">>> Running DeepSearchFocusedAgent (aggressive)..."
harbor run \
    --path "$TASK_PATH" \
    --agent-import-path agents.mcp_variants:DeepSearchFocusedAgent \
    --model "$MODEL" \
    -n 1 \
    --jobs-dir "$JOBS_DIR/aggressive" \
    --job-name "aggressive-${TIMESTAMP}" \
    2>&1 | tee "$JOBS_DIR/aggressive.log"

echo ""
echo ">>> Running BaselineClaudeCodeAgent (no MCP)..."
harbor run \
    --path "$TASK_PATH" \
    --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
    --model "$MODEL" \
    -n 1 \
    --jobs-dir "$JOBS_DIR/baseline" \
    --job-name "baseline-${TIMESTAMP}" \
    2>&1 | tee "$JOBS_DIR/baseline.log"

echo ""
echo "============================================"
echo "Experiment Complete"
echo "============================================"
echo "Results in: $JOBS_DIR"
echo ""
echo "To analyze:"
echo "  # Count Deep Search calls"
echo "  grep -r 'sg_deepsearch' $JOBS_DIR/*/*/agent/trajectory.json | wc -l"
echo ""
echo "  # Check rewards"
echo "  cat $JOBS_DIR/*/result.json | jq '.reward'"
echo ""
