#!/bin/bash
# Quick reference for running Harbor tests with/without Sourcegraph MCP

set -e

# Configuration
BENCHMARK_PATH="benchmarks/github_mined"
MODEL="anthropic/claude-3-5-sonnet-20241022"
TASKS=1  # Number of concurrent tasks

# Load environment
if [ -f "infrastructure/load-env.sh" ]; then
    source infrastructure/load-env.sh
fi

echo "============================================"
echo "Harbor + Sourcegraph MCP Test Runner"
echo "============================================"
echo ""
echo "Configuration:"
echo "  Benchmark: $BENCHMARK_PATH"
echo "  Model: $MODEL"
echo "  Concurrent tasks: $TASKS"
echo ""

# Parse command line
MODE=${1:-"help"}

case "$MODE" in
    baseline)
        echo "Running BASELINE (no MCP)..."
        echo ""
        
        # Check ANTHROPIC_API_KEY
        if [ -z "$ANTHROPIC_API_KEY" ]; then
            echo "❌ ANTHROPIC_API_KEY not set"
            echo "   Set it: export ANTHROPIC_API_KEY=sk-..."
            exit 1
        fi
        
        TIMESTAMP=$(date +%Y-%m-%d__%H-%M-%S)
        JOB_DIR="jobs/claude-baseline-github_mined-$TIMESTAMP"
        
        echo "Job directory: $JOB_DIR"
        echo ""
        echo "Command:"
        echo "harbor run \\"
        echo "  --path $BENCHMARK_PATH \\"
        echo "  --agent claude-code \\"
        echo "  --model $MODEL \\"
        echo "  --env daytona \\"
        echo "  -n $TASKS \\"
        echo "  --jobs-dir $JOB_DIR"
        echo ""
        
        read -p "Run? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            harbor run \
              --path "$BENCHMARK_PATH" \
              --agent claude-code \
              --model "$MODEL" \
              --env daytona \
              -n "$TASKS" \
              --jobs-dir "$JOB_DIR"
            
            echo "✓ Baseline run complete. Output: $JOB_DIR"
        fi
        ;;
    
    mcp)
        echo "Running MCP (with Sourcegraph)..."
        echo ""
        
        # Check credentials
        if [ -z "$ANTHROPIC_API_KEY" ]; then
            echo "❌ ANTHROPIC_API_KEY not set"
            echo "   Set it: export ANTHROPIC_API_KEY=sk-..."
            exit 1
        fi
        
        if [ -z "$SRC_ACCESS_TOKEN" ]; then
            echo "❌ SRC_ACCESS_TOKEN not set"
            echo "   Set it: export SRC_ACCESS_TOKEN=sgp_..."
            exit 1
        fi
        
        TIMESTAMP=$(date +%Y-%m-%d__%H-%M-%S)
        JOB_DIR="jobs/claude-mcp-github_mined-$TIMESTAMP"
        
        echo "Job directory: $JOB_DIR"
        echo "Credentials:"
        echo "  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
        echo "  SRC_ACCESS_TOKEN: ${SRC_ACCESS_TOKEN:0:10}..."
        echo ""
        echo "Command:"
        echo "harbor run \\"
        echo "  --path $BENCHMARK_PATH \\"
        echo "  --agent claude-code \\"
        echo "  --model $MODEL \\"
        echo "  --env daytona \\"
        echo "  --ek SOURCEGRAPH_ACCESS_TOKEN=\$SRC_ACCESS_TOKEN \\"
        echo "  --ek SOURCEGRAPH_URL=https://sourcegraph.sourcegraph.com \\"
        echo "  -n $TASKS \\"
        echo "  --jobs-dir $JOB_DIR"
        echo ""
        
        read -p "Run? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            harbor run \
              --path "$BENCHMARK_PATH" \
              --agent claude-code \
              --model "$MODEL" \
              --env daytona \
              --ek SOURCEGRAPH_ACCESS_TOKEN="$SRC_ACCESS_TOKEN" \
              --ek SOURCEGRAPH_URL="https://sourcegraph.sourcegraph.com" \
              -n "$TASKS" \
              --jobs-dir "$JOB_DIR"
            
            echo "✓ MCP run complete. Output: $JOB_DIR"
        fi
        ;;
    
    compare)
        echo "Comparing baseline and MCP results..."
        echo ""
        
        # Find most recent runs
        BASELINE=$(ls -dt jobs/claude-baseline-github_mined-* 2>/dev/null | head -1)
        MCP=$(ls -dt jobs/claude-mcp-github_mined-* 2>/dev/null | head -1)
        
        if [ -z "$BASELINE" ] || [ -z "$MCP" ]; then
            echo "❌ Could not find recent baseline or MCP runs"
            echo "   Baseline: $BASELINE"
            echo "   MCP: $MCP"
            exit 1
        fi
        
        echo "Baseline: $BASELINE"
        echo "MCP:      $MCP"
        echo ""
        
        # Extract key metrics
        echo "Results Summary:"
        echo ""
        
        # Show success rates if result.json exists
        if [ -f "$BASELINE/result.json" ]; then
            echo "Baseline result.json:"
            python3 -c "
import json
with open('$BASELINE/result.json') as f:
    data = json.load(f)
    total = data.get('stats', {}).get('n_trials', 0)
    errors = data.get('stats', {}).get('n_errors', 0)
    passed = total - errors
    print(f'  Total: {total}, Passed: {passed}, Failed: {errors}')
" || echo "  (error reading results)"
        fi
        
        if [ -f "$MCP/result.json" ]; then
            echo "MCP result.json:"
            python3 -c "
import json
with open('$MCP/result.json') as f:
    data = json.load(f)
    total = data.get('stats', {}).get('n_trials', 0)
    errors = data.get('stats', {}).get('n_errors', 0)
    passed = total - errors
    print(f'  Total: {total}, Passed: {passed}, Failed: {errors}')
" || echo "  (error reading results)"
        fi
        
        echo ""
        echo "To compare in detail:"
        echo "  diff <(ls -la $BASELINE) <(ls -la $MCP)"
        echo "  python3 runners/compare_results.py $BASELINE $MCP"
        ;;
    
    help|*)
        echo "Usage: $0 {baseline|mcp|compare|help}"
        echo ""
        echo "Commands:"
        echo "  baseline   Run Harbor with native Claude Code (no MCP)"
        echo "  mcp        Run Harbor with Sourcegraph MCP enabled"
        echo "  compare    Compare most recent baseline vs MCP runs"
        echo "  help       Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  ANTHROPIC_API_KEY       Required for both tests"
        echo "  SRC_ACCESS_TOKEN        Required for MCP test"
        echo "  SOURCEGRAPH_URL         Optional (defaults to sourcegraph.com)"
        echo ""
        echo "Quick start:"
        echo "  1. export ANTHROPIC_API_KEY=sk-..."
        echo "  2. export SRC_ACCESS_TOKEN=sgp_..."
        echo "  3. source infrastructure/load-env.sh"
        echo "  4. $0 baseline"
        echo "  5. $0 mcp"
        echo "  6. $0 compare"
        ;;
esac
