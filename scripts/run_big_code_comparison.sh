#!/bin/bash
# Run big code MCP comparisons without Harbor reward evaluation
# Directly invokes harbor CLI and collects trajectories from both agents

set -e

source .env.local

TIMESTAMP=$(date +%Y%m%d-%H%M)
JOBS_DIR="jobs/bigcode-comparison-${TIMESTAMP}"
mkdir -p "$JOBS_DIR"

declare -a TASKS=("big-code-vsc-001" "big-code-servo-001" "big-code-k8s-001" "big-code-trt-001")

echo "=========================================="
echo "Big Code MCP Comparisons"
echo "Timestamp: $TIMESTAMP"
echo "=========================================="
echo ""

for TASK in "${TASKS[@]}"; do
    echo ">>> Running $TASK..."
    echo ""
    
    # Run baseline (Claude Code without MCP guidance)
    echo "  Baseline (no MCP)..."
    mkdir -p "$JOBS_DIR/$TASK/baseline"
    harbor run \
        --path "benchmarks/big_code_mcp/$TASK" \
        --agent claude-code \
        --model anthropic/claude-haiku-4-5-20251001 \
        -n 1 \
        --jobs-dir "$JOBS_DIR/$TASK/baseline" \
        --ek "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
        2>&1 | tail -5
    
    # Extract trajectory
    BASELINE_TRAJ=$(find "$JOBS_DIR/$TASK/baseline" -name "trajectory.json" -type f | head -1)
    if [ -f "$BASELINE_TRAJ" ]; then
        echo "  ✓ Baseline trajectory saved"
    else
        echo "  ✗ Baseline trajectory not found"
    fi
    
    # Run MCP agent (with Sourcegraph MCP guidance)
    echo "  MCP agent (with Sourcegraph guidance)..."
    mkdir -p "$JOBS_DIR/$TASK/mcp"
    harbor run \
        --path "benchmarks/big_code_mcp/$TASK" \
        --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
        --model anthropic/claude-haiku-4-5-20251001 \
        -n 1 \
        --jobs-dir "$JOBS_DIR/$TASK/mcp" \
        --ek "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
        --ek "SOURCEGRAPH_URL=$SOURCEGRAPH_URL" \
        --ek "SOURCEGRAPH_ACCESS_TOKEN=$SOURCEGRAPH_ACCESS_TOKEN" \
        2>&1 | tail -5
    
    # Extract trajectory
    MCP_TRAJ=$(find "$JOBS_DIR/$TASK/mcp" -name "trajectory.json" -type f | head -1)
    if [ -f "$MCP_TRAJ" ]; then
        echo "  ✓ MCP trajectory saved"
    else
        echo "  ✗ MCP trajectory not found"
    fi
    
    echo ""
done

echo "=========================================="
echo "✅ All Comparisons Complete!"
echo "=========================================="
echo ""
echo "Results location: $JOBS_DIR"
echo ""
echo "Extract metrics:"
echo "  python scripts/extract_big_code_metrics.py $JOBS_DIR"
