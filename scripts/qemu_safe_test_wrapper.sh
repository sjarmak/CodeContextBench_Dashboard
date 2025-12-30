#!/bin/bash
# QEMU-safe test wrapper for ARM64 Macs
# Runs tests and writes reward directly, bypassing segfaulting parser
# 
# Usage: Set HARBOR_TEST_WRAPPER=/path/to/this/script before running harbor

set -uo pipefail

LOG_FILE="${1:-/tmp/test.log}"
TEST_CMD="${2:-pytest}"

echo "=== QEMU-Safe Test Wrapper ==="
echo "Log file: $LOG_FILE"
echo "Test command: $TEST_CMD"

# Ensure verifier output directory exists
mkdir -p /logs/verifier

# Run the actual test command and capture exit code
if eval "$TEST_CMD" 2>&1 | tee "$LOG_FILE"; then
    TEST_RESULT=0
    REWARD=1
else
    TEST_RESULT=$?
    REWARD=0
fi

# Write reward directly (bypasses segfaulting parser)
echo "$REWARD" > /logs/verifier/reward.txt
chmod 644 /logs/verifier/reward.txt

# Write a success marker so Harbor knows verification completed
echo "VERIFICATION_COMPLETE" > /logs/verifier/verification.marker

echo ""
echo "=== Test Result ==="
echo "Exit code: $TEST_RESULT"
echo "Reward: $REWARD"
echo "Reward file: $(cat /logs/verifier/reward.txt)"

exit $TEST_RESULT
