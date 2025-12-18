# CodeContextBench Mining Plan (Master Document)

**Status**: Research-grounded, ready to execute  
**Last updated**: 2025-12-17  
**Related beads**: CodeContextBench-wkb (mining), CodeContextBench-cy6 (execution), CodeContextBench-von (analysis)

---

## Quick Reference

This document is the **master plan** for mining, generating, and evaluating 100+ Harbor tasks to test the hypothesis:

**"Sourcegraph code search (via MCP) improves autonomous coding agent performance on multi-file, repository-scale tasks."**

### Key Documents
- **[MINING_STRATEGY.md](MINING_STRATEGY.md)** — Detailed mining pipeline, repo selection, task filters, execution steps
- **[RESEARCH_ALIGNMENT.md](RESEARCH_ALIGNMENT.md)** — How mining strategy aligns with paper hypothesis and literature review

### Related Beads (Phase 2)
| Bead | Work | Status | References |
|------|------|--------|-----------|
| **CodeContextBench-wkb** | Mine 6 repos → 50-75 tasks |  Open | MINING_STRATEGY.md |
| **CodeContextBench-cy6** | Run Harbor benchmarks (baseline vs +MCP) |  Open (blocked on wkb) | MINING_PLAN.md |
| **CodeContextBench-von** | Aggregate results, test hypothesis |  Open (blocked on cy6) | MINING_PLAN.md |

---

## Hypothesis & Task Design

### Core Hypothesis
**Access to Sourcegraph code search improves agent success on multi-file, repository-scale tasks.**

### Trevor Nederlof Validation (December 2025)
**Critical Finding**: Trevor Nederlof's experimental testing (documented in ~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md) provides **empirical evidence** that our hypothesis is correct:

**Big Code Tasks** (Large single repositories):
- **Without Sourcegraph**: "Shakier implementations that do not account for the full architecture/patterns of the codebase and miss certain areas"
- **With Sourcegraph MCP**: "Finds existing mechanisms instead of duplicating functionality; comprehensive context of full architecture"

**Multi-Repo Tasks** (Cross-repository integration):
- **Without Sourcegraph**: Claude Code "made up a bunch of things and missed certain flags... can be quite dangerous for developers to rely on"
- **With Sourcegraph MCP**: Correctly traces APIs and contracts across service boundaries

**Trevor's Final Conclusion**:
> "All of my tests with Sourcegraph MCP added significant value in the large repos... Without it, Claude Code is too eager, leading to shakier implementations."

**Integration**: Three Trevor-validated tasks (sgt-005, sgt-006, sgt-007) are already identified and should be included in our mining set to validate findings.

### Operationalization
- **Baseline agent** (claude-baseline): File ops, git ops only — **NO** code search
- **Treatment agent** (claude-mcp): File ops, git ops **+** Sourcegraph Deep Search via MCP
- **Task set**: 100 real-world GitHub tasks (25 Kubernetes + 50-75 from 6 additional repos)
- **Evaluation**: Success rate, efficiency, cost, failure modes
- **Stratification**: By task category (bugs, features, refactoring, upgrades), difficulty, language

### Expected Results
- Baseline success: 30-40%
- Treatment success: 40-55% (hypothesis: +10-15% improvement)
- Efficiency: +MCP reduces search steps by 20-30%
- Cost: +MCP uses ~10-15% more tokens but achieves higher success

---

## Task Requirements (From Paper Section 3)

### Hard Filters (Mandatory)
 **Multi-file**: ≥2 files changed (enforces codebase understanding requirement)  
 **Real work**: Closed issues + merged PRs from GitHub (not synthetic)  
 **Ground truth**: Can reproduce fix (merged PR shows solution)  
 **Deterministic verification**: Test command exists + expected to pass  
 **Schema validation**: All required fields present (task_filter.py)  

### Soft Filters (Balancing)
⚠️ **Difficulty**: Distribute as easy (40%), medium (40%), hard (20%)  
⚠️ **Category**: Balance bugs, features, refactoring, upgrades  
⚠️ **Language**: Ensure 5+ languages represented  

### Out of Scope
 Single-file edits  
 Synthetic / AI-generated tasks  
 Tasks without test coverage  
 Pattern-matchable fixes  
 Tasks without ground truth  

---

## Repository Selection (6 Additional Repos)

### Target Repos

| Repo | Language | Archetype | Task Target | Rationale | Trevor Validated |
|------|----------|-----------|-------------|-----------|-----------------|
| **mozilla/firefox** | C++ | Browser engine (SpiderMonkey) | 10 | Systems code, complex architecture | — |
| **pytorch/pytorch** | C++/Python | ML framework | 10 | Cross-language interop, performance | — |
| **microsoft/vscode** | TypeScript | Large IDE codebase | 10 | Canonical TS application scale |  sgt-004 |
| **ffmpeg/ffmpeg** | C | Multimedia library | 8 | Signal processing, codec logic | — |
| **NVIDIA/TensorRT-LLM** | C++ | Inference engine | 7 | Performance-critical systems |  sgt-007 |
| **servo/servo** | Rust | Browser engine | 7 | Systems code, memory safety focus |  sgt-006 |

**Total**: 25 Kubernetes + 52 new = ~77 tasks (target: 50-100)

**Trevor Validated Tasks** (from sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md):
-  **sgt-005**: Kubernetes NoScheduleNoTraffic Taint (8 files, HARD, 12K tokens)
-  **sgt-006**: Servo scrollend Event (7 files, HARD, 13K tokens)
-  **sgt-007**: TensorRT-LLM W4A8_MXFP4_INT8 Quantization (7 files, HARD, 11K tokens)

**Multi-Repo Trevor Tasks** (optional, requires cross-repo indexing):
- Optional: **sgt-201**: Temporalio WorkflowInfo (3 repos, HARD, 8.5K tokens)
- Optional: **sgt-202**: Temporalio ParentClosePolicy (3 repos, HARD, 10K tokens)
- Optional: **sgt-203**: Microservices Payment Integration (2 repos, HARD, 9.5K tokens)

### Language Coverage
-  C/C++: firefox, pytorch, tensorrt_llm (3), servo (1) = 4 repos
-  Go: kubernetes (1 repo) + sgt-005
-  Python: pytorch cross-lang plugins
-  TypeScript: vscode (1 repo)
-  Rust: servo (1 repo)
-  Java (optional): Multi-repo tasks

---

## Mining Pipeline (5 Phases)

See **[MINING_STRATEGY.md](MINING_STRATEGY.md)** for full details. Quick summary:

### Phase 1: Repository Selection 
Target 6 repos as above. Pre-check buildability.

### Phase 2: Task Mining
```bash
for repo in firefox pytorch vscode ffmpeg tensorrt_llm servo:
  python -m src.task_mining.mine_tasks \
    --repos $repo \
    --days-back 365 \
    --output artifacts/mining_results_${repo}.json
```

**Criteria**:
- Closed issues with ≥1 merged linked PR
- Merged PRs with ≥2 files changed
- PR has test additions/modifications
- Mining window: Last 365 days

### Phase 3: Task Generation
```bash
for repo_file in artifacts/mining_results_*.json:
  python runners/generate_github_tasks.py \
    $repo_file \
    benchmarks/github_mined/
```

**Output**: Each task gets:
- `instruction.md` (title, description, task, success criteria)
- `task.toml` (metadata: id, language, difficulty, time_limit)
- `environment/Dockerfile` (language-specific)
- `tests/test.sh` (verification script)
- `repo_path` (reference for Harbor)

### Phase 4: Task Validation
```bash
python src/task_mining/task_filter.py \
  --input benchmarks/github_mined/ \
  --output artifacts/task_validation_report.json
```

**Filters applied** (from task_filter.py):
- Schema validation
- Test command presence
- Language support
- Token budget (1000-20000)
- Time limits (60-3600s)
- Git revisions (pre_fix_rev, ground_truth_rev)

**Success criteria**: ≥80% pass validation

### Phase 5: Pilot & Calibration
Run 10 tasks (both agents) to validate:
- Tasks are neither trivial nor intractable
- Success criteria deterministic
- Timeouts appropriate
- Adjust filters if needed before full-scale benchmark

---

## Benchmark Execution (Phase 2b, CodeContextBench-cy6)

See **[MINING_PLAN.md#Benchmark-Execution](#benchmark-execution)** for commands.

### Test Matrix
```
Benchmarks:       10figure, github_mined
Agents:           claude-baseline, claude-mcp
Total runs:       2 benchmarks × 2 agents = 4 job sets
Tasks per run:    10figure (4 tasks) + github_mined (50-100 tasks)
```

### Execution Flow
1. Run baseline on 10figure (4 tasks) → capture manifests
2. Run +MCP on 10figure (4 tasks) → capture manifests
3. Run baseline on github_mined (50-100 tasks) → capture manifests
4. Run +MCP on github_mined (50-100 tasks) → capture manifests

### Instrumentation
Each Harbor run captures:
-  `run_manifest.json` (token usage, cost, duration, success)
-  NeMo traces (if available) or Claude output parsing
-  Tool usage metrics (search queries, file ops, git ops)
-  Execution logs (stdout, stderr, agent reasoning)

---

## Analysis (Phase 2c, CodeContextBench-von)

### Aggregation
```bash
python runners/extract_nemo_traces.py \
  --jobs-dir jobs/ \
  --all \
  --output artifacts/manifests_aggregate.json
```

### Comparative Metrics
For **baseline vs +MCP**:
- **Success rate** (%): Tasks completed per agent per benchmark
- **Avg duration** (s): Mean execution time per successful task
- **Token efficiency** (tokens/success): Cost per successful completion
- **Tool usage**: Search queries, file operations, git operations
- **Failure modes**: Categorize why agents failed (localization, implementation, verification)

### Stratified Analysis
Break results down by:
- **Task category** (bug fix, feature, refactoring, upgrade) → which benefits most from search?
- **Difficulty level** (easy, medium, hard) → does search help hard tasks more?
- **Language** (C++, Go, Python, TS, Rust) → does retrieval generalize?
- **Repo** (kubernetes, firefox, pytorch, etc.) → repo-specific effects?

### Hypothesis Validation
-  **H1**: +MCP success rate > baseline (target: +10-15%)
-  **H2**: +MCP finds relevant code faster (measured by step count in trajectory)
-  **H3**: Bug fixes + upgrades benefit more from search than features
- ⚠️ **H4**: Even with search, some failures persist (localization, implementation, verification)

### Report Output
- HTML report with comparative charts (success rate, cost, efficiency)
- Failure mode analysis (categories + examples)
- Language-specific findings (does TS agent use search differently than C++ agent?)
- Recommendations for agent improvements

---

## Quality Metrics & Success Criteria

### Mining Success 
| Metric | Target | Why |
|--------|--------|-----|
| Tasks mined | 50-100 | Sufficient sample for statistical analysis |
| Pass validation | ≥80% | Most tasks usable as-is |
| Language diversity | 5+ | Demonstrates generalization |
| Avg files per task | 3-8 | Multi-file requirement enforced |
| Test coverage | 100% | Every task verifiable |

### Benchmark Success 
| Metric | Target | Why |
|--------|--------|-----|
| Baseline success | 30-50% | Validates difficulty calibration |
| +MCP improvement | +10-15% | Tests hypothesis |
| Tasks completed | >90% | Minimal failures due to infrastructure |
| Cost per task | <$0.50 | Economically feasible |

### Analysis Success 
| Metric | Target | Why |
|--------|--------|-----|
| Failure modes categorized | >80% | Understand agent bottlenecks |
| Stratified breakdown | 4+ dimensions | Reveal which task types benefit |
| Trajectory quality | >90% | Full agent reasoning captured |

---

## Risk Mitigation

### Mining Risks
| Risk | Mitigation |
|------|-----------|
| Repo buildability issues | Pre-test Dockerfiles on each repo |
| Task flakiness (tests fail randomly) | Allow retries, set reasonable timeouts (10 min) |
| Language complexity (Rust, Go build systems) | Use Harbor's built-in support, test early |
| Too many single-module tasks | Hard filter: ≥2 files mandatory |
| Too few quality tasks per repo | Relax time_limit if needed, include older PRs |

### Execution Risks
| Risk | Mitigation |
|------|-----------|
| Cost explosion | Run pilot (10 tasks) first, monitor per-task cost |
| Long total runtime | Parallelize via Harbor (4 workers), stagger by agent |
| Results non-reproducible | Freeze repo commits, capture env details |
| Agent failures due to setup | Test both agents on 10figure first |

### Analysis Risks
| Risk | Mitigation |
|------|-----------|
| Insufficient sample size | Ensure ≥50 tasks per category for significance |
| Confounding variables | Keep all constants (model, prompting, env) except search |
| Unbalanced difficulty | Use stratified sampling, report by difficulty |

---

## Timeline Estimate

| Phase | Work | Est. Time | Notes |
|-------|------|-----------|-------|
| **Wkb** | Mine 6 repos, generate tasks | 2-4 hours | Depends on GitHub rate limits |
| **Pilot** | Run 10 tasks (both agents) | 30-60 min | Calibrate before full run |
| **Cy6** | Full benchmark (100 tasks × 2 agents) | 4-8 hours | Parallel execution, depends on Harbor |
| **Von** | Aggregate + analysis | 1-2 hours | Post-processing, report generation |
| **Total** | Full pipeline | ~12-15 hours | Can overlap phases |

---

## Files & References

### Core Strategy Documents
- [MINING_STRATEGY.md](MINING_STRATEGY.md) — Detailed pipeline, repo selection, task filters
- [RESEARCH_ALIGNMENT.md](RESEARCH_ALIGNMENT.md) — Paper ↔ strategy alignment

### Input/Output Files
- **Input**: GitHub API via `src/task_mining/`
- **Mining results**: `artifacts/mining_results_*.json`
- **Generated tasks**: `benchmarks/github_mined/`
- **Validation report**: `artifacts/task_validation_report.json`
- **Benchmark results**: `jobs/claude-*-github_mined-*/run_manifest.json`
- **Aggregated metrics**: `artifacts/manifests_aggregate.json`
- **Final report**: `artifacts/comparative_report.html`

### Code References
- **Mining**: `src/task_mining/mine_tasks.py`, `github_client.py`, `task_generator.py`
- **Generation**: `runners/generate_github_tasks.py`
- **Validation**: `src/task_mining/task_filter.py`
- **Analysis**: `runners/extract_nemo_traces.py`, `aggregator.py`

### Configuration
- **Repository definitions**: `src/task_mining/repo_registry.py`
- **Harbor config**: `infrastructure/harbor-config.yaml`
- **Agent configs**: `agents/*.py`

---

## Paper & Literature References

### Paper Goals (Addressed by This Plan)
-  **Section 3**: Task scope requires multi-file, real-world, deterministic verification
-  **Section 3.3**: Repository selection ensures language & domain diversity
-  **Section 3.4**: Task categories stress distinct reasoning behaviors
-  **Section 3.6**: Agent interface isolates causal effect of code search

### Literature Consensus (Operationalized)
-  **GitTaskBench, NL2Repo-Bench**: Long-horizon, multi-file tasks required
-  **ReCode, CoSIL**: Retrieval quality dominates; graph-guided search helps
-  **LoCoBench-Agent**: Trajectory-level metrics capture process quality
-  **SWE-Effi**: Efficiency metrics (tokens, steps, cost) matter alongside correctness

---

## Integrating Trevor Nederlof's Validated Tasks

### Three High-Priority Tasks (Already Researched)

Instead of mining fresh tasks for vscode, tensorrt_llm, servo, **incorporate Trevor's validated scenarios**:

| Task ID | Repo | Problem | Files | Difficulty | Trevor Finding |
|---------|------|---------|-------|-----------|-----------------|
| **sgt-005** | kubernetes | NoScheduleNoTraffic Taint Effect | 8 | HARD | Local grep returns 100s of results; Sourcegraph finds actual evaluation points |
| **sgt-006** | servo | scrollend DOM Event | 7 | HARD | Scroll pipeline spans multiple systems; Sourcegraph traces full flow |
| **sgt-007** | tensorrt_llm | W4A8_MXFP4_INT8 Quantization | 7 | HARD | Cross-language (Python + C++); Sourcegraph keeps sync across layers |

### Integration Strategy

1. **Do NOT mine** for new tasks in vscode, tensorrt_llm, servo (already well-studied)
2. **Use Trevor's task specs** to validate our hypothesis on "big code" tasks
3. **Mine remaining 4 repos** (firefox, pytorch, ffmpeg) + other kubernetes tasks
4. **Add multi-repo tasks** (sgt-201, sgt-202, sgt-203) if cross-repo indexing available

### Expected Outcome

- **Baseline vs +MCP on Trevor's tasks**: Directly compare against Trevor's experimental findings
- **Validation**: Our results should align with Trevor's observations about Sourcegraph value
- **Additional mining**: Identify 40-50 more tasks from other repos for diversity

**Revised target**: 25 Kubernetes (existing) + 3 Trevor (sgt-005/006/007) + 40-50 new mined = ~70-80 total

---

## Next Steps

**Immediate** (CodeContextBench-wkb):
1.  Review MINING_STRATEGY.md + TREVOR_VALIDATED_SCENARIOS.md from ~/sg_benchmark/
2.  Verify GITHUB_TOKEN in .env.local
3. ⚠️ **Adjust mining targets**: Keep Trevor's 3 tasks (don't re-mine), mine 4 new repos (firefox, pytorch, ffmpeg, + more K8s)
4. Monitor first 10 tasks for quality, adjust filters if needed

**After Mining** (CodeContextBench-cy6):
1. Run pilot benchmark with Trevor's 3 tasks (both agents) to validate setup
2. Validate Harbor execution, cost, timing
3. Run full benchmark suite

**After Benchmark** (CodeContextBench-von):
1. Compare our results vs Trevor's findings for sgt-005/006/007
2. Aggregate results across all task types
3. Test hypothesis: does +MCP improve success rate? (expect alignment with Trevor)

---

**Document maintainer**: CodeContextBench project team  
**Last reviewed**: 2025-12-17  
**Status**: Ready to execute (with Trevor integration)
**Trevor Integration**:  COMPLETE (reference ~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md)
