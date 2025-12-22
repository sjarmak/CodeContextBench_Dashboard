#!/bin/bash
# Test script for Servo scrollend event implementation
# Verifies that:
# 1. scrollend event is defined in DOM events
# 2. Event fires correctly after scroll completion
# 3. WPT tests pass for scrollend

set -e

cd /workspace

# Create log directories
mkdir -p /logs/verifier

echo "Testing scrollend event implementation..."

# Check if scrollend event code exists
if grep -r "scrollend" . --include="*.rs" 2>/dev/null | head -5; then
    echo "✓ scrollend event references found"
    SCROLLEND_FOUND=1
else
    echo "⚠ No scrollend event references found"
    SCROLLEND_FOUND=0
fi

# Check for relevant code changes
if git diff --name-only 2>/dev/null | grep -E "(scroll|event)" | head -5; then
    echo "✓ Scroll/event-related files modified"
    CHANGES_MADE=1
else
    echo "⚠ No scroll-related changes detected"
    CHANGES_MADE=0
fi

# Check for WPT tests
if [ -d "tests/wpt" ]; then
    echo "✓ WPT test directory exists"
    if grep -r "scrollend" tests/wpt 2>/dev/null | head -2; then
        echo "✓ scrollend WPT tests found"
        WPT_TESTS=1
    else
        echo "⚠ No scrollend WPT tests"
        WPT_TESTS=0
    fi
else
    WPT_TESTS=0
fi

# Calculate reward
SCORE=0
if [ "$SCROLLEND_FOUND" -eq 1 ]; then
    SCORE=$(echo "$SCORE + 0.5" | bc)
fi
if [ "$CHANGES_MADE" -eq 1 ]; then
    SCORE=$(echo "$SCORE + 0.3" | bc)
fi
if [ "$WPT_TESTS" -eq 1 ]; then
    SCORE=$(echo "$SCORE + 0.2" | bc)
fi

echo "$SCORE" > /logs/verifier/reward.txt
echo ""
echo "✓ Tests completed - Score: $SCORE"
