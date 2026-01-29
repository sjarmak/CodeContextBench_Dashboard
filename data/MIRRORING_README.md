# Repository Mirroring for Sourcegraph Indexing

This directory contains the data and scripts for mirroring benchmark repositories to the `sg-benchmarks` GitHub organization for Sourcegraph indexing.

## Overview

CodeContextBench tasks reference external repositories at specific commits. For Sourcegraph MCP to work, these repositories must be indexed. We create mirrors in `github.com/sg-benchmarks/` with naming convention `{repo-name}--{commit-prefix}` (e.g., `pytorch--ca246612`).

## Files

- `instance_to_mirror.json` - Generated mapping of benchmark tasks to their required repo mirrors
- `mirror_*.log` - Logs from mirror creation runs

## Scripts (in `/scripts/`)

### extract_benchmark_repos.py

Scans benchmark directories and extracts all unique (repo, commit) pairs that need mirroring.

```bash
python3 scripts/extract_benchmark_repos.py
```

Output: `data/instance_to_mirror.json`

### create_benchmark_mirrors.sh

Creates mirrors in the `sg-benchmarks` GitHub org.

```bash
# Preview what would be created (no actual changes)
./scripts/create_benchmark_mirrors.sh --dry-run

# Mirror all repos
./scripts/create_benchmark_mirrors.sh

# Mirror specific benchmark only
./scripts/create_benchmark_mirrors.sh --benchmark big_code_mcp
./scripts/create_benchmark_mirrors.sh --benchmark github_mined

# Mirror a range (useful for resuming)
./scripts/create_benchmark_mirrors.sh --start 5 --end 10
```

### extract_tac_commits.sh

TAC (TheAgentCompany) tasks use Docker images with bundled repos. This script extracts the exact git commits from those images.

```bash
# Extract commits (requires images to be pulled first)
./scripts/extract_tac_commits.sh

# Pull TAC images first, then extract
./scripts/extract_tac_commits.sh --pull
```

Note: TAC images are hosted on ghcr.io/theagentcompany and may require authentication.

## Benchmarks and Their Repos

### big_code_mcp (4 repos at HEAD)
- `kubernetes/kubernetes` → `kubernetes--latest`
- `microsoft/vscode` → `vscode--latest`
- `servo/servo` → `servo--latest`
- `NVIDIA/TensorRT-LLM` → `TensorRT-LLM--latest`

### github_mined (12 PyTorch commits)
- `pytorch/pytorch` at various commits → `pytorch--{commit[:8]}`

### tac_mcp_value (4 repos, commits from Docker)
- `cmu-db/bustub` → `bustub--{commit[:8]}`
- `All-Hands-AI/OpenHands` → `OpenHands--{commit[:8]}`
- `ggerganov/llama.cpp` → `llama.cpp--{commit[:8]}`
- `lmarena/copilot-arena` → `copilot-arena--{commit[:8]}`

## Workflow

1. **Extract repos**: Run `extract_benchmark_repos.py` to generate `instance_to_mirror.json`
2. **For TAC tasks**: Run `extract_tac_commits.sh --pull` to get exact commits from Docker images
3. **Create mirrors**: Run `create_benchmark_mirrors.sh` to create GitHub mirrors
4. **Index in Sourcegraph**: Add `sg-benchmarks` org to Sourcegraph code host config

## Mirror Naming Convention

- `{repo-name}--latest` for HEAD/latest commits
- `{repo-name}--{commit[:8]}` for specific commits

Examples:
- `kubernetes--latest`
- `pytorch--ca246612`
- `bustub--abc12345`
