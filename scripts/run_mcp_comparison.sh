#!/bin/bash
# Run single-task comparison: baseline vs MCP on big code tasks
# Tests if MCP provides value on large codebases requiring broad architectural understanding
#
# USAGE:
#   ./run_mcp_comparison.sh <benchmark_dir> <task_name>
#
# Examples:
#   ./run_mcp_comparison.sh github_mined sgt-001         # Use mined task with MCP guidance
#   ./run_mcp_comparison.sh big_code_mcp k8s-001          # Use big code task with MCP guidance
#
# Results saved to: jobs/comparison-YYYYMMDD-HHMM-(baseline|mcp)/

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <benchmark_dir> <task_name>"
    echo ""
    echo "Examples:"
    echo "  $0 github_mined sgt-001        # Run mined task with MCP prompting"
    echo "  $0 big_code_mcp k8s-001        # Run big code task"
    exit 1
fi

BENCHMARK_DIR="$1"
TASK_NAME="$2"

echo "=========================================="
echo "MCP Value Comparison: Single Task"
echo "Benchmark: $BENCHMARK_DIR"
echo "Task: $TASK_NAME"
echo "=========================================="
echo ""
echo "Setting up environment..."
source .env.local
source harbor/bin/activate

# Verify credentials
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not found in .env.local"
    exit 1
fi
if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "ERROR: SOURCEGRAPH_ACCESS_TOKEN not found in .env.local"
    exit 1
fi

echo "✓ ANTHROPIC_API_KEY is set"
echo "✓ SOURCEGRAPH_ACCESS_TOKEN is set"
echo "✓ SOURCEGRAPH_URL is set to: ${SOURCEGRAPH_URL:-https://sourcegraph.com}"
echo ""

export ANTHROPIC_API_KEY
export SOURCEGRAPH_URL
export SOURCEGRAPH_ACCESS_TOKEN

# Create timestamped directory
TIMESTAMP=$(date +%Y%m%d-%H%M)
JOBS_DIR="jobs/comparison-${TIMESTAMP}"

echo "Results will be saved to: $JOBS_DIR/"
echo ""

# Run baseline WITHOUT MCP prompting
echo ""
echo ">>> Running BASELINE agent (no MCP guidance)..."
echo "Task: $TASK_NAME"
echo ""

harbor run \
  --path "benchmarks/${BENCHMARK_DIR}" \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --task-name "$TASK_NAME" \
  -n 1 \
  --jobs-dir "${JOBS_DIR}/baseline" \
  2>&1 | tail -15

echo ""
echo ">>> Running MCP agent (with MCP guidance enabled)..."
echo "Task: $TASK_NAME"
echo ""

# Run MCP agent with guidance
harbor run \
  --path "benchmarks/${BENCHMARK_DIR}" \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --task-name "$TASK_NAME" \
  -n 1 \
  --jobs-dir "${JOBS_DIR}/mcp" \
  2>&1 | tail -15

echo ""
echo "=========================================="
echo "✅ Comparison Complete!"
echo "=========================================="
echo ""
echo "Results saved to:"
echo "  Baseline: ${JOBS_DIR}/baseline/"
echo "  MCP:      ${JOBS_DIR}/mcp/"
echo ""
echo "VERIFICATION CHECKLIST:"
echo "1. Check token counts: python scripts/validate_comparison_results.py ${JOBS_DIR}/baseline ${JOBS_DIR}/mcp"
echo "2. Analyze results: python scripts/comprehensive_metrics_analysis.py"
echo ""
