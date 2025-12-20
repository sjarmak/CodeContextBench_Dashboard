#!/bin/bash
# Phase 3 Rerun with proper experimental design
# 
# This fixes the critical flaw in the original Phase 3 evaluation:
# - Original: Baseline got empty repo stubs, MCP got Sourcegraph + repo cloning
# - Fixed: Both baseline and MCP get pre-cloned repos (equal file access)
#
# Difference measured: Search strategy (grep vs Sourcegraph MCP), not file access
#
# Tasks:
#   big-code-vsc-001: VS Code (1GB+ TypeScript)
#   big-code-k8s-001: Kubernetes (1.4GB Go)
#   big-code-servo-001: Servo (1.6GB Rust)
#   big-code-trt-001: TensorRT-LLM (1.6GB Python/C++)

set -e

# CRITICAL: Source AND export credentials
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Verify credentials
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    exit 1
fi
if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "ERROR: SOURCEGRAPH_ACCESS_TOKEN not set"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d-%H%M)
JOBS_DIR="jobs/phase3-rerun-proper-${TIMESTAMP}"
mkdir -p "$JOBS_DIR"

declare -a TASKS=("big-code-vsc-001" "big-code-k8s-001" "big-code-servo-001" "big-code-trt-001")

echo "=========================================="
echo "Phase 3 Rerun: Big Code MCP (Proper Setup)"
echo "Timestamp: $TIMESTAMP"
echo "=========================================="
echo ""
echo "EXPERIMENTAL DESIGN FIX:"
echo "  - Both agents: Pre-cloned repos (identical file access)"
echo "  - Baseline: Local grep/find/rg only"
echo "  - MCP: Sourcegraph semantic search (+ local tools)"
echo "  - Measures: Search strategy difference, not file visibility"
echo ""

for TASK in "${TASKS[@]}"; do
    echo ">>> Running $TASK..."
    echo ""
    
    # Run baseline (Claude Code without MCP guidance, but WITH repo files)
    echo "  Baseline (local grep/find/rg, no MCP)..."
    mkdir -p "$JOBS_DIR/$TASK/baseline"
    harbor run \
        --path "benchmarks/big_code_mcp/$TASK" \
        --agent claude-code \
        --model anthropic/claude-haiku-4-5-20251001 \
        -n 1 \
        --jobs-dir "$JOBS_DIR/$TASK/baseline" \
        --ek "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
        2>&1 | tail -5
    
    BASELINE_TRAJ=$(find "$JOBS_DIR/$TASK/baseline" -name "trajectory.json" -type f | head -1)
    if [ -f "$BASELINE_TRAJ" ]; then
        echo "  ✓ Baseline trajectory saved"
    else
        echo "  ✗ Baseline trajectory not found"
    fi
    
    # Run MCP agent (with Sourcegraph MCP guidance + repo files)
    echo "  MCP agent (Sourcegraph semantic search)..."
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
    
    MCP_TRAJ=$(find "$JOBS_DIR/$TASK/mcp" -name "trajectory.json" -type f | head -1)
    if [ -f "$MCP_TRAJ" ]; then
        echo "  ✓ MCP trajectory saved"
    else
        echo "  ✗ MCP trajectory not found"
    fi
    
    echo ""
done

echo "=========================================="
echo "✅ Phase 3 Rerun Complete!"
echo "=========================================="
echo ""
echo "Results location: $JOBS_DIR"
echo ""
echo "Extract metrics:"
echo "  python scripts/extract_big_code_metrics.py $JOBS_DIR"
echo ""
echo "Judge quality:"
echo "  python scripts/llm_judge_big_code.py $JOBS_DIR"
