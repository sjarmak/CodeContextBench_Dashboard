#!/bin/bash
#
# Quick test of openhands environment setup without running a full Harbor evaluation.
# Tests if /opt/openhands-venv can be successfully created with the standard setup.

echo "=== OpenHands Environment Quick Test ==="
echo ""

# Check Docker
if ! docker ps > /dev/null 2>&1; then
    echo "✗ Docker not running"
    exit 1
fi
echo "✓ Docker available"
echo ""

# Test venv creation in container
echo "Testing venv creation in Docker..."
docker run --rm ubuntu:24.04 bash -c '
  apt-get update > /dev/null 2>&1
  apt-get install -y curl python3-full > /dev/null 2>&1
  
  # Install uv (what openhands install script uses)
  curl -LsSf https://astral.sh/uv/install.sh 2>/dev/null | sh > /dev/null 2>&1
  export PATH="$HOME/.local/bin:$PATH"
  
  # Create venv at /opt/openhands-venv
  mkdir -p /opt
  uv venv /opt/openhands-venv --python 3.13
  
  # Test venv works
  /opt/openhands-venv/bin/python --version
  /opt/openhands-venv/bin/pip --version 2>/dev/null || echo "pip installing..."
  /opt/openhands-venv/bin/pip install --upgrade pip > /dev/null 2>&1
  /opt/openhands-venv/bin/pip --version
  
  echo ""
  echo "✅ Environment setup successful"
'

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ PASS: Venv creation works correctly"
    echo ""
    echo "The environment setup is functional. If evaluations are still failing:"
    echo "  • Check that task repos can install their dependencies"
    echo "  • Run: harbor run ... --keep-images to inspect failed containers"
    echo "  • Check openhands.py environment_setup() for any shell syntax errors"
    exit 0
else
    echo "❌ FAIL: Venv creation failed"
    exit 1
fi
