#!/bin/bash
# scripts/compound/analyze-report.sh
# Analyzes a prioritized report and returns the top priority item as JSON

set -e

REPORT_FILE="$1"

if [ -z "$REPORT_FILE" ] || [ ! -f "$REPORT_FILE" ]; then
  echo '{"error": "No report file provided or file not found"}' >&2
  exit 1
fi

REPORT_CONTENT=$(cat "$REPORT_FILE")

# Use Claude to analyze the report and extract the top priority
claude -p "Analyze this prioritized report and return ONLY a JSON object (no markdown, no explanation) with two fields:
- priority_item: a one-line description of the #1 priority item
- branch_name: a git branch name (lowercase, hyphens, no spaces) like 'compound/short-description'

Report:
$REPORT_CONTENT" \
  --dangerously-skip-permissions \
  2>/dev/null
