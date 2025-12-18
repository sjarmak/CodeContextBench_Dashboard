# Research Alignment: Mining Strategy ↔ Paper & Literature Review

## Core Hypothesis → Task Requirements

**Paper Hypothesis**: Sourcegraph code search (via MCP) improves agent performance on multi-file, repository-scale tasks.

###  How Mining Strategy Operationalizes This

| Research Requirement | Mining Implementation |
|---|---|
| **Long-horizon, multi-file tasks** | Hard filter: ≥2 files, ≥2 commits |
| **Real-world work, not synthetic** | Source: Closed GitHub issues + merged PRs |
| **Deterministic verification** | Hard filter: Test command + expected pass/fail |
| **Large, realistic codebases** | Target repos: 100k-1M+ LOC each |
| **Ground truth available** | Use merged PR as reference implementation |
| **Codebase understanding required** | Filter out 1-2 line fixes, single-module changes |

---

## Literature Review → Task Categories & Evaluation

### 2.1 Fine-Grained Retrieval-Augmented Generation

**Literature finding**: "Retrieval quality dominates repair success. Algorithm-aware narrowing and dual encoders outperform generic embedding search."

**Mining implication**: 
- Tasks should require agents to find specific APIs, function calls, interdependencies
- Cross-module bugs (paper section 3.4) force agent to navigate between related functions
- Feature implementations require finding registration points, configuration layers

**Mining filter**: Include category="CROSS_MODULE_BUG_FIX" tasks heavily

---

### 2.2 Graph-Guided Repository Navigation

**Literature finding**: "Code graphs (call graphs, dependency graphs) nearly double localization accuracy. Graph-constrained exploration outperforms free-form search."

**Mining implication**:
- Tasks where the bug fix touches a calling function + callers (not just leaf functions)
- Refactoring tasks that require finding all call sites (dependency-traverse problem)
- Dependency upgrades where change must cascade through call chain

**Mining filter**: Prioritize tasks with 3-8 files changed (enough to require graph traversal, not so many it's intractable)

---

### 3.1-3.2 Memory Systems for Long-Horizon Agents

**Literature finding**: "Memory policy can outweigh model scale. Agents must retain working memory, episodic memory of prior searches, and persistent repo structure."

**Mining implication**:
- Tasks that benefit from agent "remembering" earlier findings (multi-turn)
- Tasks where the solution requires integrating pieces from >3 distinct files
- Refactoring where consistency must be maintained across all locations

**Mining filter**: Tasks with "refactor" or "upgrade" in title/description likely require sustained memory

---

### 1.1 Repository-Level & Long-Horizon Benchmarks

**Literature finding** (GitTaskBench, NL2Repo-Bench):
- "Failures dominated by missing workflow context (dependencies, environment setup)"
- "Even strong agents fail on 35-50% of tasks"
- "Multi-file consistency and project structure correctness are hard"

**Mining implication**:
- Expect 30-50% baseline success rate (validates if we're testing the right difficulty)
- Include tasks that require dependency resolution (feature deps, version constraints)
- Verify test commands include setup steps (not just "pytest")

**Mining filter**: Ensure test_command includes any build/install steps, not just test runner

---

## Paper Task Categories → Mining Task Types

| Paper Category | Mining Target | Why |
|---|---|---|
| **Cross-module bug fixes** | Issues with linked PRs where PR spans 3+ modules | Tests localization + implementation |
| **Feature implementations** | PRs adding new options/commands with wiring through config/registry | Tests navigation to extension points |
| **Dependency upgrades** | PRs with version bumps + systematic call-site updates | Tests high-recall retrieval (find all sites) |
| **Refactoring** | PRs deduplicating code, extracting utilities | Tests cross-file pattern matching |
| **Performance optimization** | PRs with measurable improvement (optional, phased) | Tests non-functional reasoning |

**Mining strategy**: Weight cross-module bugs + dependency upgrades (leverages code search) over simple single-module fixes.

---

## Paper Language & Domain Diversity → Repository Selection

**Paper requirement** (Section 3.5): "Coverage across languages and repository archetypes"

**Mining selection**:

| Repo | Language | Archetype | Justifies |
|---|---|---|---|
| kubernetes | Go | Service orchestration | Go systems code |
| firefox | C++ | Browser engine (SpiderMonkey) | C++ systems, complex architecture |
| pytorch | C++/Python | ML framework | C++/Python interop, performance |
| vscode | TypeScript | IDE (large TS codebase) | TypeScript application scale |
| ffmpeg | C | Multimedia library | C systems, codecs, signal processing |
| tensorrt_llm | C++ | Inference engine | C++ performance-critical |
| servo | Rust | Browser engine | Rust systems code, memory safety |

**Coverage achieved**:
-  C/C++: firefox, pytorch, tensorrt_llm, servo (4 repos)
-  Go: kubernetes (1 repo)
-  Python: pytorch (cross-lang), vscode-python plugins
-  TypeScript: vscode (1 repo)
-  Rust: servo (1 repo)
-  Java/C#: Not included (can add if time permits)

---

## Evaluation Metrics Alignment

**Paper Section 3.1** & **Literature Review Section 1.3** emphasize:
- Trajectory-level analysis (not just pass/fail)
- Efficiency metrics (steps, queries, tokens, cost)
- Process quality (how agent succeeded, not just if)

**Mining strategy feeds into downstream evaluation**:

Each mined task includes:
-  **Time limits** (60-3600s) → measure latency
-  **Test command** → deterministic verification
-  **Repo snapshot** (pre-fix rev + ground-truth rev) → reproducible
-  **Category** (bug, feature, refactor, upgrade) → analyze by type
-  **Difficulty** (easy, medium, hard) → stratified analysis
-  **Language** → cross-ecosystem generalization
-  **Estimated tokens** → cost modeling

---

## Hypothesis Testing via Task Design

**Core question**: *Does Sourcegraph code search improve agent success on multi-file tasks?*

**Task design for isolating effect**:

1. **Matched conditions**: Both agents (baseline + MCP) run on identical tasks
2. **Only variable**: MCP gives access to code search; baseline doesn't
3. **All else held constant**: Model, prompting, execution environment, timeouts
4. **Stratification**: Analyze by category, language, difficulty to reveal which task *types* benefit most from search

**Mining implications**:
- Must have diversity in difficulty (easy tasks may saturate both agents; hard tasks may defeat both)
- Must have diversity in category (some task types may rely more on search than others)
- Must be large enough (77 tasks across conditions, assuming some failures) to achieve statistical significance

---

## Success Criteria Checklist

### For Mining Completeness 
- [ ] 50+ tasks mined from 6 repos (paper requires diverse sources)
- [ ] ≥80% pass schema validation (task_filter.py)
- [ ] ≥5 language types represented (paper Section 3.5)
- [ ] All tasks have verified test commands
- [ ] Difficulty distribution balanced (40/40/20 easy/medium/hard)
- [ ] Category distribution balanced (bugs, features, refactoring, upgrades)

### For Hypothesis Testing 
- [ ] Baseline agent success rate 30-50% (validates difficulty level per literature)
- [ ] MCP agent success rate 40-55%+ (hypothesis: +10% improvement)
- [ ] Analysis reveals which categories benefit most from search (expected: bugs, upgrades > features)
- [ ] Trajectory analysis shows MCP agent finds relevant code faster (fewer steps)
- [ ] Token usage comparable (+MCP uses ~5-15% more due to search overhead)

---

## Risks & Mitigations

### Risk: Tasks too easy (agents saturate at 90%+)
**Mitigation**: Filter to ≥3 files, ≥10 test cases, avoid trivial one-liners

### Risk: Tasks too hard (agents fail at <20%)
**Mitigation**: Bias toward closed issues (proven solvable by humans), cap at 50% hard difficulty

### Risk: Test coverage insufficient
**Mitigation**: Hard filter requires visible test additions in PR, fallback to manual verification

### Risk: Language imbalance (e.g., 40/77 are C++)
**Mitigation**: Set per-language quotas (target 12-15 per language for 6 languages)

### Risk: Too many single-module "fixes"
**Mitigation**: Filter to ≥2 files mandatory, prefer ≥3 for better codebase understanding signal

---

## Summary

**The mining strategy directly operationalizes the paper's hypothesis** by:

1. Sourcing **real, multi-file developer work** (GitHub issues + PRs)
2. Enforcing **deterministic verification** (tests must pass)
3. Requiring **codebase understanding** (≥2 files, cross-module impact)
4. Ensuring **language and domain diversity** (5+ languages, 7 repos)
5. Capturing **task categories** that stress retrieval (bugs, upgrades, refactoring)
6. Enabling **stratified analysis** (by difficulty, category, language)

This task set will isolate the causal impact of Sourcegraph code search (via MCP) on agent performance in the exact domain the paper emphasizes: **long-horizon, repository-scale software engineering tasks where codebase understanding is the limiting factor**.
