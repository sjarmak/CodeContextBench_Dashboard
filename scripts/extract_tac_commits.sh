#!/bin/bash
# Extract git commits from TAC Docker images
#
# TAC tasks use pre-built Docker images that contain the repos internally.
# This script runs each image and extracts the git commit from /workspace.
#
# Usage:
#   ./extract_tac_commits.sh          # Extract commits (images must be pulled)
#   ./extract_tac_commits.sh --pull   # Pull images first, then extract

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$REPO_ROOT/data"
INPUT_FILE="$DATA_DIR/instance_to_mirror.json"
OUTPUT_FILE="$DATA_DIR/instance_to_mirror.json"

PULL_IMAGES=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --pull)
            PULL_IMAGES=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--pull]"
            exit 1
            ;;
    esac
done

# TAC task configurations (bash 3.2 compatible)
# Format: task_id|image|workspace|upstream_repo
TAC_CONFIGS=(
    "tac-buffer-pool-manager|ghcr.io/theagentcompany/sde-implement-buffer-pool-manager-bustub-image:1.0.0|/workspace|cmu-db/bustub"
    "tac-implement-hyperloglog|ghcr.io/theagentcompany/sde-implement-hyperloglog-image:1.0.0|/workspace|cmu-db/bustub"
    "tac-dependency-change|ghcr.io/theagentcompany/sde-dependency-change-1-image:1.0.0|/workspace|All-Hands-AI/OpenHands"
    "tac-write-unit-test|ghcr.io/theagentcompany/sde-write-a-unit-test-for-search_file-function-image:1.0.0|/workspace|All-Hands-AI/OpenHands"
    "tac-troubleshoot-dev-setup|ghcr.io/theagentcompany/sde-troubleshoot-dev-setup-image:1.0.0|/workspace|All-Hands-AI/OpenHands"
    "tac-find-in-codebase-1|ghcr.io/theagentcompany/sde-find-answer-in-codebase-1-image:1.0.0|/workspace|ggerganov/llama.cpp"
    "tac-find-in-codebase-2|ghcr.io/theagentcompany/sde-find-answer-in-codebase-2-image:1.0.0|/workspace|ggerganov/llama.cpp"
    "tac-copilot-arena-endpoint|ghcr.io/theagentcompany/sde-copilot-arena-server-new-endpoint-image:1.0.0|/workspace|lmarena/copilot-arena"
)

echo "TAC Commit Extraction"
echo "====================="

# Pull images if requested
if [ "$PULL_IMAGES" = true ]; then
    echo ""
    echo "Pulling TAC Docker images..."
    for config in "${TAC_CONFIGS[@]}"; do
        IFS='|' read -r task_id image workspace repo <<< "$config"
        echo "  Pulling: $image"
        if ! docker pull "$image" 2>/dev/null; then
            echo "    WARNING: Failed to pull $image"
        fi
    done
fi

# Temporary file for extracted commits
COMMITS_FILE=$(mktemp)
echo "" > "$COMMITS_FILE"

echo ""
echo "Extracting commits from containers..."

for config in "${TAC_CONFIGS[@]}"; do
    IFS='|' read -r task_id image workspace upstream_repo <<< "$config"

    echo ""
    echo "[$task_id]"
    echo "  Image: $image"
    echo "  Upstream: $upstream_repo"

    # Check if image exists locally
    if ! docker image inspect "$image" &>/dev/null; then
        echo "  SKIP: Image not found locally. Run with --pull to download."
        continue
    fi

    # Run container and extract git info
    echo "  Extracting git commit..."

    # Try to get commit from workspace
    commit=$(docker run --rm --platform linux/amd64 "$image" bash -c "cd $workspace && git rev-parse HEAD 2>/dev/null" 2>/dev/null)

    if [ -n "$commit" ] && [ ${#commit} -eq 40 ]; then
        echo "  ✅ Commit: $commit"
        echo "$task_id|$commit|$upstream_repo" >> "$COMMITS_FILE"

        # Also try to get remote URL for verification
        remote=$(docker run --rm --platform linux/amd64 "$image" bash -c "cd $workspace && git remote get-url origin 2>/dev/null" 2>/dev/null)
        if [ -n "$remote" ]; then
            echo "  Remote: $remote"
        fi
    else
        echo "  ❌ Could not extract commit from $workspace"

        # Try alternative workspace paths
        for alt_path in "/workspace/repo" "/home/user/workspace" "/root/workspace" "/app"; do
            alt_commit=$(docker run --rm --platform linux/amd64 "$image" bash -c "cd $alt_path && git rev-parse HEAD 2>/dev/null" 2>/dev/null)
            if [ -n "$alt_commit" ] && [ ${#alt_commit} -eq 40 ]; then
                echo "  Found in $alt_path: $alt_commit"
                echo "$task_id|$alt_commit|$upstream_repo" >> "$COMMITS_FILE"
                break
            fi
        done
    fi
done

# Count extracted commits
extracted_count=$(grep -c "|" "$COMMITS_FILE" 2>/dev/null || echo "0")

echo ""
echo "=============================="
echo "Extraction Summary"
echo "=============================="
echo "Tasks processed: ${#TAC_CONFIGS[@]}"
echo "Commits extracted: $extracted_count"

# Update the JSON file if we have commits
if [ "$extracted_count" -gt 0 ]; then
    echo ""
    echo "Updating $OUTPUT_FILE..."

    # Create Python script to update JSON
    python3 << EOF
import json

with open("$INPUT_FILE", "r") as f:
    data = json.load(f)

# Read extracted commits
commits = {}
with open("$COMMITS_FILE", "r") as f:
    for line in f:
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                task_id, commit = parts[0], parts[1]
                commits[task_id] = commit

updated = 0
for entry in data:
    task_id = entry.get("task_id", "")
    if task_id in commits:
        old_commit = entry.get("commit", "")
        new_commit = commits[task_id]
        if old_commit != new_commit:
            entry["commit"] = new_commit
            # Update mirror name
            repo_name = entry.get("repo", "").split("/")[-1]
            entry["mirror_name"] = f"{repo_name}--{new_commit[:8]}"
            updated += 1
            print(f"  Updated {task_id}: {old_commit[:20] if old_commit else 'N/A'}... -> {new_commit[:8]}")

with open("$OUTPUT_FILE", "w") as f:
    json.dump(data, f, indent=2)

print(f"\nUpdated {updated} entries in $OUTPUT_FILE")
EOF

else
    echo ""
    echo "No commits extracted. JSON file unchanged."
    echo ""
    echo "To extract commits, ensure you have access to ghcr.io/theagentcompany images"
    echo "and run: $0 --pull"
fi

# Cleanup
rm -f "$COMMITS_FILE"
