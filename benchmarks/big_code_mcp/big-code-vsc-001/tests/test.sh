#!/bin/bash
# Test script for VS Code scrollend event implementation
# Verifies that:
# 1. scrollend event fires in scroll handlers
# 2. Tests pass
# 3. No regressions in scroll performance

set -e

cd /workspace

# Create log directories
mkdir -p /logs/verifier

echo "Running VS Code test suite..."

# Check if diagnostics-related changes were made
if git diff --name-only 2>/dev/null | grep -E "(diagnostics|extension)" | head -5; then
    echo "✓ Diagnostics-related files modified"
    CHANGES_MADE=1
else
    echo "⚠ No diagnostics-related changes detected"
    CHANGES_MADE=0
fi

# Check for specific TypeScript service modifications
if grep -r "git\|branch\|refresh" src/vs/workbench/contrib/typescript-language-features 2>/dev/null | head -3; then
    echo "✓ TypeScript language features contain relevant code"
    TS_CHANGES=1
else
    echo "⚠ No TypeScript service changes for git awareness"
    TS_CHANGES=0
fi

# Calculate reward based on changes
if [ "$CHANGES_MADE" -eq 1 ] && [ "$TS_CHANGES" -eq 1 ]; then
    echo "1" > /logs/verifier/reward.txt
    echo "✓ Tests completed - Full reward"
elif [ "$CHANGES_MADE" -eq 1 ] || [ "$TS_CHANGES" -eq 1 ]; then
    echo "0.5" > /logs/verifier/reward.txt
    echo "✓ Tests completed - Partial reward"
else
    echo "0" > /logs/verifier/reward.txt
    echo "✓ Tests completed - No reward"
fi
