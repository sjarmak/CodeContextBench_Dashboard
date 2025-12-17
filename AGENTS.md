# CodeContextBench Agent Workflow Guide

This file documents agent-specific patterns, workflows, and best practices for the CodeContextBench repository.

**Note:** Keep this file at ~500 lines max. If adding content, consider:
- Moving detailed docs to `docs/` directory
- Archiving past examples to `history/` directory
- Linking to external resources rather than duplicating
- This file should be the **quick reference**, not comprehensive documentation

## Project Overview

CodeContextBench is a benchmark evaluation framework for assessing how improved codebase understanding through Sourcegraph tools improves coding agent output. It supports multiple agent implementations (Claude Code, Claude+MCP, etc.) running against standardized benchmark task sets.

**See detailed architecture:** `docs/ARCHITECTURE.md`

## Engram Integration: Continuous Learning Loop

CodeContextBench uses **Engram** for structured learning from task execution. Every completed bead creates a learning signal that improves future agent performance.

### Engram Workflow

**For each completed bead:**

```bash
# 1. Work on the task (implement, test, commit)
bd update <bead-id> --status in_progress

# ... do the work ...

# 2. Run quality gates
python -m pytest tests/ -q

# 3. Close the bead (triggers automatic learning)
bd close <bead-id> --reason "Completed: [brief summary of what was done]"
```

**Engram automatically:**
- Captures execution traces (test results, build outcomes, errors)
- Extracts patterns from logs and traces
- Generates insights about failure modes and success patterns
- Stores learnings in `.engram/engram.db`
- Updates knowledge base for future work

### Learning Signals

Each bead closure generates learning data:

- **Successful tasks** → Extract what approach worked
- **Failed tasks** → Extract error patterns and root causes
- **Test results** → Correlate failures with code patterns
- **Execution metadata** → Track tool usage and performance

### Manual Learning (if needed)

If you need to capture learning without closing a bead:

```bash
en learn --beads <bead-id>
```

This runs the learning pipeline on a specific bead's execution traces.

### Querying Learned Knowledge

```bash
# See learned patterns
en get-insights --limit 10 --sort-by confidence

# Get specific patterns by tag
en get-insights --tags error-handling --min-confidence 0.8

# Review bullets (formatted learnings)
en get-bullets --limit 20 --sort-by helpful
```

### Key Engram Concepts

- **Trace**: Execution record (test pass/fail, build errors, etc.)
- **Insight**: Extracted learning from one or more traces
- **Bullet**: Formatted insight for reuse (stored in knowledge base)
- **engram.db**: SQLite database containing all learnings

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

**Standard workflow with Engram learning:**

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Run quality gates**: `python -m pytest tests/ -q` (or equivalent)
5. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
6. **Complete and learn**: `bd close <id> --reason "Completed: [summary]"`
   - A git hook automatically runs `en learn` to capture knowledge from completed work
   - Engram extracts patterns from test results, errors, and execution traces
   - Learnings stored in `.engram/engram.db` for future reference
7. **Commit together**: Always commit the `.beads/issues.jsonl` file together with the code changes so issue state stays in sync with code state

**Key principle:** Learning is NOT optional. Closing a bead triggers Engram to extract patterns that improve future performance.

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

- ✅ Clean repository root (no clutter)
- ✅ Clear separation between ephemeral and permanent documentation
- ✅ Beads are the source of truth, not ephemeral docs
- ✅ Preserves planning history for archeological research (in history/ dir)
- ✅ Reduces noise when browsing the project

### Important Rules

- ✅ Use bd for ALL task tracking and status
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Store AI planning/design docs in `history/` directory only
- ✅ Record test results in bead metadata (via `ace capture` or test execution)
- ❌ Do NOT create markdown TODO lists in root
- ❌ Do NOT create status/progress markdown files in root
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems
- ❌ Do NOT clutter repo root with planning, status, or progress documents

### Landing the Plane

**When the user says "let's land the plane"**, follow this clean session-ending protocol:

1. **File beads issues for any remaining work** that needs follow-up
2. **Ensure all quality gates pass** (only if code changes were made) - run tests, linters, builds (file P0 issues if broken)
3. **Update beads issues** - close finished work, update status
4. **Sync the issue tracker carefully** - Work methodically to ensure both local and remote issues merge safely. This may require pulling, handling conflicts (sometimes accepting remote changes and re-importing), syncing the database, and verifying consistency. Be creative and patient - the goal is clean reconciliation where no issues are lost.
5. **Clean up git state** - Clear old stashes and prune dead remote branches:
   ```bash
   git stash clear                    # Remove old stashes
   git remote prune origin            # Clean up deleted remote branches
   ```
6. **Verify clean state** - Ensure all changes are committed and pushed, no untracked files remain
7. **Choose a follow-up issue for next session**
   - Provide a prompt for the user to give to you in the next session
   - Format: "Continue work on bd-X: [issue title]. [Brief context about what's been done and what's next]"

**Example "land the plane" session:**

```bash
# 1. File remaining work
bd create "Add integration tests" -t task -p 2

# 2. Run quality gates (only if code changes were made)
npm test
npm run build

# 3. Close finished issues
bd close bd-42 bd-43 --reason "Completed"

# 4. Sync carefully - example workflow (adapt as needed):
git pull --rebase
# If conflicts in .beads/issues.jsonl, resolve thoughtfully:
#   - Accept remote if needed
#   - Re-import if changed
bd sync

# 5. Verify clean state
git status

# 6. Choose next work
bd ready
```

Then provide the user with:

- Summary of what was completed this session
- What issues were filed for follow-up
- Status of quality gates (all passing / issues filed)
- Recommended prompt for next session

## Agent Best Practices

### General Rules

NEVER start development servers for applications you're working on.
