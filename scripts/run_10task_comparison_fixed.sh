#!/bin/bash
# Run 10-task comparison: baseline vs MCP
# FIXED: Ensure ANTHROPIC_API_KEY is properly passed to containers

set -e

echo "=========================================="
echo "10-Task Comparison: Baseline vs MCP (FIXED)"
echo "=========================================="
echo ""
echo "Setting up environment..."
source .env.local
source harbor/bin/activate

# Verify API key and tokens are available BEFORE running
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set in .env.local"
    exit 1
fi

if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "ERROR: SOURCEGRAPH_ACCESS_TOKEN not set in .env.local"
    exit 1
fi

echo "✓ ANTHROPIC_API_KEY is set"
echo "✓ SOURCEGRAPH_ACCESS_TOKEN is set"
echo "✓ SOURCEGRAPH_URL: $SOURCEGRAPH_URL"
echo ""

# Tasks to run
TASKS=(sgt-001 sgt-002 sgt-003 sgt-004 sgt-005 sgt-006 sgt-007 sgt-008 sgt-009 sgt-010)

# Run baseline on 10 tasks (sequential)
echo ""
echo ">>> Running BASELINE agent on 10 pilot tasks..."
echo "Tasks: ${TASKS[@]}"
echo ""

for task in "${TASKS[@]}"; do
  echo "[BASELINE] Running $task..."
  # Pass env vars via shell environment (they're already exported)
  # Harbor will inherit them from the parent shell
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  SOURCEGRAPH_URL="$SOURCEGRAPH_URL" \
  SOURCEGRAPH_ACCESS_TOKEN="$SOURCEGRAPH_ACCESS_TOKEN" \
  harbor run \
    --path benchmarks/github_mined \
    --agent claude-code \
    --model anthropic/claude-haiku-4-5-20251001 \
    --task-name "$task" \
    -n 1 \
    --jobs-dir jobs/comparison-20251219-fixed/baseline \
    2>&1 | tail -10
done

echo ""
echo ">>> Running MCP agent on 10 pilot tasks..."
echo "Tasks: ${TASKS[@]}"
echo ""

for task in "${TASKS[@]}"; do
  echo "[MCP] Running $task..."
  # Pass env vars via shell environment
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  SOURCEGRAPH_URL="$SOURCEGRAPH_URL" \
  SOURCEGRAPH_ACCESS_TOKEN="$SOURCEGRAPH_ACCESS_TOKEN" \
  harbor run \
    --path benchmarks/github_mined \
    --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
    --model anthropic/claude-haiku-4-5-20251001 \
    --task-name "$task" \
    -n 1 \
    --jobs-dir jobs/comparison-20251219-fixed/mcp \
    2>&1 | tail -10
done

echo ""
echo "=========================================="
echo "✅ 10-Task Comparison Complete!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  Baseline: jobs/comparison-20251219-fixed/baseline/"
echo "  MCP:      jobs/comparison-20251219-fixed/mcp/"
echo ""
echo "To analyze results:"
echo "  python scripts/comprehensive_metrics_analysis.py"
