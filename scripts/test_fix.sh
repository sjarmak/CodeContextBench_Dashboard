#!/bin/bash
# Test the system prompt fix - verify Claude makes actual code changes
# This script runs a quick test with the MCP agent on sgt-001

set -e

echo "=== Testing System Prompt Fix ==="
echo ""
echo "Prerequisites:"
echo "- Export environment variables"
source .env.local
export ANTHROPIC_API_KEY
export SOURCEGRAPH_URL
export SOURCEGRAPH_ACCESS_TOKEN
echo "✓ Environment configured"
echo ""

# Activate Harbor
source harbor/bin/activate
echo "✓ Harbor activated"
echo ""

# Run single task with timeout
echo "Running MCP agent on sgt-001 (with system prompt fix)..."
echo "This will attempt to implement the thread safety fix."
echo ""

TIMESTAMP=$(date +%s)
JOB_DIR="jobs/claude-mcp-haiku-single-test-${TIMESTAMP}"

timeout 600 harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --task-name sgt-001 \
  -n 1 \
  --jobs-dir "$JOB_DIR" 2>&1 || true

echo ""
echo "=== Checking Results ==="
echo ""

# Find the most recent task run
TASK_DIR=$(find "$JOB_DIR" -name "sgt-001__*" -type d | head -1)

if [ -z "$TASK_DIR" ]; then
  echo "❌ Task directory not found"
  exit 1
fi

echo "Task directory: $TASK_DIR"
echo ""

# Check for actual code changes
echo "Analyzing code changes..."
git -C "$TASK_DIR/agent" diff --name-only HEAD 2>/dev/null | head -20 || echo "⚠ No git diff available"

# Check git diff size
DIFF_SIZE=$(cd "$TASK_DIR/agent" && git diff HEAD 2>/dev/null | wc -c || echo "0")
echo "Total diff size: $DIFF_SIZE bytes"
echo ""

# Check test results
REWARD_FILE="$TASK_DIR/verifier/reward.txt"
if [ -f "$REWARD_FILE" ]; then
  REWARD=$(cat "$REWARD_FILE")
  echo "Test reward: $REWARD"
  if [ "$REWARD" = "1" ]; then
    echo "✅ SUCCESS! Full reward (1.0) - fix implemented correctly"
  elif [ "$REWARD" = "0.5" ]; then
    echo "⚠ PARTIAL SUCCESS (0.5) - changes detected but may need improvement"
  elif [ "$REWARD" = "0" ]; then
    echo "❌ FAILED (0.0) - no successful implementation"
  fi
else
  echo "⚠ Reward file not found"
fi

# Check test output
TEST_OUTPUT="$TASK_DIR/verifier/test-stdout.txt"
if [ -f "$TEST_OUTPUT" ]; then
  echo ""
  echo "Test output:"
  head -30 "$TEST_OUTPUT"
fi

echo ""
echo "Full results saved to: $JOB_DIR"
