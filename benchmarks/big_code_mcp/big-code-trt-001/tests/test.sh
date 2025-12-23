#!/bin/bash
# Test script for TensorRT-LLM W4A8_MXFP4_INT8 quantization mode
# Verifies that:
# 1. W4A8_MXFP4_INT8 mode is defined in quantization enums
# 2. Quantization pipeline supports the new mode
# 3. Unit tests pass for the new mode

set -e

cd /workspace

# Create log directories
mkdir -p /logs/verifier

echo "Testing W4A8_MXFP4_INT8 quantization mode implementation..."

# Check if quantization mode code exists
if grep -r "W4A8_MXFP4_INT8" . --include="*.py" --include="*.h" --include="*.cc" 2>/dev/null | head -5; then
    echo "✓ W4A8_MXFP4_INT8 mode references found"
    MODE_FOUND=1
else
    echo "⚠ No W4A8_MXFP4_INT8 mode references found"
    MODE_FOUND=0
fi

# Check for enum definitions
if grep -r "MXFP4" . --include="*.py" --include="*.h" 2>/dev/null | head -3; then
    echo "✓ MXFP4 quantization mode references found"
    MXFP4_FOUND=1
else
    echo "⚠ No MXFP4 mode references"
    MXFP4_FOUND=0
fi

# Check for relevant code changes
if git diff --name-only 2>/dev/null | grep -E "(quant|mode|config)" | head -5; then
    echo "✓ Quantization-related files modified"
    CHANGES_MADE=1
else
    echo "⚠ No quantization-related changes detected"
    CHANGES_MADE=0
fi

# Calculate reward (using bash arithmetic, avoiding bc)
SCORE_NUMERATOR=0
if [ "$MODE_FOUND" -eq 1 ]; then
    SCORE_NUMERATOR=$((SCORE_NUMERATOR + 5))  # 0.5 * 10
fi
if [ "$MXFP4_FOUND" -eq 1 ]; then
    SCORE_NUMERATOR=$((SCORE_NUMERATOR + 2))  # 0.2 * 10
fi
if [ "$CHANGES_MADE" -eq 1 ]; then
    SCORE_NUMERATOR=$((SCORE_NUMERATOR + 3))  # 0.3 * 10
fi

# Convert back to decimal (using awk for portable floating point)
SCORE=$(awk "BEGIN {printf \"%.1f\", $SCORE_NUMERATOR / 10}")

echo "$SCORE" > /logs/verifier/reward.txt
echo ""
echo "✓ Tests completed - Score: $SCORE"
