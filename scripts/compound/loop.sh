#!/bin/bash
# scripts/compound/loop.sh
# Iterative execution loop - runs Claude on tasks one at a time
# Usage: ./loop.sh [max_iterations]

set -e

MAX_ITERATIONS=${1:-25}
PROJECT_DIR="/Users/sjarmak/CodeContextBench"
LOG_FILE="$PROJECT_DIR/logs/auto-compound.log"
TASKS_FILE="$PROJECT_DIR/scripts/compound/prd.json"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [loop] $1" | tee -a "$LOG_FILE"
}

if [ ! -f "$TASKS_FILE" ]; then
  log "No tasks file found at $TASKS_FILE"
  exit 1
fi

cd "$PROJECT_DIR"

for i in $(seq 1 "$MAX_ITERATIONS"); do
  # Check if there are pending tasks
  PENDING=$(jq '[.tasks[] | select(.status == "pending")] | length' "$TASKS_FILE" 2>/dev/null || echo "0")

  if [ "$PENDING" -eq 0 ]; then
    log "All tasks complete after $i iterations."
    break
  fi

  log "Iteration $i/$MAX_ITERATIONS - $PENDING tasks remaining"

  # Get the next pending task
  NEXT_TASK=$(jq -r '[.tasks[] | select(.status == "pending")][0] | .title' "$TASKS_FILE")

  log "Working on: $NEXT_TASK"

  claude -p "Read the task list at scripts/compound/prd.json. Pick the first task with status 'pending'. Implement it following the acceptance criteria. After implementation:
1. Run any relevant tests to verify your work
2. Update the task status to 'done' in prd.json
3. Commit your changes with a descriptive message
If the task fails or you encounter blockers, update its status to 'blocked' and add a 'blocker_reason' field, then move to the next pending task." \
    --dangerously-skip-permissions \
    2>&1 | tee -a "$LOG_FILE"

  log "Iteration $i complete."
done

# Final summary
DONE=$(jq '[.tasks[] | select(.status == "done")] | length' "$TASKS_FILE" 2>/dev/null || echo "0")
TOTAL=$(jq '.tasks | length' "$TASKS_FILE" 2>/dev/null || echo "0")
log "Execution loop finished: $DONE/$TOTAL tasks completed."
