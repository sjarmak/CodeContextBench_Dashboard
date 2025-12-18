# Trevor Nederlof Integration: Mining Plan Updated

**Date**: 2025-12-17  
**Source**: ~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md  
**Status**:  Integrated into CodeContextBench-wkb mining strategy

---

## What We Found

Trevor Nederlof (December 2025) conducted **empirical research** testing Claude Code with/without Sourcegraph MCP on large codebases. His findings **directly validate our hypothesis** and provide **pre-researched task specifications** we can leverage.

---

## Three Trevor-Validated Big Code Tasks

These tasks are already well-studied and have documented Sourcegraph value:

### sgt-005: Kubernetes NoScheduleNoTraffic Taint Effect

**Repository**: kubernetes/kubernetes (1.4 GB, Go)  
**Problem**: Implement new node taint effect affecting scheduling AND load balancing  
**Scope**: 8 files, HARD difficulty, 12K tokens  

**Why Sourcegraph Matters**:
- Taint evaluation points spread across scheduler, controller, endpoint slice subsystems
- Local grep for "taint" returns 100s of results (poor signal)
- Sourcegraph indexed search identifies actual evaluation points across modules

**Trevor Finding**:
> "Test2 (CC + Sourcegraph) was much more comprehensive in finding tests, utilities, and settings to change."

---

### sgt-006: Servo scrollend DOM Event Implementation

**Repository**: servo/servo (1.6 GB, Rust)  
**Problem**: Add scrollend DOM event with debouncing for scroll input types  
**Scope**: 7 files, HARD difficulty, 13K tokens  

**Why Sourcegraph Matters**:
- Scroll event pipeline spans compositor, document, and element event systems
- Understanding full flow requires tracing events from multiple entry points
- Local search difficult to correlate different scroll mechanisms

**Trevor Finding**:
> "Sourcegraph MCP showed significant improvement in both speed and answer quality, with more comprehensive context."

---

### sgt-007: TensorRT-LLM W4A8_MXFP4_INT8 Quantization Mode

**Repository**: NVIDIA/TensorRT-LLM (1.6 GB, Python + C++ + CUDA)  
**Problem**: Add new quantization mode matching existing W4A8_MXFP4_FP8 pattern  
**Scope**: 7 files, HARD difficulty, 11K tokens  

**Why Sourcegraph Matters**:
- Cross-language implementation (Python + C++)
- Quantization mode used in multiple layers (enum, kernel selection, validation)
- Must keep Python/C++ in sync — requires understanding all usage points
- Local search across both languages inefficient

**Trevor Finding**:
> "Claude Code + Sourcegraph MCP is much superior. Without it, shakier implementations that do not account for the full architecture/patterns of the codebase and miss certain areas."

---

## Multi-Repo Tasks (Optional, Research-Grade)

Trevor also documented three multi-repo tasks that demonstrate Sourcegraph value across service boundaries:

### sgt-201: Temporalio WorkflowInfo Field

**Repositories**: temporalio/sdk-go + go.temporal.io/api + temporalio/temporal  
**Problem**: Expose server-tracked data in SDK's WorkflowInfo  
**Why Sourcegraph Matters**: Data flows through 3 repos (server → API bindings → SDK)

**Trevor Finding**:
> "Sourcegraph MCP is needed in this case to provide a meaningful answer since information from the API, go bindings and server are needed."

---

### sgt-202: Temporalio ParentClosePolicy Debugging

**Repositories**: temporalio/sdk-go + go.temporal.io/api + temporalio/temporal  
**Problem**: Child workflows not terminating based on ParentClosePolicy  
**Why Sourcegraph Matters**: Bug could be at any layer; policy handling spans all 3 repos

**Trevor Finding**:
> "Without Sourcegraph MCP, Claude Code made up a bunch of things and missed certain flags without the visibility. The most striking thing is how much Claude Code will try and claim without having access to the code, this can be quite dangerous for developers to rely on."

---

### sgt-203: Microservices Payment Service Integration

**Repositories**: orders-service + payment-service  
**Problem**: Orders fail with "Payment declined" despite sufficient funds  
**Why Sourcegraph Matters**: Must understand API contract between services

**Trevor Finding**:
> "Claude Code alone is pretty useless for this type of query unless the other repos are cloned locally. CC also hallucinated quite a bit in assuming/making things up."

---

## Integration Strategy

### What Changed

**Original Plan**:
- Mine 6 repos (firefox, pytorch, vscode, ffmpeg, tensorrt_llm, servo)
- Generate 50-75 new tasks
- Total: 25 K8s + 50-75 new = ~100 tasks

**Updated Plan**:
- **Reuse Trevor's 3 big code tasks** (sgt-005, sgt-006, sgt-007) — don't re-mine
- Mine 4 repos only (firefox, pytorch, ffmpeg, + more K8s for broader coverage)
- Generate 40-50 new tasks
- **Optional**: Add Trevor's 3 multi-repo tasks if cross-repo indexing available
- Total: 25 K8s + 3 Trevor + 40-50 new = ~70-80 tasks + optional multi-repo

### Why This Approach

1. **Efficiency**: Trevor already did the hard work (finding/validating complex tasks)
2. **Validation**: We can directly compare our results vs Trevor's findings
3. **Quality**: Ensures at least 3 high-difficulty tasks with documented Sourcegraph value
4. **Coverage**: Still get diverse languages/repos from mining 4 new repos
5. **Scope Control**: Reduces total tasks to ~70-80 (still sufficient for statistical analysis)

### Expected Research Outcome

**For sgt-005, sgt-006, sgt-007**:
- Baseline agent success rate: ~30% (expected to struggle without search)
- +MCP agent success rate: ~50%+ (expected to benefit from Sourcegraph)
- **Validation**: Our results should align with Trevor's observations

**For newly mined tasks**:
- Broader coverage across languages/domains
- Test if benefits generalize beyond Trevor's curated set

**For multi-repo tasks (optional)**:
- First CodeContextBench evaluation of cross-repo code search
- Addresses enterprise use case (microservices, federated systems)
- Highlights hallucination reduction with Sourcegraph

---

## Files & References

### Trevor's Original Documentation
- **Primary**: ~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md
- **Full Research Notes**: https://docs.google.com/document/d/1DsmVoUbo4fl94VkhmcIE5jLSzz7SWowcVNMMyRADcy0/edit?usp=sharing

### CodeContextBench Integration
- **Master Plan**: history/MINING_PLAN.md (updated section: "Integrating Trevor's Validated Tasks")
- **Bead Reference**: CodeContextBench-wkb (mining task)
- **Status**:  Trevor tasks pre-specified; don't re-mine

---

## Trevor's Key Quotes (For Hypothesis Validation)

### On Big Code Problems

> "All of my tests with Sourcegraph MCP added significant value in the large repos below (VS Code, Kubernetes, Servo, TensorRT-LLM). Without it, Claude Code is too eager, leading to shakier implementations that do not account for the full architecture/patterns of the codebase and miss certain areas."

### On Multi-Repo Problems

> "Without Sourcegraph MCP, Claude Code made up a bunch of things and missed certain flags without the visibility. The most striking thing is how much Claude Code will try and claim without having access to the code, this can be quite dangerous for developers to rely on."

### On Cross-Service Debugging

> "Sourcegraph MCP is needed in this case to provide a meaningful answer since information from the API, go bindings and server are needed. When using Claude Code alone it just guesses at some of these things and tells the user to go look in other repos."

---

## Next Steps

### For CodeContextBench-wkb (Mining)

1.  Read ~/sg_benchmark/TREVOR_VALIDATED_SCENARIOS.md
2.  Confirm task specs for sgt-005, sgt-006, sgt-007 match our format
3. Copy/convert Trevor's task specs into benchmarks/github_mined/ (or separate trevor_validated/ dir)
4. Mine firefox, pytorch, ffmpeg (+ more K8s tasks) for 40-50 additional tasks
5. Total: 25 K8s + 3 Trevor + 40-50 new = ~70-80 tasks

### For CodeContextBench-cy6 (Benchmarks)

1. Run pilot with Trevor's 3 tasks (both agents) to validate infrastructure
2. Compare results vs Trevor's documented findings
3. Run full benchmark suite (all 70-80 tasks)

### For CodeContextBench-von (Analysis)

1. Verify our results align with Trevor's observations for sgt-005/006/007
2. Analyze whether benefits generalize to newly mined tasks
3. Generate final report with hypothesis validation

---

## Document Status

 **Trevor's validation integrated into CodeContextBench mining strategy**  
 **Three pre-researched high-difficulty tasks identified for pilot**  
 **Multi-repo tasks documented for optional Phase 2 expansion**  
 **Mining plan adjusted to leverage existing research**

**Integration Date**: 2025-12-17  
**Integrated By**: CodeContextBench project team  
**Ref**: Trevor Nederlof's Experimental Testing (December 2025)
