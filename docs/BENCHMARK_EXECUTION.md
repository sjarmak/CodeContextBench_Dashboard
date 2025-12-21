# Benchmark Execution Guide

Detailed guides for running specific benchmark types in CodeContextBench.

## RepoQA Benchmark Execution

### Architecture: Separate Agent and Verifier Containers

**Critical insight:** Agent and verifier run in SEPARATE Docker containers with separate filesystems. Agent writes must go to `/app/` (mounted in both containers), NOT `/logs/verifier/` (container-specific).

### Using Validated Dataset

A pre-validated dataset with 5 instances from the requests repository is available:

```bash
benchmarks/repoqa_instances_validated.jsonl
```

All commit hashes in this dataset have been verified to exist in their respective repositories.

### Generating Tasks

```bash
cd ~/harbor/adapters/repoqa

# Generate with commit validation (recommended)
python run_adapter.py \
  --dataset_path /path/to/CodeContextBench/benchmarks/repoqa_instances_validated.jsonl \
  --output_dir /path/to/output/repoqa_tasks \
  --variants sr-qa \
  --limit 5

# Skip validation for speed (only if dataset is pre-validated)
python run_adapter.py \
  --dataset_path repoqa-instances.jsonl \
  --output_dir repoqa_tasks \
  --variants sr-qa \
  --skip-validation
```

### Validating Commit Hashes

Before using a dataset, validate all commit hashes:

```bash
cd ~/harbor/adapters/repoqa
python commit_validator.py repoqa-instances.jsonl
```

Output shows:
- VALID COMMITS: Commits found in repositories
- INVALID COMMITS: Commits not found (with error details)
- Summary: X/Y instances valid

### Running Baseline vs MCP Comparison

After generating tasks:

```bash
cd /path/to/CodeContextBench

# Setup environment
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Run comparison
bash scripts/run_mcp_comparison.sh repoqa_benchmark requests-001-sr-qa

# Validate results
python scripts/validate_comparison_results.py \
  jobs/comparison-YYYYMMDD-HHMM/baseline \
  jobs/comparison-YYYYMMDD-HHMM/mcp
```

### Verifier Output Files

The RepoQA verifier:
1. Expects agent output at `/app/solution.json` (shared mount between agent & verifier containers)
2. Expects ground truth at `/tests/ground_truth.json` (uploaded by Harbor)
3. Writes verification results to `/logs/verifier/reward.json` (downloaded by Harbor after verifier completes)

---

## Big Code Task Template & Experimental Design

### Equal File Access Requirement

When evaluating baseline vs MCP agents on big code tasks:

**CRITICAL:** Both agents must have identical file access for valid comparison.

```
VALID SETUP:
  Both agents: Pre-cloned repos in task container
  Baseline: Local grep/find/rg on pre-cloned files
  MCP: Sourcegraph semantic search on pre-cloned files
  -> Measures search strategy difference, not file visibility

INVALID SETUP:
  Baseline: Task container with empty directory stubs
  MCP: Task container with empty stubs + Sourcegraph access (can clone)
  -> Measures file access capability, not search strategy
```

### Big Code Task Dockerfile Pattern

All big code task containers should pre-clone their target repositories:

```dockerfile
FROM [appropriate language image]

WORKDIR /workspace

# Install dependencies
RUN apt-get update && apt-get install -y \
    git curl build-essential [language-specific deps]

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# PRE-CLONE the actual repository (CRITICAL for equal file access)
RUN git clone --depth 1 https://github.com/[owner]/[repo].git . && \
    git config user.email "agent@example.com" && \
    git config user.name "Agent"

# Install language dependencies (optional, for testing)
RUN [language-specific setup: npm install, go build, cargo build, etc.]
```

**Key points:**
- Use `--depth 1` for shallow clone (faster, less disk)
- Clone into `.` (current directory = /workspace)
- Initialize git config (agents need to make commits)
- Language dependencies optional (testing may fail, that's ok)

### Big Code Task Instruction Template

For all big code tasks, include explicit critical requirements:

```markdown
## CRITICAL REQUIREMENTS

YOU MUST MAKE ACTUAL CODE CHANGES. Do not plan or analyze. You must:

1. Understand the distributed architecture using Sourcegraph MCP
   - Issue deepsearch questions about system architecture
   - Find all locations where your changes need to be made

2. Make code changes to the real codebase
   - Real files, real git commits
   - Follow existing patterns and conventions

3. Attempt to run the test suite
   - Run tests: [command]
   - If tests fail due to environment (missing deps, build failure):
     - Document the specific error
     - Provide comprehensive alternative validation
     - Show architectural correctness through code review

4. Commit all changes
   - Proper git commit messages
   - Each commit should be atomic (one feature/fix per commit)

## What Counts

- Real code changes in real files
- Proper git commits with sensible messages
- Test execution attempt with documented failures
- Integration with existing patterns

## What Doesn't Count

- Mock implementations separate from real codebase
- Test documentation without execution attempt
- Architectural analysis without code changes
- Skipping the test attempt entirely
```

---

## Comparison Results Best Practices

### Naming Conventions

Use **timestamped directory names** to prevent confusion with retries:

```
jobs/comparison-YYYYMMDD-HHMM/
  ├── baseline/     (baseline agent results)
  └── mcp/          (MCP agent results)
```

### Validation Checklist

Before analyzing any comparison results, ALWAYS:

1. **Run validation script**: `python scripts/validate_comparison_results.py baseline/ mcp/`
2. **Check for API key errors**: Look for "Invalid API key" in trajectory messages
3. **Verify token counts**: Should be >0 for all valid runs (0 tokens + 6 steps = likely API failure)
4. **Confirm task completeness**: All tasks should have trajectories
5. **Cross-reference timestamps**: Baseline and MCP runs should be from same session

---

## Harbor Adapter Locations

Harbor adapters are installed separately in the Harbor package, NOT in CodeContextBench:

| Adapter | Location | Status |
|---------|----------|--------|
| DI-Bench | `~/harbor/adapters/dibench/` | Production-ready |
| DependEval | `~/harbor/adapters/dependeval/` | In progress |
| RepoQA | `~/harbor/adapters/repoqa/` | Production-ready |

See each adapter's README.md and QUICKSTART.md for usage details.
