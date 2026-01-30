#!/bin/bash
# Create GitHub mirrors for benchmark repos in sg-benchmarks org
#
# This script reads instance_to_mirror.json and creates mirrors in the
# sg-benchmarks GitHub organization for Sourcegraph indexing.
#
# Usage: ./create_benchmark_mirrors.sh [--dry-run] [--benchmark <name>] [--start N] [--end N]
#
# Prerequisites:
#   - GitHub CLI (gh) authenticated with sg-benchmarks org access
#   - Git configured with push access to sg-benchmarks org
#
# Example:
#   ./create_benchmark_mirrors.sh --benchmark big_code_mcp --dry-run
#   ./create_benchmark_mirrors.sh --benchmark github_mined

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_FILE="${SCRIPT_DIR}/../data/instance_to_mirror.json"
PROGRESS_FILE="${SCRIPT_DIR}/../data/.mirror_progress"
LOG_FILE="${SCRIPT_DIR}/../data/mirror_$(date +%Y%m%d_%H%M%S).log"

# Configuration
GH_ORG="sg-benchmarks"
CLONE_TIMEOUT=180
PUSH_TIMEOUT=300
MAX_RETRIES=3
SLEEP_BETWEEN=2

# Parse arguments
DRY_RUN=false
BENCHMARK_FILTER=""
START_INDEX=0
END_INDEX=999999

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
            START_INDEX="$2"
            shift 2
            ;;
        --end)
            END_INDEX="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Check prerequisites
if ! command -v gh &>/dev/null; then
    echo "ERROR: GitHub CLI (gh) not found. Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR: GitHub CLI not authenticated. Run: gh auth login"
    exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "ERROR: Input file not found: $INPUT_FILE"
    echo "Run: python3 scripts/extract_benchmark_repos.py"
    exit 1
fi

log "Starting benchmark mirror creation"
log "Input: $INPUT_FILE"
log "Organization: $GH_ORG"
log "Dry run: $DRY_RUN"
if [[ -n "$BENCHMARK_FILTER" ]]; then
    log "Filtering to benchmark: $BENCHMARK_FILTER"
fi

# Read JSON and iterate
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

counter=0
success=0
skipped=0
failed=0

# Process each instance
for instance_id in $(jq -r 'keys[]' "$INPUT_FILE"); do
    counter=$((counter + 1))
    
    # Skip if outside range
    if [[ $counter -lt $START_INDEX || $counter -gt $END_INDEX ]]; then
        continue
    fi
    
    # Extract fields
    mirror_name=$(jq -r ".\"$instance_id\".mirror_name" "$INPUT_FILE")
    original_repo=$(jq -r ".\"$instance_id\".original_repo" "$INPUT_FILE")
    commit=$(jq -r ".\"$instance_id\".commit" "$INPUT_FILE")
    benchmark=$(jq -r ".\"$instance_id\".benchmark" "$INPUT_FILE")
    
    # Apply benchmark filter
    if [[ -n "$BENCHMARK_FILTER" && "$benchmark" != "$BENCHMARK_FILTER" ]]; then
        continue
    fi
    
    # Skip if commit needs extraction
    if [[ "$commit" == "EXTRACT_FROM_DOCKER" ]]; then
        log "[$counter] SKIP: $instance_id - commit needs extraction from Docker"
        skipped=$((skipped + 1))
        continue
    fi
    
    log "[$counter] Processing: $instance_id"
    log "  Mirror: $mirror_name"
    log "  Original: $original_repo @ $commit"
    log "  Benchmark: $benchmark"
    
    if $DRY_RUN; then
        log "  [DRY RUN] Would create: github.com/$GH_ORG/$mirror_name"
        success=$((success + 1))
        continue
    fi
    
    # Check if mirror already exists
    if gh repo view "$GH_ORG/$mirror_name" &>/dev/null; then
        log "  ⏭️  Mirror already exists, skipping"
        skipped=$((skipped + 1))
        continue
    fi
    
    # Create working directory
    WORK_DIR="$TEMP_DIR/$mirror_name"
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    
    # Clone original repo
    log "  Cloning $original_repo..."
    for attempt in $(seq 1 $MAX_RETRIES); do
        if timeout $CLONE_TIMEOUT git clone "https://github.com/$original_repo.git" . 2>&1; then
            break
        fi
        log "  Clone attempt $attempt failed, retrying..."
        rm -rf "$WORK_DIR"/*
        sleep $SLEEP_BETWEEN
    done
    
    if [[ ! -d ".git" ]]; then
        log "  ❌ Failed to clone after $MAX_RETRIES attempts"
        failed=$((failed + 1))
        continue
    fi
    
    # Checkout specific commit (if not HEAD)
    if [[ "$commit" != "HEAD" ]]; then
        log "  Checking out $commit..."
        if ! git checkout "$commit" 2>&1; then
            log "  ❌ Failed to checkout commit"
            failed=$((failed + 1))
            continue
        fi
        # Reset main branch to this commit
        git checkout -B main
    else
        # For HEAD, ensure we have a main branch (some repos use master)
        default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "master")
        if [[ "$default_branch" != "main" ]]; then
            log "  Converting $default_branch to main..."
            git checkout -B main "origin/$default_branch"
        fi
    fi
    
    # Remove origin
    git remote remove origin
    
    # Create new GitHub repo
    log "  Creating GitHub repo: $GH_ORG/$mirror_name"
    if ! gh repo create "$GH_ORG/$mirror_name" --public --description "Mirror of $original_repo @ ${commit:0:8} for CodeContextBench" 2>&1; then
        log "  ❌ Failed to create repo"
        failed=$((failed + 1))
        continue
    fi
    
    # Set new origin and push
    git remote add origin "https://github.com/$GH_ORG/$mirror_name.git"
    
    log "  Pushing to mirror..."
    for attempt in $(seq 1 $MAX_RETRIES); do
        if timeout $PUSH_TIMEOUT git push -u origin main 2>&1; then
            break
        fi
        log "  Push attempt $attempt failed, retrying..."
        sleep $SLEEP_BETWEEN
    done
    
    if git push -u origin main --dry-run &>/dev/null; then
        log "  ✅ Successfully mirrored"
        success=$((success + 1))
        echo "$instance_id" >> "$PROGRESS_FILE"
    else
        log "  ❌ Failed to push"
        failed=$((failed + 1))
    fi
    
    # Cleanup
    cd "$SCRIPT_DIR"
    rm -rf "$WORK_DIR"
    
    sleep $SLEEP_BETWEEN
done

log ""
log "=============================="
log "Mirror Creation Complete"
log "=============================="
log "Success: $success"
log "Skipped: $skipped"
log "Failed: $failed"
log "Log: $LOG_FILE"
