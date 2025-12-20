#!/bin/bash
# DI-Bench Test Script
# Runs the project's CI/CD tests to verify dependency configurations

set -e

cd /app/repo

# Create logs directory for Harbor
mkdir -p /logs/verifier

# Initialize test result
test_passed=0

# Run the act command to execute CI/CD tests
echo "Running CI/CD tests with: act -j 'test' --matrix python-version:3.8 --matrix os:ubuntu-latest -W '.github/workflows/tests.yml'"
echo "CI file: .github/workflows/tests.yml"

# Configure act if not already configured
if [ ! -f /root/.config/act/actrc ]; then
    mkdir -p /root/.config/act
    echo "-P ubuntu-latest=catthehacker/ubuntu:act-latest" > /root/.config/act/actrc
fi

# Execute the tests and capture the result
if act -j 'test' --matrix python-version:3.8 --matrix os:ubuntu-latest -W '.github/workflows/tests.yml'; then
    echo "✓ All tests passed!"
    test_passed=1
else
    echo "✗ Tests failed"
    test_passed=0
fi

# Write reward for Harbor (1 for pass, 0 for fail)
echo "$test_passed" > /logs/verifier/reward.txt

# Ensure proper permissions
chmod 664 /logs/verifier/reward.txt 2>/dev/null || true

# Always exit 0 for Harbor compatibility
exit 0
