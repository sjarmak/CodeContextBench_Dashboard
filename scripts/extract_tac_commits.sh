#!/bin/bash
# Extract commit hashes from TAC Docker images
#
# TAC tasks use pre-built Docker images that contain repos at specific commits.
# This script runs each image and extracts the git commit from /workspace.
#
# Usage: ./extract_tac_commits.sh [--pull]
#
# Options:
#   --pull    Pull images before extracting (requires docker login to ghcr.io)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="${SCRIPT_DIR}/../data/tac_commits.json"

# TAC Docker image registry
TAC_REGISTRY="ghcr.io/theagentcompany"
TAC_VERSION="1.0.0"

# TAC tasks with their repo paths inside the container
declare -A TAC_TASKS=(
    ["sde-implement-hyperloglog"]="/workspace/bustub"
    ["sde-implement-buffer-pool-manager-bustub"]="/workspace/bustub"
    ["sde-dependency-change-1"]="/workspace/openhands"
    ["sde-find-answer-in-codebase-1"]="/workspace/llama.cpp"
    ["sde-find-answer-in-codebase-2"]="/workspace/llama.cpp"
    ["sde-copilot-arena-server-new-endpoint"]="/workspace/copilot-arena-server"
    ["sde-write-a-unit-test-for-search_file-function"]="/workspace/openhands"
    ["sde-troubleshoot-dev-setup"]="/workspace/openhands"
)

# Map TAC task to original repo
declare -A TASK_TO_REPO=(
    ["sde-implement-hyperloglog"]="cmu-db/bustub"
    ["sde-implement-buffer-pool-manager-bustub"]="cmu-db/bustub"
    ["sde-dependency-change-1"]="All-Hands-AI/OpenHands"
    ["sde-find-answer-in-codebase-1"]="ggerganov/llama.cpp"
    ["sde-find-answer-in-codebase-2"]="ggerganov/llama.cpp"
    ["sde-copilot-arena-server-new-endpoint"]="lmarena/copilot-arena"
    ["sde-write-a-unit-test-for-search_file-function"]="All-Hands-AI/OpenHands"
    ["sde-troubleshoot-dev-setup"]="All-Hands-AI/OpenHands"
)

PULL_IMAGES=false
if [[ "$1" == "--pull" ]]; then
    PULL_IMAGES=true
fi

echo "TAC Commit Extraction"
echo "====================="
echo ""

# Initialize JSON output
echo "{" > "$OUTPUT_FILE"
first=true

for task in "${!TAC_TASKS[@]}"; do
    image="${TAC_REGISTRY}/${task}-image:${TAC_VERSION}"
    repo_path="${TAC_TASKS[$task]}"
    original_repo="${TASK_TO_REPO[$task]}"
    
    echo "Processing: $task"
    echo "  Image: $image"
    echo "  Repo path: $repo_path"
    
    if $PULL_IMAGES; then
        echo "  Pulling image..."
        if ! docker pull "$image" 2>/dev/null; then
            echo "  ⚠️  Failed to pull image (may not exist or require auth)"
            continue
        fi
    fi
    
    # Check if image exists locally
    if ! docker image inspect "$image" &>/dev/null; then
        echo "  ⚠️  Image not found locally, skipping"
        continue
    fi
    
    # Extract commit hash from container
    echo "  Extracting commit..."
    commit=$(docker run --rm "$image" sh -c "cd $repo_path && git rev-parse HEAD 2>/dev/null || echo 'NOT_FOUND'" 2>/dev/null || echo "ERROR")
    
    if [[ "$commit" == "NOT_FOUND" || "$commit" == "ERROR" || -z "$commit" ]]; then
        echo "  ⚠️  Could not extract commit"
        continue
    fi
    
    commit_short="${commit:0:8}"
    echo "  ✅ Commit: $commit_short"
    
    # Add to JSON
    if ! $first; then
        echo "," >> "$OUTPUT_FILE"
    fi
    first=false
    
    cat >> "$OUTPUT_FILE" << EOF
  "$task": {
    "original_repo": "$original_repo",
    "commit": "$commit",
    "commit_short": "$commit_short",
    "repo_path": "$repo_path"
  }
EOF
done

echo "" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

echo ""
echo "Results written to: $OUTPUT_FILE"
echo ""

# Show unique repos
echo "Unique repos found:"
cat "$OUTPUT_FILE" | grep '"original_repo"' | sort -u | sed 's/.*: "/  - /' | sed 's/".*//'
