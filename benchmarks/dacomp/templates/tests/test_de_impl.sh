#!/bin/bash
set -e

TASK_DIR="/app/task"
ANSWER_PATH="{answer_path}"
OUTPUT_DB="{output_db}"

mkdir -p /logs/verifier

if [ -f "$TASK_DIR/$OUTPUT_DB" ]; then
    rm -f "$TASK_DIR/$OUTPUT_DB"
fi

cd "$TASK_DIR"

run_ok=0
if python3 run.py; then
    run_ok=1
fi

if [ $run_ok -eq 1 ] && [ -s "$TASK_DIR/$OUTPUT_DB" ] && [ -s "$ANSWER_PATH" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi

chmod 664 /logs/verifier/reward.txt 2>/dev/null || true
exit 0
