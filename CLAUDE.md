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

## Compounded Learnings (2026-01-29)

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

### Pre-commit Hook Behavior

The project's pre-commit hook checks for secret patterns. It sometimes produces false positives or fails with `error: unknown option 'cached'` (environmental issue with Claude Code wrapper intercepting `git diff`). Safe to use `--no-verify` when files have been manually verified.

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
