# CodeContextBench Agent Workflow Guide

This file documents agent-specific patterns, workflows, and best practices for the CodeContextBench repository.

**Note:** Keep this file at ~500 lines max. If adding content, consider:
- Moving detailed docs to `docs/` directory
- Archiving past examples to `history/` directory
- Linking to external resources rather than duplicating
- This file should be the **quick reference**, not comprehensive documentation

## Current Status (Phase 3: Real Benchmarks)

**Baseline Pilot**: RUNNING (10 tasks, claude-code agent)  
**Start Time**: 2025-12-17 21:26 UTC  
**ETA**: 1.5-2 hours  
**Expected Result**: 30-40% success rate  

All 25 Dockerfiles fixed with git clone logic. Single test validated. MCP pilot queued after baseline.

See `history/HARBOR_READY.md` for detailed phase status.

## Project Overview

CodeContextBench is a benchmark evaluation framework for assessing how improved codebase understanding through Sourcegraph tools improves coding agent output. It supports multiple agent implementations (Claude Code, Claude+MCP, etc.) running against standardized benchmark task sets.

**See detailed architecture:** `docs/ARCHITECTURE.md`

## Design Principles (Mandatory for all code changes)

These principles apply to ALL code changes in CodeContextBench. Agents MUST follow these when implementing features or fixes.

### 1. Minimal, Focused Changes

- **Each commit = one feature or fix.** Don't bundle multiple features in a single commit.
- **Code changes should be as small as possible.** Implement only what's needed to satisfy the bead requirement.
- **No speculative features.** Don't add code "just in case" it might be useful later.
- **Rationale:** Smaller changes are easier to review, test, and debug. They reduce risk of unexpected side effects.

### 2. Adversarial Review (Mandatory for Complex/Large Changes)

Before closing a bead with complex or large code changes:
- **Ask yourself:** "What could break with this change?"
- **Test the failure cases:** What happens if inputs are wrong? What edge cases aren't covered?
- **Look for side effects:** Does this change affect other modules? Unintended consequences?
- **Code review the change yourself:** Would you approve this if another agent wrote it?
- If you can't confidently answer all of these, **keep the bead open** and leave notes for the next agent.

### 3. Automated Tests Per Commit

- **Every commit must have associated automated tests** that validate the functionality works as designed.
- **Tests must run in CI/locally:** `python -m pytest tests/ -q`
- **Tests must be specific to the change:** Generic test suites don't count.
- **Tests must use real code, not mocks** (unless bead explicitly requires mocking).
- **If you can't write a test for your change, your design is wrong.** Refactor until testable.

### 4. Clear, Descriptive Naming

Names are for the next agent or developer reading your code months later.

- **Functions:** Use full words, describe what it does: `validate_task_completion()` not `check()`
- **Classes:** Use clear types: `TaskValidator` not `Helper`
- **Files:** Name after the primary responsibility: `task_validator.py` not `utils.py`
- **Variables:** Use meaningful names: `max_retries` not `mr`
- **Comments:** Explain WHY, not WHAT. Code shows what, comments explain why decisions were made.

**Bad example:** `src/utils.py` with a `process()` function
**Good example:** `src/task_validators/timeout_validator.py` with `validate_task_timeout()` function

### 5. Modular, Independently Testable Design

- **Single responsibility:** Each class/module should have one job.
- **Dependencies explicit:** Pass dependencies in, don't create them inside the function.
- **Independently testable:** You should be able to test one module without starting up the whole system.
- **Loose coupling:** Changes to one module shouldn't ripple through the codebase.

**Bad example:** `HarborRunner` class that creates its own agents, loads configs, runs tests, and aggregates results all in one class
**Good example:** `HarborRunner` accepts injected `AgentFactory`, `ConfigLoader`, `TestRunner`, `ResultAggregator` as dependencies

### 6. Root Directory is Sacred

**CRITICAL RULE:** Do NOT create random markdown files in the root directory.

- ✅ **DO:** `docs/`, `history/`, `.beads/`, `src/`, `tests/`
- ❌ **DON'T:** `PLAN.md`, `STATUS.md`, `NOTES.md`, `IMPLEMENTATION.md`, `TODO.md` in root
- ❌ **DON'T:** `MIGRATION_STATUS.md`, `PROGRESS.md`, `SESSION_SUMMARY.md` in root

**Where things go:**
- **Permanent documentation:** `docs/` (ARCHITECTURE.md, DEVELOPMENT.md, API.md)
- **Temporary planning:** `history/` (PLAN.md, SESSION_NOTES.md)
- **Issue tracking:** `.beads/issues.jsonl` (NOT markdown files)
- **This file (AGENTS.md):** Quick reference for agents only

If you feel the urge to create a markdown file in root, STOP. Either:
1. Add it to AGENTS.md if it's agent guidance
2. Put it in `docs/` if it's permanent documentation
3. Put it in `history/` if it's temporary planning

---

## Engram Integration: Continuous Learning Loop

CodeContextBench uses **Engram** for structured learning from task execution. Every completed bead creates a learning signal that improves future agent performance.

### Bead Closure: Only When Work is Actually Complete

**⚠️ DO NOT close beads prematurely.** Only close a bead when the work is FULLY DONE and tested with **deterministic, specific tests** for the bead's exact requirements. Closing beads early means:
- ❌ Work appears complete to other agents but is actually incomplete
- ❌ The next agent wastes time discovering the work isn't done
- ❌ Engram learns from incomplete work (bad signal)

**What "complete" means (ALL required):**
- ✅ **Bead-specific test**: A deterministic test that validates the EXACT behavior required by this bead (not generic tests)
- ✅ **Unit tests**: Any new code changes have accompanying unit tests to prevent regressions
- ✅ **Tests NOT mocked**: Use real implementations unless the bead explicitly specifies mocking
- ✅ **All tests pass**: Run `python -m pytest tests/ -q` and verify EVERY test passes
- ✅ **Code committed**: All code changes committed to git
- ✅ **No known bugs**: No open issues or TODOs from this work
- ✅ **Documentation**: Updated if functionality/API changed
- ✅ **Ready to hand off**: Next agent can pick this up and immediately use it

**Testing requirement details:**
- Each bead MUST have a test that proves its specific requirement is met
- Do NOT rely on generic test suites to validate bead-specific work
- Do NOT use mocks unless the bead description explicitly says to mock something
- Write unit tests alongside any code changes (test-first is preferred)

**If work is NOT complete:** Keep the bead in `in_progress` status. Do NOT close it.

### Engram Workflow

**When work on a bead is COMPLETELY FINISHED:**

```bash
# 1. Create a bead-specific test (if one doesn't exist)
# This test MUST prove the exact requirement of the bead is met
# Example: If bead is "Add feature X", test should call feature X and verify it works
# DO NOT use mocks unless the bead description says to

# 2. Create unit tests for any new code
# These prevent regressions when other agents modify the code later

# 3. Run the bead-specific test to verify it passes
python -m pytest tests/test_<feature_name>.py -v

# 4. Run all tests to ensure no regressions
python -m pytest tests/ -q

# 5. Verify test results prove the bead requirement is met
# If the test doesn't directly validate the bead requirement, your work isn't done

# 6. Commit all code and tests
git add .
git commit -m "<bead-id>: [description]. Tests: [what tests validate the requirement]"

# 7. ONLY then close the bead (and only if step 5 passed)
bd close <bead-id> --reason "Completed: [detailed description]. Validated by: tests/<test_file>.py::<test_name>"
```

**What happens on `bd close`:**
- Bead gets `closedAt` timestamp (marks it as finished)
- Git hook automatically detects closure and runs `en learn`
- Engram captures execution traces from your test/build runs
- Engram extracts patterns and stores learnings in `.engram/engram.db`
- Knowledge base is automatically updated for future work

### Important Notes

- **Each bead needs a specific test.** Don't rely on generic suites to validate bead requirements.
- **Always use real implementations, not mocks**, unless the bead explicitly requires mocking.
- **Unit tests are mandatory** for any code changes (prevents regressions).
- **ONLY close when tests prove the requirement is met.** Passing generic tests ≠ bead complete.
- **Closing a bead is a promise** that the next agent can pick it up and it will work.
- **When in doubt, leave it in `in_progress`.** It's better to be conservative.
- **Engram learns from complete, tested code.** Untested or incomplete code creates bad learning signals.

### Manual Learning Capture (if needed)

If you need to learn from specific test/build runs without closing:

```bash
# Run this after executing tests/builds
en learn --beads <bead-id>
```

This runs the learning pipeline on a specific bead's execution traces.

### Querying Learned Knowledge

To see what Engram has learned:

```bash
# View patterns from AGENTS.md (auto-generated from database)
grep "Bullet #ccb-" AGENTS.md | head -20

# Or directly query the database
sqlite3 .engram/engram.db "SELECT * FROM insights LIMIT 10;"
```

### Key Engram Concepts

- **Trace**: Execution record (test pass/fail, build errors, etc.)
- **Insight**: Extracted learning from one or more traces
- **Bullet**: Formatted insight for reuse (stored in knowledge base)
- **engram.db**: SQLite database containing all learnings

## Phase 4: Single-Task Validation (Current Focus)

**Status**: In progress  
**Start**: Dec 18 2025  
**Goal**: Run sgt-001 with baseline and MCP agents to definitively prove whether MCP helps

### Key Changes for Phase 4

1. **System Prompt Requirement**
   - All agents now receive explicit system prompt: "You MUST complete this coding task"
   - No placeholders, no "here's what I would do", must make actual code changes
   - Prompt saved to `system_prompt.txt` in agent logs for verification

2. **Code Changes Validation**
   - Execution FAILS if git diff is empty (0 bytes)
   - Agents cannot succeed without making code edits
   - Validates fundamental requirement: actual code changes needed

3. **Real Test Validation (sgt-001)**
   - Replaced fake `make test` with proper validation in `tests/test.sh`
   - Validates specific files modified: `NCCLUtils.cpp`, `NCCLUtils.hpp`
   - Checks for thread safety patterns (mutex, locks, atomic)
   - Returns 1.0 for success, 0.5 for partial, 0.0 for failure

4. **Complete Trace Capture**
   - New runner: `runners/capture_single_task_trace.py`
   - Captures full conversation turns (not just final JSON)
   - Extracts metrics: tokens, time, tool calls
   - For MCP: tracks all Deep Search queries and results
   - Validation checks: code changes exist, test files found, system prompt applied

### Running Single-Task Comparison

See `history/RUNBOOK_SINGLE_TASK_COMPARISON.md` for detailed instructions:

```bash
# Baseline agent (no Sourcegraph)
harbor run \
  --path benchmarks/github_mined \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 \
  --jobs-dir jobs/claude-baseline-github_mined-single-test \
  --task-name sgt-001

# MCP agent (with Sourcegraph)
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 \
  --jobs-dir jobs/claude-mcp-github_mined-single-test \
  --task-name sgt-001

# Capture traces
python3 runners/capture_single_task_trace.py \
  --task-dir jobs/claude-baseline-github_mined-single-test/*/sgt-001__*/ \
  --output artifacts/baseline-single-test-trace.json
```

### Job Naming Convention

All new jobs MUST follow: `<agent-type>-<benchmark-set>-<test-scope>`

✅ Good: `claude-baseline-github_mined-single-test`, `claude-mcp-github_mined-pilot`
❌ Bad: `harbor-baseline-pilot`, `mcp-sanity-verify`, `harbor-test-single`

See `jobs/README.md` for full naming guide.

### Critical Validation Checklist

Before concluding MCP testing:
- [ ] Baseline patch.diff > 0 bytes (code changes exist)
- [ ] MCP patch.diff > 0 bytes (not zero code)
- [ ] Baseline test output shows real validation (not fake `make test`)
- [ ] MCP test output shows real validation
- [ ] Both system_prompt.txt files exist and contain requirements
- [ ] Token counts captured and reasonable (not zero)
- [ ] Code changes match expected patterns (thread safety for sgt-001)

## Learned Patterns

### Agent Implementation Patterns

[Bullet #ccb-001, helpful:0, harmful:0] Always implement agent initialization in `__init__` with tool registration - Agents should register available tools (Sourcegraph Deep Search, file operations, etc.) during initialization, not at runtime

[Bullet #ccb-002, helpful:0, harmful:0] Agent methods must return structured Result objects - All agent methods should return a consistent Result object containing status, output, and metadata for benchmark aggregation

[Bullet #ccb-003, helpful:0, harmful:0] Sourcegraph Deep Search integration requires conversation ID tracking - When using Deep Search, store and reuse conversation IDs across multiple questions in the same task context to maintain context

### Benchmark Execution Patterns

[Bullet #ccb-010, helpful:0, harmful:0] Always validate task context before agent execution - Load task manifest, verify required files exist, and validate expected output format before running any agent against a benchmark

[Bullet #ccb-011, helpful:0, harmful:0] Benchmark results must include execution metadata - All results should capture agent name, task ID, execution time, tool usage, and error traces for proper analysis

[Bullet #ccb-012, helpful:0, harmful:0] Run aggregator after multi-benchmark executions - After executing tasks across multiple benchmark sets, run `aggregator.py` to generate cross-benchmark comparative reports

### Container & Infrastructure Patterns

[Bullet #ccb-020, helpful:0, harmful:0] Podman is the primary container runtime - Use Podman commands in scripts; docker-wrapper.sh provides compatibility for Docker-only environments

[Bullet #ccb-021, helpful:0, harmful:0] Harbor job outputs must be collected to `jobs/` directory - After Harbor executions, archive job outputs to `jobs/` with timestamped naming convention: `jobs/run-YYYY-MM-DD-HH-MM-SS/`

[Bullet #ccb-022, helpful:0, harmful:0] Lightweight JSON observability replaces NeMo - Use ManifestWriter and MetricsCollector from observability/ module to capture execution metrics; write run_manifest.json with tool usage and performance data (see docs/OBSERVABILITY.md)

### Testing & Validation Patterns

[Bullet #ccb-030, helpful:0, harmful:0] Run smoke_test.sh before any benchmark execution - Validates environment setup, tool availability, and basic agent functionality

[Bullet #ccb-031, helpful:0, harmful:0] Use agent_capabilities_test.py to verify agent features - Tests tool integration (Sourcegraph Deep Search, file operations) before running against actual benchmarks

[Bullet #ccb-032, helpful:0, harmful:0] Result validation must check for required fields - All benchmark results must validate against the Result schema defined in `docs/API.md`

[Bullet #ccb-033, helpful:0, harmful:0] Fixture data in `tests/fixtures/` should be small and self-contained - Fixtures should be under 1MB each to ensure fast test execution; use symbolic references to `benchmarks/` for larger datasets

### CodeContextBench-Specific Patterns

[Bullet #ccb-100, helpful:0, harmful:0] Harbor task validation requires all 5 files - Tasks must have: instruction.md, task.toml, task.yaml, environment/Dockerfile, tests/test.sh. Use gen_harbor_tasks.py to ensure completeness.

[Bullet #ccb-101, helpful:0, harmful:0] Task instructions must be type-specific - Each task type (cross_file_reasoning, refactor_rename, api_upgrade, bug_localization) needs specialized instruction language tailored to the problem domain.

[Bullet #ccb-102, helpful:0, harmful:0] Claude baseline and Claude+MCP differ only in credentials and MCP config - Both agents use identical command generation; differentiation happens via SRC_ACCESS_TOKEN and --mcp-config at runtime, not in agent class code.

[Bullet #ccb-103, helpful:0, harmful:0] Engram learning must be triggered on bead closure - Do NOT skip `en learn` after completing work. Learning is the mechanism for improving future agent performance across the codebase.

[Bullet #ccb-108, helpful:0, harmful:0] NeMo-Agent-Toolkit integration provides structured execution tracing - Use NeMoTraceParser to extract per-tool metrics (latency, token counts, failure rates). Falls back to Claude log parsing if traces unavailable. Always pass nemo_trace to ManifestWriter.write_manifest() when available.

[Bullet #ccb-109, helpful:0, harmful:0] Use extract_nemo_traces.py runner for batch manifest generation - Automatically discovers NeMo traces in job directories, extracts metrics, and generates run_manifest.json files with failure analysis and per-tool breakdowns.

[Bullet #ccb-110, helpful:0, harmful:0] NeMo metrics enable per-tool cost analysis and failure debugging - Extract tool_latency_by_tool, token_count_by_tool, and failure_rate_by_tool for detailed performance and cost breakdown. Use in cost optimization and bottleneck analysis.

[Bullet #ccb-104, helpful:0, harmful:0] Root directory contains ONLY permanent documentation - No ephemeral status files (MIGRATION_STATUS.md, SMOKE_TEST_RESULTS.md). Status is tracked in beads; planning docs go in history/ directory.

[Bullet #ccb-105, helpful:0, harmful:0] External corpus contracts belong in infrastructure/datasets.yaml - Define image name, env vars, paths, validator contract, resource requirements, and reference detailed docs. Never hardcode dataset paths in code.

[Bullet #ccb-106, helpful:0, harmful:0] 10Figure corpus setup requires container image + environment variable - Use harbor-10figure:base image (pre-loaded with corpus) and HARBOR_10FIGURE env var. See docs/10FIGURE.md for full setup instructions.

[Bullet #ccb-107, helpful:0, harmful:0] All credentials must be in .env.local (never committed) - Create from .env.local.example, fill in ANTHROPIC_API_KEY and SRC_ACCESS_TOKEN, source infrastructure/load-env.sh before running benchmarks. load-env.sh validates required vars and masks sensitive values.

[Bullet #ccb-111, helpful:0, harmful:0] Docker wrapper script (docker-wrapper.sh) translates docker commands to podman - Located at infrastructure/docker-wrapper.sh; handles docker compose exec/cp commands with special flags that podman-compose doesn't support (e.g., -it, cp). Install to ~/.bin/docker and add to PATH.

[Bullet #ccb-112, helpful:0, harmful:0] Harbor configuration belongs in infrastructure/harbor-config.yaml - Defines container runtime, agent timeouts, memory limits, task execution parallelism, benchmark environments, agent profiles, and observability settings. Read by runners and infrastructure scripts.

[Bullet #ccb-113, helpful:0, harmful:0] Podman requires explicit setup on macOS via podman machine - Use `podman machine init --cpus 4 --memory 4096 && podman machine start` before running benchmarks. Allocate sufficient resources (4+ CPU, 4GB+ RAM). See infrastructure/PODMAN.md for full setup.

[Bullet #ccb-114, helpful:0, harmful:0] Infrastructure documentation should be modular and Podman-first - PODMAN.md covers setup/troubleshooting, docker-wrapper.sh is executable wrapper, harbor-config.yaml is configuration file. All referenced in infrastructure/README.md. Users should read PODMAN.md first.

[Bullet #ccb-115, helpful:0, harmful:0] Task mining infrastructure enables real-world OSS task generation - src/task_mining/ provides GitHub API integration for mining issues/PRs from 7 target repos (Firefox, Kubernetes, PyTorch, VSCode, FFmpeg, TensorRT-LLM, Servo). Pipeline: mine → generate TaskSpecification → filter by CodeContextBench eligibility criteria (multi-file, token budget, test commands).

[Bullet #ccb-harbor-mcp-001, helpful:1, harmful:0] Harbor + Daytona + Claude Code works with API key in .env.local - Validate via: (1) source .venv-harbor/bin/activate, (2) source infrastructure/load-env.sh, (3) harbor run with --env daytona --agent claude-code --disable-verification for testing. Agent will clone repo and execute, producing 6M+ cached tokens on second run. Dockerfile must include git clone logic or workspace will be empty.

[Bullet #ccb-harbor-mcp-002, helpful:1, harmful:0] Sourcegraph MCP integration for Claude Code - DON'T create custom agent. Instead use --agent claude-code. MCP setup requires task's entrypoint or RUN command that creates .mcp.json in /workspace with env vars SOURCEGRAPH_MCP_URL and SOURCEGRAPH_ACCESS_TOKEN. Claude Code auto-discovers .mcp.json on startup. Challenge: env vars only available at runtime, not build time. Solution: create setup-mcp.sh entrypoint or use bash -c to write config during container start.

[Bullet #ccb-harbor-mcp-003, helpful:1, harmful:0] .env.local gets overwritten if .env.local.save exists - Git hooks or tools may create .env.local.save as a backup. Check if .env.local is tracked in git (should not be, it's in .gitignore). If it gets reset, check git log and .env.local.save location. Solution: keep only .env.local, delete .env.local.save, ensure .gitignore excludes .env.local.

[Bullet #ccb-harb-001, helpful:1, harmful:0] Official harborai package (v0.1.25) works without typer conflicts - Use `pip install harborai` instead of old harbor-cli 0.3.0. Works perfectly with anthropic package. Create isolated .venv-harbor to avoid dependency issues.

[Bullet #ccb-harb-002, helpful:1, harmful:0] Harbor Dockerfiles must clone PyTorch repo at task-specific commit - Initial test showed /workspace empty because Dockerfiles didn't clone. Added git clone + git checkout to all task Dockerfiles. Each task has correct commit SHA extracted from instruction.md (21 use main, 4 use specific SHAs).

[Bullet #ccb-harb-003, helpful:1, harmful:0] Harbor executions hang on long git clone operations—expect 15+ minutes per task - PyTorch repo is 10GB+. First task takes longer due to full clone. Subsequent tasks reuse cached layers. Use -n 1 concurrency for testing, increase for full runs.

## Development & Operations

**See development guide:** `docs/DEVELOPMENT.md`

- Setting up new agent implementations
- Running benchmarks and comparing performance
- Debugging agent execution
- Development commands and code quality standards

**See troubleshooting guide:** `docs/TROUBLESHOOTING.md`

- Agent initialization issues
- Benchmark execution problems
- Container and infrastructure issues
- Result aggregation and comparison
- Engram learning troubleshooting
- Git and beads synchronization

### Documentation Maintenance

When working on CodeContextBench, keep these docs in sync with your changes:

- **docs/ARCHITECTURE.md** - Update when directory structure, file organization, or agent architecture changes
- **docs/DEVELOPMENT.md** - Update when adding new development workflows, commands, or setup procedures
- **docs/TROUBLESHOOTING.md** - Update whenever you encounter and fix an issue not already documented
- **AGENTS.md** - Update learned patterns section when discovering new patterns; keep file at ~500 lines max

**Workflow:**
1. Complete your work and commit code changes
2. Update corresponding docs in `docs/` to reflect what you did
3. Commit documentation updates together with code
4. Close bead via `bd close` (triggers Engram learning)

Documentation is part of the deliverable, not an afterthought.

---

## Deep Search CLI (ds)

The `ds` CLI tool provides programmatic access to Sourcegraph Deep Search for AI-powered codebase analysis.

### Setup

Requires `SRC_ACCESS_TOKEN` environment variable. Optional: `SOURCEGRAPH_URL` (defaults to https://sourcegraph.sourcegraph.com)

### Common Usage Patterns

**Start a new conversation:**

```bash
ds start --question "Does the repo have authentication middleware?" | jq -r '.id'
```

**Continue existing conversation (using UUID from web UI):**

```bash
ds ask --id fb1f21bb-07e5-48ff-a4cf-77bd2502c8a8 --question "How does it handle JWT tokens?"
```

**Get conversation by ID or UUID:**

```bash
ds get --id 332  # numeric ID
ds get --id fb1f21bb-07e5-48ff-a4cf-77bd2502c8a8  # UUID from share_url
```

**List recent conversations:**

```bash
ds list --first 5 --sort -created_at
```

**Async mode for long-running queries:**

```bash
ds start --question "Complex question" --async | jq -r '.id'
# Poll for results
ds get --id <id>
```

### Best Practices

- Use `--async` for complex questions that search large codebases
- Parse JSON output with `jq` for extracting specific fields
- Save conversation IDs to continue multi-turn conversations
- UUIDs from web UI share URLs work directly with all commands

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Auto-syncs to JSONL for version control
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

**Standard workflow:**

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Understand the requirement**: Read the bead description carefully - what EXACT behavior must be demonstrated?
4. **Test-first approach** (strongly recommended):
   - Write a test that proves the bead requirement works
   - Test should use REAL implementations, not mocks (unless bead says to mock)
   - This test should fail initially (red state)
5. **Implement**: Write code to make the test pass
6. **Unit tests**: Add unit tests for any new code to prevent regressions
7. **Verify tests pass**:
   ```bash
   python -m pytest tests/test_<bead_feature>.py -v  # Bead-specific test
   python -m pytest tests/ -q                         # All tests (no regressions)
   ```
   - If tests don't directly validate the bead requirement, work isn't done
8. **Document**: Update docs/code comments if API or functionality changed
9. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
10. **Commit your changes**:
    ```bash
    git add .
    git commit -m "<bead-id>: [description]. Tests: tests/test_<name>.py::<test_func>"
    ```
11. **Only if work is 100% complete and tests prove it**: Close the bead
    ```bash
    bd close <id> --reason "Completed: [detailed summary]. Validated by: tests/test_<name>.py::<test_func>"
    ```
    - Finalizes the bead with a `closedAt` timestamp
    - Git hook detects closure and auto-runs `en learn`
    - Engram extracts patterns from your test/build runs
    - Knowledge stored in `.engram/engram.db` for future work

**Key principles:** 
- ✅ Create a **specific test for the bead requirement** (not generic tests)
- ✅ Use real implementations unless bead explicitly says to mock
- ✅ Write unit tests for new code to prevent regressions
- ✅ Only close when tests PROVE the requirement is met
- ✅ Keep beads in `in_progress` if more work remains
- ❌ Don't assume generic test passing = bead complete
- ❌ Don't close a bead to "finish" it if work is incomplete

### Auto-Sync

bd automatically syncs with git:

- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Best Practices

- **One agent per module at a time.** Cross-module changes split into separate beads.
- Close beads as soon as work is complete (don't batch).
- Use `bd ready` to find unblocked work.
- Always update status to `in_progress` when starting work.
- Always use `--json` flag for programmatic use.
- Link discovered work with `discovered-from` dependencies.
- Check `bd ready` before asking "what should I work on?"

### Managing Status & Progress Documents

**CRITICAL RULE: No status/progress documents in repository root. EVER.**

Root-level markdown files like STATUS.md, PROGRESS.md, MIGRATION_STATUS.md, SMOKE_TEST_RESULTS.md have NO BUSINESS being in the root directory. All issue status, testing status, and project progress must be tracked in beads.

**The Single Source of Truth:**

- **Issue status** → tracked in `.beads/issues.jsonl` via `bd` CLI
- **Test results** → captured in bead description/comments (e.g., "Smoke test: 49/49 passing")
- **Migration progress** → each bead represents a migration step; closed beads = completed work
- **Execution traces** → stored in bead metadata via `ace capture` or `en learn`

**Why this matters:**

- Repository root should only contain permanent, high-level documentation (README.md, AGENTS.md, setup docs)
- Status documents are ephemeral—they become stale and create duplicate tracking systems
- Beads are the actual source of truth for task state; markdown files create confusion
- Clean root directory improves navigation and reduces noise

### AI-Generated Planning Documents

AI assistants often create temporary planning documents during development:

- PLAN.md, IMPLEMENTATION.md, ARCHITECTURE.md
- DESIGN.md, CODEBASE_SUMMARY.md, INTEGRATION_PLAN.md
- TESTING_GUIDE.md, TECHNICAL_DESIGN.md, and similar files

**Required approach:**

- Store ALL AI-generated planning/design docs in `history/` directory (never root)
- Keep the repository root clean and focused on permanent project files
- Only access `history/` when explicitly asked to review past planning

**Rationale:**

-  Clean repository root (no clutter)
-  Clear separation between ephemeral and permanent documentation
-  Beads are the source of truth, not ephemeral docs
-  Preserves planning history for archeological research (in history/ dir)
-  Reduces noise when browsing the project

### Important Rules

-  Use bd for ALL task tracking and status
-  Always use `--json` flag for programmatic use
-  Link discovered work with `discovered-from` dependencies
-  Check `bd ready` before asking "what should I work on?"
-  Store AI planning/design docs in `history/` directory only
-  Record test results in bead metadata (via `ace capture` or test execution)
-  Do NOT create markdown TODO lists in root
-  Do NOT create status/progress markdown files in root
-  Do NOT use external issue trackers
-  Do NOT duplicate tracking systems
-  Do NOT clutter repo root with planning, status, or progress documents

### Landing the Plane

**When the user says "let's land the plane"**, follow this clean session-ending protocol:

1. **Review each bead you worked on** - Only close beads where work is COMPLETELY finished
   ```bash
   bd list --json | jq '.[] | select(.status == "in_progress") | {id, title}'
   ```
   For each bead, verify:
   - **Specific test exists**: Is there a test that directly validates the bead's exact requirement?
   - **Test uses real code**: Does the test call actual implementations (not mocks)?
   - **Tests pass**: Does `python -m pytest tests/<bead_test>.py -v` pass?
   - **No regressions**: Does `python -m pytest tests/ -q` pass (all tests)?
   - **Code committed**: Are all changes committed to git?
   - **No remaining issues**: Are there open TODOs or known bugs?
   
   If ALL YES: Close it. If ANY NO: Leave it open.
   ```bash
   bd close <bead-id> --reason "Completed: [detailed summary]. Verified by: tests/test_<name>.py::<test_func>"
   ```

2. **File beads issues for remaining work** that needs follow-up
   ```bash
   bd create "Remaining task" -t task -p 2
   ```

3. **Ensure all quality gates pass** (if code changes were made) - run tests/builds (file P0 issues if broken)
   ```bash
   python -m pytest tests/ -q
   ```

4. **Commit everything**:
   ```bash
   git add .
   git commit -m "Session close: <summary>"
   ```

5. **Sync the issue tracker carefully** - Work methodically to ensure both local and remote issues merge safely. This may require pulling, handling conflicts (sometimes accepting remote changes and re-importing), syncing the database, and verifying consistency. Be creative and patient - the goal is clean reconciliation where no issues are lost.
   ```bash
   git pull --rebase
   bd sync
   ```

6. **Clean up git state** - Clear old stashes and prune dead remote branches:
   ```bash
   git stash clear                    # Remove old stashes
   git remote prune origin            # Clean up deleted remote branches
   ```

7. **Verify clean state** - Ensure all changes are committed and pushed, no untracked files remain:
   ```bash
   git status
   git log --oneline -5
   ```

8. **Choose a follow-up issue for next session**
   - Provide a prompt for the user to give to you in the next session
   - Format: "Continue work on bd-X: [issue title]. [Brief context about what's been done and what's next]"

**Example "land the plane" session:**

```bash
# 1. Check what's in progress
bd list --json | jq '.[] | select(.status == "in_progress") | {id, title}'

# 2. For EACH bead - verify ALL criteria are met before closing
echo "=== Checking bd-42: Implemented feature X ==="
python -m pytest tests/test_feature_x.py -v  # Bead-specific test
python -m pytest tests/ -q                   # All tests (check for regressions)
grep -r "TODO\|FIXME" src/feature_x/        # Check for open issues
# Result: Specific test passes, no regressions, no TODOs → CLOSE IT

echo "=== Checking bd-43: Fixed bug Y ==="
python -m pytest tests/test_bug_y.py -v     # Does test prove bug is fixed?
# Result: Test doesn't exist or fails → LEAVE IT OPEN

# Close only the ones that are truly complete
bd close bd-42 --reason "Completed: Implemented feature X. Verified by: tests/test_feature_x.py::test_feature_x_works"
# bd-43 stays open (needs test or bug still present)

# 3. File remaining work
bd create "Complete feature Y implementation and write test" -t task -p 1 --deps discovered-from:bd-43

# 4. Commit everything
git add .
git commit -m "Session: Closed bd-42 (feature X working, tested)"

# 5. Sync carefully
git pull --rebase
bd sync

# 6. Clean up
git stash clear
git remote prune origin

# 7. Verify
git status
bd ready  # See what's ready to work on

# 8. Report back to user
# - Closed beads: bd-42 (feature X implemented and tested)
# - Open beads: bd-43 (still needs test coverage and bug fix verification)
# - New issues: follow-up work filed
```

**Key insight:** Closing beads too early creates false confidence. The next agent thinks work is done when it's not. A test that doesn't validate the bead requirement is useless. Be conservative. When in doubt, leave it open.

Then provide the user with:

- Summary of what was completed this session
- What issues were filed for follow-up
- Status of quality gates (all passing / issues filed)
- Recommended prompt for next session

## Agent Best Practices

### General Rules

NEVER start development servers for applications you're working on.
