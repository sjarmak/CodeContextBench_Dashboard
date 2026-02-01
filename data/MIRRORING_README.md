# Repository Mirroring for CodeContextBench

This directory contains data and scripts for mirroring benchmark repositories to the `sg-benchmarks` GitHub organization for Sourcegraph indexing.

## Overview

For MCP/Deep Search to provide value, the benchmark codebases must be indexed in Sourcegraph. This requires:

1. **Identifying repos and commits** used by each benchmark
2. **Mirroring to sg-benchmarks** at the exact commit used in the task
3. **Indexing in Sourcegraph** so Deep Search can query them

## Files

| File | Description |
|------|-------------|
| `instance_to_mirror.json` | Mapping of benchmark instances to repos/commits |
| `tac_commits.json` | TAC-specific commits (extracted from Docker images) |
| `.mirror_progress` | Tracks which mirrors have been created |
| `mirror_*.log` | Logs from mirror creation runs |

## Workflow

### 1. Extract Repository Information

```bash
# Extract all benchmark repos
python3 scripts/extract_benchmark_repos.py

# Extract only specific benchmark
python3 scripts/extract_benchmark_repos.py --benchmark big_code_mcp
```

### 2. Extract TAC Commits (if running TAC tasks)

TAC tasks use pre-built Docker images with code at specific commits:

```bash
# Pull TAC images and extract commits
./scripts/extract_tac_commits.sh --pull

# Or if images are already local
./scripts/extract_tac_commits.sh
```

### 3. Create Mirrors

```bash
# Dry run (show what would be created)
./scripts/create_benchmark_mirrors.sh --dry-run

# Create mirrors for specific benchmark
./scripts/create_benchmark_mirrors.sh --benchmark big_code_mcp

# Create all mirrors
./scripts/create_benchmark_mirrors.sh
```

### 4. Verify Sourcegraph Indexing

After mirrors are created, verify they're indexed:

```bash
# Check if repo is searchable
ds search --query "repo:sg-benchmarks/vscode--latest file:README"
```

## instance_to_mirror.json Format

```json
{
  "big-code-vsc-001": {
    "mirror_name": "vscode--latest",
    "original_repo": "microsoft/vscode",
    "commit": "HEAD",
    "benchmark": "big_code_mcp",
    "language": "typescript"
  }
}
```

## Benchmark Repository Requirements

| Benchmark | Repos | Commit Pinning | Status |
|-----------|-------|----------------|--------|
| swebench_pro | 23 repos, 1231 instances | Yes (per-task) | ✅ Already mirrored |
| locobench_agent | 34 synthetic projects | N/A | ✅ Indexed |
| big_code_mcp | 4 repos (k8s, vscode, servo, trt) | No (HEAD) | 🔄 Pending |
| tac_mcp_value | 4 repos (bustub, openhands, llama.cpp, copilot-arena) | Yes | 🔄 Pending |
| github_mined | 1 repo (pytorch), 12 commits | Yes | 🔄 Pending |
| kubernetes_docs | 1 repo (kubernetes) | No (HEAD) | 🔄 Pending |

## Notes

- **HEAD commits**: For benchmarks using `--depth 1` clones, we mirror the latest commit. Re-mirror periodically if tasks need updating.
- **TAC commits**: Must be extracted from Docker images since TAC uses a private GitLab fork.
- **Rate limits**: The mirror script includes sleep delays to avoid GitHub rate limiting.
