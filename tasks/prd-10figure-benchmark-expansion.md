# PRD: 10Figure Benchmark Expansion for MCP Value Evaluation

## Introduction

Expand the 10Figure benchmark from 5 Kubernetes-only tasks to 10 tasks spanning all 4 Phase 1 repositories (Kubernetes, Django, Envoy, TensorFlow), with a focus on cross-repo tasks that maximize the measurable delta between baseline agents and agents equipped with Sourcegraph MCP (code search, cross-file navigation, deep search). Tasks are LLM-assisted: Claude analyzes the actual repos to propose tasks targeting real symbols and code paths, then each task is validated manually.

## Goals

- Produce 10 total benchmark tasks that maximize baseline vs. MCP signal
- Include cross-repo tasks as the primary differentiator (tasks spanning 2+ repos)
- Cover all 4 Phase 1 repos: Kubernetes (Go), Django (Python), Envoy (C++), TensorFlow (C++/Python)
- Cover all 4 task types: cross-file reasoning, refactor/rename, API upgrade, bug localization
- Each task must be runnable via Harbor with automated scoring (reward 0.0-1.0)
- Tasks should be hard enough that baseline agents struggle but MCP agents can succeed

## User Stories

### US-001: Analyze upstream repos for task candidates
**Description:** As a benchmark developer, I want Claude to analyze the 4 Phase 1 repos and propose concrete task candidates targeting real symbols, functions, and code paths so that tasks are grounded in actual code rather than synthetic placeholders.

**Acceptance Criteria:**
- [ ] For each repo (Kubernetes, Django, Envoy, TensorFlow), identify 3-5 candidate symbols/code paths suitable for benchmark tasks
- [ ] Candidates include: symbol name, file path(s), why this tests MCP value (e.g., deep call chain, cross-file refs)
- [ ] Cross-repo candidates identify shared patterns or integration points between repos (e.g., gRPC patterns in both Kubernetes and Envoy, Python bindings in TensorFlow and Django)
- [ ] Output a candidate list as a markdown table with columns: task_type, repos, symbol/target, difficulty, MCP_advantage_rationale

### US-002: Design cross-repo tasks (at least 4)
**Description:** As a benchmark developer, I want at least 4 tasks that require reasoning across 2+ repositories so that MCP cross-repo search capability is directly tested.

**Acceptance Criteria:**
- [ ] At least 4 tasks span 2 or more of the Phase 1 repos
- [ ] Each cross-repo task has a clear rationale for why it requires cross-repo context (not artificially forced)
- [ ] Cross-repo tasks cover at least 2 different task types (e.g., cross-file reasoning + bug localization)
- [ ] Each task has defined expected output (patch, analysis document, or both)

### US-003: Design single-repo tasks for remaining repos (at least 3)
**Description:** As a benchmark developer, I want single-repo tasks for Django, Envoy, and TensorFlow so that the benchmark covers multiple languages and repo structures beyond Kubernetes.

**Acceptance Criteria:**
- [ ] At least 1 task each for Django (Python), Envoy (C++), and TensorFlow (C++/Python)
- [ ] Tasks target real code paths in each repo, not placeholders
- [ ] Each task is hard enough that grep-based exploration is insufficient (large search space, deep nesting, ambiguous naming)
- [ ] Each task type (cross-file reasoning, refactor, API upgrade, bug localization) is represented at least once across the full 10-task set

### US-004: Create Harbor task packages for all 10 tasks
**Description:** As a benchmark runner, I want each task packaged with instruction.md, task.toml, task.yaml, Dockerfile, test.sh, and expected_changes.json so that Harbor can execute and score them.

**Acceptance Criteria:**
- [ ] Each task directory follows the existing structure: `<task_id>/instruction.md`, `task.toml`, `task.yaml`, `environment/Dockerfile`, `tests/test.sh`, `tests/expected_changes.json`
- [ ] Dockerfiles inherit from `harbor-10figure:base` (or a new multi-repo base if needed)
- [ ] test.sh validates agent output and writes reward to `/logs/verifier/reward.txt`
- [ ] All 10 tasks pass structural validation via `smoke_test_10figure.py`

### US-005: Update base Docker image for multi-repo support
**Description:** As a benchmark runner, I want the base Docker image to contain all 4 Phase 1 repos so that cross-repo tasks can execute in a single container.

**Acceptance Criteria:**
- [ ] `base/Dockerfile` imports Kubernetes, Django, Envoy, and TensorFlow source trees into `/10figure/src/`
- [ ] `base/build.sh` updated to clone/checkout all 4 repos at pinned commits
- [ ] Base image builds successfully and contains all 4 repos
- [ ] Image size documented in `base/README.md`

### US-006: Update README and docs
**Description:** As a benchmark user, I want the README to reflect the expanded task set, multi-repo coverage, and cross-repo task design so that the benchmark purpose is clear.

**Acceptance Criteria:**
- [ ] README.md updated with new task table (all 10 tasks)
- [ ] README documents cross-repo vs single-repo task distinction
- [ ] README documents which repos are included and at what commits
- [ ] docs/10FIGURE.md updated with expanded task descriptions

### US-007: Push expanded benchmark to ccb-10figure repo
**Description:** As a project maintainer, I want the expanded benchmark pushed to the ccb-10figure GitHub repo and synced back to CodeContextBench_Dashboard so both repos stay in sync.

**Acceptance Criteria:**
- [ ] All 10 task directories committed to sjarmak/ccb-10figure
- [ ] benchmarks/10figure/ in CodeContextBench_Dashboard matches ccb-10figure contents
- [ ] No broken references between repos

## Functional Requirements

- FR-1: The benchmark must contain exactly 10 scored tasks (simple_test_01 remains as an unnumbered smoke test, not counted)
- FR-2: At least 4 tasks must be cross-repo (spanning 2+ of Kubernetes, Django, Envoy, TensorFlow)
- FR-3: All 4 task types must be represented: cross_file_reasoning, refactor_rename, api_upgrade, bug_localization
- FR-4: All 4 Phase 1 repos must be represented: Kubernetes (Go), Django (Python), Envoy (C++), TensorFlow (C++/Python)
- FR-5: Each task must target real symbols/code paths in the actual repos (no placeholder symbols like FooMethod)
- FR-6: Each task must include automated scoring via test.sh that produces a reward between 0.0 and 1.0
- FR-7: Cross-repo tasks must require information from multiple repos to solve correctly (not just touching multiple repos for cosmetic reasons)
- FR-8: The base Docker image must contain all 4 repos at pinned commits for reproducibility
- FR-9: Tasks must be designed so that MCP agents have a measurable advantage (large search space, deep call chains, cross-repo references)
- FR-10: Existing 4 scored tasks (api_upgrade_01, bug_localization_01, cross_file_reasoning_01, refactor_rename_01) are retained; 6 new tasks are added to reach 10

## Non-Goals

- Not building a general-purpose benchmark framework (this is specifically for MCP value evaluation)
- Not generating tasks via the upstream 10Figure transform pipeline (using LLM-assisted approach instead)
- Not covering Phase 2/3/4 repos from repos.yaml (etcd, Prometheus, Linux kernel, etc.)
- Not implementing new scoring algorithms (reuse existing patch validation)
- Not creating a web UI or dashboard for this benchmark (use existing CodeContextBench dashboard)
- Not adding support for non-Harbor execution environments

## Technical Considerations

- **Repo pinning:** Each repo must be pinned to a specific commit SHA for reproducibility. Use recent stable tags (e.g., Kubernetes v1.29.x, Django 5.0.x, Envoy v1.29.x, TensorFlow v2.16.x)
- **Image size:** Adding 4 repos will significantly increase the base image. Consider multi-stage builds or shallow clones to manage size. Document expected image size.
- **Cross-repo task design:** The challenge is finding genuine cross-repo connections. Realistic options include:
  - Shared patterns (gRPC in K8s and Envoy, Python C extensions in TF and Django)
  - Similar bug patterns across repos (nil/null pointer handling in Go vs C++)
  - API migration patterns that appear in multiple languages
  - Architectural patterns (middleware chains in Django vs filter chains in Envoy)
- **LLM-assisted task creation:** Use Claude to analyze repos via Sourcegraph search or local checkout, identify candidate symbols, then manually verify the task is solvable and scorable
- **Scoring cross-repo tasks:** test.sh must check patches/output that span multiple repo directories under `/10figure/src/`

## Success Metrics

- At least 20% higher average reward for MCP agents vs baseline agents on cross-repo tasks
- At least 10% higher average reward for MCP agents vs baseline on the full 10-task set
- All 10 tasks produce non-trivial scores (no tasks where both agents score 0.0 or both score 1.0)
- Cross-repo tasks show larger MCP delta than single-repo tasks (validating the benchmark design thesis)

## Resolved Decisions

- **simple_test_01** stays as an unnumbered smoke test, not counted in the 10 scored tasks
- **Repo pinning** confirmed — each repo pinned to a specific commit SHA for reproducibility
- **Q1: Commit SHAs** — Pinned to 10Figure-Codebases corpus commits (these are HEAD-ish commits already checked out in the local corpus):
  | Repo | Commit SHA | Short |
  |------|-----------|-------|
  | Kubernetes (Go) | `ef274e869c3ea3d4042fada38a56221283a42362` | `ef274e86` |
  | Envoy (C++) | `782c6caee166a8414097f548f7309114863379a8` | `782c6cae` |
  | Django (Python) | `c4e07f94ebc1f9eaa3dae7b3dc6a2b9832182a10` | `c4e07f94` |
  | TensorFlow (C++/Python) | `420baf67d8c9fce3b66e435e7a4fdec57ecf4122` | `420baf67` |
  Note: `kubernetes--latest` mirror exists in sg-benchmarks org. Envoy and TensorFlow mirrors need to be created for Sourcegraph MCP indexing.
- **Q2: Patch format** — Single combined patch per task. Agents produce one `patch.diff` at `/logs/agent/patch.diff` that may span multiple repo directories under `/10figure/src/`. The test.sh script splits and scores per-repo, then combines into a weighted reward. This is simpler for agents and consistent with existing single-repo tasks.
- **Q3: Docker image strategy** — Keep the existing corpus-copy approach (`COPY 10Figure-Codebases /10figure`). The base image already contains all 4 repos (~6-8GB per base/README.md). Multi-stage build is not needed since the corpus is pre-built externally. Run on Daytona VMs with pre-pulled images for CI; local builds acceptable for development.
- **Q4: Scoring rubric** — Per-repo weighted scoring. Each cross-repo task defines weights in `expected_changes.json` (e.g., `{"kubernetes": 0.6, "envoy": 0.4}`). Weights proportional to expected changes per repo. `validate_patch.py` extended with `--weights` argument (US-008). Task-type-specific scoring logic (pattern matching, symbol chain, file identification) remains in each task's `test.sh`. The weighted combination is the shared cross-repo layer on top.
