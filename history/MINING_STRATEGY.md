# CodeContextBench GitHub Mining Strategy

## Research Goals (from Paper & Literature Review)

### Primary Hypothesis
**Explicit codebase context retrieval (Sourcegraph code search via MCP) improves autonomous coding agent performance on multi-file, repository-scale tasks.**

### What We're Measuring
- **Effectiveness**: Does the agent succeed? (outcome-driven, not patch-plausible)
- **Efficiency**: How many steps, queries, tokens to succeed?
- **Cost**: What's the USD cost per task?
- **Process**: Which failure modes persist even WITH code search?

---

## Task Requirements (from Paper Section 3)

### In Scope 
- **Multi-file changes** (minimum 2 files): Requires understanding cross-module dependencies
- **Real-world development tasks**: Bug fixes, feature implementations, refactoring, dependency upgrades
- **Ground truth available**: Merged PRs or closed issues with linked PRs (reproducible)
- **Deterministic verification**: Test suite passes OR reproduction command succeeds
- **Realistic codebases**: Large (10k+ LOC), multiple languages, established projects

### Out of Scope 
- Single-file edits (too easy, doesn't require codebase understanding)
- Synthetic or generated tasks (we want real developer work)
- Tasks without deterministic verification (subjective "does this look good?")
- Tasks that can be solved by pattern matching (e.g., "rename all occurrences of X")
- Tasks without existing test coverage (risky to verify)

### Task Diversity Required
**Categories** (from Paper Section 3.4):
- Cross-module bug fixes (root cause + downstream impact across files)
- Feature implementations (new option/config + wiring through layers)
- Dependency/API upgrades (systematic changes across codebase)
- Refactoring tasks (behavior-preserving restructuring)
- Performance optimizations (optional, phased)

**Languages** (from Paper Section 3.5):
- At least one task per language: C/C++, Go, Python, TypeScript, Rust
- Stretch: Java, C#

**Difficulty** (inferred from literature):
- Easy: 2-5 files, straightforward fix, abundant tests
- Medium: 5-15 files, requires understanding 2-3 modules, some edge cases
- Hard: 15+ files, subtle bug across architecture, sparse test coverage

---

## GitHub Mining Pipeline

### Step 1: Repository Selection
**Target 6 additional repos** (already have 25 Kubernetes tasks):

| Repo | Language | Type | Task Count Target |
|------|----------|------|------------------|
| mozilla/firefox | C++ | Browser engine (systems) | 10 |
| pytorch/pytorch | C++/Python | ML framework | 10 |
| microsoft/vscode | TypeScript | IDE | 10 |
| ffmpeg/ffmpeg | C | Multimedia | 8 |
| NVIDIA/TensorRT-LLM | C++ | Inference engine | 7 |
| servo/servo | Rust | Browser engine | 7 |

**Total target**: 25 + 52 = ~77 tasks

### Step 2: Task Mining Criteria
For each repo, search closed issues + merged PRs:

**Closed Issues (with linked merged PR)**:
- Must have ≥1 merged PR in timeline
- PR changed ≥2 files
- PR has ≥1 test (check diff for `test_`, `_test.`, `.test.`)
- Issue description + PR title reasonable (no spam)

**Merged PRs (without required linked issue)**:
- ≥2 files changed
- ≥2 commits (not 1-liner)
- Test additions/modifications present (pattern: `test.*` in PR diff)
- PR merged in last 180-365 days (fresh enough)

**Mining window**: Last 365 days (2024-12-17 to 2023-12-17)

### Step 3: Task Quality Filtering
After mining, apply `task_filter.py` criteria:

**Hard filters** (rejection):
- Schema validation fails
- Test command missing/malformed
- Difficulty, category, or language not set
- Language not in {python, typescript, go, rust, cpp, c, java, csharp}
- Token estimate <1000 or >20000
- Time limit <60s or >3600s
- Missing `source_issue_url` or git revisions

**Soft filters** (warning, use for difficulty balancing):
- Too many files changed (>20) → mark as HARD
- Few files changed (=2) + small diff → mark as EASY
- No test command → manual review

### Step 4: Task Specification Format
Each mined task becomes a Harbor task directory with:

```
benchmarks/github_mined/<task-id>/
├── instruction.md          # Title, description, task, success criteria
├── task.toml               # Metadata (id, repo, language, difficulty, time_limit)
├── task.yaml               # (future expansion)
├── environment/
│   └── Dockerfile          # Language-specific base image + deps
├── tests/
│   └── test.sh             # Verification script
└── repo_path               # Path to repo in Harbor container
```

### Step 5: Execution Plan

**Phase 2a: Mining (CodeContextBench-wkb)**
```bash
# For each repo:
python -m src.task_mining.mine_tasks \
  --repos <repo-key> \
  --days-back 365 \
  --output artifacts/mining_results_<repo>.json

# Generate Harbor tasks from results:
python runners/generate_github_tasks.py \
  artifacts/mining_results_<repo>.json \
  benchmarks/github_mined/

# Validate generated tasks:
python src/task_mining/task_filter.py \
  --input benchmarks/github_mined/ \
  --output artifacts/task_validation_<repo>.json
```

**Phase 2b: Benchmark Execution (CodeContextBench-cy6)**
```bash
# For each benchmark set (10figure, github_mined):
harbor run \
  --agent claude-baseline \
  --benchmark <benchmark-name> \
  --dataset <path-or-env> \
  --jobs-dir jobs/claude-baseline-<benchmark>-<date>

harbor run \
  --agent claude-mcp \
  --benchmark <benchmark-name> \
  --mcp-config infrastructure/mcp-config.json \
  --jobs-dir jobs/claude-mcp-<benchmark>-<date>
```

**Phase 2c: Analysis (CodeContextBench-von)**
```bash
# Extract NeMo traces + generate manifests:
python runners/extract_nemo_traces.py \
  --jobs-dir jobs/ \
  --all \
  --output artifacts/manifests_aggregate.json

# Generate comparative report:
python runners/aggregator.py \
  --manifests artifacts/manifests_aggregate.json \
  --baseline claude-baseline \
  --treatment claude-mcp \
  --output artifacts/comparative_report.html
```

---

## Expected Outcomes

### Task Quantity & Diversity
- **77 total tasks** (25 Kubernetes + 52 from 6 new repos)
- **5+ language coverage** (C++, C, Go, Python, TypeScript, Rust)
- **Difficulty distribution**: ~40% Easy, ~40% Medium, ~20% Hard
- **Category distribution**: Balanced across bug fixes, features, refactoring, upgrades

### Benchmark Results (Hypothesis)
- **Baseline (claude-baseline)**: 30-40% success rate on multi-file tasks
- **Treatment (claude-mcp)**: 40-50% success rate with code search
- **Efficiency**: +MCP reduces steps/queries by 20-30% on successful tasks
- **Cost**: +MCP uses ~10-15% more tokens but achieves higher success

### Failure Mode Analysis
Even with +MCP, expect failures due to:
- **Localization**: Agent finds wrong file (but CoSIL + ReCode suggest graph-guided search helps)
- **Implementation**: Agent understands issue but writes incorrect fix
- **Verification**: Agent doesn't validate against existing behavior
- **State loss**: Agent loses track of goal mid-execution (memory issue)

---

## Mining Success Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Tasks mined | 50-100 | Total across 6 repos |
| Pass validation | >80% | Must pass task_filter.py |
| Language diversity | 5+ languages | C++, Go, Python, TS, Rust minimum |
| Avg files per task | 3-8 | ~= multi-file requirement |
| Test coverage | 100% | Every task must have verification |
| Buildable | >90% | Repos must build in Docker |

---

## Risk Mitigation

### Mining Risks
- **Repo buildability**: Some repos (Firefox, PyTorch) are heavy. Solution: Pre-check Dockerfile feasibility, may need to limit to simple cases
- **Test flakiness**: Tests might be slow or non-deterministic. Solution: Set reasonable timeouts (10 min), allow retries
- **Language support**: Some repos (Go, Rust, C++) may have complex build systems. Solution: Harbor already handles this, test first

### Task Quality Risks
- **Too easy**: Single-liner fixes dominated. Solution: Filter to minimum 2+ files + test count threshold
- **Too hard**: Real-world bugs unsolvable in timeframe. Solution: Bias toward closed issues (proven solvable) + cap time limits at 10 min
- **Sparse tests**: Task verification unclear. Solution: Hard filter on test presence

### Execution Risks
- **Cost explosion**: Many tasks × 2 agents × many retries. Solution: Run pilot (10 tasks, both agents) first to calibrate costs
- **Time to completion**: Full benchmark could take hours. Solution: Parallelize via Harbor (4 workers), stagger by agent

---

## Next Steps

1. **Update CodeContextBench-wkb** with this strategy
2. **Start mining** with firefox + pytorch (2 largest repos)
3. **Monitor first 10 tasks** for quality (language, difficulty, verifiability)
4. **Adjust filters** based on early results (may be too strict/loose)
5. **Scale to remaining 4 repos** once confident

---

## References from Paper

- Paper Section 3.3: Multi-file requirement is **non-negotiable** for evaluating codebase understanding
- Paper Section 3.4: Task diversity is key (bugs + features + refactoring)
- Paper Section 3.5: Language coverage shows if retrieval generalizes across ecosystems
- Literature Review Section 1: Repository-level benchmarks expose context localization as bottleneck
- Literature Review Section 2: Graph-guided retrieval outperforms text-only search
