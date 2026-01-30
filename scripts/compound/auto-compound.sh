#!/bin/bash
# scripts/compound/auto-compound.sh
# Nightly research & review loop
# Reviews the benchmark setup, researches improvements, and writes recommendations
# Schedule: 11:00 PM nightly via launchd

set -e

PROJECT_DIR="/Users/sjarmak/CodeContextBench"
LOG_FILE="$PROJECT_DIR/logs/auto-compound.log"
DATE=$(date '+%Y-%m-%d')
REPORT_DIR="$PROJECT_DIR/reports/nightly"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting Nightly Review ==="

cd "$PROJECT_DIR"

# Source environment if it exists
if [ -f .env.local ]; then
  source .env.local
fi

# Fetch latest (including tonight's CLAUDE.md updates)
git fetch origin main
git reset --hard origin/main

# Create output directory for tonight's report
mkdir -p "$REPORT_DIR"

log "Running nightly benchmark review..."

claude -p "You are reviewing the CodeContextBench project to produce a nightly research report.

Read the following to understand the current state:
- AGENTS.md (project instructions and patterns)
- CLAUDE.md (compound learnings)
- README.md (project overview)
- benchmarks/locobench_agent/NEXT_RUN_RECOMMENDATIONS.md (latest benchmark findings)
- benchmarks/locobench_agent/HANDOFF_SUMMARY.md (current setup status)
- dashboard/ (UI code and views)
- reports/priorities.md (current priorities)
- reports/nightly/ (previous nightly reports, to avoid repeating findings)

Then produce a report at reports/nightly/$DATE-review.md covering:

## 1. Benchmark Setup Review
- Are there issues with current adapter configs, verifier weights, or task generation?
- Any stale configs or outdated references?
- Are the agent variants well-differentiated for meaningful A/B comparison?

## 2. Dashboard & UI Improvements
- What views or features are missing from the Streamlit dashboard?
- What would make experiment results easier to interpret?
- Sketch specific UI flows that would improve the workflow (e.g. triggering runs, comparing agents, drilling into traces)

## 3. Evaluation Quality
- Review the verifier/scoring approach - are there blind spots?
- Suggest improvements to how agent performance is measured
- Look at how other benchmarks (SWE-bench, etc.) evaluate and see if we can learn from them

## 4. Research Recommendations
- What recent papers, tools, or benchmark practices could improve CodeContextBench?
- Are there new agent evaluation techniques worth adopting?
- Any ideas for new benchmark tasks or categories?

## 5. Action Items
- Concrete, prioritized list of things to work on next
- Distinguish between quick wins and larger efforts
- Do NOT repeat action items from previous nightly reports unless they are still unresolved

Be specific and reference actual files/code in the project. Don't be vague.
Commit the report and push to main." \
  --dangerously-skip-permissions \
  2>&1 | tee -a "$LOG_FILE"

log "=== Nightly Review Complete ==="
