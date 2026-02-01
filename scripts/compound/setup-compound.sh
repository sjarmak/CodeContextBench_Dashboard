#!/bin/bash
# setup-compound.sh
# Set up the nightly compound engineering loop for any project
#
# Usage:
#   ./setup-compound.sh /path/to/project
#   ./setup-compound.sh /path/to/project --review-hour 1 --review-min 0 --compound-hour 1 --compound-min 30
#
# This creates:
#   - scripts/compound/ and scripts/daily-compound-review.sh in the project
#   - LaunchAgent plists in ~/Library/LaunchAgents/
#   - logs/, reports/nightly/, and CLAUDE.md if missing

set -e

# ─────────────────────────────────────────────────────────────────────
# Parse arguments
# ─────────────────────────────────────────────────────────────────────
PROJECT_DIR=""
REVIEW_HOUR=22
REVIEW_MIN=30
COMPOUND_HOUR=23
COMPOUND_MIN=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --review-hour) REVIEW_HOUR="$2"; shift 2 ;;
    --review-min) REVIEW_MIN="$2"; shift 2 ;;
    --compound-hour) COMPOUND_HOUR="$2"; shift 2 ;;
    --compound-min) COMPOUND_MIN="$2"; shift 2 ;;
    *)
      if [ -z "$PROJECT_DIR" ]; then
        PROJECT_DIR="$1"
      fi
      shift ;;
  esac
done

if [ -z "$PROJECT_DIR" ]; then
  echo "Usage: ./setup-compound.sh /path/to/project [--review-hour H] [--review-min M] [--compound-hour H] [--compound-min M]"
  exit 1
fi

# Resolve to absolute path
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
USER_HOME="$HOME"
USERNAME="$(whoami)"

# Derive the claude-archive folder name (matches claude-code-transcripts convention)
ARCHIVE_NAME="$USERNAME-$PROJECT_NAME"

# Sanitize project name for launchd label (lowercase, hyphens to dots)
LABEL_BASE="com.compound.$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | tr ' _' '-')"

echo "Setting up compound engineering for: $PROJECT_DIR"
echo "  Project name: $PROJECT_NAME"
echo "  Archive dir:  $USER_HOME/claude-archive/$ARCHIVE_NAME"
echo "  Review time:  $(printf '%02d:%02d' $REVIEW_HOUR $REVIEW_MIN)"
echo "  Compound time: $(printf '%02d:%02d' $COMPOUND_HOUR $COMPOUND_MIN)"
echo "  Label prefix: $LABEL_BASE"
echo ""

# ─────────────────────────────────────────────────────────────────────
# Create project directories
# ─────────────────────────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/reports/nightly"
mkdir -p "$PROJECT_DIR/scripts/compound"

# Create CLAUDE.md if it doesn't exist
if [ ! -f "$PROJECT_DIR/CLAUDE.md" ]; then
  cat > "$PROJECT_DIR/CLAUDE.md" << 'CLAUDE_EOF'
# Compound Engineering - Claude Code Memory

This file is automatically updated by the nightly compound review loop.
It captures patterns, learnings, and context from each development session.

## Project Overview

<!-- Add project overview here -->

## Patterns

<!-- Learnings and patterns will be added here automatically -->

## Gotchas

<!-- Known issues and workarounds will be added here automatically -->

## Architecture Decisions

<!-- Key decisions and their rationale will be added here automatically -->

## Debugging Notes

<!-- Debugging insights will be added here automatically -->
CLAUDE_EOF
  echo "Created CLAUDE.md"
fi

# Create priorities.md if it doesn't exist
if [ ! -f "$PROJECT_DIR/reports/priorities.md" ]; then
  cat > "$PROJECT_DIR/reports/priorities.md" << 'PRIORITIES_EOF'
# Nightly Review Focus Areas

The nightly loop produces a research report each night at `reports/nightly/YYYY-MM-DD-review.md`.
Edit these focus areas to guide what the nightly review covers.

## Code Quality
- Review for stale code, outdated patterns, or technical debt
- Flag broken tests or missing coverage

## Architecture
- Identify architectural improvements
- Propose refactoring opportunities

## Features
- Suggest the most impactful next feature to build
- Review current feature gaps

## Research
- Surface relevant tools, libraries, or techniques
- Identify best practices from similar projects
PRIORITIES_EOF
  echo "Created reports/priorities.md"
fi

# ─────────────────────────────────────────────────────────────────────
# Create the review script
# ─────────────────────────────────────────────────────────────────────
cat > "$PROJECT_DIR/scripts/daily-compound-review.sh" << REVIEW_EOF
#!/bin/bash
# scripts/daily-compound-review.sh
# Exports Claude Code transcripts, then reviews them for learnings

set -e

PROJECT_DIR="$PROJECT_DIR"
ARCHIVE_DIR="$USER_HOME/claude-archive/$ARCHIVE_NAME"
LOG_FILE="\$PROJECT_DIR/logs/compound-review.log"

log() {
  echo "[\$(date '+%Y-%m-%d %H:%M:%S')] \$1" | tee -a "\$LOG_FILE"
}

log "=== Starting Compound Review ==="

cd "\$PROJECT_DIR"

git checkout main
git pull origin main

log "Exporting Claude Code transcripts..."
claude-code-transcripts all 2>&1 | tee -a "\$LOG_FILE"

log "Running Claude Code compound review..."

claude -p "You are extracting learnings from recent Claude Code sessions for the $PROJECT_NAME project.

The transcripts are HTML files at \$ARCHIVE_DIR/. Each subdirectory is a session, containing index.html and page-NNN.html files.

Steps:
1. List the session directories in \$ARCHIVE_DIR
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

Focus on actionable learnings that will help future sessions. Skip sessions you've already reviewed (check if the learnings are already in CLAUDE.md)." \\
  --dangerously-skip-permissions \\
  2>&1 | tee -a "\$LOG_FILE"

log "=== Compound Review Complete ==="
REVIEW_EOF

chmod +x "$PROJECT_DIR/scripts/daily-compound-review.sh"
echo "Created scripts/daily-compound-review.sh"

# ─────────────────────────────────────────────────────────────────────
# Create the auto-compound script
# ─────────────────────────────────────────────────────────────────────
cat > "$PROJECT_DIR/scripts/compound/auto-compound.sh" << 'COMPOUND_HEADER'
#!/bin/bash
# scripts/compound/auto-compound.sh
# Nightly loop: review → research → PRD → Ralph loop → validate

set -e
COMPOUND_HEADER

cat >> "$PROJECT_DIR/scripts/compound/auto-compound.sh" << COMPOUND_EOF

PROJECT_DIR="$PROJECT_DIR"
LOG_FILE="\$PROJECT_DIR/logs/auto-compound.log"
DATE=\$(date '+%Y-%m-%d')
REPORT_DIR="\$PROJECT_DIR/reports/nightly"
RALPH_DIR="\$PROJECT_DIR/scripts/ralph"

log() {
  echo "[\$(date '+%Y-%m-%d %H:%M:%S')] \$1" | tee -a "\$LOG_FILE"
}

log "=== Starting Nightly Compound Loop ==="

cd "\$PROJECT_DIR"

if [ -f .env.local ]; then
  source .env.local
fi

git fetch origin main
git reset --hard origin/main

mkdir -p "\$REPORT_DIR"

# Phase 1: Research & Recommendations
log "Phase 1: Producing nightly research report..."

claude -p "You are reviewing the $PROJECT_NAME project to produce a nightly research report.

Read the following to understand the current state:
- CLAUDE.md (compound learnings)
- README.md (project overview)
- reports/priorities.md (review focus areas)
- reports/nightly/ (previous nightly reports, to avoid repeating findings)

Then produce a report at reports/nightly/\$DATE-review.md covering:

## 1. Code & Architecture Review
- Are there issues, stale configs, or technical debt?
- What improvements would have the most impact?

## 2. Feature & UX Improvements
- What's missing or could be improved?
- Sketch specific improvements

## 3. Research Recommendations
- What tools, libraries, or practices could improve the project?

## 4. Recommended Next Feature
- Based on all findings, what is the SINGLE most impactful feature to build next?
- Describe it clearly enough that a PRD can be written from it

Be specific and reference actual files/code. Don't repeat findings from previous nightly reports.
Commit the report and push to main." \\
  --dangerously-skip-permissions \\
  2>&1 | tee -a "\$LOG_FILE"

log "Phase 1 complete."

# Phase 2: Create PRD
log "Phase 2: Creating PRD from top recommendation..."

claude -p "Read tonight's nightly report at reports/nightly/\$DATE-review.md.

Look at the 'Recommended Next Feature' section. Create a detailed Product Requirements Document (PRD) for that feature.

The PRD should include:
- Overview and motivation
- User stories with acceptance criteria
- Technical approach
- Edge cases and constraints
- Each user story must include 'Typecheck passes' in acceptance criteria where applicable
- Stories should be small enough to complete in one iteration

Save the PRD to tasks/prd-compound-\$DATE.md" \\
  --dangerously-skip-permissions \\
  2>&1 | tee -a "\$LOG_FILE"

log "Phase 2 complete."

# Phase 3: Convert PRD to Ralph format
log "Phase 3: Converting PRD to Ralph format..."

claude -p "Read the PRD at tasks/prd-compound-\$DATE.md and convert it into Ralph's prd.json format at the project root (prd.json).

The format must be:
{
  \\\"project\\\": \\\"$PROJECT_NAME - [Feature Name]\\\",
  \\\"branchName\\\": \\\"ralph/compound-\$DATE\\\",
  \\\"description\\\": \\\"[Feature description]\\\",
  \\\"userStories\\\": [
    {
      \\\"id\\\": \\\"US-001\\\",
      \\\"title\\\": \\\"[Story title]\\\",
      \\\"description\\\": \\\"As a [user], I want [feature] so that [benefit]\\\",
      \\\"acceptanceCriteria\\\": [\\\"Criterion 1\\\", \\\"Typecheck passes\\\"],
      \\\"priority\\\": 1,
      \\\"passes\\\": false,
      \\\"notes\\\": \\\"\\\"
    }
  ]
}

Rules:
- Stories ordered by dependency
- Each story completable in one Ralph iteration
- Always include 'Typecheck passes' in acceptance criteria
- Branch name must start with 'ralph/'
- All stories start with passes: false

Commit prd.json and push to main." \\
  --dangerously-skip-permissions \\
  2>&1 | tee -a "\$LOG_FILE"

log "Phase 3 complete."

# Phase 4: Run Ralph loop
log "Phase 4: Running Ralph loop..."

if [ -f "\$RALPH_DIR/ralph.sh" ]; then
  cd "\$RALPH_DIR"
  ./ralph.sh --tool claude 20 2>&1 | tee -a "\$LOG_FILE"
  RALPH_EXIT=\$?
  cd "\$PROJECT_DIR"
  log "Ralph loop exited with code \$RALPH_EXIT"
else
  log "No ralph.sh found at \$RALPH_DIR. Skipping implementation phase."
fi

# Phase 5: Run tests and create PR
log "Phase 5: Running tests to validate..."

BRANCH_NAME=\$(jq -r '.branchName' prd.json 2>/dev/null || echo "")

if [ -n "\$BRANCH_NAME" ]; then
  git checkout "\$BRANCH_NAME" 2>/dev/null || true

  python -m pytest tests/ -v --tb=short 2>&1 | tee -a "\$LOG_FILE"
  TEST_EXIT=\$?

  if [ \$TEST_EXIT -eq 0 ]; then
    log "Tests PASSED"
  else
    log "Tests FAILED (exit code \$TEST_EXIT)"
  fi

  git push -u origin "\$BRANCH_NAME" 2>&1 | tee -a "\$LOG_FILE"

  DONE=\$(jq '[.userStories[] | select(.passes == true)] | length' prd.json 2>/dev/null || echo "0")
  TOTAL=\$(jq '.userStories | length' prd.json 2>/dev/null || echo "0")

  gh pr create \\
    --draft \\
    --title "Compound \$DATE: \$(jq -r '.description' prd.json)" \\
    --base main \\
    --body "\$(cat <<PR_EOF
## Nightly Compound Engineering

**Date:** \$DATE
**Stories completed:** \$DONE/\$TOTAL
**Tests:** \$([ \$TEST_EXIT -eq 0 ] && echo "PASSING" || echo "FAILING")

### Source
- Nightly report: reports/nightly/\$DATE-review.md
- PRD: tasks/prd-compound-\$DATE.md
- Progress: progress.txt

### What was built
\$(jq -r '.userStories[] | select(.passes == true) | "- [x] " + .id + ": " + .title' prd.json 2>/dev/null)
\$(jq -r '.userStories[] | select(.passes == false) | "- [ ] " + .id + ": " + .title' prd.json 2>/dev/null)

Generated by the nightly compound engineering loop.
PR_EOF
)" 2>&1 | tee -a "\$LOG_FILE"

  log "Draft PR created."
else
  log "No branch name found in prd.json. Skipping test/PR phase."
fi

log "=== Nightly Compound Loop Complete ==="
COMPOUND_EOF

chmod +x "$PROJECT_DIR/scripts/compound/auto-compound.sh"
echo "Created scripts/compound/auto-compound.sh"

# ─────────────────────────────────────────────────────────────────────
# Create the toggle script
# ─────────────────────────────────────────────────────────────────────
cat > "$PROJECT_DIR/scripts/compound/toggle.sh" << TOGGLE_EOF
#!/bin/bash
# scripts/compound/toggle.sh
# Toggle the nightly compound loop on/off
#
# Usage:
#   ./toggle.sh          # Show current status
#   ./toggle.sh on       # Enable the nightly loop
#   ./toggle.sh off      # Disable the nightly loop

LABEL_REVIEW="$LABEL_BASE.review"
LABEL_COMPOUND="$LABEL_BASE.compound"
PLIST_REVIEW="$USER_HOME/Library/LaunchAgents/\$LABEL_REVIEW.plist"
PLIST_COMPOUND="$USER_HOME/Library/LaunchAgents/\$LABEL_COMPOUND.plist"

is_loaded() {
  launchctl list 2>/dev/null | grep -q "\$1"
}

show_status() {
  echo "Compound Engineering Loop: $PROJECT_NAME"
  echo "─────────────────────────────────────────"
  if is_loaded "\$LABEL_REVIEW"; then
    echo "  Review ($(printf '%02d:%02d' $REVIEW_HOUR $REVIEW_MIN)):    ON"
  else
    echo "  Review ($(printf '%02d:%02d' $REVIEW_HOUR $REVIEW_MIN)):    OFF"
  fi
  if is_loaded "\$LABEL_COMPOUND"; then
    echo "  Compound ($(printf '%02d:%02d' $COMPOUND_HOUR $COMPOUND_MIN)): ON"
  else
    echo "  Compound ($(printf '%02d:%02d' $COMPOUND_HOUR $COMPOUND_MIN)): OFF"
  fi
}

case "\${1:-status}" in
  on)
    echo "Enabling nightly loop for $PROJECT_NAME..."
    launchctl load "\$PLIST_REVIEW" 2>/dev/null && echo "  Review: loaded" || echo "  Review: already loaded"
    launchctl load "\$PLIST_COMPOUND" 2>/dev/null && echo "  Compound: loaded" || echo "  Compound: already loaded"
    echo ""
    show_status
    ;;
  off)
    echo "Disabling nightly loop for $PROJECT_NAME..."
    launchctl unload "\$PLIST_REVIEW" 2>/dev/null && echo "  Review: unloaded" || echo "  Review: already unloaded"
    launchctl unload "\$PLIST_COMPOUND" 2>/dev/null && echo "  Compound: unloaded" || echo "  Compound: already unloaded"
    echo ""
    show_status
    ;;
  status|"")
    show_status
    ;;
  *)
    echo "Usage: ./toggle.sh [on|off|status]"
    exit 1
    ;;
esac
TOGGLE_EOF

chmod +x "$PROJECT_DIR/scripts/compound/toggle.sh"
echo "Created scripts/compound/toggle.sh"

# ─────────────────────────────────────────────────────────────────────
# Create LaunchAgent plists
# ─────────────────────────────────────────────────────────────────────
PLIST_DIR="$USER_HOME/Library/LaunchAgents"

# Review plist
cat > "$PLIST_DIR/$LABEL_BASE.review.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL_BASE.review</string>
	<key>ProgramArguments</key>
	<array>
		<string>$PROJECT_DIR/scripts/daily-compound-review.sh</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$PROJECT_DIR</string>
	<key>StartCalendarInterval</key>
	<dict>
		<key>Hour</key>
		<integer>$REVIEW_HOUR</integer>
		<key>Minute</key>
		<integer>$REVIEW_MIN</integer>
	</dict>
	<key>StandardOutPath</key>
	<string>$PROJECT_DIR/logs/compound-review.log</string>
	<key>StandardErrorPath</key>
	<string>$PROJECT_DIR/logs/compound-review.log</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
		<key>HOME</key>
		<string>$USER_HOME</string>
	</dict>
</dict>
</plist>
PLIST_EOF

echo "Created $PLIST_DIR/$LABEL_BASE.review.plist"

# Compound plist
cat > "$PLIST_DIR/$LABEL_BASE.compound.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL_BASE.compound</string>
	<key>ProgramArguments</key>
	<array>
		<string>$PROJECT_DIR/scripts/compound/auto-compound.sh</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$PROJECT_DIR</string>
	<key>StartCalendarInterval</key>
	<dict>
		<key>Hour</key>
		<integer>$COMPOUND_HOUR</integer>
		<key>Minute</key>
		<integer>$COMPOUND_MIN</integer>
	</dict>
	<key>StandardOutPath</key>
	<string>$PROJECT_DIR/logs/auto-compound.log</string>
	<key>StandardErrorPath</key>
	<string>$PROJECT_DIR/logs/auto-compound.log</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>$USER_HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
		<key>HOME</key>
		<string>$USER_HOME</string>
	</dict>
</dict>
</plist>
PLIST_EOF

echo "Created $PLIST_DIR/$LABEL_BASE.compound.plist"

# ─────────────────────────────────────────────────────────────────────
# Load the agents
# ─────────────────────────────────────────────────────────────────────
launchctl load "$PLIST_DIR/$LABEL_BASE.review.plist" 2>/dev/null
launchctl load "$PLIST_DIR/$LABEL_BASE.compound.plist" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Compound engineering set up for: $PROJECT_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Review:   $(printf '%02d:%02d' $REVIEW_HOUR $REVIEW_MIN) nightly"
echo "  Compound: $(printf '%02d:%02d' $COMPOUND_HOUR $COMPOUND_MIN) nightly"
echo ""
echo "  Toggle:   $PROJECT_DIR/scripts/compound/toggle.sh [on|off]"
echo "  Logs:     $PROJECT_DIR/logs/"
echo "  Reports:  $PROJECT_DIR/reports/nightly/"
echo ""
echo "  Note: Make sure the caffeinate LaunchAgent is running"
echo "  to keep your Mac awake during the nightly window."
echo ""
