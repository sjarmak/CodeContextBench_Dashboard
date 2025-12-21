#!/bin/bash
# Run MCP agent variant comparison benchmark
# CodeContextBench-1md: Tests three agent configurations to isolate tool value
#
# Variants:
#   1. deep-search-focused - Aggressive Deep Search prompting
#   2. mcp-no-deepsearch   - MCP tools except Deep Search
#   3. full-toolkit        - All tools, neutral prompting
#
# Usage:
#   ./scripts/run_mcp_variants_comparison.sh <task_path> [options]
#
# Example:
#   ./scripts/run_mcp_variants_comparison.sh benchmarks/big_code_mcp/big-code-vsc-001

set -euo pipefail

TASK_PATH="${1:-}"
MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
N_RUNS="${N_RUNS:-1}"

if [[ -z "$TASK_PATH" ]]; then
    echo "Usage: $0 <task_path> [options]"
    echo ""
    echo "Example: $0 benchmarks/big_code_mcp/big-code-vsc-001"
    echo ""
    echo "Environment variables:"
    echo "  MODEL   - Model to use (default: anthropic/claude-haiku-4-5-20251001)"
    echo "  N_RUNS  - Number of runs per variant (default: 1)"
    exit 1
fi

# Ensure credentials are available
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Run: source .env.local && export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL"
    exit 1
fi

if [[ -z "${SOURCEGRAPH_ACCESS_TOKEN:-}" ]]; then
    echo "ERROR: SOURCEGRAPH_ACCESS_TOKEN not set"
    exit 1
fi

# Export for subprocesses
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
JOB_DIR="jobs/mcp-variants-${TIMESTAMP}"

echo "=== MCP Agent Variant Comparison ==="
echo "Task: $TASK_PATH"
echo "Model: $MODEL"
echo "Runs per variant: $N_RUNS"
echo "Output: $JOB_DIR"
echo ""

mkdir -p "$JOB_DIR"

# Agent configurations
declare -A AGENTS=(
    ["deep-search-focused"]="agents.mcp_variants:DeepSearchFocusedAgent"
    ["mcp-no-deepsearch"]="agents.mcp_variants:MCPNonDeepSearchAgent"
    ["full-toolkit"]="agents.mcp_variants:FullToolkitAgent"
    ["baseline"]="agents.claude_baseline_agent:BaselineClaudeCodeAgent"
)

# Run each variant
for variant in "${!AGENTS[@]}"; do
    agent_path="${AGENTS[$variant]}"
    variant_dir="${JOB_DIR}/${variant}"

    echo ""
    echo "=== Running variant: ${variant} ==="
    echo "Agent: ${agent_path}"

    mkdir -p "$variant_dir"

    # Run harbor
    harbor run \
        --path "$TASK_PATH" \
        --agent-import-path "$agent_path" \
        --model "$MODEL" \
        -n "$N_RUNS" \
        --output-dir "$variant_dir" \
        2>&1 | tee "${variant_dir}/run.log"

    echo "✓ Variant ${variant} complete"
done

echo ""
echo "=== All variants complete ==="
echo "Results in: $JOB_DIR"
echo ""
echo "To analyze results:"
echo "  python scripts/extract_tool_calls.py ${JOB_DIR}"
echo "  python scripts/generate_full_report.py ${JOB_DIR}"
