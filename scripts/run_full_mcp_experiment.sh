#!/bin/bash
# Full MCP Experiment: Run all big_code_mcp tasks with all agent variants
# Includes LLM-as-judge evaluation of retrieval and code quality
#
# Usage:
#   ./scripts/run_full_mcp_experiment.sh
#
# Or run a subset:
#   TASKS="big-code-vsc-001 big-code-k8s-001" ./scripts/run_full_mcp_experiment.sh

set -e

# Configuration
MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"
JUDGE_MODEL="${JUDGE_MODEL:-anthropic/claude-haiku-4-5-20251001}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
EXPERIMENT_DIR="jobs/full-mcp-experiment-${TIMESTAMP}"

# All big_code_mcp tasks
ALL_TASKS=(
    "benchmarks/big_code_mcp/big-code-vsc-001"
    "benchmarks/big_code_mcp/big-code-k8s-001"
    "benchmarks/big_code_mcp/big-code-servo-001"
    "benchmarks/big_code_mcp/big-code-trt-001"
)

# Allow override via environment
if [ -n "$TASKS" ]; then
    IFS=' ' read -ra TASK_NAMES <<< "$TASKS"
    ALL_TASKS=()
    for name in "${TASK_NAMES[@]}"; do
        ALL_TASKS+=("benchmarks/big_code_mcp/$name")
    done
fi

# Agent configurations
AGENTS=(
    "strategic:agents.mcp_variants:StrategicDeepSearchAgent"
    "aggressive:agents.mcp_variants:DeepSearchFocusedAgent"
    "baseline:agents.claude_baseline_agent:BaselineClaudeCodeAgent"
)

# Check required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Run: source .env.local && export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL"
    exit 1
fi

if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "WARNING: SOURCEGRAPH_ACCESS_TOKEN not set - MCP agents will fail"
fi

echo "============================================"
echo "Full MCP Experiment"
echo "============================================"
echo "Timestamp: $TIMESTAMP"
echo "Model: $MODEL"
echo "Judge Model: $JUDGE_MODEL"
echo "Output: $EXPERIMENT_DIR"
echo ""
echo "Tasks (${#ALL_TASKS[@]}):"
for task in "${ALL_TASKS[@]}"; do
    echo "  - $task"
done
echo ""
echo "Agents (${#AGENTS[@]}):"
for agent_spec in "${AGENTS[@]}"; do
    agent_name="${agent_spec%%:*}"
    echo "  - $agent_name"
done
echo "============================================"
echo ""

mkdir -p "$EXPERIMENT_DIR"

# Create experiment config
cat > "$EXPERIMENT_DIR/config.json" << EOF
{
    "timestamp": "$TIMESTAMP",
    "model": "$MODEL",
    "judge_model": "$JUDGE_MODEL",
    "tasks": $(printf '%s\n' "${ALL_TASKS[@]}" | jq -R . | jq -s .),
    "agents": ["strategic", "aggressive", "baseline"]
}
EOF

# Run each task with each agent
for task_path in "${ALL_TASKS[@]}"; do
    task_name=$(basename "$task_path")
    echo ""
    echo "========================================"
    echo "TASK: $task_name"
    echo "========================================"

    task_dir="$EXPERIMENT_DIR/$task_name"
    mkdir -p "$task_dir"

    for agent_spec in "${AGENTS[@]}"; do
        agent_name="${agent_spec%%:*}"
        agent_import="${agent_spec#*:}"

        echo ""
        echo ">>> Running $agent_name on $task_name..."

        agent_dir="$task_dir/$agent_name"
        mkdir -p "$agent_dir"

        # Run the agent
        if harbor run \
            --path "$task_path" \
            --agent-import-path "$agent_import" \
            --model "$MODEL" \
            -n 1 \
            --jobs-dir "$agent_dir" \
            --job-name "${agent_name}-${TIMESTAMP}" \
            2>&1 | tee "$agent_dir/run.log"; then
            echo "✓ $agent_name completed on $task_name"
        else
            echo "✗ $agent_name FAILED on $task_name"
        fi
    done
done

echo ""
echo "============================================"
echo "All Runs Complete - Starting Analysis"
echo "============================================"

# Run LLM judge evaluation
echo ""
echo ">>> Running LLM Judge Evaluation..."
python3 scripts/llm_judge_experiment.py "$EXPERIMENT_DIR" --model "$JUDGE_MODEL" 2>&1 | tee "$EXPERIMENT_DIR/judge.log"

# Generate summary report
echo ""
echo ">>> Generating Summary Report..."
python3 scripts/analyze_mcp_experiment.py "$EXPERIMENT_DIR" 2>&1 | tee "$EXPERIMENT_DIR/analysis.log"

echo ""
echo "============================================"
echo "Experiment Complete"
echo "============================================"
echo "Results: $EXPERIMENT_DIR"
echo "Summary: $EXPERIMENT_DIR/REPORT.md"
echo "Judge Results: $EXPERIMENT_DIR/llm_judge_results.json"
echo ""
