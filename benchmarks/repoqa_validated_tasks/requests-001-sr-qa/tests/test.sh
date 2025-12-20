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

# Ground truth is in /app/tests/ground_truth.json
if [ ! -f /app/tests/ground_truth.json ]; then
    echo "ERROR: No ground_truth.json found"
    echo '{"score": 0.0}' > /logs/verifier/reward.json
    exit 0
fi

# Check if solution.json exists
if [ ! -f /app/solution.json ]; then
    echo "ERROR: Agent did not create /app/solution.json"
    echo "The agent must run: cat > /app/solution.json << 'JSONEOF' ... JSONEOF"
    echo '{"score": 0.0}' > /logs/verifier/reward.json
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
from verifiers import SemanticRetrievalQAVerifier

try:
    # Load ground truth
    with open("/app/tests/ground_truth.json") as f:
        ground_truth = json.load(f)
    
    # Load agent output (as JSON)
    with open("/app/solution.json") as f:
        agent_output = json.load(f)
    
    # Verify using SR-QA verifier
    verifier = SemanticRetrievalQAVerifier(ground_truth)
    result = verifier.verify(agent_output)
    
    # Build reward dict - Harbor expects a SINGLE scalar metric
    # We use correct_function (0.0-1.0) as the primary metric
    reward = {
        "score": float(result.correct_function),
    }
    
    # Log the detailed breakdown
    print(f"\nVerification Results:")
    print(f"  Correct Function: {result.correct_function:.2f}")
    print(f"  Correct Path: {result.correct_path:.2f}") 
    print(f"  Justification: {result.justification_score:.2f}")
    print(f"  Details: {result.reasoning}")
    
    # Write reward for Harbor
    with open("/logs/verifier/reward.json", "w") as f:
        json.dump(reward, f, indent=2)

except Exception as e:
    import traceback
    print(f"ERROR: Verification failed: {e}")
    traceback.print_exc()
    reward = {
        "score": 0.0,
    }
    with open("/logs/verifier/reward.json", "w") as f:
        json.dump(reward, f, indent=2)

VERIFY_SCRIPT

# Ensure proper permissions
chmod 664 /logs/verifier/reward.json 2>/dev/null || true

# Always exit 0 for Harbor compatibility
exit 0
