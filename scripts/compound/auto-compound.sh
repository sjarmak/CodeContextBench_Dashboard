#!/bin/bash
# scripts/compound/auto-compound.sh
# Nightly loop: review → research → PRD → Ralph loop → validate

set -e

PROJECT_DIR="/Users/sjarmak/CodeContextBench"
LOG_FILE="$PROJECT_DIR/logs/auto-compound.log"
DATE=$(date '+%Y-%m-%d')
REPORT_DIR="$PROJECT_DIR/reports/nightly"
RALPH_DIR="$PROJECT_DIR/scripts/ralph"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting Nightly Compound Loop ==="

cd "$PROJECT_DIR"

if [ -f .env.local ]; then
  source .env.local
fi

git fetch origin main
git reset --hard origin/main

mkdir -p "$REPORT_DIR"

# Phase 1: Research & Recommendations
log "Phase 1: Producing nightly research report..."

claude -p "You are reviewing the CodeContextBench project to produce a nightly research report.

Read the following to understand the current state:
- CLAUDE.md (compound learnings)
- README.md (project overview)
- reports/priorities.md (review focus areas)
- reports/nightly/ (previous nightly reports, to avoid repeating findings)

Then produce a report at reports/nightly/$DATE-review.md covering:

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
Commit the report and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "Phase 1 complete."

# Phase 2: Create PRD
log "Phase 2: Creating PRD from top recommendation..."

claude -p "Read tonight's nightly report at reports/nightly/$DATE-review.md.

Look at the 'Recommended Next Feature' section. Create a detailed Product Requirements Document (PRD) for that feature.

The PRD should include:
- Overview and motivation
- User stories with acceptance criteria
- Technical approach
- Edge cases and constraints
- Each user story must include 'Typecheck passes' in acceptance criteria where applicable
- Stories should be small enough to complete in one iteration

Save the PRD to tasks/prd-compound-$DATE.md" \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "Phase 2 complete."

# Phase 3: Convert PRD to Ralph format
log "Phase 3: Converting PRD to Ralph format..."

claude -p "Read the PRD at tasks/prd-compound-$DATE.md and convert it into Ralph's prd.json format at the project root (prd.json).

The format must be:
{
  \\"project\\": \\"CodeContextBench - [Feature Name]\\",
  \\"branchName\\": \\"ralph/compound-$DATE\\",
  \\"description\\": \\"[Feature description]\\",
  \\"userStories\\": [
    {
      \\"id\\": \\"US-001\\",
      \\"title\\": \\"[Story title]\\",
      \\"description\\": \\"As a [user], I want [feature] so that [benefit]\\",
      \\"acceptanceCriteria\\": [\\"Criterion 1\\", \\"Typecheck passes\\"],
      \\"priority\\": 1,
      \\"passes\\": false,
      \\"notes\\": \\"\\"
    }
  ]
}

Rules:
- Stories ordered by dependency
- Each story completable in one Ralph iteration
- Always include 'Typecheck passes' in acceptance criteria
- Branch name must start with 'ralph/'
- All stories start with passes: false

Commit prd.json and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "Phase 3 complete."

# Phase 4: Run Ralph loop
log "Phase 4: Running Ralph loop..."

if [ -f "$RALPH_DIR/ralph.sh" ]; then
  cd "$RALPH_DIR"
  ./ralph.sh --tool claude 20 2>&1 | tee -a "$LOG_FILE"
  RALPH_EXIT=$?
  cd "$PROJECT_DIR"
  log "Ralph loop exited with code $RALPH_EXIT"
else
  log "No ralph.sh found at $RALPH_DIR. Skipping implementation phase."
fi

# Phase 5: Run tests and create PR
log "Phase 5: Running tests to validate..."

BRANCH_NAME=$(jq -r '.branchName' prd.json 2>/dev/null || echo "")

if [ -n "$BRANCH_NAME" ]; then
  git checkout "$BRANCH_NAME" 2>/dev/null || true

  python -m pytest tests/ -v --tb=short 2>&1 | tee -a "$LOG_FILE"
  TEST_EXIT=$?

  if [ $TEST_EXIT -eq 0 ]; then
    log "Tests PASSED"
  else
    log "Tests FAILED (exit code $TEST_EXIT)"
  fi

  git push -u origin "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"

  DONE=$(jq '[.userStories[] | select(.passes == true)] | length' prd.json 2>/dev/null || echo "0")
  TOTAL=$(jq '.userStories | length' prd.json 2>/dev/null || echo "0")

  gh pr create \
    --draft \
    --title "Compound $DATE: $(jq -r '.description' prd.json)" \
    --base main \
    --body "$(cat <<PR_EOF
## Nightly Compound Engineering

**Date:** $DATE
**Stories completed:** $DONE/$TOTAL
**Tests:** $([ $TEST_EXIT -eq 0 ] && echo "PASSING" || echo "FAILING")

### Source
- Nightly report: reports/nightly/$DATE-review.md
- PRD: tasks/prd-compound-$DATE.md
- Progress: progress.txt

### What was built
$(jq -r '.userStories[] | select(.passes == true) | "- [x] " + .id + ": " + .title' prd.json 2>/dev/null)
$(jq -r '.userStories[] | select(.passes == false) | "- [ ] " + .id + ": " + .title' prd.json 2>/dev/null)

Generated by the nightly compound engineering loop.
PR_EOF
)" 2>&1 | tee -a "$LOG_FILE"

  log "Draft PR created."
else
  log "No branch name found in prd.json. Skipping test/PR phase."
fi

log "=== Nightly Compound Loop Complete ==="
