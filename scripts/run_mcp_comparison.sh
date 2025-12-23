#!/bin/bash

# Load credentials
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

BENCHMARK_PATH="benchmarks/big_code_mcp/big-code-vsc-001"
MODEL="anthropic/claude-haiku-4-5-20251001"
RESULTS_DIR="results/mcp_comparison_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "========================================"
echo "Running MCP Comparison Experiment"
echo "========================================"
echo "Benchmark: $BENCHMARK_PATH"
echo "Model: $MODEL"
echo "Results: $RESULTS_DIR"
echo ""

# Array of agents to test
agents=(
    "agents.claude_baseline_agent:BaselineClaudeCodeAgent:baseline"
    "agents.mcp_variants:DeepSearchFocusedAgent:deep_search_focused"
    "agents.mcp_variants:MCPNonDeepSearchAgent:mcp_no_deep_search"
    "agents.mcp_variants:FullToolkitAgent:full_toolkit"
)

# Run each agent
for agent_spec in "${agents[@]}"; do
    IFS=':' read -r import_path class_name agent_name <<< "$agent_spec"
    
    echo ""
    echo "========================================"
    echo "Running: $agent_name"
    echo "Import: $import_path:$class_name"
    echo "========================================"
    
    log_file="$RESULTS_DIR/${agent_name}.log"
    
    harbor run \
        --path "$BENCHMARK_PATH" \
        --agent-import-path "$import_path:$class_name" \
        --model "$MODEL" \
        -n 1 \
        --timeout-multiplier 2.0 \
        2>&1 | tee "$log_file"
    
    echo "✓ Completed: $agent_name (log: $log_file)"
done

echo ""
echo "========================================"
echo "All agents completed!"
echo "Results saved to: $RESULTS_DIR"
echo "========================================"

# Create summary
echo ""
echo "Summary:"
for agent_spec in "${agents[@]}"; do
    IFS=':' read -r import_path class_name agent_name <<< "$agent_spec"
    log_file="$RESULTS_DIR/${agent_name}.log"
    
    if grep -q "Execution completed successfully" "$log_file" 2>/dev/null; then
        echo "✓ $agent_name: SUCCESS"
    elif grep -q "PASS\|Success" "$log_file" 2>/dev/null; then
        echo "✓ $agent_name: SUCCESS"
    else
        echo "✗ $agent_name: INCOMPLETE/FAILED"
    fi
done
