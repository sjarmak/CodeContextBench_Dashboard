# PRD: Benchmark Trace Reviewer & Experiment Explorer

## Introduction

The benchmark evaluation platform currently lacks an ergonomic way to browse coding agent conversation traces, compare experiments across benchmark sets, and interactively review LLM judge configurations. Evaluators must navigate raw file systems, parse JSON manually, and run CLI commands to understand agent behavior. This PRD defines a comprehensive dashboard overhaul that makes experiment discovery, trace review, paired comparison, and quality judging fully GUI-driven.

## Goals

- Provide a single dashboard interface for discovering, filtering, and reviewing all benchmark experiment runs
- Render full coding agent traces (from claude-code.txt) with interactive search, filtering, and timeline visualization
- Support paired and individual experiment comparison grouped by benchmark set (LoCoBench, SWE-Bench Pro, etc.)
- Embed a repository file browser with diff view showing agent changes alongside the trace
- Make the LLM judge fully configurable via the GUI including prompt editing, template management, and human alignment verification
- Consolidate all analysis modules (statistical, comparison, time series, cost, failure) into a unified Analysis Hub accessible without CLI
- Migrate data source from `jobs/` and `eval_runs_v2/` to `runs/` directory structure
- Remove the "include archived runs" option

## User Stories

### US-001: Migrate data source from jobs/ to runs/
**Description:** As a developer, I need the dashboard to read from the new `~/evals/custom_agents/agents/claudecode/runs/` directory instead of `jobs/` or `eval_runs_v2/` so that future benchmark runs are discovered automatically.

**Acceptance Criteria:**
- [ ] All references to `jobs/` directory path in dashboard code are updated to `runs/`
- [ ] All references to `eval_runs_v2/` are updated to use the new unified `runs/` structure
- [ ] The "include archived runs" checkbox/option is removed from the UI
- [ ] The data source path is configurable via `.env.local` or dashboard settings page (default: `~/evals/custom_agents/agents/claudecode/runs/`)
- [ ] Existing parsers (harbor_parser, transcript_parser) work with the new path
- [ ] Typecheck/lint passes

### US-002: Benchmark set grouping in experiment selector
**Description:** As an evaluator, I want experiments grouped by benchmark set (LoCoBench, SWE-Bench Pro, RepoQA, DIBench) in the experiment selector so I can quickly find runs for a specific benchmark.

**Acceptance Criteria:**
- [ ] Experiment selector displays a two-level hierarchy: benchmark set > experiment name
- [ ] Benchmark set is derived from manifest.json `config.benchmarks` field or from the run directory naming convention (e.g., `locobench_*`, `swebenchpro_*`)
- [ ] Each benchmark group shows the count of available experiments
- [ ] Selecting a benchmark set filters the experiment list to only show matching runs
- [ ] Benchmark sets with no runs are hidden
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-003: Paired and individual experiment selection
**Description:** As an evaluator, I want to select experiments as paired (baseline vs variant) or individually so I can compare different agent configurations on the same tasks.

**Acceptance Criteria:**
- [ ] Toggle between "Paired Comparison" and "Individual Review" modes
- [ ] In paired mode: select two runs (baseline + variant) that share the same task set; the UI auto-detects pairs from `pairs/` directory or allows manual pairing
- [ ] In individual mode: select a single run to review in detail
- [ ] In paired mode: task list shows side-by-side status (pass/fail) for both runs
- [ ] Runs from separate experiments can be manually paired if they share common tasks (matched by task_id)
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-004: Task-level filtering and selection
**Description:** As an evaluator, I want to filter and select individual tasks within an experiment by various criteria so I can focus on specific areas of interest.

**Acceptance Criteria:**
- [ ] Filter tasks by: status (pass/fail/error), language, task type (architecture, bug, refactoring), difficulty level, duration range, token usage range
- [ ] Search tasks by task_id or task name substring
- [ ] Sort tasks by: name, duration, token count, reward, pass/fail status
- [ ] Task list shows key metrics inline: status badge, duration, token count, reward score
- [ ] Clicking a task navigates to the detailed task view
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-005: Task detail view - metadata and metrics
**Description:** As an evaluator, I want to see all relevant task information on one page including build environment, CLAUDE.md content, task instruction prompt, and execution metrics.

**Acceptance Criteria:**
- [ ] Display task metadata: task_id, benchmark source, language, difficulty, tags
- [ ] Display build environment info from config.json: docker image, agent model, agent name, environment type
- [ ] Display CLAUDE.md content (extracted from the agent's session or the repository)
- [ ] Display the task instruction prompt that was sent to the agent
- [ ] Display execution metrics: total duration, token usage (input/output/cached), tool call count, error/failure status, reward score
- [ ] Display agent result: exit code, pass/fail determination
- [ ] Display verifier output: test results, reward breakdown
- [ ] All sections are collapsible for space management
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-006: Interactive trace viewer - summary overview
**Description:** As an evaluator, I want a summary overview at the top of the trace that shows tool call metrics, a high-level execution timeline, and key statistics so I can quickly understand what the agent did.

**Acceptance Criteria:**
- [ ] Summary panel shows: total messages, total tool calls, unique tools used, total tokens consumed, session duration
- [ ] Tool usage breakdown: bar chart showing count per tool type (Read, Edit, Write, Bash, Glob, Grep, etc.)
- [ ] Execution timeline: horizontal timeline showing phases of agent work (reading, editing, testing, etc.) color-coded by activity type
- [ ] Key decision points highlighted (e.g., plan mode entry/exit, error recovery)
- [ ] File access summary: list of files read/written/edited with access count
- [ ] Summary is rendered from parsed claude-code.txt data
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-007: Interactive trace viewer - full trace rendering
**Description:** As an evaluator, I want to view the full coding agent trace rendered as interactive collapsible cards with syntax highlighting so I can understand every step the agent took.

**Acceptance Criteria:**
- [ ] Each JSONL line from claude-code.txt is parsed and rendered as a card
- [ ] Cards are typed: system (init), assistant (text + tool_use), user (tool_result), with distinct visual styling per type
- [ ] Tool call cards show: tool name badge, input parameters (syntax-highlighted JSON), and are collapsible
- [ ] Tool result cards show: the returned content with syntax highlighting for code files, truncation with "show more" for large results
- [ ] Assistant text messages are rendered as markdown
- [ ] Token usage is displayed per message (from the usage field)
- [ ] Cards show parent_tool_use_id linkage for sub-agent calls
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-008: Trace search and filtering
**Description:** As an evaluator, I want to search and filter trace messages so I can quickly find specific tool calls, errors, or content within large traces.

**Acceptance Criteria:**
- [ ] Full-text search across all trace messages with match highlighting
- [ ] Filter by message type: system, assistant, user (tool_result)
- [ ] Filter by tool name: dropdown with all tools used in this trace
- [ ] Filter by content type: text, tool_use, tool_result
- [ ] Show/hide tool results (to focus on just the agent's decisions)
- [ ] Jump to next/previous match navigation
- [ ] Result count indicator (e.g., "Showing 23 of 156 messages")
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-009: Tool call timeline artifact
**Description:** As an evaluator, I want a visual timeline showing all tool calls in sequence with file access patterns so I can see the agent's exploration and editing strategy.

**Acceptance Criteria:**
- [ ] Vertical timeline showing each tool call as a node with: timestamp/sequence number, tool name, brief description (file path for Read/Edit/Write, command for Bash, pattern for Grep/Glob)
- [ ] Nodes are color-coded by tool category: file read (blue), file write (green), search (yellow), bash (gray), planning (purple)
- [ ] Clicking a timeline node scrolls the full trace to that message
- [ ] File access graph: shows which files were accessed and in what order, with read/write/edit annotations
- [ ] Timeline can be collapsed/expanded by tool category
- [ ] Duration between calls shown on timeline edges
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-010: Embedded repository file browser with diff view
**Description:** As an evaluator, I want to see the repository files the agent worked with and view diffs of the agent's changes alongside the trace.

**Acceptance Criteria:**
- [ ] File tree panel shows the repository structure (derived from file paths accessed in the trace)
- [ ] Clicking a file shows its content with syntax highlighting
- [ ] Diff view shows before/after for files modified by the agent (Edit/Write tool calls)
- [ ] Diffs are rendered in unified or side-by-side format (user toggle)
- [ ] Each diff links back to the trace message where the change was made
- [ ] Repository reference links to the GitHub locobench* repo at the correct path
- [ ] Files not accessed by the agent are shown grayed out in the tree
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-011: LLM judge - full GUI configuration
**Description:** As an evaluator, I want to configure the LLM judge entirely from the GUI including editing prompts, scoring rubrics, dimensions, and model selection.

**Acceptance Criteria:**
- [ ] System prompt editor with syntax highlighting and preview
- [ ] Scoring rubric editor: add/remove/reorder evaluation dimensions (e.g., code_quality, correctness, completeness, efficiency)
- [ ] Per-dimension weight configuration (sliders or numeric inputs)
- [ ] Per-dimension scoring criteria text editor (what constitutes a 1 vs 5)
- [ ] Model selection dropdown (Claude 3.5 Sonnet, Claude Opus 4.5, etc.)
- [ ] Temperature and max_tokens configuration
- [ ] "Test prompt" button that runs the judge on a single task and shows the result inline
- [ ] All changes saved to config without requiring code edits or CLI
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-012: LLM judge - template management
**Description:** As an evaluator, I want to save, load, and A/B test different judge configurations so I can iterate on evaluation criteria.

**Acceptance Criteria:**
- [ ] Save current judge config as a named template
- [ ] Load a template from the saved list, populating all fields
- [ ] Delete templates
- [ ] Duplicate a template to create a variant
- [ ] A/B comparison mode: run two different judge templates on the same set of tasks, show scores side-by-side
- [ ] Template list shows: name, creation date, dimensions included, model used
- [ ] Templates stored as JSON files in a configurable directory
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-013: LLM judge - human alignment verification
**Description:** As an evaluator, I want to verify that the LLM judge produces human-aligned scores by reviewing and overriding individual scores with human ratings.

**Acceptance Criteria:**
- [ ] Task list showing LLM judge scores alongside a column for human scores
- [ ] Inline score override: click a score cell to enter a human rating (1-5 per dimension)
- [ ] Agreement metrics displayed: Cohen's kappa, Pearson correlation, mean absolute error between human and LLM scores
- [ ] Disagreement highlighter: tasks where human and LLM scores differ by more than a configurable threshold are flagged
- [ ] Export human-annotated scores as CSV/JSON for offline analysis
- [ ] Progress tracker: X of Y tasks human-reviewed
- [ ] Batch annotation mode: navigate through tasks sequentially with keyboard shortcuts
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-014: Unified Analysis Hub
**Description:** As an evaluator, I want all analysis modules (statistical, comparison, time series, cost, failure) accessible from a single Analysis Hub page without needing CLI commands.

**Acceptance Criteria:**
- [ ] Analysis Hub page with card-based navigation to each analysis type
- [ ] Each analysis can be configured and run entirely from the GUI (no terminal needed)
- [ ] Analysis configuration: select experiment(s), select tasks to include, set parameters
- [ ] Statistical analysis: configure significance level, test type, effect size threshold from GUI
- [ ] Comparison analysis: select two runs to compare, choose metrics, generate comparison report
- [ ] Time series analysis: select metric, date range, aggregation level from GUI
- [ ] Cost analysis: select experiment(s), view token costs, execution time, cost per task
- [ ] Failure analysis: select experiment, view error clusters, failure patterns, root causes
- [ ] All analysis results displayed inline with interactive Plotly charts
- [ ] Export analysis results as PDF/CSV from the GUI
- [ ] Typecheck/lint passes
- [ ] Verify in browser using dev-browser skill

### US-015: Remove archived runs option
**Description:** As a developer, I need to remove the "include archived runs" toggle and related logic from the dashboard.

**Acceptance Criteria:**
- [ ] The "include archived runs" checkbox/toggle is removed from all UI views
- [ ] Related filtering logic in `filters.py`, `filter_ui.py`, and view files is removed
- [ ] No references to "archived" run status remain in the dashboard code
- [ ] Typecheck/lint passes

## Functional Requirements

- FR-1: Dashboard reads experiment data from `~/evals/custom_agents/agents/claudecode/runs/` (configurable via settings)
- FR-2: Experiment selector groups experiments by benchmark set derived from manifest metadata or directory naming
- FR-3: Experiment selector supports paired mode (baseline+variant) and individual mode
- FR-4: Task list within an experiment supports filtering by status, language, task type, difficulty, duration, and token usage
- FR-5: Task detail view displays: metadata, build environment, CLAUDE.md, task prompt, execution metrics, verifier output
- FR-6: Trace viewer parses claude-code.txt JSONL format and renders each message as an interactive card with syntax highlighting
- FR-7: Trace viewer provides full-text search with match highlighting and filtering by message type and tool name
- FR-8: Trace viewer includes a summary panel with tool usage metrics, execution timeline, and file access graph
- FR-9: Trace viewer includes a tool call timeline with color-coded nodes and click-to-navigate
- FR-10: Embedded diff viewer shows before/after file changes with links back to the trace message
- FR-11: Repository file tree shows accessed files with syntax highlighting and GitHub reference links
- FR-12: LLM judge configuration (prompt, rubric, dimensions, weights, model, temperature) is editable via GUI
- FR-13: LLM judge templates can be saved, loaded, deleted, duplicated, and A/B tested
- FR-14: Human alignment verification allows inline score overrides with agreement metrics (Cohen's kappa, correlation)
- FR-15: Analysis Hub provides GUI-driven configuration and execution of all analysis types (statistical, comparison, time series, cost, failure)
- FR-16: All analysis results are displayable inline with interactive charts and exportable as PDF/CSV
- FR-17: The "include archived runs" option is removed from the UI and related code

## Non-Goals

- Migrating historical data from `jobs/` or `eval_runs_v2/` to `runs/` (users handle this separately)
- Real-time streaming of agent traces during live benchmark execution
- Multi-user authentication or role-based access control
- Automated judge prompt optimization (manual editing only)
- Full git clone of locobench repositories (use file paths from traces + GitHub links)
- Custom benchmark creation through the GUI (use existing CLI/config workflow)
- Mobile-responsive design (desktop-focused dashboard)

## Design Considerations

- Use Streamlit's existing component model (st.tabs, st.expander, st.columns) for layout
- Reuse existing `dashboard/components/` for consistent styling
- Trace viewer should use virtual scrolling or lazy loading for 800KB+ files (render visible messages only)
- Diff view can use Python's `difflib` for unified diff generation
- File tree can be built from the set of file paths found in Read/Edit/Write tool calls in the trace
- Syntax highlighting via `streamlit-code-editor` or Streamlit's built-in `st.code`
- LLM judge templates stored as JSON in `configs/judge_templates/`
- Human alignment scores stored in SQLite alongside LLM scores

## Technical Considerations

- claude-code.txt files are JSONL (one JSON object per line), not plain text. The parser must handle malformed lines gracefully.
- Token usage data is embedded in the `usage` field of assistant messages within claude-code.txt
- The `parent_tool_use_id` field links sub-agent tool calls to their parent, enabling hierarchical trace rendering
- Large traces (500+ messages) need pagination or virtual scrolling to avoid Streamlit rendering bottlenecks
- Existing parsers in `src/ingest/transcript_parser.py` and `src/benchmark/trace_parser.py` should be unified or extended rather than rewritten
- The manifest.json schema (version 1.0.0) in eval_runs_v2 should be adopted as the standard for the new `runs/` directory
- Streamlit session state must be used carefully to avoid re-parsing traces on every interaction
- Analysis modules already exist in `src/analysis/` and should be wired to GUI controls rather than reimplemented

## Success Metrics

- Evaluator can find and open a specific task trace in under 3 clicks from the dashboard home
- Full trace for an 800KB claude-code.txt file renders within 5 seconds with all interactive features
- LLM judge can be reconfigured and re-run on a dataset without touching any config files or terminal
- Human alignment review of 50 tasks can be completed in a single session with inline scoring
- All 6 analysis types (statistical, comparison, time series, cost, failure, LLM judge) are accessible and configurable from the Analysis Hub without CLI

## Open Questions

1. Should the trace viewer support rendering sub-agent traces (from Task tool calls) inline or in a separate panel?
2. What is the expected directory structure within `runs/` - will it mirror `eval_runs_v2/` (manifest.json, index.json, runs/, pairs/) or adopt a new schema?
3. Should human alignment scores persist across sessions (SQLite) or be exportable only (CSV)?
4. For the file diff viewer, should we attempt to reconstruct file state from sequential Edit operations, or only show individual edit diffs?
5. Should the Analysis Hub support saving analysis configurations as presets for repeated use?
6. What is the retention policy for judge templates - should old templates be auto-archived?
