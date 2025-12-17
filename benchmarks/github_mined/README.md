# GitHub Task Mining Infrastructure

Mines CodeContextBench tasks from real open-source repositories using GitHub API.

Tasks are generated from closed issues and merged PRs across OSS projects (Kubernetes, Firefox, PyTorch, VSCode, etc.).

## Components

### Repository Registry (`src/task_mining/repo_registry.py`)

Defines target repositories and their configurations:

```python
from src.task_mining.repo_registry import RepositoryRegistry, Language

registry = RepositoryRegistry()
k8s = registry.get_repo("kubernetes")
cpp_repos = registry.repos_by_language(Language.CPP)
```

**Target Repositories** (Phase 0.5):
- **Firefox** (C/C++): Browser engine
- **Kubernetes** (Go): Container orchestration
- **PyTorch** (Python/C++): ML framework
- **VSCode** (TypeScript): Developer tool
- **FFmpeg** (C): Multimedia library
- **TensorRT-LLM** (C++): Inference engine
- **Servo** (Rust): Browser engine

### GitHub Client (`src/task_mining/github_client.py`)

GitHub REST API wrapper for mining closed issues and merged PRs:

```python
from src.task_mining.github_client import GitHubClient

client = GitHubClient()  # Requires GITHUB_TOKEN env var

# Find closed issues with linked PRs
issues = client.closed_issues_with_linked_prs(
    repo="kubernetes/kubernetes",
    days_back=365,
)

# Find merged PRs with multiple file changes
prs = client.merged_prs_with_tests(
    repo="kubernetes/kubernetes",
    days_back=365,
    min_files_changed=2,
)
```

### Task Generator (`src/task_mining/task_generator.py`)

Converts GitHub issues/PRs to `TaskSpecification` objects:

```python
from src.task_mining.task_generator import TaskGenerator

task_gen = TaskGenerator(client)

# From PR
task = task_gen.from_pr(
    pr=pr_obj,
    repo_config=k8s_repo,
    task_id="sgt-001",
    pre_fix_rev="abc123",
    ground_truth_rev="def456",
)

# From issue with linked PR
task = task_gen.from_issue(
    issue=issue_obj,
    repo_config=k8s_repo,
    task_id="sgt-002",
    pre_fix_rev="abc123",
    ground_truth_rev="def456",
)
```

**Eligibility Filters:**
- Multi-file requirement: min 2 files changed
- Codebase understanding: filtered by category/labels
- Deterministic verifiers: inferred from repo language

**Difficulty Heuristics:**
- Easy: 1-2 files
- Medium: 3-4 files
- Hard: 5+ files

**Category Inference:**
- "fix", "bug" → CROSS_MODULE_BUG_FIX
- "refactor", "rename", "extract" → REFACTORING
- "feature", "add", "implement" → FEATURE_IMPLEMENTATION
- "perf", "optimize" → PERFORMANCE_OPTIMIZATION
- "upgrade", "update" → DEPENDENCY_UPGRADE

## Mining Pipeline

### 1. Run Mining

From CodeContextBench root:

```bash
# Mine from target repos (default: firefox, kubernetes, pytorch, vscode)
python -m src.task_mining.mine_tasks \
  --repos kubernetes pytorch vscode \
  --days-back 365 \
  --output artifacts/mining_results.json

# Mine from all repos
python -m src.task_mining.mine_tasks \
  --repos all \
  --output artifacts/mining_results.json

# With task limit
python -m src.task_mining.mine_tasks \
  --repos all \
  --limit 100 \
  --output artifacts/mining_results.json
```

### 2. Output Format

```json
{
  "timestamp": "2025-01-01T00:00:00.000000",
  "repos_mined": ["kubernetes", "pytorch"],
  "days_back": 365,
  "total_candidates": 47,
  "repositories": [
    {
      "repo_key": "kubernetes",
      "status": "success",
      "candidates_generated": 25,
      "candidates": [
        {
          "id": "sgt-001",
          "repo_key": "kubernetes",
          "title": "Fix etcd timeout handling",
          "category": "cross_module_bug_fix",
          ...
        }
      ]
    }
  ]
}
```

## Setup

### Prerequisites

```bash
pip install requests
export GITHUB_TOKEN=<your-github-token>
```

To generate a token:
1. Go to https://github.com/settings/tokens
2. Create "Personal access token (classic)"
3. Scopes: `public_repo`, `read:user`
4. Copy token to `.env` or shell

### Tests

```bash
# Run mining tests
python -m pytest tests/test_task_mining.py -v

# Run with coverage
python -m pytest tests/test_task_mining.py --cov=src.task_mining
```

## Next Steps (sg_benchmark-5qn)

1. **Task Filtering & Validation**: Apply additional filters
   - Verify test files exist in repo
   - Check for code complexity signals
   - Filter by verifier health

2. **Language Classification**: Auto-detect from file extensions

3. **Multi-file Verification**: Ensure changes span module boundaries

See `docs/ROADMAP.md` Phase 0.5 for details.
