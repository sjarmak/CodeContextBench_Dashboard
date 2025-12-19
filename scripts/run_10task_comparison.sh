#!/bin/bash
# Run 10-task comparison: baseline vs MCP
# Compares Claude baseline vs Claude+MCP on 10 pilot tasks

set -e

echo "=========================================="
echo "10-Task Comparison: Baseline vs MCP"
echo "=========================================="
echo ""
echo "Setting up environment..."
source .env.local
source harbor/bin/activate

export ANTHROPIC_API_KEY
export SOURCEGRAPH_URL
export SOURCEGRAPH_ACCESS_TOKEN

# Tasks to run
TASKS=(sgt-001 sgt-002 sgt-003 sgt-004 sgt-005 sgt-006 sgt-007 sgt-008 sgt-009 sgt-010)

# Run baseline on 10 tasks (sequential)
echo ""
echo ">>> Running BASELINE agent on 10 pilot tasks..."
echo "Tasks: ${TASKS[@]}"
echo ""

for task in "${TASKS[@]}"; do
  echo "[BASELINE] Running $task..."
  harbor run \
    --path benchmarks/github_mined_pilot \
    --agent claude-code \
    --model anthropic/claude-haiku-4-5-20251001 \
    --task-name "$task" \
    -n 1 \
    --jobs-dir jobs/baseline-10task-20251219 \
    2>&1 | tail -10
done

echo ""
echo ">>> Running MCP agent on 10 pilot tasks..."
echo "Tasks: ${TASKS[@]}"
echo ""

for task in "${TASKS[@]}"; do
  echo "[MCP] Running $task..."
  harbor run \
    --path benchmarks/github_mined_pilot \
    --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
    --model anthropic/claude-haiku-4-5-20251001 \
    --task-name "$task" \
    -n 1 \
    --jobs-dir jobs/mcp-10task-20251219 \
    2>&1 | tail -10
done

echo ""
echo "=========================================="
echo "✅ 10-Task Comparison Complete!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  Baseline: jobs/baseline-10task-20251219/"
echo "  MCP:      jobs/mcp-10task-20251219/"
echo ""
echo "To analyze results:"
echo "  python scripts/analyze_comparison_results.py"
