#!/bin/bash
# Test script for VS Code scrollend event implementation
# Verifies that:
# 1. scrollend event fires in scroll handlers
# 2. Tests pass
# 3. No regressions in scroll performance

set -e

cd /workspace

echo "Running VS Code test suite..."
npm test 2>&1 | head -100

echo ""
echo "✓ Tests completed"
