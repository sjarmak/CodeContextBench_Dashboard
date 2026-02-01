#!/bin/bash
# scripts/daily-compound-review.sh
# Exports Claude Code transcripts, then reviews them for learnings

set -e

PROJECT_DIR="/Users/sjarmak/CodeContextBench"
ARCHIVE_DIR="/Users/sjarmak/claude-archive/sjarmak-CodeContextBench"
LOG_FILE="$PROJECT_DIR/logs/compound-review.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting Compound Review ==="

cd "$PROJECT_DIR"

git checkout main
git pull origin main

log "Exporting Claude Code transcripts..."
claude-code-transcripts all 2>&1 | tee -a "$LOG_FILE"

log "Running Claude Code compound review..."

claude -p "You are extracting learnings from recent Claude Code sessions for the CodeContextBench project.

The transcripts are HTML files at $ARCHIVE_DIR/. Each subdirectory is a session, containing index.html and page-NNN.html files.

Steps:
1. List the session directories in $ARCHIVE_DIR
2. Read the HTML pages from sessions that look recent (check file modification times)
3. For each recent session, extract:
   - What was worked on
   - Patterns discovered
   - Gotchas or bugs encountered
   - Architectural decisions made
   - Debugging insights
   - What went well or poorly
4. Update CLAUDE.md with any new learnings that aren't already captured
5. Commit your changes and push to main

Focus on actionable learnings that will help future sessions. Skip sessions you've already reviewed (check if the learnings are already in CLAUDE.md)." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "=== Compound Review Complete ==="
