#!/bin/bash
# Run SWE-bench Pro comparison between baseline and MCP agents
# Usage: ./run_swebench_pro_comparison.sh [task_path] [num_runs]

set -euo pipefail

TASK_PATH="${1:-benchmarks/swebench_pro/tasks}"
NUM_RUNS="${2:-1}"
MODEL="${MODEL:-anthropic/claude-haiku-4-5-20251001}"

# Ensure credentials are exported
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set. Run: source .env.local && export ANTHROPIC_API_KEY"
    exit 1
fi

echo "=== SWE-bench Pro Comparison ==="
echo "Task path: $TASK_PATH"
echo "Model: $MODEL"
echo "Runs: $NUM_RUNS"
echo ""

# Find all task directories
TASKS=$(find "$TASK_PATH" -name "task.toml" -exec dirname {} \; | sort | head -20)

if [ -z "$TASKS" ]; then
    echo "No tasks found in $TASK_PATH"
    echo "Run the adapter first: python benchmarks/swebench_pro/run_adapter.py --all --limit 10 --task-dir $TASK_PATH"
    exit 1
fi

TASK_COUNT=$(echo "$TASKS" | wc -l | tr -d ' ')
echo "Found $TASK_COUNT tasks"
echo ""

# Create results directory
RESULTS_DIR="jobs/swebench-pro-comparison-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

# Run baseline agent
echo "=== Running Baseline Agent ==="
for task in $TASKS; do
    TASK_NAME=$(basename "$task")
    echo "Running: $TASK_NAME (baseline)"
    
    harbor run \
        --path "$task" \
        --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
        --model "$MODEL" \
        -n "$NUM_RUNS" \
        --output-dir "$RESULTS_DIR/baseline" \
        || echo "Failed: $TASK_NAME"
done

# Run Strategic Deep Search agent (MCP)
echo ""
echo "=== Running Strategic Deep Search Agent (MCP) ==="
for task in $TASKS; do
    TASK_NAME=$(basename "$task")
    echo "Running: $TASK_NAME (strategic)"
    
    harbor run \
        --path "$task" \
        --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
        --model "$MODEL" \
        -n "$NUM_RUNS" \
        --output-dir "$RESULTS_DIR/strategic" \
        || echo "Failed: $TASK_NAME"
done

echo ""
echo "=== Comparison Complete ==="
echo "Results saved to: $RESULTS_DIR"
echo ""
echo "Next: Run analysis script"
echo "  python scripts/analyze_mcp_experiment.py $RESULTS_DIR"
