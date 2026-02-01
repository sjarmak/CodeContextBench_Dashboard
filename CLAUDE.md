# Claude Instructions for CodeContextBench

Instructions for AI assistants (Claude) working on this codebase.

**See also:** `history/CLAUDE.md` for detailed workflows, `dashboard/CLAUDE.md` for dashboard-specific patterns.

---

## CRITICAL: Pre-Flight Checks

### 1. Secret Management
**NEVER commit secrets.** Pre-commit hook blocks: `sgp_`, `SOURCEGRAPH_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, `.env`, `.env.local`, `.mcp.json`

### 2. Model Configuration
**ALWAYS USE:** `anthropic/claude-haiku-4-5-20251001`

### 3. Environment Setup for Harbor
```bash
source .env.local
export ANTHROPIC_API_KEY DAYTONA_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
```

**Why Daytona for all benchmarks?** Real x86_64 cloud VMs (no QEMU emulation issues on ARM Mac), 6x faster, consistent environment. Required for SWE-bench.

---

## Project Context

**What:** CodeContextBench evaluates how Sourcegraph code intelligence tools improve coding agent output.

**Key Components:**
- **Agents:** `agents/` - Agent implementations (baseline and MCP variants)
- **Benchmarks:** `benchmarks/` - Task suites for evaluation
- **Dashboard:** `dashboard/` - Streamlit-based analysis dashboard
- **Runners:** `runners/` - Execution harness
- **Scripts:** `scripts/` - Tooling and automation

---

## Compounded Learnings (2026-01-31)

### Benchmark Repo Mirroring

**Pattern:** All benchmark repos are mirrored to the `sg-benchmarks` GitHub org for Sourcegraph indexing. The naming convention is `<repo>--<commit>` (e.g., `pytorch--ca246612`) or `<repo>--latest` for HEAD mirrors.

**Scripts:** `scripts/extract_benchmark_repos.py`, `scripts/create_benchmark_mirrors.sh`, `scripts/extract_tac_commits.sh`

**Gotchas discovered:**
- **Shallow clones fail for old commits**: `git clone --depth 1` won't find commits that aren't at HEAD. For PyTorch mirrors at specific commits, a full clone (~10GB) is needed, then checkout + force push.
- **macOS bash is v3.2**: Scripts using associative arrays (`declare -A`) fail on macOS. Use POSIX-compatible alternatives or explicitly use `/usr/local/bin/bash` (Homebrew bash 4+).
- **GitHub secret scanning blocks pushes**: Repos containing hardcoded secrets (e.g., Slack webhook URLs in `copilot-arena`) get blocked by GitHub's push protection. Must manually approve via the security URL GitHub provides, or create the repo as private.
- **TAC Docker images don't contain git repos**: TheAgentCompany (TAC) Docker images clone repos at runtime from a private GitLab. Cannot extract exact commits without server access. Use HEAD mirrors instead.

**Current mirror status:** 20/20 repos mirrored across big_code_mcp (4), github_mined (12 pytorch commits), tac_mcp_value (4).

### Dashboard Architecture Insights

**Harbor result.json format:** Timing fields (`started_at`, `finished_at`) are at the top level of result.json, NOT in a nested `timing` dict. This caused a persistent "Duration N/A" bug.

**Database NULL handling:** `list_agents()` queries can return NULL `agent_name` values. Always add `WHERE agent_name IS NOT NULL` and defensive Python filtering.

**View-Model alignment:** Analysis views must exactly match data model class attributes. Common mismatches include `agent_results` vs `agent_metrics`, `anomalies` vs `total_anomalies`, dict access vs dataclass attributes. Always verify classes in `src/analysis/`.

**Filesystem-first approach:** The Comparison Analysis was rewritten to scan `~/evals/custom_agents/agents/claudecode/runs/` directly rather than requiring database ingestion. This is more reliable — no ingestion step, always current data, no schema mismatches. `comparison_config.py` demonstrates this pattern.

**Streamlit sidebar limitation:** Config panels in `st.sidebar` appear below navigation and may be invisible. Use `st.columns()` in main content area instead.

**Streamlit duplicate keys:** Prefix widget keys by context (`nav_`, `hub_goto_`, `analysis_`) to avoid `StreamlitDuplicateElementKey` errors.

### LLM Judge System

**Oracle-guided evaluation pattern:** Load ground truth from `benchmarks/locobench_agent/data/output/agent_scenarios/<task_name>.json`, which contains `ground_truth`, `expected_approach`, `evaluation_criteria`, and `context_files`. Pass these alongside the agent's solution for reference-based grading. 3-point scoring (pass=1.0, partial=0.5, fail=0.0) is more reliable than finer-grained 0-4 scales.

**JSON parsing failures in LLM judge output have two root causes:**
1. **Input truncation** -- Cutting solution content mid-string produces "Unterminated string" errors. The judge's input limit was too low (5,000 chars); increased to 20,000.
2. **Unescaped quotes in LLM output** -- When the judge LLM quotes from the solution text, it breaks JSON. Fix: add "Respond with valid JSON only (escape all quotes and special characters)" to all prompt templates.
3. **max_tokens too low** -- 1000 tokens insufficient for oracle-guided evaluation; increased to 2000.

**Task name resolution via config.json:** Trial directory names are truncated with hash suffixes (e.g., `c_api_graphql_expert_079_archite__pm9xcPn`), but the real task name lives in `config.json` at the `task.path` field. Essential for matching against oracle scenario files.

**Sourcegraph skills do NOT load in Claude Code headless mode:** Skills installed via `npx -y skills add` show `"skills": []` in agent logs while MCP connects fine. Fix: embed skill prompt content directly in CLAUDE.md and instruction.md uploaded to the task environment.

**Streamlit `st.session_state` cannot be modified after widget instantiation:** Use `on_click` callback pattern that sets state before widget rerender, not direct assignment after the widget is created.

**Multi-round judge voting:** `EnhancedLLMJudge` uses 3-round voting for consistency with confidence scores. Tracks `oracle_alignment`, `vote_confidence`, `vote_distribution` in database. Dimensions: `ORACLE_CORRECTNESS`, `ORACLE_COMPLETENESS`, `MCP_EFFECTIVENESS`. More reliable than single evaluation pass.

**LoCoBench task types require different evaluation:** Understanding/analysis tasks produce solution reports to `/logs/agent/solution.md`. Code modification tasks should produce actual code changes. Dashboard detects type by checking which files were modified in agent trace (green banner = code changes, blue = analysis).

### LoCoBench Agent Benchmark

**Data structure:** Data lives in `data/output/scenarios/*.json` (8000 individual JSON files, NOT JSONL). Synthetic projects in `data/generated/` (1000 projects, NOT real GitHub repos). 8 task categories: `architectural_understanding`, `bug_investigation`, `code_comprehension`, `cross_file_refactoring`, `feature_implementation`, `integration_testing`, `multi_session_development`, `security_analysis`.

**Task selection:** Top 50 selected: 34 architectural_understanding, 13 cross_file_refactoring, 3 bug_investigation. Average context: 968K tokens, average files: 81. Scoring weights: context_length (0.3), files_count (0.3), task_category_bonus (0.4).

**Verifier keyword scoring dominates:** Current weights keyword_overlap at 50%, but ground truth keywords are too specific (only 21% average overlap). Recommended: reduce to 30% and increase file_ref_score to 30%.

**Ambiguous instructions for code modification tasks:** All LoCoBench tasks say "Write your solution to `/logs/agent/solution.md`" regardless of task type. For code modification tasks, agents write design documents instead of actual code. The verifier expects code changes but gets analysis reports.

### MCP Configuration & Harbor Integration

**HTTP MCP endpoints (NOT npx):** The correct way to configure MCP for Sourcegraph uses HTTP type:
- Sourcegraph: `${SOURCEGRAPH_URL}/.api/mcp/v1` with header `Authorization: token ${SOURCEGRAPH_ACCESS_TOKEN}`
- Deep Search: `${SOURCEGRAPH_URL}/.api/mcp/deepsearch` with same auth header

**MCP config file location in Harbor containers:** Must be at `/logs/agent/sessions/.mcp.json` (Harbor sets `CLAUDE_CONFIG_DIR=/logs/agent/sessions`). NOT `/app/.mcp.json` or `/root/.mcp.json`.

**MCP SSL certificate failure in Docker:** Node.js `fetch()` fails with Sourcegraph endpoints inside containers due to missing CA certs. Workaround: `NODE_TLS_REJECT_UNAUTHORIZED=0` set globally via `/etc/profile` in container. Note: HTTP MCP transport does NOT support the `env` field in `.mcp.json` config -- you cannot set `NODE_TLS_REJECT_UNAUTHORIZED` there. Must set it in the process environment directly (e.g., in the agent's command execution code).

**Clean A/B/C experiment design:** Single `BaselineClaudeCodeAgent` controlled by `BASELINE_MCP_TYPE` env var: `none` (pure baseline), `sourcegraph` (keyword_search, nls_search, read_file -- no deep search), `deepsearch` (deep search only). For SWE-agent variants, use separate classes (`MiniSweAgentBaseline`, `MiniSweAgentSourcegraphMCP`, `MiniSweAgentDeepSearchMCP`) in `mini_swe_agent_mcp.py`.

**Harbor CLI argument gotchas:** `--task-ids` does not exist (use `--task-name`). Agent import paths (e.g., `mini_swe_agent_mcp:MiniSweAgentBaseline`) are different from registered agent names (e.g., `mini-swe-agent`). Use import paths with `--agent-import-path` flag. Harbor's remote registry endpoint may return malformed JSON -- use `--path benchmarks/<name>/tasks/` instead of `--dataset` as a workaround.

### SWE-bench Debugging Patterns

**QEMU segfaults on ARM Mac:** `uv tool install` and `uv run parser.py` segfault inside x86_64 Docker containers emulated via QEMU on ARM. This is why Daytona is required for all benchmarks.

**Reward=0 has multiple layered causes:** Peel back one at a time: (1) Agent not installing (Python version), (2) Agent not executing (binary not found), (3) Agent changes not captured (empty submission via `git add -A` capturing debug scripts -- use `git add -u`), (4) Test.sh output not reaching Harbor (file path mismatch), (5) Parser segfaulting on ARM (QEMU).

**SWE-bench test.sh file path mismatch:** test.sh writes logs to `$LOG_FILE=/tmp/tmpXXXXXX` (temp file), but Harbor expects output in `/logs/verifier/test-stdout.txt` (mounted directory). The parser adds required `START_TEST_OUTPUT`/`END_TEST_OUTPUT` markers to the temp file, never to the Harbor location. Fix: `scripts/patch_swebench_testsh.py` injects `cp "$LOG_FILE" /logs/verifier/test-stdout.txt` into all cached tasks at `~/.cache/harbor/tasks/`.

**Agent execution time as smoke test:** 0.7-0.8 second execution is a clear signal the agent never ran. Normal execution is 5-12 minutes.

**Over-engineering install scripts breaks defaults:** Harbor's simple 2-line install (pip install --break-system-packages) works. A 120-line custom install script with venv setup, Python version detection, and verification checks BROKE what the defaults already handled.

### Dashboard Subprocess & Run Tracking

**File handle closed prematurely with context manager:** Using `with open(log_file) as f: subprocess.Popen(..., stdout=f)` closes the file handle immediately after `Popen()` returns. Fix: `log_fd = open(log_file, "w", buffering=1)` without context manager.

**Profile runner blocks on `subprocess.run()`:** `src/benchmark/profile_runner.py` line 405 uses blocking `subprocess.run()` in `_invoke_harbor()`, preventing background execution from dashboard. Needs same Popen fix as evaluation_runner.py.

**File-based persistence for run tracking:** Use JSON metadata + log files in `.dashboard_runs/` with PID-based process monitoring (psutil). Survives dashboard restarts. Streamlit session state is lost on page refresh.

**Non-blocking subprocess requires line buffering:** When using `subprocess.Popen()` for background execution, `buffering=1` (line-buffered) is required for real-time log output. Without it, output is cached and logs appear empty until the process completes. Pattern: `log_fd = open(log_file, "w", buffering=1)` then pass to `Popen(stdout=log_fd, stderr=subprocess.STDOUT)`.

**Streamlit auto-refresh grey flashing:** 2-second auto-refresh causes disorienting grey flash. Use 5-second interval + user toggle + manual refresh button.

### Python dict.get() None Gotcha

**`dict.get(key, default)` does NOT protect against `None` values.** If the key exists with value `None`, the default is NOT used. Use `data.get("key") or default_value` instead. This pattern is needed throughout the codebase for Harbor result.json fields (`verifier_result`, `agent_info`, `agent_result`, etc.) which can be `null`.

### Benchmark Results Summary (2026-01-25)

| Benchmark | Baseline | DeepSearch MCP | Delta | Notes |
|-----------|----------|---------------|-------|-------|
| LoCoBench (50 tasks) | 0.4478 mean | 0.4520 mean | +0.9% | DeepSearch used 6.5x more tokens (51M vs 7.8M input) |
| SWE-bench Pro archive (29 common) | 62.1% (18/29) | 62.1% (18/29) | 0% | Identical outcomes on common tasks |

**Statistical artifact warning:** When baseline and MCP runs have different task sets, raw mean reward comparisons produce misleading deltas. Must filter to common tasks for valid comparison.

### Pre-commit Hook Behavior

The project's pre-commit hook checks for secret patterns. It sometimes produces false positives or fails with `error: unknown option 'cached'` (environmental issue with Claude Code wrapper intercepting `git diff`). Safe to use `--no-verify` when files have been manually verified.

### Harbor Adapter Development Patterns

**Tests uploaded at verification time, NOT build time:** Harbor uploads test files to containers via `docker compose cp` at verification time. Dockerfile `COPY` commands for test files will fail because tests don't exist in the build context. Only copy project files and runtime dependencies in Dockerfile.

**TOML template syntax:** Task TOML templates must have valid TOML syntax -- cannot use variable placeholders like `{context_length}`. Use static placeholder values and update metadata programmatically after parsing.

**LoCoBench scenario ID format:** IDs follow `{language}_{domain}_{complexity}_{num}_{task_category}_{difficulty}_{variant}`. Context file paths use `//` separator that must be normalized to `/`. Ground truth format varies: string for analysis tasks, object/dict for bug investigation.

**JSONL supplements from raw JSON:** LoCoBench JSONL may be incomplete. Supplement missing fields (`context_files`, `description`, `expected_approach`) from raw scenario JSON files at load time. More flexible than regenerating the dataset.

**Agent testing order:** Use nop agent first (framework validation, fast), then oracle agent (correctness verification, requires `solution/solve.sh`), then real agents (full execution, slowest). Reward=0 from nop agent is expected, not a failure.

### uv Tool Isolation

**`uv tool install` creates isolated Python environments** (e.g., Python 3.13) with compiled binaries incompatible with system Python (e.g., 3.11). Importing packages from a uv tool's environment into system Python causes `pydantic_core._pydantic_core` missing errors. Solution: use the tool's own Python at `~/.local/share/uv/tools/<tool_name>/bin/python`. Check site-packages at `~/.local/share/uv/tools/<tool_name>/lib/python<version>/site-packages/`.

**Error diagnosis sequence for module imports:** (1) Check `python --version`, (2) Check `pip3 show <package>`, (3) For uv tools: `find ~/.local/share/uv -name <package>`, (4) Match error to cause: `tomllib` missing = Python <3.11, `pydantic_core` missing = version mismatch.

### Ralph Autonomous Agent Patterns

Ralph sessions (implementing PRD user stories) self-compound learnings to `progress.txt` on their feature branch. Key patterns discovered across Ralph sessions:
- **Mock context managers suppress exceptions**: When mocking `st.spinner()`, the mock's `__exit__` returns truthy, suppressing exceptions. Tests must account for this.
- **Template management pattern**: Save/load/duplicate templates using `judge_config.py` with `TemplateInfo` dataclass for metadata.
- **Filter controls pattern**: Create pure-function filters in `utils/` (e.g., `trace_filters.py`), integrate UI with `render_*_controls()`, use frozen dataclasses for immutable filter state.
- **Pre-commit hook false positives**: Ralph agents consistently encounter false secret detection. Using `--no-verify` is documented as acceptable when code is verified clean.

---

## Quick Reference

**Find work:**
```bash
bd ready
```

**Run benchmark:**
```bash
source .env.local && \
export ANTHROPIC_API_KEY DAYTONA_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL && \
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  -n 1
```

**Test:**
```bash
python -m pytest tests/ -q
```

**Root cleanliness check:**
```bash
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|CLAUDE|setup|pyproject|LICENSE|\.)"
```
