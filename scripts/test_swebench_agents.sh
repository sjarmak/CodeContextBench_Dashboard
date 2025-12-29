#!/bin/bash
# Test SWE-bench agent configurations with Daytona
#
# Tests all agent variants to ensure they work correctly with:
# - Daytona cloud VMs
# - Sourcegraph MCP integration
# - Deep Search MCP integration
#
# Usage: ./scripts/test_swebench_agents.sh [task-name]
#
# Default task: astropy__astropy-12907 (known working oracle test)

set -euo pipefail

# Configuration
TASK_NAME="${1:-astropy__astropy-12907}"
DATASET="swebench-verified@1.0"
MODEL="anthropic/claude-haiku-4-5-20251001"
JOBS_DIR="jobs/swebench-agent-tests-$(date +%Y%m%d-%H%M%S)"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Optional: Export MCP credentials if available
export SOURCEGRAPH_ACCESS_TOKEN="${SOURCEGRAPH_ACCESS_TOKEN:-}"
export SOURCEGRAPH_URL="${SOURCEGRAPH_URL:-https://sourcegraph.com}"

echo "========================================="
echo "SWE-bench Agent Configuration Testing"
echo "========================================="
echo "Task: $TASK_NAME"
echo "Dataset: $DATASET"
echo "Model: $MODEL"
echo "Jobs Dir: $JOBS_DIR"
echo "========================================="
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local agent="$2"
    local env_vars="${3:-}"

    echo -e "${YELLOW}Testing: $test_name${NC}"
    echo "Agent: $agent"
    echo "Env vars: ${env_vars:-none}"

    local test_dir="$JOBS_DIR/$test_name"
    mkdir -p "$test_dir"

    # Build command
    local cmd="harbor run \
        --dataset $DATASET \
        --task-name $TASK_NAME \
        --agent $agent \
        --model $MODEL \
        --env daytona \
        --jobs-dir $test_dir \
        -n 1"

    # Add environment variables if specified
    if [[ -n "$env_vars" ]]; then
        cmd="$env_vars $cmd"
    fi

    echo "Command: $cmd"
    echo ""

    # Run test
    local start_time=$(date +%s)
    if eval "$cmd" > "$test_dir/harbor.log" 2>&1; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo -e "${GREEN}✓ PASSED${NC} (${duration}s)"

        # Check reward
        if [[ -f "$test_dir/"*"/verifier/reward.txt" ]]; then
            local reward=$(cat "$test_dir/"*"/verifier/reward.txt" | head -1)
            echo "  Reward: $reward"
        fi
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo -e "${RED}✗ FAILED${NC} (${duration}s)"
        echo "  Check log: $test_dir/harbor.log"
    fi

    echo ""
}

# Test 1: Oracle (baseline - should always work)
echo "========================================="
echo "Test 1: Oracle Agent (Golden Solution)"
echo "========================================="
run_test "oracle" "oracle"

# Test 2: Harbor's ClaudeCode (no MCP)
echo "========================================="
echo "Test 2: Harbor ClaudeCode Baseline"
echo "========================================="
run_test "harbor-claudecode-baseline" "claudecode"

# Test 3: Harbor's ClaudeCode + Sourcegraph MCP
echo "========================================="
echo "Test 3: Harbor ClaudeCode + Sourcegraph MCP"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    # Note: Harbor's built-in ClaudeCode may need MCP config via different mechanism
    echo "Note: Testing requires MCP configuration mechanism for built-in ClaudeCode"
    # Skip for now - need to understand Harbor's MCP configuration
    echo -e "${YELLOW}SKIPPED: Need to configure MCP for built-in ClaudeCode${NC}"
    echo ""
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 4: SWEAgentBaselineAgent (no MCP)
echo "========================================="
echo "Test 4: SWEAgentBaselineAgent (No MCP)"
echo "========================================="
run_test "swe-agent-baseline" "agents.swe_agent_wrapper:SWEAgentBaselineAgent"

# Test 5: SWEAgentMCPAgent (with Sourcegraph)
echo "========================================="
echo "Test 5: SWEAgentMCPAgent (Sourcegraph)"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "swe-agent-mcp" "agents.swe_agent_wrapper:SWEAgentMCPAgent"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 6: BaselineClaudeCodeAgent (no MCP)
echo "========================================="
echo "Test 6: BaselineClaudeCodeAgent (No MCP)"
echo "========================================="
run_test "baseline-claude-no-mcp" \
    "agents.claude_baseline_agent:BaselineClaudeCodeAgent" \
    "BASELINE_MCP_TYPE=none"

# Test 7: BaselineClaudeCodeAgent + Sourcegraph MCP
echo "========================================="
echo "Test 7: BaselineClaudeCodeAgent + Sourcegraph"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "baseline-claude-sourcegraph" \
        "agents.claude_baseline_agent:BaselineClaudeCodeAgent" \
        "BASELINE_MCP_TYPE=sourcegraph"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 8: BaselineClaudeCodeAgent + Deep Search MCP
echo "========================================="
echo "Test 8: BaselineClaudeCodeAgent + Deep Search"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "baseline-claude-deepsearch" \
        "agents.claude_baseline_agent:BaselineClaudeCodeAgent" \
        "BASELINE_MCP_TYPE=deepsearch"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 9: StrategicDeepSearchAgent
echo "========================================="
echo "Test 9: StrategicDeepSearchAgent"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "strategic-deepsearch" \
        "agents.mcp_variants:StrategicDeepSearchAgent"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 10: DeepSearchFocusedAgent
echo "========================================="
echo "Test 10: DeepSearchFocusedAgent"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "deepsearch-focused" \
        "agents.mcp_variants:DeepSearchFocusedAgent"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 11: MCPNonDeepSearchAgent (keyword/NLS only)
echo "========================================="
echo "Test 11: MCPNonDeepSearchAgent"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "mcp-no-deepsearch" \
        "agents.mcp_variants:MCPNonDeepSearchAgent"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Test 12: FullToolkitAgent
echo "========================================="
echo "Test 12: FullToolkitAgent"
echo "========================================="
if [[ -n "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    run_test "full-toolkit" \
        "agents.mcp_variants:FullToolkitAgent"
else
    echo -e "${YELLOW}SKIPPED: SOURCEGRAPH_ACCESS_TOKEN not set${NC}"
    echo ""
fi

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Results saved to: $JOBS_DIR"
echo ""
echo "To view individual results:"
echo "  cat $JOBS_DIR/*/verifier/reward.txt"
echo ""
echo "To view logs:"
echo "  ls $JOBS_DIR/*/harbor.log"
echo ""
