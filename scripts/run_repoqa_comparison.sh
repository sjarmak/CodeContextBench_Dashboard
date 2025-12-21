#!/bin/bash

# Run RepoQA baseline vs MCP comparison
# Generates timestamped directories with results

set -e

TASK_DIR="${1:?Usage: $0 <task_dir>}"
TIMESTAMP=$(date +%Y%m%d-%H%M)
JOBS_DIR="jobs/repoqa-comparison-${TIMESTAMP}"

mkdir -p "$JOBS_DIR"/{baseline,mcp}

echo "=== RepoQA Baseline vs MCP Comparison ==="
echo "Task dir: $TASK_DIR"
echo "Results: $JOBS_DIR"
echo ""

# Source environment
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Run baseline
echo "[1/2] Running baseline agent (claude-code, no MCP)..."
harbor run \
  --path "$TASK_DIR" \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1 \
  --output "$JOBS_DIR/baseline" \
  2>&1 | tee "$JOBS_DIR/baseline.log"

echo ""
echo "[2/2] Running MCP agent (claude-code + Sourcegraph)..."
harbor run \
  --path "$TASK_DIR" \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1 \
  --output "$JOBS_DIR/mcp" \
  2>&1 | tee "$JOBS_DIR/mcp.log"

echo ""
echo "=== Validation ==="
python scripts/validate_comparison_results.py "$JOBS_DIR/baseline" "$JOBS_DIR/mcp"

echo ""
echo "Results saved to: $JOBS_DIR"
