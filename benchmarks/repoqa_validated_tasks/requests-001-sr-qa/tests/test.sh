#!/bin/bash
# RepoQA Verification Script
# Verifies agent solution against ground truth

echo "Starting RepoQA verifier..." 1>&2

cd /app || { echo "ERROR: Cannot cd to /app"; exit 1; }

# Create logs directory for Harbor
mkdir -p /logs/verifier || { echo "ERROR: Cannot create /logs/verifier"; exit 1; }

echo "=========================================="
echo "RepoQA Verifier"
echo "Task Variant: sr-qa"
echo "=========================================="

# DEBUG: Check what directories exist
echo "DEBUG: Checking directories..."
ls -la /logs/ 2>&1 || echo "Cannot list /logs"
echo "Creating /logs/verifier if needed..."
mkdir -p /logs/verifier 2>&1 || echo "Cannot create /logs/verifier"

# Ground truth is uploaded by Harbor to /tests/ground_truth.json
echo "DEBUG: Checking for /tests/ground_truth.json..."
if [ ! -f /tests/ground_truth.json ]; then
    echo "ERROR: No ground_truth.json found at /tests/ground_truth.json"
    echo "Contents of /tests:"
    ls -la /tests/ || echo "Cannot list /tests"
    echo '{"score": 0.0}' > /logs/verifier/reward.json
    echo "DEBUG: Wrote error reward to /logs/verifier/reward.json"
    exit 0
fi
echo "DEBUG: Found /tests/ground_truth.json"

# The agent should have created solution.json in /logs/verifier/
# But since the test runs in a fresh container, it won't be there yet
# We'll check in /app/solution.json (which is in the current container's /app if agent wrote it)
# Or we can try /logs/verifier/solution.json if it was somehow preserved

SOLUTION_FILE="/app/solution.json"
if [ ! -f "$SOLUTION_FILE" ]; then
    # Try alternate location
    SOLUTION_FILE="/logs/verifier/solution.json"
fi

if [ ! -f "$SOLUTION_FILE" ]; then
    echo "ERROR: Agent did not create solution.json in /app/ or /logs/verifier/"
    echo "The agent must run: mkdir -p /logs/verifier && cat > /logs/verifier/solution.json << 'JSONEOF' ... JSONEOF"
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
    # Load ground truth from Harbor's uploaded tests directory
    with open("/tests/ground_truth.json") as f:
        ground_truth = json.load(f)
    
    # Load agent output (as JSON)
    # Try multiple possible locations
    solution_paths = [
        Path("/app/solution.json"),
        Path("/logs/verifier/solution.json"),
    ]
    
    solution_file = None
    for path in solution_paths:
        if path.exists():
            solution_file = path
            break
    
    if solution_file is None:
        raise FileNotFoundError("No solution.json found in /app/ or /logs/verifier/")
    
    with open(solution_file) as f:
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
