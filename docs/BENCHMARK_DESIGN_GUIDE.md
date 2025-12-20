# Comprehensive Benchmark Design Guide for Large Codebase Code Agents

## Overview

This document provides a comprehensive framework for evaluating LLM-based coding agents on realistic, large-scale software engineering tasks. Rather than focusing on isolated code snippets, this design emphasizes the enterprise developer experience: understanding sprawling codebases, making coordinated multi-file changes, debugging legacy systems, and maintaining consistency across components.

The guide synthesizes insights from recent research benchmarks (DI-Bench, DependEval, RepoQA, CrossCodeEval, PerfBench, etc.) and proposes task categories that directly demonstrate the value of integrated code intelligence tools like Sourcegraph.

---

## Goals and Challenges

### Core Objectives

1. **Showcase Code Context Benefits**
   - Choose tasks where baseline agents (e.g., Claude Code alone) likely fail or hallucinate due to missing context
   - Demonstrate how the same agent augmented with code search and retrieval succeeds
   - Directly illustrate the value of integrated code intelligence

2. **Reflect Enterprise Developer Tasks**
   - Focus on realistic workflows from large tech companies
   - Cover the full software development lifecycle: coding, debugging, code review, maintenance
   - Include tasks like codebase exploration, multi-file edits, dependency management, legacy system handling

3. **Simulate Multi-Step Workflows**
   - Incorporate iterative reasoning scenarios
   - Require multi-file or multi-repository coordination
   - Test agent memory and information integration over long contexts

4. **Robust Evaluation Methodology**
   - Use objective metrics where possible (test pass/fail, ground-truth code matches)
   - Supplement with LLM-as-judge for subjective criteria
   - Follow best practices for fair assessment (clear rubrics, careful prompt design)

---

## Task Categories

### 1. Repository-Level Dependency and Architecture Tasks

Understanding how code pieces fit together is crucial in large, legacy systems. Single-task benchmarks miss this entirely.

#### 1.1 Dependency Inference (DI-Bench)

**Problem Space:**
- Given a codebase with dependency declarations masked, agents must produce the correct list of required libraries (with versions)
- Real-world impact: ~50% of runtime errors in generated projects stem from missing/incorrect dependencies
- Research finding: Even top models achieve only ~42.9% execution success on DI-Bench

**Why MCP Matters:**
- Agents can search for `import` statements and API usages across files instead of guessing
- Mirrors how developers use code search to update `requirements.txt` or `build.toml`
- Example: An agent might spot usage of `metrics.SCORERS` (added in scikit-learn 0.24) and select the correct version, whereas a baseline would pick an outdated version causing runtime errors

**Evaluation Metrics:**
- Textual match to ground-truth dependency list (set similarity)
- Execution success: does project build/run with inferred dependencies?
- Completeness: what % of required dependencies were identified?

#### 1.2 Cross-Component Understanding (DependEval)

**Problem Space:**
- Determine invocation order between files (Dependency Recognition)
- Organize code into correct multi-file structure given a design (Repository Construction)
- Tests architectural reasoning: can agents figure out how files depend on each other?

**Why MCP Matters:**
- Deep search quickly locates function definitions across repositories
- Handles multi-package/microservice scenarios (common in enterprises)
- Example: "Module in service_A calls function in service_B; identify and fix broken dependency"

**Evaluation Metrics:**
- Correctness of modifications (code compiles, tests pass)
- Consistency: were all relevant locations updated?
- Completeness: did agent find all cross-module dependencies?

#### Key Insight
Consistency across files is a documented weakness of vanilla LLMs. Retrieval-augmented agents can systematically find all occurrences (like "Find All References" in an IDE) and ensure nothing is missed.

---

### 2. Long-Context Code Search and Comprehension

Developers at large companies spend significant time searching codebases for answers. This category measures an agent's skill in navigating large, complex codebases.

#### 2.1 Code Question-Answering (RepoQA-inspired)

**Problem Space:**
- Evaluate agent's ability to retrieve and interpret code from large contexts
- Tasks like: "Where is the function that handles JWT validation?" or "What does the Scheduler class do?"
- Research finding: Baseline models struggle if relevant code isn't explicitly in the prompt; more context improves success rates
- Challenge: Stuffing 16K tokens of code is not scalable for truly large projects

**Why MCP Matters:**
- Live code search via Sourcegraph API (substring, regex, or semantic)
- Pinpoints relevant files without needing full codebase in prompt
- Enables baseline agents to handle tasks previously requiring training data

**Example Tasks:**
- "Identify the function that validates user JWT tokens in the Auth service repository"
- "What does the Scheduler class do, and where is it implemented?"
- "Find all places where we format SQL queries by string concatenation" (security-relevant search)

**Evaluation Metrics:**
- Exact-match correctness of the answer
- Semantic similarity to target code (BLEU, code overlap)
- Information Retrieval metrics: did search hits include the true answer?

#### 2.2 Code Reading and Summarization

**Problem Space:**
- Real developer workflows involve reading and summarizing code (onboarding, code review)
- Agent reads a module and explains its logic
- Requires understanding of function definitions, usages, related documentation

**Why MCP Matters:**
- Retrieval of related function definitions, usage patterns, and commit messages
- Tests comprehension beyond code-generation alone
- Simulates how developers learn new codebases

**Example Tasks:**
- "Explain the authentication flow in this service"
- "What are the dependencies and side effects of this function?"

**Evaluation Metrics:**
- LLM-as-judge: clarity and accuracy of explanation
- Completeness: did explanation cover key aspects?
- Correctness: does explanation match code behavior?

#### Key Insight
Research surveys note that "long-context understanding is especially vital for assisting development of real-world projects with thousands or millions of lines of code." RepoQA found that even with retrieval, models aren't perfect—but with it, performance improves dramatically.

---

### 3. Cross-File Code Completion and Refactoring

Real enterprises frequently need coordinated edits across dozens of modules. This category tests multi-file code generation and consistency.

#### 3.1 Cross-File Code Completion (CrossCodeEval)

**Problem Space:**
- Complete code snippets that require referencing code in other files
- Example: "Implement function Y in module A that must interact with class X in module B"
- Research finding: Models perform "extremely challenging" when cross-file context is absent, but improve dramatically with retrieval
- Challenge: State-of-the-art models with retrieval are still far from perfect

**Why MCP Matters:**
- On-demand retrieval of imported files or identifier definitions
- Agents can search for dependencies before generating code
- Eliminates guessing about cross-file APIs

**Evaluation Metrics:**
- Exact match to reference solution
- Edit similarity to known correct implementation
- Test execution: does generated code pass tests?

#### 3.2 Multi-File Editing Consistency (DependEval)

**Problem Space:**
- Make modifications affecting multiple files (e.g., changing function signature and updating all callers)
- Example: "Refactor Config class into Config + DatabaseConfig, updating all references"
- Requires consistency across many locations

**Why MCP Matters:**
- Systematically search for all occurrences (like IDE "Find All References")
- Ensure all callers are updated
- Verify consistency of changes

**Evaluation Metrics:**
- Code compilation success
- All tests pass after edits
- Consistency validation: are all affected sites handled?
- Completeness: search for old API usage should return zero hits

#### Key Insight
Without code-aware retrieval, agents miss references or create inconsistent changes. CrossCodeEval noted that effective cross-file completion requires not just LLM capacity but a good code retriever.

---

### 4. Bug Localization and Fixing in Legacy Codebases

Debugging large, unfamiliar codebases is a major part of the development lifecycle. This category tests end-to-end issue resolution.

#### 4.1 Bug Localization (CoSIL)

**Problem Space:**
- Given a bug report or failing scenario, locate the cause in the code
- Navigate codebase at function level, guided by issue description
- Research finding: LLM-guided iterative search can significantly reduce search space and home in on buggy function

**Why MCP Matters:**
- Targeted searches: find error messages, suspicious logic related to description
- Reduces search space without pre-training or pre-built index
- Mirrors how developers debug: "grep for error message, then examine context"

**Example Tasks:**
- "A crash occurs when uploading image files. Find the bug and explain it."
- "The cache coherence test fails randomly. Identify the race condition."

**Evaluation Metrics:**
- Localization success: does agent point to correct file/function?
- Use IR metrics: did search hits include the culprit?
- Quality of explanation: does agent cite correct location?

#### 4.2 Automated Bug Repair (ReCode)

**Problem Space:**
- After locating a bug, fix it in context
- Requires understanding broader context (how feature is used elsewhere)
- Research finding: Retrieval-Augmented Generation reduces hallucination on unseen defects

**Why MCP Matters:**
- Fetch relevant code examples, documentation, similar bugs
- Retrieve commit history: recent changes that might have introduced regression
- Reduces hallucination by grounding fixes in real code patterns

**Example Tasks:**
- "Fix the crash when uploading large files; test must pass"
- "Fix the race condition in the cache invalidation logic"

**Evaluation Metrics:**
- Execution-based: does bug go away? Are tests passing?
- Correctness: does fix match developer's solution?
- No regressions: are new errors introduced?

#### 4.3 Using Commit History as Knowledge

**Problem Space:**
- Commit messages and diffs are documentation in legacy systems
- Agent can "bisect" through history to find when/why something changed
- Example: "This function was refactored last year; find out why (what issue was addressing)"

**Why MCP Matters:**
- Search commit messages and diffs via Sourcegraph APIs
- Answer "why was this done?" by mining history
- Non-augmented agents have virtually no chance

**Evaluation Metrics:**
- QA task: does explanation match commit rationale?
- Correctness of identified commit
- Completeness: were relevant commits found?

#### Key Insight
This demonstrates agent acting as "knowledge miner"—digging through years of code history. For enterprise value: answers "why" questions that consume significant senior engineer time. Baseline agents essentially fail (0%), augmented agents succeed (20%+).

---

### 5. Performance and Optimization Tasks

Beyond functional correctness, non-functional requirements (performance, scalability) matter in industry. Most LLM benchmarks ignore this entirely.

#### 5.1 Performance Bug Identification and Fixing (PerfBench)

**Problem Space:**
- Code is functionally correct but inefficient (O(n²) loops, excessive memory, redundant computation)
- No failing test signals the bug
- Success metric: compare performance before/after fix against known improvement
- Research finding: Baseline agent achieved ~3% success; with tooling, rose to ~20%

**Why MCP Matters:**
- Agent can search for patterns: "nested loops over large collections," "TODO: optimize," etc.
- Find inefficient API usage (N+1 database queries)
- Trivial for tools, impossible for closed-box LLM on large repo

**Example Tasks:**
- "Optimize function X without changing external behavior" (guided by performance benchmark)
- "Find obvious performance bottlenecks in module Y" (open-ended review task)

**Evaluation Metrics:**
- Performance delta: is fixed code faster?
- Comparison to known optimization
- Correctness: does behavior match original?

#### Key Insight
This demonstrates agent on tasks where baseline is essentially helpless (0% success). Even modest improvements (to 20%) are compelling evidence of value. Aligns with enterprise interests: many companies dedicate significant effort to performance.

---

### 6. Multi-Repository Collaboration Scenarios

Modern enterprises organize code into many repositories (microservices, libraries). Real tasks require coordinating changes across them.

#### 6.1 Cross-Repository API Updates

**Problem Space:**
- Upgrade API in one repo; update usage in another
- Example: "Upgrade Repo A's function foo() signature; update Repo B to use new signature"
- Requires:
  - Modifying foo() and related code in Repo A
  - Finding all calls to foo() in Repo B
  - Ensuring both repos build/tests pass

**Why MCP Matters:**
- Proactive search for function references across repos
- Agent aware of cross-repo impact without trial-and-error
- Mirrors enterprise use case: breaking changes propagating through dozens of services

**Evaluation Metrics:**
- End-to-end: do both repos function after changes?
- Completeness: did agent find and modify all call sites?
- Correctness: are modifications correct?
- Validation: search for old API usage should return zero

#### 6.2 Library Dependency Cross-Repo Coordination

**Problem Space:**
- Similar to dependency inference, but across repos
- Example: "Upgrade shared library version; ensure all consumers handle changes"
- Requires understanding multiple codebases

**Why MCP Matters:**
- Search for usage of library across repos
- Find all consumers that need updates
- Validate compatibility

#### Key Insight
Multi-repo evaluation is cutting-edge; few benchmarks exist. Our design shows agent acting as coordinator across services—another enterprise pain point. Success demonstrates feasibility of cross-repository reasoning.

---

## Agent Memory and Iterative Workflow

### Memory Considerations

Real developers don't solve complex tasks in one shot—they read, plan, write, test, iterate. Our evaluation permits multi-turn interactions to observe how agents manage information.

**Key Questions:**
- Does agent avoid asking the same question twice? (remembering prior search results)
- Does it correctly integrate knowledge from step 1 into code in step 3?
- How efficiently does it summarize context to stay within token limits?

### External vs. Internal Memory

- **External Memory:** Sourcegraph MCP retrieval; agent can query again when needed
- **Working Memory:** Conversation history, scratchpad notes
- **Contextual Awareness:** Does agent maintain understanding across steps?

### Tasks Testing Memory

- Provide design document/API spec via retrieval early; later ask to implement according to spec
  - Strong agent: recalls spec details when coding
  - Weak agent: needs to search repeatedly or hallucinates
- Multi-step tasks where agent must refer back to earlier findings

### Measurement

- Implicit evaluation through success on long-horizon tasks (>context window length)
- Track searches: does agent reuse prior results or search redundantly?
- Observe if agent summarizes context to stay within limits

---

## Evaluation Methodology

### Automated Metrics (Objective Evaluation)

**Dependency Tasks:**
- Exact match or set similarity to ground-truth list
- Execution success: does code run with inferred dependencies?

**Code Search Tasks:**
- Similarity score to target (BLEU, code overlap)
- Exact-match correctness of identified location/function

**Code Generation/Editing:**
- Execution-based metrics: do tests pass?
- Test suite success pre/post modification
- Reference implementation comparison

**Performance Tasks:**
- Benchmark metrics: time/memory before vs. after
- Comparison to known optimization delta

**Completeness Metrics:**
- Search validation: do old API usages return zero hits?
- Compile success on modified code

### LLM-as-Judge (Subjective Evaluation)

**When to Use LLM Judge:**
- Comparing two agents' outputs side-by-side
- Evaluating code quality aspects not captured by tests
- Assessing explanations and documentation
- Scoring qualitative correctness

**Best Practices for LLM Judgment:**
- Use latest GPT-4 or Claude-2 as judge (smaller models unreliable)
- Provide clear evaluation criteria and rubrics
- Request justification to reduce random guessing
- Consider multiple judges or chain-of-thought prompting
- Validate judge consistency on known examples (calibration)
- Combine with execution metrics: if code passes tests, don't need judge's opinion on correctness

**Example Evaluation Prompt:**
```
Task: Judge which solution better resolves the issue.

Criteria:
1. Correctness: Does solution actually fix the described issue?
2. Completeness: Were all aspects handled?
3. Safety: Could solution introduce new problems?

Solution A: [agent output]
Solution B: [baseline output]

Explain which is better and why. If both pass criteria equally, note that.
```

### Hybrid Approach

**Strongest results combine:**
- Execution-based validation (primary; objective)
- LLM judgment for nuanced comparisons
- Explicit case studies showing successes/failures
- Quantitative metrics per task type

---

## Success Criteria

### Expected Outcomes

By design, we anticipate these improvements for MCP-augmented agents:

1. **Dependency Inference:** 70% vs. 40% success (with vs. without retrieval)
2. **Bug Localization:** Correctly identify bug location in legacy code (near 100%)
3. **Cross-File Edits:** Higher consistency, fewer missed locations
4. **Performance Optimization:** Non-trivial success where baseline fails
5. **Multi-Repo Coordination:** Successful cross-repository updates with zero inconsistencies
6. **Code Search:** Rapid, accurate answers to codebase questions

### Validation Criteria

- ✅ Metrics are reliably collected from all agents
- ✅ Baseline and MCP agents show different patterns (validate tool differences)
- ✅ Metrics are interpretable to non-engineers
- ✅ At least 3-5 clear performance differentiators identified
- ✅ Results are reproducible across multiple runs
- ✅ Concrete case studies show concrete wins for MCP agent

---

## Benchmark Impact and Enterprise Value

### What These Results Demonstrate

**For Prospects/Customers:**

1. **Faster Onboarding:** Asking codebase questions to AI assistant vs. reading docs
2. **Quicker Debugging:** Navigating complex legacy code to find root causes
3. **Safer Refactoring:** Ensuring all impacts are handled when making large-scale changes
4. **Efficient Use of Developer Time:** Reducing time spent on code search and context-gathering

### Why This Matters

- Bridges "research-practice gap" between academic benchmarks and enterprise reality
- Simulates full software development lifecycle, not just isolated tasks
- Demonstrates transformation (not incremental improvement) from adding code intelligence
- Provides concrete quantitative evidence of tool value

---

## Implementation Roadmap

### Phase 1: Task Design and Sourcing (2-3 weeks)
- [ ] Identify task repositories and examples
- [ ] Mine 50+ real PRs for diverse tasks benchmark
- [ ] Document task definitions and ground truth
- [ ] Create Dockerfile templates (pre-cloned repos)

### Phase 2: Benchmark Implementation (2-3 weeks)
- [ ] Create task structure (instruction.md, task.toml, tests/)
- [ ] Implement test harnesses and evaluation scripts
- [ ] Develop metrics calculation code
- [ ] Create example trajectory data

### Phase 3: Instrumentation & Validation (2 weeks)
- [ ] Add logging to Claude Code agent
- [ ] Add logging to MCP agent
- [ ] Validate trajectory capture
- [ ] Ensure metrics computation correctness

### Phase 4: Pilot Run & Analysis (1-2 weeks)
- [ ] Run baseline vs. MCP on 10-20 tasks
- [ ] Analyze results
- [ ] Refine task definitions based on pilot
- [ ] Document findings and case studies

---

## References and Related Work

### Core Benchmarks Referenced

- **DI-Bench:** Dependency Inference (Zhang et al., 2025)
- **DependEval:** Repository Dependency Understanding (Du et al., 2025)
- **RepoQA:** Long-Context Code Understanding (Liu et al., 2024)
- **CrossCodeEval:** Cross-File Code Completion (Ding et al., 2023)
- **PerfBench:** Real-World Performance Bug Fixes (Garg et al., 2025)
- **CoSIL:** Issue Localization via Code Graph Search (Ren et al., 2025)
- **ReCode:** Retrieval-Augmented Code Repair (Wang et al., 2025)
- **EnvX:** Agentized Multi-Repository Collaboration
- **RepoMaster/GitTaskBench:** Autonomous Code Reuse (Wang et al., 2025)

### Related Research

- Code Foundation Models to Agents Survey (Yang et al., 2025)
- Memory in the Age of AI Agents (Hu et al., 2025)
- MemSearcher: Training LLMs to Search and Manage Memory (Liu et al., 2025)
- LLM-as-a-Judge Effectiveness (Ciniselli et al., 2025)
- LLM-as-a-Judge Best Practices (Evidently AI, 2025)

---

## Document Status

- **Last Updated:** December 20, 2025
- **Related Beads:**
  - CodeContextBench-2wz: Diverse Task Types Benchmark
  - CodeContextBench-13j: Process Metrics Benchmark
  - CodeContextBench-2wz: New Benchmark Design
  - CodeContextBench-13j: Process Quality Metrics
- **Location:** docs/BENCHMARK_DESIGN_GUIDE.md
