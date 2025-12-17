# CodeContextBench: Evaluating Codebase Understanding and Context Retrieval in Autonomous Coding Agents

## Introduction

Recent advances in large language models (LLMs) have led to coding agents that can write, modify, and debug code with minimal human input. These agents have achieved impressive performance on short, self-contained programming tasks—for example, going from single-digit success on early benchmarks to over 95% on problems like HumanEval \[1]. However, real-world software development involves long-horizon, multi-module tasks that current benchmarks hardly capture \[2]\[3]. Existing evaluations tend to focus on single-function generation or isolated bug fixes with provided test cases, leaving open the question of whether an AI agent can understand an entire large codebase and perform a complex development task (e.g., implement a new feature in a legacy codebase or fix a subtle bug that spans modules) over an extended sequence of steps \[2]\[4].

At the same time, developers in practice have powerful tools like Sourcegraph for code search and navigation. Such tools dramatically improve human productivity by allowing quick lookup of where functions are used, finding examples, and understanding cross-file dependencies. We hypothesize that integrating a code search capability into coding agents will similarly boost their autonomous performance on large-scale tasks. Our goal is to design a new benchmark and evaluation strategy for coding agents that emphasizes long-horizon tasks on real-world repositories, and to quantify how Sourcegraph (or similar code search) can improve agent outcomes in terms of success rate, efficiency, and reliability.

Recent work has begun to address this gap through benchmarks that emphasize long-horizon, realistic agent behavior in interactive environments. In particular, Terminal-Bench introduces a suite of difficult, real-world tasks executed in fully provisioned command-line environments, where agents must autonomously explore, modify files, install dependencies, and verify outcomes over extended trajectories rather than solving isolated functions. However, Terminal-Bench demonstrates that even frontier models achieve less than 50% task resolution on such realistic terminal-based workloads, reinforcing our core hypothesis: long-horizon autonomy in real development settings remains an unsolved problem, and benchmarks must reflect the full workflow experienced by practicing engineers rather than simplified, single-shot tasks.

Why now? 2025 has seen a surge of research addressing the gap between toy benchmarks and real development scenarios. For instance, NL2Repo-Bench explicitly evaluates agents on generating an entire small repository from scratch \[5], and found that even top-tier models struggle to maintain global coherence and planning over hundreds of steps (achieving <40% test pass rate, rarely completing all required components) \[4]. This suggests long-horizon autonomy remains unsolved. Other work has turned to multi-agent or multi-tool approaches to tackle complex tasks: a recent “LLM vs human” coding tournament on a logistics problem showed that human-coded agents still defeat LLM-coded ones in strategic planning tasks, highlighting reasoning and optimization gaps in current AI agents \[6]. Meanwhile, surveys of the field emphasize a growing research–practice gap: academic benchmarks focus on narrow correctness, whereas real deployment demands handling large codebases, integrating with development workflows, and writing secure, maintainable code \[7].

Our focus is to bridge these gaps by evaluating coding agents on tasks that more closely resemble real developer work. Specifically, we plan to:

1. Assemble a suite of tasks drawn from actual open-source software repositories (e.g., Mozilla Firefox, Kubernetes, PyTorch, VSCode, FFmpeg, and others)—tasks such as fixing a known bug, implementing a requested feature, or upgrading a dependency—each of which requires understanding and modifying a non-trivial, multi-language codebase; and
2. For each task, compare the performance of an agent with vs. without access to Sourcegraph's code search.

This will directly test the value of fast, global code navigation in an autonomous setting. By measuring not just whether the agent succeeds but also how efficiently (in terms of steps or model queries) it does so, we will produce a holistic assessment of productivity gains, in line with the notion of **effectiveness = outcome quality / resources consumed** \[8].

In the rest of this document, we outline the current landscape of coding agent evaluation and tooling, then detail our proposed benchmark design, task selection, and evaluation methodology. Finally, we discuss expected results and how this can demonstrate Sourcegraph’s impact on developer productivity through AI.

## Limitations of Existing Benchmarks and Need for Long-Horizon Tasks

Early code generation benchmarks like HumanEval and MBPP test an AI’s ability to write a single function given a docstring or solve competitive programming problems emphasizing local code correctness and algorithmic reasoning. While useful, these benchmarks do not require the agent to manage extended context or make high-level design decisions. The code to be written is small, self-contained, and often the problem description fully specifies the requirements. Real software tasks, in contrast, often involve understanding an under-specified natural language issue, reading and modifying multiple existing files, and ensuring the changes align with the project’s architecture.

Some newer benchmarks have begun to scale up, but each addresses only part of the problem:

- **SWE-Bench (2023–2024)** — a collection of real GitHub issues and patches that evaluates bug-fixing in the context of a full repository. Agents are given a repository and an issue description and expected to produce a patch. This is closer to reality, but as later analysis found, many tasks could be “cheated” by passing provided tests without truly fixing the bug \[9]. The tasks are single-step: fix the bug and you’re done. There’s no notion of multi-turn interaction or long-term planning, and the agent is usually evaluated on one fix at a time.
- **HumanEval-X and similar long-context benchmarks** — these present longer code snippets or multiple-function programs to the model for completion, pushing context lengths into the 10k+ token range. They test if the model can handle reading a lot of code, but still the evaluation is single-turn: provide input, get output. There’s no simulation of an interactive development process with iterative improvements.
- **APPS, CodeContests** — collections of programming problems that are more challenging algorithmically. They sometimes require writing more code (like a full program), but again, they don’t involve reading or modifying existing code bases. The context is still just the problem description, not thousands of lines of existing code that the agent must navigate.

In summary, there is a lack of benchmarks that require an agent to sustain coherent reasoning, planning, and execution over an extended sequence of steps on a persistent codebase \[10]. Most benchmarks either reset context every time or focus on one-off tasks. As a result, current leaderboards might overestimate an agent’s capability to serve as an autonomous software developer. An agent that scores, say, 90% on HumanEval could still completely fail when asked to start with an empty workspace and a complex spec, and develop a multi-module system—or when asked to fix a bug in a 50k-line codebase—because it might lose track of the overarching goal, or break things while fixing others, etc. Experiments in NL2Repo-Bench illustrate this: even GPT-4-class models struggled to build a correct multi-file Python library without significant guidance \[4]. The failure modes included prematurely stopping before the project was complete, losing global consistency between files, fragile dependencies that break upon integration, and lack of upfront planning \[11].

Furthermore, prevailing evaluation metrics have been narrow. Unit test pass rates are the de facto standard—used in HumanEval, MBPP, SWE-Bench, etc.—but they don’t capture everything. Passing tests is necessary but not sufficient; an agent might write code that passes tests by hardcoding outputs or by luck, especially if tests are sparse \[9]. Also, unit tests typically check functional correctness, not qualities like code style, maintainability, or performance. Non-functional requirements (efficiency, security, readability) are largely ignored in evaluations, yet in real development these are very important. As Danassis et al. argue, benchmarks focusing only on test passes and syntax miss higher-level problem-solving skills \[12]\[13]. They introduced a benchmark requiring strategic decision-making (bidding in an auction + routing deliveries), where pure code generation ability wasn’t enough—agents had to plan and reason over multiple rounds. The outcome was telling: out of 40 agents coded by various LLMs, 33 were beaten by even simple human-made baseline strategies \[14]. This indicates that new metrics and benchmarks must incorporate reasoning quality and real-world efficacy, not just whether the final code runs.

Another limitation is that many benchmarks under-model tool use and workflow. Humans don’t develop software in isolation—we rely on IDEs, debuggers, search, documentation, version control, and iterative execution/testing loops. Earlier benchmarks treated coding like a closed-book exam, but agentic frameworks increasingly allow models to use tools (e.g., run code, browse documentation, search within a repo) and sustain multi-turn interaction.

For example, LoCoBench-Agent equips agents with a suite of specialized tools (file operations, compilation, runtime execution, web search) and evaluates whether they can choose actions over long conversations, recover from errors, and maintain state across hundreds of turns \[15]. Initial results show an intuitive trade-off: broader exploration and heavier tool use often improves eventual success, but can reduce efficiency due to wandering and repeated attempts \[16]. In practice, exhaustive exploration can solve problems, but often with significant thrashing—precisely the kind of behavior we expect a strong code search/navigation tool (e.g., Sourcegraph) to reduce by enabling more targeted discovery.

Terminal-Bench strengthens this point from a complementary angle: even when agents do have access to fully interactive terminal environments—where they can explore, edit files, install dependencies, and run commands—frontier systems still resolve fewer than half of tasks, indicating that “having tools” is not sufficient without robust tool selection, verification, and recovery behavior over long trajectories. \[terminal bench ref] Terminal-Bench also highlights a related evaluation issue: success in realistic workflows cannot be reduced to “producing a patch that passes a narrow test.” Its tasks are outcome-driven and verified via end-state checks on the environment/container state, forcing agents to reason about configuration, build/run behavior, and verification—conditions that mirror real development more closely than single-shot code generation. \[terminal bench ref]

There is a critical need for benchmarks that:

- Present long-horizon, multi-turn tasks (not solvable in one or two prompt completions).
- Use realistic codebases (not just isolated snippets), forcing the agent to handle large context and existing code.
- Allow/encourage tool use, especially code navigation and execution, as part of the evaluation.
- Measure not just correctness but also process quality—did the agent need 100 attempts or 10; how much compute or “consultation” did it use (important for practical deployment where cost matters \[8]).
- Potentially include human-in-the-loop scenarios, since in reality developers and AI will work together.

Our proposed benchmark, which we’ll tentatively call **CodeContextBench**, aims to fulfill these criteria. In the next section, we draw on the latest research to guide how we design this benchmark.

## Insights from Recent Research to Inform Our Approach

### Long-horizon coding benchmarks

Early coding benchmarks such as HumanEval and MBPP focus on short, self-contained tasks and provide limited insight into an agent’s ability to sustain reasoning over large codebases. More recent benchmarks attempt to address this gap. NL2Repo-Bench evaluates agents on end-to-end repository generation from a natural language specification, requiring multi-file consistency and long-horizon planning. Despite this, even frontier models achieve under 40% unit-test success, frequently failing due to loss of global coherence, incomplete implementations, or broken cross-file references. These results highlight that long-horizon autonomy remains a major challenge and that binary pass/fail evaluation can obscure partial but informative progress.

Complementary evidence comes from interactive benchmarks such as Terminal-Bench, which evaluates agents on diverse, realistic command-line tasks with containerized environments and end-to-end verification. Terminal-Bench shows that even when agents can explore, edit files, install dependencies, and execute commands, fewer than half of tasks are successfully completed. This underscores that long-horizon failures are not limited to repository patching, but persist in broader development workflows that require sustained execution, verification, and recovery.

### Synthetic and programmatically generated benchmarks

Some benchmarks pursue scale and diversity through synthesis. SWE-Playground generates synthetic repositories, issues, and corresponding ground-truth solutions, enabling large numbers of tasks beyond those found in existing open-source projects. This approach supports dense supervision and controlled task generation, but may sacrifice realism relative to tasks drawn from real-world repositories. Synthetic benchmarks are therefore often viewed as complementary rather than substitutive, and have been proposed as a means of augmentation (e.g., generating additional tests or task variants) rather than as standalone evaluations.

### Tool-augmented and long-context agent evaluation

Several benchmarks explicitly study tool use and long-context reasoning. LoCoBench-Agent extends long-context code understanding benchmarks into an interactive setting, equipping agents with multiple tools (file access, search, execution) and evaluating their behavior over hundreds of turns. Results reveal a consistent trade-off: agents that explore more thoroughly and use tools extensively tend to succeed more often, but at substantially higher cost in steps and time. This mirrors human development workflows and motivates evaluation along both effectiveness and efficiency dimensions.

### Strategic reasoning beyond code generation

Other work demonstrates that realistic software tasks often require reasoning beyond code correctness. The “vibe coding” study by Danassis et al. evaluates agents on competitive, strategic problems involving auctions and routing, where pure code generation is insufficient. LLM-based agents were consistently outperformed by simple human strategies, highlighting deficits in planning, optimization, and self-assessment. These findings suggest that realistic benchmarks should include tasks that surface higher-level reasoning gaps rather than only syntactic or functional correctness.

### Beyond unit-test-based evaluation

A growing body of work questions the sufficiency of unit-test pass rates as the primary evaluation metric. UTBoost showed that many patches deemed correct on SWE-Bench fail under more comprehensive, automatically generated test suites. PRDBench introduces project-level tasks evaluated via natural-language requirements, using agent-based judges alongside traditional tests to assess correctness when outcomes are not strictly binary. PerfBench similarly moves beyond functional tests by focusing on performance bugs, requiring agents to measure and validate performance improvements rather than merely passing tests. Together, these works argue for outcome-driven, multi-faceted evaluation that captures correctness, robustness, and non-functional properties.

### Analyzing agent behavior and efficiency

Empirical analyses of agent trajectories provide further insight into failure modes. Majgaonkar et al. show that agents often identify the correct files to modify (over 70% of the time) even when they ultimately fail, suggesting that implementation and verification—not localization—are common bottlenecks. SWE-Effi formalizes efficiency considerations by re-evaluating agents under token and time budgets, identifying issues such as context “token snowballing” and expensive failures where agents fail to recognize stagnation. These findings motivate reporting success alongside cost and process metrics.

### Repository-level task execution and economic framing

GitTaskBench evaluates agents on end-to-end tasks that require leveraging existing repositories to accomplish concrete goals, incorporating environment setup, execution, and verification. Its use of an economic “alpha-value” metric highlights the gap between academic benchmarks and real-world developer productivity, showing that even strong agents fail frequently due to mundane setup and workflow issues rather than core algorithmic difficulty.

### Human–AI collaboration and trust

Finally, studies of human–AI collaboration, such as HAI-Eval and “Code with Me or for Me?”, demonstrate that neither humans nor agents alone consistently solve complex tasks, but that collaboration improves outcomes. These works also emphasize the importance of transparency and interpretability in agent behavior, as developers struggle to trust or supervise agents whose actions are opaque.

With these perspectives in mind, we now introduce CodeContextBench, a benchmark designed to isolate and evaluate codebase understanding and context retrieval as first-class capabilities in long-horizon autonomous coding agents.

## Benchmark Design and Task Selection

### Task scope

Each task in CodeContextBench corresponds to a realistic software development ticket drawn from practice, including bug reports, feature requests, refactoring tasks, and maintenance chores (e.g., dependency upgrades or API renames). The benchmark targets long-horizon, multi-file work that requires agents to:

1. Build a working mental model of a large codebase,
2. Retrieve and integrate relevant context across files, and
3. Validate changes via execution or tests.

### Repository selection

CodeContextBench will be instantiated on a diverse set of large, actively maintained open-source repositories spanning multiple implementation languages and architectural styles (e.g., C/C++/Rust systems code, Go services, Python libraries, TypeScript applications). Candidate repositories include **[REPO_A]**, **[REPO_B]**, **[REPO_C]**, **[REPO_D]**, and **[REPO_E]** (e.g., representative browser engines, container/orchestration systems, ML frameworks, developer tools, and multimedia libraries). Additional repositories may be added to improve language and domain coverage, subject to feasibility constraints (buildability, test runtime, licensing).

### Task identification

Tasks will be mined from issue trackers and commit histories. We prioritize closed issues / merged pull requests where:

1. The ground-truth fix is available (enabling reproducible evaluation),
2. The change spans multiple files or non-trivial dependencies (ensuring codebase understanding is required), and
3. Verification is feasible via existing tests, lightweight reproduction scripts, or deterministic checks.

For each selected task, we snapshot the repository at a pre-fix revision and provide the agent with a natural-language ticket description plus any minimal artifacts needed to reproduce the issue (e.g., failing test name, stack trace, repro command), consistent across agents.

### Task categories

CodeContextBench includes multiple task types to stress distinct context-retrieval and reasoning behaviors:

- **Cross-module bug fixes.** Bugs whose root cause and fix cross file/module boundaries (e.g., parsing/validation plus downstream handling), requiring agents to locate and update multiple interacting components.
- **Feature implementations.** Small feature additions that require wiring through existing registries/configuration layers (e.g., adding an option, schema update, and behavioral logic in the relevant component).
- **Dependency or API upgrades.** Systematic updates across a codebase to accommodate API deprecations or version changes, stressing high-recall context retrieval (finding all call sites) and consistent edits.
- **Refactoring tasks.** Behavior-preserving restructuring (e.g., deduplication into shared utilities), which requires identifying semantically related code across the repository and validating no regressions.
- **Performance optimizations (optional / phased).** A limited number of tasks where success is defined by measurable improvement under a lightweight benchmark, complementing functional tests when feasible.

### Language and domain diversity

The task suite is constructed to ensure coverage across languages and repository archetypes. The initial release targets **[N_TASKS_TOTAL]** tasks across **[N_REPOS]** repositories, with **[2–3]** tasks per repository as a starting point. The suite will include at least one task in each of **[LANG_SET: C/C++, Rust, Go, Python, TypeScript]** (and optionally **[Java/C#]**), enabling analysis of whether context retrieval and tool augmentation benefits generalize across ecosystems.

### Task specification format

Each task is delivered to the agent as a structured ticket containing:

1. A natural-language description,
2. Expected behavior and/or failure symptom,
3. A suggested reproduction procedure (e.g., run tests, run `<command>`),
4. Allowed time/budget limits, and
5. Success criteria.

Where available, the benchmark references an existing regression test introduced by the upstream fix; otherwise, it provides a minimal deterministic checker or reproduction harness.

### Agent interface and tool augmentation

Agents interact with the repository through a constrained set of tools typical of development workflows: file read/write, repository search/navigation, and command execution (tests/build/repro). A core experimental axis is access to codebase context retrieval: agents are evaluated under matched conditions with and without an explicit search/navigation tool (e.g., Sourcegraph-backed code search or an equivalent local index such as ripgrep/Zoekt). All other components (base model, scaffolding/prompting, execution environment, budgets) are held constant to isolate the causal effect of context retrieval.

### Reproducibility

CodeContextBench will provide:

1. Repository snapshots or commit hashes,
2. Task specifications,
3. Containerized or scripted environment setup, and
4. Standardized evaluation scripts.

The benchmark will avoid hard dependency on proprietary infrastructure; where a commercial search API is used, an open substitute and instructions will be provided to reproduce results under comparable retrieval functionality.

### Calibration and feasibility

Prior to full-scale release, a pilot subset of **[N_PILOT_TASKS]** tasks will be used to validate that:

1. Tasks are neither trivial nor intractable,
2. Success criteria are deterministic, and
3. Evaluation runs within practical time limits.

This pilot informs task difficulty balancing and any necessary adjustments to the tool interfaces and logging instrumentation.

## Conclusion and Future Work

This work introduces **CodeContextBench**, a benchmark designed to evaluate autonomous coding agents on long-horizon, repository-scale tasks that require effective codebase understanding and context retrieval. By grounding tasks in real-world development tickets drawn from large, multi-language repositories and by emphasizing outcome-driven evaluation, CodeContextBench addresses limitations of prior benchmarks that focus on short-horizon generation or narrow unit-test success.

Building on insights from recent interactive and outcome-driven benchmarks such as Terminal-Bench, our methodology evaluates agents based on end-state correctness—whether the repository and execution environment satisfy the task’s success criteria—rather than on patch plausibility alone. This framing more accurately reflects real software development workflows, where correctness depends on navigation, integration across modules, verification, and recovery from intermediate failures.

The experimental design isolates the impact of explicit codebase context retrieval by comparing agents with identical models and scaffolding, differing only in access to search and navigation tools. This enables a controlled analysis of how retrieval affects both effectiveness and efficiency, revealing not only whether agents succeed, but how they succeed and at what cost. Beyond aggregate metrics, trajectory-level analysis provides insight into failure modes that persist even with improved context access, helping distinguish localization failures from implementation and verification errors.

Several directions remain open for extension:

- Incorporating limited human-in-the-loop variants—such as allowing a single hint or critique—to quantify how retrieval tools interact with human oversight.
- Expanding task coverage to include more performance optimization and refactoring tasks to stress non-functional reasoning and self-evaluation.
- Evaluating richer retrieval modalities—such as commit history, documentation, or issue discussion search—within the same framework to understand which sources of context most improve long-horizon autonomy.

Finally, CodeContextBench is intended as a reusable evaluation framework. By releasing task definitions, environments, and evaluation scripts, the benchmark can support comparative studies of agent architectures, retrieval mechanisms, and efficiency strategies under realistic constraints. As autonomous coding systems continue to evolve, benchmarks that explicitly measure codebase understanding and context integration will be essential for tracking progress toward reliable, economically meaningful autonomy in software development.

## References

1. **From Code Foundation Models to Agents and Applications: A Comprehensive Survey and Practical Guide to Code Intelligence** (arXiv:2511.18538)  
   https://arxiv.org/abs/2511.18538

2. **NL2Repo-Bench: Towards Long-Horizon Repository Generation Evaluation of Coding Agents** (arXiv:2512.12730)  
   https://arxiv.org/abs/2512.12730

3. **GitTaskBench: A Benchmark for Code Agents Solving Real-World Tasks Through Code Repository Leveraging** (arXiv:2508.18993)  
   https://arxiv.org/abs/2508.18993

4. **Can Vibe Coding Beat Graduate CS Students? An LLM vs. Human Coding Tournament on Market-driven Strategic Planning** (arXiv:2511.20613)  
   https://arxiv.org/abs/2511.20613

5. **SWE-Effi: Re-Evaluating Software AI Agent System Effectiveness Under Resource Constraints** (arXiv:2509.09853)  
   https://arxiv.org/abs/2509.09853

6. **LoCoBench-Agent: An Interactive Benchmark for LLM Agents in Long-Context Software Engineering** (arXiv:2511.13998)  
   https://arxiv.org/abs/2511.13998

7. **Training Versatile Coding Agents in Synthetic Environments** (arXiv:2512.12216)  
   https://www.arxiv.org/abs/2512.12216

8. **HAI-Eval: Measuring Human-AI Synergy in Collaborative Coding** (arXiv:2512.04111)  
   https://arxiv.org/abs/2512.04111

9. **Automatically Benchmarking LLM Code Agents through Agent-Driven Annotation and Evaluation** (arXiv:2510.24358)  
   https://arxiv.org/abs/2510.24358

10. **PerfBench: Can Agents Resolve Real-World Performance Bugs?** (arXiv:2509.24091)  
   https://arxiv.org/abs/2509.24091

11. **Understanding Code Agent Behaviour: An Empirical Study of Success and Failure Trajectories** (arXiv:2511.00197)  
   https://arxiv.org/abs/2511.00197

12. **GitTaskBench (GitHub repository)**  
   https://github.com/QuantaAlpha/GitTaskBench

13. **Autonomous Code Evolution Meets NP-Completeness** (arXiv:2509.07367)  
   https://arxiv.org/abs/2509.07367

14. **Code Researcher: Deep Research Agent for Large Systems Code and Commit History (Microsoft Research)**  
   https://www.microsoft.com/en-us/research/publication/code-researcher-deep-research-agent-for-large-systems-code-and-commit-history/

15. **Code with Me or for Me? How Increasing AI Automation Transforms Developer Workflows** (arXiv:2507.08149)  
   https://arxiv.org/abs/2507.08149

16. **LLM Agents for Automated Dependency Upgrades** (arXiv:2510.03480)  
   https://arxiv.org/abs/2510.03480

17. **VeriEquivBench: An Equivalence Score for Ground-Truth-Free Evaluation of Formally Verifiable Code** (arXiv:2510.06296)  
   https://www.arxiv.org/abs/2510.06296
