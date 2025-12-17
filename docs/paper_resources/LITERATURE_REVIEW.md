# Improving Agentic Coding via Codebase Context Retrieval  
**A Literature Review (2025)**

## Abstract

Agentic coding systems—LLM-based agents capable of planning, searching, editing, and validating code over multiple steps—are increasingly applied to real-world software development tasks. However, their effectiveness is strongly constrained by how well they retrieve, compress, and reason over large, heterogeneous codebase context. This review synthesizes recent work (2025) across benchmarks, code search and retrieval, memory systems, and agent architectures to evaluate how improved contextual grounding supports long-horizon coding performance. We emphasize repository-level benchmarks, retrieval-augmented agent workflows, and evaluation methodologies relevant to enterprise-scale systems such as Sourcegraph Deep Search and agent MCPs.

---

## 1. Benchmarking Agentic Coding Systems

### 1.1 Repository-Level and Long-Horizon Benchmarks

**GitTaskBench** introduces realistic, end-to-end software engineering tasks that require agents to leverage entire repositories, including source code, configuration, and documentation. Results show that even strong agents fail on 35–50% of tasks, with failures dominated by missing workflow context (dependencies, environment setup, CI configuration). This benchmark strongly suggests that improved context retrieval—not model size alone—is the dominant bottleneck.

**NL2Repo-Bench** and **LoCoBench-Agent** further extend evaluation to long-context and repository-generation settings, emphasizing multi-file consistency, project structure correctness, and sustained reasoning over large contexts.

**Key takeaway:** Benchmarks that require repository navigation expose weaknesses in agent context localization, prioritization, and memory persistence.

---

### 1.2 Non-Functional and Specialized Benchmarks

**PerfBench** evaluates agents on real-world performance bugs rather than functional correctness. Agents must reason about runtime behavior and validate improvements empirically. Baseline agents solve ~3% of tasks; performance-aware agent scaffolds reach ~20%.

**PentestEval** and **VulnLLM-R** evaluate security reasoning and vulnerability workflows, revealing that agents require domain-specific context (e.g., CVE patterns, exploit paths) to succeed.

**Key takeaway:** Context retrieval must include dynamic signals (measurements, logs, benchmarks), not just static code.

---

### 1.3 Holistic and Production-Oriented Evaluation

**HAL (Holistic Agent Leaderboard)** provides large-scale, cost-aware evaluation infrastructure and reveals that increased reasoning often *reduces* accuracy due to compounding errors. Log-level analysis exposes failure modes invisible to pass/fail metrics.

**Beyond Task Completion** and **Measuring Agents in Production** argue for multi-dimensional evaluation: reasoning quality, memory correctness, tool usage, and environmental robustness.

**Key takeaway:** Evaluation must track *agent trajectories*, not just final outputs.

---

## 2. Code Search and Context Retrieval for Coding Agents

### 2.1 Fine-Grained Retrieval-Augmented Generation

**ReCode** demonstrates that retrieval quality dominates repair success. Algorithm-aware narrowing and dual encoders outperform generic embedding search, especially on real user-submitted bugs (RACodeBench).

**DeepCodeSeek** and **Repository-Aware File Path Retrieval** focus on precise API and file-level localization, reducing hallucinated usage patterns.

**Key takeaway:** Retrieval must be structure-aware (algorithms, APIs, file paths), not just text-similar.

---

### 2.2 Graph-Guided Repository Navigation

**CoSIL** introduces iterative graph-guided search using module- and function-level call graphs with pruning and reflection. This approach nearly doubles localization accuracy on SWE-bench variants and significantly improves downstream repair.

**LocAgent** and **Issue Localization via Iterative Code Graph Searching** reinforce the effectiveness of graph-constrained exploration over free-form search.

**Key takeaway:** Code graphs are a powerful prior for narrowing agent attention in large repositories.

---

### 2.3 Token-Efficient Retrieval and Compression

**TeaRAG** compresses retrieved context into knowledge graphs and trains agents to minimize unnecessary reasoning steps, reducing token usage by ~60% while improving accuracy.

**EDU-based context decomposition** shows that structured chunking outperforms naive truncation or summarization.

**Key takeaway:** Compression and prioritization are as important as retrieval itself.

---

## 3. Memory Systems for Long-Horizon Agents

### 3.1 Memory as a First-Class Primitive

**Memory in the Age of AI Agents** provides a unifying taxonomy of memory:
- Working memory (short-term reasoning state)
- Experiential memory (past actions and outcomes)
- Factual memory (persistent knowledge)

It highlights memory formation, retrieval, and decay as core design axes.

---

### 3.2 Learned Memory Management

**MemSearcher** trains agents via reinforcement learning to decide what to retain, discard, or retrieve across turns. A 3B model with learned memory outperforms a 7B baseline, demonstrating that memory policy can outweigh scale.

**Key takeaway:** Memory management should be learned and adaptive, not heuristic.

---

## 4. Agent Architectures and Design Considerations

### 4.1 Behavioral Analysis and Failure Modes

**Understanding Code Agent Behaviour** analyzes success and failure trajectories, finding that successful agents:
- Localize early
- Retrieve selectively
- Avoid long unstable loops

Failures correlate with poor context prioritization and over-editing.

---

### 4.2 Multi-Agent and Reflective Architectures

**PARC**, **VIGIL**, and **Chain-of-Agents** introduce reflection, self-healing, and staged reasoning. However, increased architectural complexity introduces coordination failures if retrieval is weak.

**Key takeaway:** Reflection and multi-agent designs amplify retrieval quality—good or bad.

---

### 4.3 Safety, Control, and Trust

**MiniScope** and **Data Flow Control** enforce least-privilege tool access. Studies of professional developers show preference for controllable, steerable agents over fully autonomous systems.

**Key takeaway:** Context retrieval must be transparent and inspectable to support trust.

---

## 5. Implications for Sourcegraph Deep Search and MCP Agents

Key design implications emerging from the literature:

1. **Iterative Retrieval > One-Shot Context**
   - Agents should search, inspect, refine, and re-search.

2. **Graph-Aware Search**
   - Call graphs, dependency graphs, and file hierarchies should guide retrieval.

3. **Context Compression Pipelines**
   - Retrieved artifacts must be summarized and ranked before entering the model context.

4. **Explicit Memory Layers**
   - Distinguish working, episodic, and persistent repo memory.

5. **Trajectory-Level Evaluation**
   - Measure localization quality, search efficiency, and loop stability.

---

## 6. Future Research Directions

- Repository-native benchmarks aligned with enterprise workflows
- Learned search and retrieval policies
- Cross-artifact retrieval (code + docs + CI + issues)
- Memory trustworthiness and decay
- Human-agent collaborative evaluation
- Production telemetry for agent behavior auditing

---

## Conclusion

The 2025 literature converges on a clear conclusion: **context retrieval—not raw model capability—is the limiting factor for agentic coding systems**. Advances in graph-guided search, learned memory, and retrieval compression significantly improve long-horizon performance. For systems like Sourcegraph Deep Search and MCP agents, these findings argue for investing in retrieval intelligence, memory architecture, and behavioral evaluation as core primitives rather than peripheral enhancements.

---

