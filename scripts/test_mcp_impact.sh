#!/bin/bash
# Test MCP Impact on Baseline Claude Code Agent
#
# Tests the same agent harness (BaselineClaudeCodeAgent) with three configurations:
# 1. Pure baseline (no MCP)
# 2. + Sourcegraph MCP (keyword, NLS, Deep Search)
# 3. + Deep Search only MCP
#
# This isolates the impact of MCP on agent performance using the simplest
# possible Harbor-compatible harness that works with ANY benchmark.
#
# Usage:
#   ./scripts/test_mcp_impact.sh --dataset <dataset> --task-name <task>
#   ./scripts/test_mcp_impact.sh --path <benchmark-path> --task-name <task>
#
# Examples:
#   # SWE-bench
#   ./scripts/test_mcp_impact.sh --dataset swebench-verified@1.0 --task-name astropy__astropy-12907
#
#   # Local benchmark
#   ./scripts/test_mcp_impact.sh --path benchmarks/big_code_mcp/big-code-vsc-001 --task-name big-code-vsc-001

set -euo pipefail

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default configuration
AGENT="agents.claude_baseline_agent:BaselineClaudeCodeAgent"
MODEL="anthropic/claude-haiku-4-5-20251001"
JOBS_DIR="jobs/mcp-impact-$(date +%Y%m%d-%H%M%S)"
DATASET=""
BENCHMARK_PATH=""
TASK_NAME=""

# Parse arguments
while [[ $# -gt 0 ]]; then
    case $1 in
        --dataset)
            DATASET="$2"
            shift 2
            ;;
        --path)
            BENCHMARK_PATH="$2"
            shift 2
            ;;
        --task-name)
            TASK_NAME="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --jobs-dir)
            JOBS_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dataset <dataset> | --path <path>] --task-name <task>"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$TASK_NAME" ]]; then
    echo -e "${RED}ERROR: --task-name is required${NC}"
    exit 1
fi

if [[ -z "$DATASET" ]] && [[ -z "$BENCHMARK_PATH" ]]; then
    echo -e "${RED}ERROR: Either --dataset or --path is required${NC}"
    exit 1
fi

# Ensure environment is loaded
if [[ ! -f .env.local ]]; then
    echo -e "${RED}ERROR: .env.local not found${NC}"
    exit 1
fi

source .env.local

# Check required environment variables
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "${RED}ERROR: ANTHROPIC_API_KEY not set${NC}"
    exit 1
fi

if [[ -z "${DAYTONA_API_KEY:-}" ]]; then
    echo -e "${RED}ERROR: DAYTONA_API_KEY not set${NC}"
    exit 1
fi

# Export for subprocesses
export ANTHROPIC_API_KEY DAYTONA_API_KEY

# Check for MCP credentials (optional but recommended)
if [[ -z "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    echo -e "${YELLOW}WARNING: SOURCEGRAPH_ACCESS_TOKEN not set. MCP tests will be skipped.${NC}"
else
    export SOURCEGRAPH_ACCESS_TOKEN="${SOURCEGRAPH_ACCESS_TOKEN}"
    export SOURCEGRAPH_URL="${SOURCEGRAPH_URL:-https://sourcegraph.com}"
fi

echo "========================================="
echo "MCP Impact Testing"
echo "========================================="
echo "Agent: BaselineClaudeCodeAgent"
if [[ -n "$DATASET" ]]; then
    echo "Dataset: $DATASET"
else
    echo "Benchmark: $BENCHMARK_PATH"
fi
echo "Task: $TASK_NAME"
echo "Model: $MODEL"
echo "Jobs Dir: $JOBS_DIR"
echo "========================================="
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local mcp_type="$2"
    local description="$3"

    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}Test: $test_name${NC}"
    echo -e "${BLUE}Configuration: $description${NC}"
    echo -e "${BLUE}=========================================${NC}"

    local test_dir="$JOBS_DIR/$test_name"
    mkdir -p "$test_dir"

    # Build Harbor command
    local cmd="BASELINE_MCP_TYPE=$mcp_type harbor run"

    if [[ -n "$DATASET" ]]; then
        cmd="$cmd --dataset $DATASET"
    else
        cmd="$cmd --path $BENCHMARK_PATH"
    fi

    cmd="$cmd --task-name $TASK_NAME \
        --agent-import-path $AGENT \
        --model $MODEL \
        --env daytona \
        --jobs-dir $test_dir \
        -n 1"

    echo "Command: $cmd"
    echo ""

    # Run test
    local start_time=$(date +%s)
    if eval "$cmd" > "$test_dir/harbor.log" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo -e "${GREEN}✓ PASSED${NC} (${duration}s / $((duration / 60))m $((duration % 60))s)"

        # Check reward
        local reward_file=$(find "$test_dir" -name "reward.txt" -type f | head -1)
        if [[ -n "$reward_file" ]]; then
            local reward=$(cat "$reward_file" | head -1)
            echo "  Reward: $reward"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo -e "${RED}✗ FAILED${NC} (${duration}s / $((duration / 60))m $((duration % 60))s)"
        echo "  Check log: $test_dir/harbor.log"
        echo "  Last 20 lines:"
        tail -20 "$test_dir/harbor.log" | sed 's/^/    /'
    fi

    echo ""
}

# Test 1: Pure baseline (no MCP)
echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}Configuration 1: Pure Baseline${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
run_test "baseline-no-mcp" "none" "Pure baseline - no MCP tools"

# Test 2: Sourcegraph MCP (if credentials available)
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════${NC}"
    echo -e "${YELLOW}Configuration 2: Sourcegraph MCP${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════${NC}"
    run_test "baseline-sourcegraph-mcp" "sourcegraph" "Sourcegraph MCP - keyword, NLS, Deep Search"
else
    echo -e "${YELLOW}SKIPPED: Sourcegraph MCP test (no credentials)${NC}"
fi

# Test 3: Deep Search only (if credentials available)
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    echo ""
    echo -e "${YELLOW}═══════════════════════════════════════${NC}"
    echo -e "${YELLOW}Configuration 3: Deep Search Only${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════${NC}"
    run_test "baseline-deepsearch-only" "deepsearch" "Deep Search MCP only"
else
    echo -e "${YELLOW}SKIPPED: Deep Search test (no credentials)${NC}"
fi

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Results saved to: $JOBS_DIR"
echo ""
echo "To view rewards:"
echo "  find $JOBS_DIR -name 'reward.txt' -exec echo {} \\; -exec cat {} \\; -exec echo \\;"
echo ""
echo "To view logs:"
echo "  ls $JOBS_DIR/*/harbor.log"
echo ""
echo "To compare results:"
echo "  # Baseline (no MCP)"
echo "  cat $JOBS_DIR/baseline-no-mcp/*/verifier/reward.txt"
echo ""
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    echo "  # Sourcegraph MCP"
    echo "  cat $JOBS_DIR/baseline-sourcegraph-mcp/*/verifier/reward.txt"
    echo ""
    echo "  # Deep Search only"
    echo "  cat $JOBS_DIR/baseline-deepsearch-only/*/verifier/reward.txt"
    echo ""
fi
