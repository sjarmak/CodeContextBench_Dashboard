#!/bin/bash
# Create GitHub mirrors for CodeContextBench benchmark repositories
#
# Features:
#   - Per-repo timeout with retry logic
#   - Progress tracking and logging
#   - Dry-run mode for testing
#   - Support for HEAD (latest) and specific commits
#   - Handles repos with master vs main default branch
#
# Usage:
#   ./create_benchmark_mirrors.sh                    # Mirror all repos
#   ./create_benchmark_mirrors.sh --dry-run          # Preview without creating
#   ./create_benchmark_mirrors.sh --benchmark NAME   # Only specific benchmark
#   ./create_benchmark_mirrors.sh --start N --end M  # Range of repos (1-indexed)

set -o pipefail

# Configuration
ORG="sg-benchmarks"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$REPO_ROOT/data"
INPUT_FILE="$DATA_DIR/instance_to_mirror.json"
LOGFILE="$DATA_DIR/mirror_$(date +%Y%m%d_%H%M%S).log"

# Defaults
DRY_RUN=false
BENCHMARK_FILTER=""
START=1
END=999999
COUNTER=0
SUCCESS=0
FAILED=0
SKIPPED=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --benchmark)
            BENCHMARK_FILTER="$2"
            shift 2
            ;;
        --start)
            START="$2"
            shift 2
            ;;
        --end)
            END="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--benchmark NAME] [--start N] [--end M]"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $msg" | tee -a "$LOGFILE"
}

# Check prerequisites
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is required but not installed"
    exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file not found: $INPUT_FILE"
    echo "Run extract_benchmark_repos.py first to generate it"
    exit 1
fi

# Count total entries
TOTAL=$(jq '. | length' "$INPUT_FILE")
log "Starting mirror creation from $INPUT_FILE"
log "Total entries: $TOTAL, Range: $START-$END"
if [ "$DRY_RUN" = true ]; then
    log "DRY RUN MODE - No repos will be created"
fi
if [ -n "$BENCHMARK_FILTER" ]; then
    log "Filtering to benchmark: $BENCHMARK_FILTER"
fi

# Create mirror function
create_mirror() {
    local task_id="$1"
    local benchmark="$2"
    local repo="$3"
    local commit="$4"
    local mirror_name="$5"

    COUNTER=$((COUNTER + 1))

    # Skip if outside range
    if [ $COUNTER -lt $START ] || [ $COUNTER -gt $END ]; then
        return 0
    fi

    # Skip if benchmark filter doesn't match
    if [ -n "$BENCHMARK_FILTER" ] && [ "$benchmark" != "$BENCHMARK_FILTER" ]; then
        return 0
    fi

    log "[$COUNTER] Processing: $task_id"
    log "  Original: $repo @ $commit"
    log "  Benchmark: $benchmark"

    # Skip if commit needs extraction from Docker
    if [ "$commit" = "EXTRACT_FROM_DOCKER" ]; then
        log "[$COUNTER] SKIP: $task_id - commit needs extraction from Docker"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Dry run mode
    if [ "$DRY_RUN" = true ]; then
        log "  [DRY RUN] Would create: github.com/$ORG/$mirror_name"
        SUCCESS=$((SUCCESS + 1))
        return 0
    fi

    # Skip if repo already exists
    if gh repo view "$ORG/$mirror_name" &>/dev/null; then
        log "  Already exists, skipping: $mirror_name"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Create temp directory
    local tmpdir=$(mktemp -d)
    cd "$tmpdir" || return 1

    # Clone with retry logic
    local clone_success=0
    for attempt in 1 2 3; do
        log "  Clone attempt $attempt/3..."

        if [ "$commit" = "HEAD" ] || [ "$commit" = "latest" ]; then
            # Clone latest with depth 1
            if timeout 300 git clone --depth 1 "https://github.com/$repo.git" repo 2>/dev/null; then
                clone_success=1
                break
            fi
        else
            # Clone full history to checkout specific commit
            if timeout 600 git clone "https://github.com/$repo.git" repo 2>/dev/null; then
                clone_success=1
                break
            fi
        fi

        log "  Clone attempt $attempt failed, retrying..."
        rm -rf repo 2>/dev/null
        sleep 5
    done

    if [ $clone_success -eq 0 ]; then
        log "  FAILED: Clone failed after 3 attempts"
        cd "$REPO_ROOT"
        rm -rf "$tmpdir"
        FAILED=$((FAILED + 1))
        return 1
    fi

    cd repo || return 1

    # Handle specific commit checkout
    if [ "$commit" != "HEAD" ] && [ "$commit" != "latest" ]; then
        if ! git checkout "$commit" 2>/dev/null; then
            log "  FAILED: Could not checkout commit $commit"
            cd "$REPO_ROOT"
            rm -rf "$tmpdir"
            FAILED=$((FAILED + 1))
            return 1
        fi
        # Reset main branch to this commit
        git checkout -B main
    else
        # For HEAD, ensure we have a main branch (some repos use master)
        default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
        if [ "$default_branch" != "main" ]; then
            log "  Converting $default_branch to main..."
            git checkout -B main "origin/$default_branch" 2>/dev/null || git checkout -B main
        fi
    fi

    # Remove origin
    git remote remove origin 2>/dev/null

    # Create GitHub repo
    log "  Creating GitHub repo: $ORG/$mirror_name"
    if ! gh repo create "$ORG/$mirror_name" --public --description "Mirror of $repo @ ${commit:0:8} for CodeContextBench" 2>/dev/null; then
        log "  FAILED: Could not create GitHub repo"
        cd "$REPO_ROOT"
        rm -rf "$tmpdir"
        FAILED=$((FAILED + 1))
        return 1
    fi

    # Add new remote and push
    git remote add origin "https://github.com/$ORG/$mirror_name.git"

    log "  Pushing to mirror..."
    local push_success=0
    for attempt in 1 2 3; do
        if timeout 600 git push -u origin main 2>/dev/null; then
            push_success=1
            break
        fi
        log "  Push attempt $attempt failed, retrying..."
        sleep 5
    done

    cd "$REPO_ROOT"
    rm -rf "$tmpdir"

    if [ $push_success -eq 0 ]; then
        log "  FAILED: Push failed after 3 attempts"
        FAILED=$((FAILED + 1))
        return 1
    fi

    log "  ✅ Successfully mirrored"
    SUCCESS=$((SUCCESS + 1))

    # Rate limiting
    sleep 3
}

# Process each entry from JSON
jq -c '.[]' "$INPUT_FILE" | while read -r entry; do
    task_id=$(echo "$entry" | jq -r '.task_id')
    benchmark=$(echo "$entry" | jq -r '.benchmark')
    repo=$(echo "$entry" | jq -r '.repo')
    commit=$(echo "$entry" | jq -r '.commit')
    mirror_name=$(echo "$entry" | jq -r '.mirror_name')

    create_mirror "$task_id" "$benchmark" "$repo" "$commit" "$mirror_name"
done

log ""
log "=============================="
log "Mirror Creation Complete"
log "=============================="
log "Success: $SUCCESS"
log "Skipped: $SKIPPED"
log "Failed: $FAILED"
log "Log: $LOGFILE"
