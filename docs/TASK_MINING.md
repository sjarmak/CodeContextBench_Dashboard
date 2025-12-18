# GitHub Task Mining Infrastructure

CodeContextBench includes infrastructure for mining real-world coding tasks from open-source repositories using GitHub API queries.

## Quick Start

### Setup

```bash
# 1. Set GitHub token
export GITHUB_TOKEN=<your-github-token>

# Create token at https://github.com/settings/tokens
# Required scopes: public_repo, read:user
```

### Mine Tasks

```bash
# Mine from specific repositories (default: Firefox, Kubernetes, PyTorch, VSCode)
python -m src.task_mining.mine_tasks \
  --repos kubernetes pytorch \
  --days-back 365 \
  --output artifacts/mining_results.json

# Mine from all registered repositories
python -m src.task_mining.mine_tasks \
  --repos all \
  --output artifacts/mining_results.json
```

### Filter Results

```bash
# Filter mining results by CodeContextBench eligibility criteria
python -m src.task_mining.filter_tasks \
  --input artifacts/mining_results.json \
  --output artifacts/filtered_tasks.json \
  --per-repo 10  # Limit to 10 per repo
```

## Architecture

### Core Modules

**src/task_mining/repo_registry.py**
- Registry of target OSS repositories
- Language classification and metadata
- Sourcegraph integration configuration

**src/task_mining/github_client.py**
- GitHub REST API wrapper
- Queries for closed issues with linked PRs
- Queries for merged PRs with multi-file changes
- Token management and pagination

**src/task_mining/task_generator.py**
- Converts GitHub issues/PRs to TaskSpecification
- Difficulty estimation (easy/medium/hard)
- Category inference (bugfix/refactor/feature/etc)
- Test command inference by language

**src/task_mining/task_filter.py**
- Task eligibility validation
- Multi-file requirement enforcement
- Token budget and time limit checks
- Language support validation

**src/task_mining/mine_tasks.py**
- Entry point for mining pipeline
- Orchestrates GitHub API queries
- Generates mining results JSON

**src/task_mining/filter_tasks.py**
- Entry point for filtering pipeline
- Applies eligibility criteria
- Generates filtered results JSON

## Target Repositories

Phase 0.5 repositories (all have been benchmarked with Sourcegraph):

| Repository | Language | Stars | Size | Use Case |
|-----------|----------|-------|------|----------|
| **Firefox** | C/C++ | 16.1k | Large | Browser engine (Gecko/SpiderMonkey) |
| **Kubernetes** | Go | 111k | Large | Container orchestration |
| **PyTorch** | Python/C++ | 81k | Large | ML framework |
| **VSCode** | TypeScript | 163k | Large | Developer tool |
| **FFmpeg** | C | 45k | Large | Multimedia library |
| **TensorRT-LLM** | C++ | 11k | Medium | LLM inference |
| **Servo** | Rust | 27k | Large | Browser engine |

## Task Generation Pipeline

### 1. Mine Issues & PRs

```python
from src.task_mining.github_client import GitHubClient

client = GitHubClient()  # GITHUB_TOKEN env var

# Closed issues with linked merged PRs (ground-truth fixes)
issues = client.closed_issues_with_linked_prs(
    repo="kubernetes/kubernetes",
    days_back=365,
    exclude_labels=["duplicate", "wontfix"]
)

# Merged PRs with multi-file changes
prs = client.merged_prs_with_tests(
    repo="kubernetes/kubernetes",
    days_back=365,
    min_files_changed=2
)
```

### 2. Generate Tasks

```python
from src.task_mining.task_generator import TaskGenerator
from src.task_mining.repo_registry import RepositoryRegistry

gen = TaskGenerator(client)
registry = RepositoryRegistry()

k8s = registry.get_repo("kubernetes")

# Generate from PR
for pr in prs[:25]:
    task = gen.from_pr(
        pr,
        repo_config=k8s,
        task_id="sgt-001",
        pre_fix_rev="HEAD~1",
        ground_truth_rev=pr.merge_commit_sha
    )
    if task:
        print(f"Generated: {task.title}")

# Generate from issue with linked PR
for issue in issues[:10]:
    task = gen.from_issue(
        issue,
        repo_config=k8s,
        task_id="sgt-002",
        pre_fix_rev="HEAD~1",
        ground_truth_rev="HEAD"
    )
    if task:
        print(f"Generated: {task.title}")
```

### 3. Filter Candidates

```python
from src.task_mining.task_filter import TaskFilter

# Filter single task
task_dict = {...}
result = TaskFilter.filter_task(task_dict)

if result.passed:
    print(f"Task {result.task_id} is eligible")
else:
    print(f"Rejected: {result.reasons}")

# Filter batch
all_tasks = [...]
batch_result = TaskFilter.filter_batch(all_tasks)

print(f"Pass rate: {batch_result['pass_rate']:.1%}")
print(f"Passed: {batch_result['passed']}/{batch_result['total']}")
```

## Eligibility Criteria

### Multi-File Requirement
- Minimum 2 files changed
- Maximum 100 files (complexity sanity check)
- Enforces cross-module understanding

### Difficulty Estimation
- **Easy**: 1-2 files changed
- **Medium**: 3-4 files changed
- **Hard**: 5+ files changed

### Category Inference
- **Bug Fix**: Keywords like "fix", "bug", "error"
- **Refactoring**: Keywords like "refactor", "rename", "extract"
- **Feature**: Keywords like "feature", "add", "implement"
- **Performance**: Keywords like "perf", "optimize", "speed"
- **Dependency Upgrade**: Keywords like "upgrade", "update", "version"

### Language Support
- Python, Go, TypeScript, JavaScript, Rust, C++, C, Java, C#
- Test commands auto-inferred per language

### Token Budget
- Minimum: 1000 tokens (complex enough)
- Maximum: 20000 tokens (fits in context)

### Time Limits
- Minimum: 60 seconds
- Maximum: 3600 seconds (1 hour)

## Output Formats

### Mining Results

```json
{
  "timestamp": "2025-01-15T10:30:00",
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
          "title": "Fix etcd timeout handling",
          "description": "...",
          "category": "cross_module_bug_fix",
          "difficulty": "medium",
          "language": "go",
          "files_changed": 3,
          "source_issue_url": "https://github.com/kubernetes/kubernetes/pull/12345"
        }
      ]
    }
  ]
}
```

### Filtered Results

```json
{
  "total_candidates": 100,
  "total_filtered": 42,
  "filter_rate": 0.42,
  "repositories": [
    {
      "repo_key": "kubernetes",
      "total_candidates": 30,
      "filtered": 15,
      "filter_rate": 0.50,
      "tasks": [...]
    }
  ],
  "all_filtered_tasks": [...]
}
```

## Development

### Run Tests

```bash
# All tests (115 total)
python -m pytest tests/test_task_mining.py -v

# Specific test class
python -m pytest tests/test_task_mining.py::TestRepositoryRegistry -v

# With coverage
python -m pytest tests/test_task_mining.py --cov=src.task_mining
```

### Key Test Suites

- `TestRepositoryRegistry`: Registry loading and filtering
- `TestTaskGenerator`: Task generation and schema validation
- `TestTaskFilter`: Eligibility checking and batch filtering
- `TestGitHubClient`: GitHub API mocking

## Related Documentation

- **Architecture**: See `docs/ARCHITECTURE.md` for system design
- **Task Schema**: See `src/benchmark/task_schema.py` for TaskSpecification
- **Benchmarks**: See `benchmarks/` for task execution
- **Agents**: See `agents/` for agent implementations

## Next Steps

For full mining workflows across the corpus, see:
- Filtering and validation improvements (tokenization, language detection)
- Pre-fix revision computation via git analysis
- Corpus integration for task execution
