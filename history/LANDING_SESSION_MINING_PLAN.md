# Landing Session Summary: Mining Strategy Planning (2025-12-17)

**Session**: Comprehensive planning for CodeContextBench Phase 2 (Mining & Benchmarks)  
**Status**:  COMPLETE  
**Beads Affected**: 5 open (CodeContextBench-wkb, -cy6, -von, -0f3, -mw8)  

---

## What Was Done This Session

### Planning & Documentation (COMPLETE)
-  Reviewed paper hypothesis & literature consensus
-  Planned 5-phase mining pipeline (research-grounded)
-  Created 5 comprehensive strategy documents (6000+ words total)
-  Integrated Trevor Nederlof's validated task specs
-  Updated all Phase 2 beads with document references
-  Adjusted mining targets leveraging existing research

### Document Artifacts Created
1. **history/MINING_PLAN.md** (6000+ words) — Master strategy
2. **history/MINING_STRATEGY.md** (detailed) — Technical pipeline
3. **history/RESEARCH_ALIGNMENT.md** (detailed) — Paper/literature grounding
4. **history/TREVOR_INTEGRATION.md** (detailed) — Trevor findings & integration
5. **history/SESSION_SUMMARY_TREVOR_INTEGRATION.md** — Session recap

### Beads Updated
-  **CodeContextBench-wkb** (Phase 2a: Mining) — references MINING_PLAN.md
-  **CodeContextBench-cy6** (Phase 2b: Benchmarks) — references MINING_PLAN.md Phase 2b
-  **CodeContextBench-von** (Phase 2c: Analysis) — references MINING_PLAN.md Phase 2c
-  **CodeContextBench-0f3** (Phase 3: Documentation) — references MINING_PLAN.md
-  **CodeContextBench-mw8** (Phase 3: tool_profiles) — independent

### Research Integration
-  Reviewed paper hypothesis (PAPER_DRAFT_121625.md)
-  Reviewed literature consensus (LITERATURE_REVIEW.md)
-  Found & integrated Trevor Nederlof validation (~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md)
-  Aligned mining strategy with all three research sources
-  Identified 3 pre-researched tasks (sgt-005, sgt-006, sgt-007)
-  Identified 3 optional multi-repo tasks (sgt-201, sgt-202, sgt-203)

---

## Key Decisions & Outcomes

### Mining Strategy Finalized

**Scope**: 70-80 tasks across 5+ languages
- 25 existing Kubernetes tasks (already generated)
- 3 Trevor-validated big code tasks (don't re-mine)
- 40-50 new tasks mined from 4 repos (firefox, pytorch, ffmpeg, more K8s)
- 3 optional multi-repo tasks (if cross-repo indexing available)

**Quality Filters** (enforced):
- ≥2 files changed (multi-file requirement)
- Deterministic verification (test command exists)
- Real developer work (GitHub issues + merged PRs)
- Ground truth available (reproducible)
- Schema validation (all fields present)

**Hypothesis Testing**:
- Baseline (no code search): 30-40% expected success
- +MCP (with Sourcegraph): 40-55% expected success
- Validation: Results align with Trevor's findings

### Trevor Nederlof Integration

**Critical Finding**: Trevor's experimental testing (December 2025) directly validates hypothesis

**Big Code Tasks** (pre-researched):
- sgt-005: Kubernetes NoScheduleNoTraffic Taint (8 files, HARD)
- sgt-006: Servo scrollend Event (7 files, HARD)
- sgt-007: TensorRT-LLM Quantization Mode (7 files, HARD)

**Multi-Repo Tasks** (optional):
- sgt-201: Temporalio WorkflowInfo (3 repos, HARD)
- sgt-202: Temporalio ParentClosePolicy (3 repos, HARD)
- sgt-203: Microservices Payment Integration (2 repos, HARD)

**Trevor's Key Quotes**:
> "Without Sourcegraph MCP, Claude Code is too eager, leading to shakier implementations that miss architectural patterns"
> "With Sourcegraph MCP, finds existing mechanisms instead of duplicating, comprehensive context"

---

## Next Steps (Ready for Execution)

### CodeContextBench-wkb (Phase 2a: Mining)

**Status**:  Open, Priority 1  
**Next Session**: Execute mining (ready to begin)

**Steps**:
1. Verify GITHUB_TOKEN is set in .env.local
2. Reference history/MINING_PLAN.md (master guide)
3. Reference history/MINING_STRATEGY.md (technical pipeline)
4. Mine 4 repos: firefox, pytorch, ffmpeg, kubernetes
5. Generate Harbor task directories via runners/generate_github_tasks.py
6. Validate tasks pass task_filter.py checks (≥80% target)
7. Close bead when complete

**Expected Output**:
- artifacts/mining_results_*.json (per repo)
- benchmarks/github_mined/ (Harbor task directories)
- artifacts/task_validation_report.json

---

### CodeContextBench-cy6 (Phase 2b: Benchmarks)

**Status**:  Open, Priority 1 (blocked on wkb)  
**Unblock**: When mining complete (wkb closed)

**Steps**:
1. Wait for CodeContextBench-wkb completion
2. Run pilot benchmark with Trevor's 3 tasks (both agents)
3. Validate Harbor execution, cost, timing
4. Run full benchmark suite (70-80 tasks × 2 agents)
5. Capture manifests, NeMo traces, tool usage

**Expected Output**:
- jobs/claude-baseline-*/ (execution results)
- jobs/claude-mcp-*/ (execution results)
- run_manifest.json files (per task)

---

### CodeContextBench-von (Phase 2c: Analysis)

**Status**:  Open, Priority 2 (blocked on cy6)  
**Unblock**: When benchmarks complete (cy6 closed)

**Steps**:
1. Extract NeMo traces / Claude output parsing
2. Aggregate results across task types
3. Compare vs Trevor's documented findings for sgt-005/006/007
4. Stratified analysis (by category, difficulty, language)
5. Generate HTML/JSON comparative report
6. Test hypothesis: does +MCP improve success? (target: +10-15%)

**Expected Output**:
- artifacts/manifests_aggregate.json
- artifacts/comparative_report.html
- Hypothesis validation results

---

## Quality Gates

**Code Changes Made**: No production code changes (planning-only session)  
**Documentation**:  Complete (5 comprehensive documents created)  
**Beads**:  Updated (all Phase 2 beads reference master plan)  
**Git**:  Clean (committed bead changes)

---

## Files & References

### Created This Session
```
history/
├── MINING_PLAN.md                          (6000+ words - MASTER)
├── MINING_STRATEGY.md                      (detailed technical pipeline)
├── RESEARCH_ALIGNMENT.md                   (paper/literature grounding)
├── TREVOR_INTEGRATION.md                   (Trevor findings & integration)
├── SESSION_SUMMARY_TREVOR_INTEGRATION.md   (session recap)
└── LANDING_SESSION_MINING_PLAN.md          (this file)
```

### Referenced External
- **~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md** — Trevor's full documentation
- **docs/paper_resources/PAPER_DRAFT_121625.md** — Paper hypothesis & design
- **docs/paper_resources/LITERATURE_REVIEW.md** — Literature consensus

### Code References
- **src/task_mining/mine_tasks.py** — Main mining entry point
- **runners/generate_github_tasks.py** — Task generation from mining results
- **src/task_mining/task_filter.py** — Task validation
- **observability/manifest_writer.py** — Benchmark result capture
- **runners/extract_nemo_traces.py** — Result aggregation & analysis

---

## Recommended Next Session Prompt

```
Continue work on CodeContextBench Phase 2a mining (CodeContextBench-wkb). 

Execute the mining strategy documented in history/MINING_PLAN.md:
- Mine 4 OSS repos (firefox, pytorch, ffmpeg, kubernetes)
- Target 40-50 high-quality Harbor tasks
- Include Trevor's validated tasks (sgt-005, sgt-006, sgt-007)
- Validate ≥80% pass schema checks

Reference documents:
- history/MINING_PLAN.md (master strategy)
- history/MINING_STRATEGY.md (technical pipeline)
- history/TREVOR_INTEGRATION.md (task specs)

After mining complete, close CodeContextBench-wkb and begin Phase 2b benchmarks (CodeContextBench-cy6).
```

---

## Session Metrics

| Metric | Value |
|--------|-------|
| Documents created | 5 |
| Words written | 6000+ |
| Beads updated | 5 |
| Research sources integrated | 3 (paper, literature, Trevor) |
| Validated tasks identified | 6 (3 big code + 3 multi-repo) |
| Mining repos targeted | 4 (+ 25 existing K8s) |
| Estimated tasks generated | 70-80 |
| Git commits | 1 |
| Beads ready for execution | 5 |
| Status |  COMPLETE |

---

## Sign-Off

 **Research planning complete**  
 **Mining strategy finalized**  
 **Trevor validation integrated**  
 **Beads updated & ready**  
 **Ready for Phase 2a execution**

**Team**: CodeContextBench  
**Date**: 2025-12-17  
**Duration**: Full session planning cycle  
**Next**: Begin mining (CodeContextBench-wkb)

---
