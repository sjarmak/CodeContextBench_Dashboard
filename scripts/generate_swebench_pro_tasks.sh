#!/bin/bash
# Generate SWE-bench Pro Harbor tasks from the dataset
# Usage: ./generate_swebench_pro_tasks.sh [limit] [output_dir]

set -euo pipefail

LIMIT="${1:-10}"
OUTPUT_DIR="${2:-benchmarks/swebench_pro/tasks}"

echo "=== SWE-bench Pro Task Generation ==="
echo "Limit: $LIMIT instances"
echo "Output: $OUTPUT_DIR"
echo ""

# Check dependencies
if ! python3 -c "import datasets" 2>/dev/null; then
    echo "Installing datasets library..."
    pip install datasets
fi

# Navigate to adapter directory
cd "$(dirname "$0")/../benchmarks/swebench_pro"

# Run the adapter
echo "Generating tasks..."
python run_adapter.py \
    --all \
    --limit "$LIMIT" \
    --task-dir "$OUTPUT_DIR" \
    --enable-mcp \
    --overwrite

echo ""
echo "=== Generation Complete ==="
echo "Tasks created in: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Run a single task:"
echo "     harbor run --path $OUTPUT_DIR/<instance_id> \\"
echo "       --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \\"
echo "       --model anthropic/claude-haiku-4-5-20251001"
echo ""
echo "  2. Run comparison:"
echo "     ./scripts/run_swebench_pro_comparison.sh $OUTPUT_DIR"
