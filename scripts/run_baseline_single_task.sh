#!/bin/bash
# Run a single task with baseline Claude Code (no MCP)
# Usage: bash scripts/run_baseline_single_task.sh

set -e

echo "Setting up environment..."
source .env.local
source harbor/bin/activate

# Export API key so Harbor can pass it to the container
export ANTHROPIC_API_KEY

echo "Running baseline Claude Code on sgt-001..."
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo ""

harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-haiku-4-5-20251001 \
  --task-name sgt-001 \
  -n 1 \
  --jobs-dir jobs/claude-baseline-haiku-single

echo ""
echo "✅ Done. Results saved to jobs/claude-baseline-haiku-single/"
