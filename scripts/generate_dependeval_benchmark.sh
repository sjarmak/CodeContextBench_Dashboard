#!/bin/bash
#
# Generate DependEval benchmark tasks for Phase 3 evaluation.
#
# This generates a small set of tasks from DependEval for Dependency Recognition,
# Repository Construction, and Multi-file Editing to test Sourcegraph MCP effectiveness.
#

set -e

echo "Generating DependEval benchmark tasks for Phase 3..."
echo ""

# Navigate to adapter directory
ADAPTER_DIR="/Users/sjarmak/harbor/adapters/dependeval"
DATA_DIR="/Users/sjarmak/DependEval/data"
OUTPUT_BASE="/Users/sjarmak/CodeContextBench/benchmarks/dependeval_benchmark"

cd "$ADAPTER_DIR"

# Create output directory
mkdir -p "$OUTPUT_BASE"

echo "Output directory: $OUTPUT_BASE"
echo ""

# Function to generate tasks for a language and task type
generate_tasks() {
    local language=$1
    local task_file=$2
    local task_type=$3
    local limit=$4
    
    local data_file=$(find "$DATA_DIR/$language" -name "$task_file*.json" | head -1)
    
    if [ ! -f "$data_file" ]; then
        echo "⚠ Skipping $language $task_type: data file not found"
        return
    fi
    
    local output_dir="$OUTPUT_BASE/${task_type}_${language}"
    
    echo "Generating: $language $task_type (limit: $limit)"
    python run_adapter.py \
        --data_path "$data_file" \
        --task_type "$task_type" \
        --language "$language" \
        --limit "$limit" \
        --output_dir "$output_dir" \
        2>&1 | grep -E "(Generating|Successfully|error)" || true
}

# Generate tasks for key languages
# Focus on Python, Java, JavaScript as they're most common

echo "============================================================"
echo "Dependency Recognition (DR) Tasks"
echo "============================================================"
generate_tasks "python" "task1_python" "DR" 3
generate_tasks "java" "task1_java" "DR" 3
generate_tasks "javascript" "task1_javascript" "DR" 3

echo ""
echo "============================================================"
echo "Repository Construction (RC) Tasks"
echo "============================================================"
generate_tasks "python" "task2_python" "RC" 2
generate_tasks "java" "task2_java" "RC" 2
generate_tasks "javascript" "task2_javascript" "RC" 2

echo ""
echo "============================================================"
echo "Multi-file Editing (ME) Tasks"
echo "============================================================"
generate_tasks "python" "task4_python" "ME" 2
generate_tasks "java" "task4_java" "ME" 2
generate_tasks "javascript" "task4_javascript" "ME" 2

echo ""
echo "============================================================"
echo "Summary"
echo "============================================================"

# Count generated tasks
total_tasks=$(find "$OUTPUT_BASE" -maxdepth 2 -name "task.toml" | wc -l)
echo "Total tasks generated: $total_tasks"

echo ""
echo "Tasks created in: $OUTPUT_BASE"
echo ""
echo "Next steps:"
echo "  1. Run baseline: harbor run --task <task> --agent claude-code"
echo "  2. Run with MCP: harbor run --task <task> --agent claude-code-with-mcp"
echo "  3. Compare results to see if MCP improves performance"
