#!/bin/bash
# scripts/daily-compound-review.sh
# Runs BEFORE auto-compound.sh to update CLAUDE.md with learnings
# Schedule: 10:30 PM nightly via launchd

set -e

PROJECT_DIR="/Users/sjarmak/CodeContextBench"
LOG_FILE="$PROJECT_DIR/logs/compound-review.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting Compound Review ==="

cd "$PROJECT_DIR"

# Ensure we're on main and up to date
git checkout main
git pull origin main

log "Running Claude Code compound review..."

claude -p "Look through and read each Claude Code conversation thread from the last 24 hours. For any thread where we did NOT extract and compound learnings at the end, do so now - extract the key learnings from that thread and update the relevant CLAUDE.md files so we can learn from our work and mistakes. Focus on: patterns discovered, gotchas encountered, architectural decisions made, and debugging insights. Commit your changes and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "=== Compound Review Complete ==="
