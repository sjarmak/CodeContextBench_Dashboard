#!/bin/bash
# Run MCP agent on sgt-010 (simplified pilot task, known to pass with baseline)
# Usage: bash scripts/run_mcp_pilot_task.sh

set -e

echo "Setting up environment..."
source .env.local
source harbor/bin/activate

# Export API and Sourcegraph credentials so Harbor can pass them to the container
export ANTHROPIC_API_KEY
export SOURCEGRAPH_URL
export SOURCEGRAPH_ACCESS_TOKEN

echo "Running MCP agent on sgt-010 (pilot task)..."
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "SOURCEGRAPH_URL: $SOURCEGRAPH_URL"
echo ""

harbor run \
  --path benchmarks/github_mined_pilot \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --task-name sgt-010 \
  -n 1 \
  --jobs-dir jobs/claude-mcp-pilot-single

echo ""
echo "✅ Done. Results saved to jobs/claude-mcp-pilot-single/"
