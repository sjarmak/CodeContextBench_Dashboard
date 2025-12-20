#!/bin/bash
#
# Run DependEval baseline vs MCP comparison.
#
# This script runs the generated DependEval benchmark tasks with two agents:
#   1. Baseline: Claude Code (no MCP)
#   2. MCP-enabled: Claude Code with Sourcegraph MCP
#
# Usage:
#   bash scripts/run_dependeval_comparison.sh
#
# Results are saved to: jobs/dependeval-comparison-YYYYMMDD-HHMM/
#

set -e

echo "DependEval Phase 3 Comparison: Baseline vs MCP"
echo "============================================================"
echo ""

# Create timestamped job directory
TIMESTAMP=$(date +%Y%m%d-%H%M)
JOB_DIR="jobs/dependeval-comparison-$TIMESTAMP"
mkdir -p "$JOB_DIR"

echo "Job directory: $JOB_DIR"
echo ""

# Ensure environment variables are set
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_INSTANCE SOURCEGRAPH_ACCESS_TOKEN GITHUB_TOKEN

echo "Configuration:"
echo "  Sourcegraph instance: $SOURCEGRAPH_INSTANCE"
echo "  Model: anthropic/claude-haiku-4-5-20251001"
echo ""

# Find all tasks
TASK_DIR="benchmarks/dependeval_benchmark"
TASK_COUNT=$(find "$TASK_DIR" -name "task.toml" | wc -l)

echo "Tasks found: $TASK_COUNT"
echo ""

# Function to run a task with a given agent
run_task_with_agent() {
    local task_path=$1
    local agent=$2
    local output_dir=$3
    
    local task_name=$(basename $(dirname "$task_path"))
    
    echo "  Running: $task_name with $agent"
    
    # Run task and capture output
    mkdir -p "$output_dir"
    
    if [ "$agent" == "baseline" ]; then
        # Run baseline without MCP
        harbor run \
            --path "$task_path" \
            --agent claude-code \
            --model anthropic/claude-haiku-4-5-20251001 \
            -n 1 \
            --timeout-multiplier 5 \
            2>&1 | tee "$output_dir/run.log" || true
    else
        # Run with MCP agent
        harbor run \
            --path "$task_path" \
            --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
            --model anthropic/claude-haiku-4-5-20251001 \
            -n 1 \
            --timeout-multiplier 5 \
            2>&1 | tee "$output_dir/run.log" || true
    fi
}

# Run baseline tasks
echo "============================================================"
echo "BASELINE RUNS (Claude Code without MCP)"
echo "============================================================"
echo ""

BASELINE_DIR="$JOB_DIR/baseline"
mkdir -p "$BASELINE_DIR"

find "$TASK_DIR" -name "task.toml" | sort | while read task_toml; do
    task_dir=$(dirname "$task_toml")
    task_name=$(basename "$task_dir")
    
    output_dir="$BASELINE_DIR/$task_name"
    run_task_with_agent "$task_dir" "baseline" "$output_dir"
done

echo ""
echo "Baseline runs complete. Results in: $BASELINE_DIR"
echo ""

# Run MCP tasks
echo "============================================================"
echo "MCP RUNS (Claude Code with Sourcegraph MCP)"
echo "============================================================"
echo ""

MCP_DIR="$JOB_DIR/mcp"
mkdir -p "$MCP_DIR"

find "$TASK_DIR" -name "task.toml" | sort | while read task_toml; do
    task_dir=$(dirname "$task_toml")
    task_name=$(basename "$task_dir")
    
    output_dir="$MCP_DIR/$task_name"
    run_task_with_agent "$task_dir" "mcp" "$output_dir"
done

echo ""
echo "MCP runs complete. Results in: $MCP_DIR"
echo ""

# Summary
echo "============================================================"
echo "COMPARISON COMPLETE"
echo "============================================================"
echo ""
echo "Results directory: $JOB_DIR"
echo "  - Baseline results: $BASELINE_DIR"
echo "  - MCP results: $MCP_DIR"
echo ""
echo "Next steps:"
echo "  1. Compare reward scores:"
echo "     find $BASELINE_DIR -name 'reward.txt' | xargs cat"
echo "     find $MCP_DIR -name 'reward.txt' | xargs cat"
echo ""
echo "  2. Analyze trajectories:"
echo "     ls $BASELINE_DIR/*/log.txt"
echo "     ls $MCP_DIR/*/log.txt"
echo ""
echo "  3. Run comparison analysis:"
echo "     python scripts/analyze_dependeval_comparison.py $JOB_DIR"
