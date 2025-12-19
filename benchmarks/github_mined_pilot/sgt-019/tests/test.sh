#!/bin/bash

# Ensure verifier output directory exists
mkdir -p /logs/verifier

# The repo is at /src in the container
cd /src 2>/dev/null || cd /workspace/src 2>/dev/null || { echo "0" > /logs/verifier/reward.txt; exit 1; }

# Simple smoke test: check that the repo structure is intact
if [ ! -f "setup.py" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

if [ ! -d "torch" ]; then
  echo "0" > /logs/verifier/reward.txt
  exit 1
fi

# Test passed - write reward file
echo "1" > /logs/verifier/reward.txt
exit 0
