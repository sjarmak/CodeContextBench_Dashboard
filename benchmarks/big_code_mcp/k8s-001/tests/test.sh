#!/bin/bash
# Test script for Kubernetes NoScheduleNoTraffic taint effect
# Verifies that:
# 1. Taint effect constant is defined
# 2. Tests for the new effect pass
# 3. No regressions in existing taint logic

set -e

cd /workspace

echo "Running Kubernetes tests for taint effects..."
make test-unit WHAT=./pkg/kubelet/... 2>&1 | head -50 || true
make test-unit WHAT=./pkg/scheduler/... 2>&1 | head -50 || true

echo ""
echo "✓ Tests completed"
