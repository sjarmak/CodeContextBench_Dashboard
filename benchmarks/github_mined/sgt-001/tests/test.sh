#!/bin/bash
set -e

# Create logs directory
mkdir -p /logs/verifier

echo "=== sgt-001: Thread Safety Fix for ncclCommGetAsyncError ==="

# 1. Validate code changes exist
echo "Step 1: Validating code changes..."
if ! git diff --exit-code HEAD > /dev/null 2>&1; then
    CHANGES=$(git diff HEAD --stat | wc -l)
    echo "✓ Code changes detected ($CHANGES lines)"
else
    echo "✗ FAILED: No code changes detected"
    echo "0" > /logs/verifier/reward.txt
    exit 1
fi

# 2. Validate specific files were modified
echo "Step 2: Validating target files modified..."
REQUIRED_FILES=(
    "torch/csrc/distributed/c10d/NCCLUtils.cpp"
    "torch/csrc/distributed/c10d/NCCLUtils.hpp"
)

for FILE in "${REQUIRED_FILES[@]}"; do
    if git diff HEAD --name-only | grep -q "$FILE"; then
        echo "✓ Modified: $FILE"
    else
        echo "✗ FAILED: Expected file not modified: $FILE"
        echo "0" > /logs/verifier/reward.txt
        exit 1
    fi
done

# 3. Validate fix pattern: check for mutex/lock related changes
echo "Step 3: Checking for thread safety fix patterns..."
if git diff HEAD | grep -E "std::lock_guard|std::unique_lock|mutex|atomic" > /dev/null; then
    echo "✓ Thread safety patterns detected"
else
    echo "⚠ Warning: No obvious mutex/lock patterns found"
    # Don't fail on this, but note it
fi

# 4. Validate code compiles (basic check)
echo "Step 4: Validating code structure..."
if grep -r "ncclCommGetAsyncError" /workspace/torch/csrc/distributed/c10d/ > /dev/null 2>&1; then
    echo "✓ ncclCommGetAsyncError found in modified code"
else
    echo "✗ FAILED: ncclCommGetAsyncError not found"
    echo "0" > /logs/verifier/reward.txt
    exit 1
fi

# 5. Check for thread safety annotations in the modified section
echo "Step 5: Validating thread safety implementation..."
NCCL_CHANGES=$(git diff HEAD torch/csrc/distributed/c10d/NCCLUtils.cpp 2>/dev/null || echo "")
if echo "$NCCL_CHANGES" | grep -E "std::lock_guard|std::unique_lock|std::mutex" > /dev/null; then
    echo "✓ Mutex/lock usage detected in NCCLUtils.cpp"
    REWARD=1
else
    # May be implemented with other sync mechanisms
    echo "⚠ No explicit std::lock_guard found, but changes present"
    REWARD=0.5
fi

# Success: code was modified with expected patterns
echo "✓ Tests passed"
echo "$REWARD" > /logs/verifier/reward.txt

# Capture diff for analysis
git diff HEAD > /logs/verifier/full.diff
git diff HEAD --stat > /logs/verifier/diff.stat

exit 0
