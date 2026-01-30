#!/bin/bash
# scripts/compound/auto-compound.sh
# Nightly loop: review threads → research → create PRD → run Ralph loop → validate
# Schedule: 11:00 PM nightly via launchd

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

# Source environment if it exists
if [ -f .env.local ]; then
  source .env.local
fi

# Fetch latest (including tonight's CLAUDE.md updates from review job)
git fetch origin main
git reset --hard origin/main

# Create output directory for tonight's report
mkdir -p "$REPORT_DIR"

# ─────────────────────────────────────────────────────────────────────
# Phase 1: Research & Recommendations
# ─────────────────────────────────────────────────────────────────────
log "Phase 1: Producing nightly research report..."

claude -p "You are reviewing the CodeContextBench project to produce a nightly research report.

Read the following to understand the current state:
- AGENTS.md (project instructions and patterns)
- CLAUDE.md (compound learnings)
- README.md (project overview)
- benchmarks/locobench_agent/NEXT_RUN_RECOMMENDATIONS.md (latest benchmark findings)
- benchmarks/locobench_agent/HANDOFF_SUMMARY.md (current setup status)
- dashboard/ (UI code and views)
- reports/priorities.md (review focus areas)
- reports/nightly/ (previous nightly reports, to avoid repeating findings)

Then produce a report at reports/nightly/$DATE-review.md covering:

## 1. Benchmark Setup Review
- Are there issues with current adapter configs, verifier weights, or task generation?
- Any stale configs or outdated references?
- Are the agent variants well-differentiated for meaningful A/B comparison?

## 2. Dashboard & UI Improvements
- What views or features are missing from the Streamlit dashboard?
- What would make experiment results easier to interpret?
- Sketch specific UI flows that would improve the workflow

## 3. Evaluation Quality
- Review the verifier/scoring approach - are there blind spots?
- Suggest improvements to how agent performance is measured

## 4. Research Recommendations
- What recent papers, tools, or benchmark practices could improve CodeContextBench?
- Any ideas for new benchmark tasks or categories?

## 5. Recommended Next Feature
- Based on all findings, what is the SINGLE most impactful feature to build next?
- Describe it clearly enough that a PRD can be written from it

Be specific and reference actual files/code. Don't repeat findings from previous nightly reports.
Commit the report and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "Phase 1 complete."

# ─────────────────────────────────────────────────────────────────────
# Phase 2: Create PRD from top recommendation
# ─────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────
# Phase 3: Convert PRD to Ralph prd.json
# ─────────────────────────────────────────────────────────────────────
log "Phase 3: Converting PRD to Ralph format..."

claude -p "Read the PRD at tasks/prd-compound-$DATE.md and convert it into Ralph's prd.json format at the project root (prd.json).

The format must be:
{
  \"project\": \"CodeContextBench - [Feature Name]\",
  \"branchName\": \"ralph/compound-$DATE\",
  \"description\": \"[Feature description]\",
  \"userStories\": [
    {
      \"id\": \"US-001\",
      \"title\": \"[Story title]\",
      \"description\": \"As a [user], I want [feature] so that [benefit]\",
      \"acceptanceCriteria\": [\"Criterion 1\", \"Criterion 2\", \"Typecheck passes\"],
      \"priority\": 1,
      \"passes\": false,
      \"notes\": \"\"
    }
  ]
}

Rules:
- Stories must be ordered by dependency (implement foundations first)
- Each story should be completable in one Ralph iteration
- Always include 'Typecheck passes' in acceptance criteria
- Branch name must start with 'ralph/'
- All stories start with passes: false

Commit prd.json and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "Phase 3 complete."

# ─────────────────────────────────────────────────────────────────────
# Phase 4: Create feature branch and run Ralph loop
# ─────────────────────────────────────────────────────────────────────
log "Phase 4: Running Ralph loop..."

# Ralph needs to be on the feature branch - ralph.sh handles this via prd.json branchName
cd "$RALPH_DIR"
./ralph.sh --tool claude 20 2>&1 | tee -a "$LOG_FILE"
RALPH_EXIT=$?

cd "$PROJECT_DIR"

log "Ralph loop exited with code $RALPH_EXIT"

# ─────────────────────────────────────────────────────────────────────
# Phase 5: Run tests to validate
# ─────────────────────────────────────────────────────────────────────
log "Phase 5: Running tests to validate..."

# Get the branch name from prd.json
BRANCH_NAME=$(jq -r '.branchName' prd.json 2>/dev/null || echo "")

if [ -n "$BRANCH_NAME" ]; then
  git checkout "$BRANCH_NAME" 2>/dev/null || true

  # Run project tests
  python -m pytest tests/ -v --tb=short 2>&1 | tee -a "$LOG_FILE"
  TEST_EXIT=$?

  if [ $TEST_EXIT -eq 0 ]; then
    log "Tests PASSED"
  else
    log "Tests FAILED (exit code $TEST_EXIT)"
  fi

  # Push the branch and create a draft PR
  git push -u origin "$BRANCH_NAME" 2>&1 | tee -a "$LOG_FILE"

  # Count completed stories
  DONE=$(jq '[.userStories[] | select(.passes == true)] | length' prd.json 2>/dev/null || echo "0")
  TOTAL=$(jq '.userStories | length' prd.json 2>/dev/null || echo "0")

  gh pr create \
    --draft \
    --title "Compound $DATE: $(jq -r '.description' prd.json)" \
    --base main \
    --body "$(cat <<EOF
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
EOF
)" 2>&1 | tee -a "$LOG_FILE"

  log "Draft PR created."
else
  log "No branch name found in prd.json. Skipping test/PR phase."
fi

log "=== Nightly Compound Loop Complete ==="
