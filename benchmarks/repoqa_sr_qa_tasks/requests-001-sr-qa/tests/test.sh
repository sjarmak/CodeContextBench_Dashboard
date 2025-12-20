#!/bin/bash
# RepoQA Verification Script
# Verifies agent solution against ground truth

set -e

cd /app

# Create logs directory for Harbor
mkdir -p /logs/verifier

echo "=========================================="
echo "RepoQA Verifier"
echo "Task Variant: sr-qa"
echo "=========================================="

# Agent's output should be in /app/solution.json
# Ground truth is in /app/tests/ground_truth.json

if [ ! -f /app/solution.json ]; then
    echo "ERROR: No solution.json found"
    echo '{"correct_function": 0.0, "correct_path": 0.0, "justification_score": 0.0, "reasoning": "No solution provided"}' > /logs/verifier/reward.json
    exit 0
fi

if [ ! -f /app/tests/ground_truth.json ]; then
    echo "ERROR: No ground_truth.json found"
    echo '{"correct_function": 0.0, "correct_path": 0.0, "justification_score": 0.0, "reasoning": "Ground truth not available"}' > /logs/verifier/reward.json
    exit 0
fi

# Run verifier
python3 << 'VERIFY_SCRIPT'
import json
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import verifiers from adapter directory
from verifiers import RepoQAVerifier

try:
    verifier = RepoQAVerifier(
        Path("/app/tests/ground_truth.json"),
        task_variant="sr-qa"
    )
    
    result = verifier.verify(Path("/app/solution.json"))
    
    reward = {
        "correct_function": result.correct_function,
        "correct_path": result.correct_path,
        "justification_score": result.justification_score,
        "reasoning": result.reasoning,
    }
    
    # Write reward for Harbor
    with open("/logs/verifier/reward.json", "w") as f:
        json.dump(reward, f, indent=2)
    
    print(f"Verification complete:")
    print(f"  Correct Function: {result.correct_function:.2f}")
    print(f"  Correct Path: {result.correct_path:.2f}")
    print(f"  Justification: {result.justification_score:.2f}")

except Exception as e:
    print(f"ERROR: Verification failed: {e}")
    reward = {
        "correct_function": 0.0,
        "correct_path": 0.0,
        "justification_score": 0.0,
        "reasoning": f"Verification error: {str(e)}",
    }
    with open("/logs/verifier/reward.json", "w") as f:
        json.dump(reward, f, indent=2)

VERIFY_SCRIPT

# Ensure proper permissions
chmod 664 /logs/verifier/reward.json 2>/dev/null || true

# Always exit 0 for Harbor compatibility
exit 0
