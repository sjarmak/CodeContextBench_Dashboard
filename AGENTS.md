# CodeContextBench Agent Workflow Guide

This file documents agent-specific patterns, workflows, and best practices for the CodeContextBench repository.

**Note:** Keep this file at ~500 lines max. If adding content, consider:

- Moving detailed docs to `docs/` directory
- Archiving past examples to `history/` directory
- Linking to external resources rather than duplicating
- This file should be the **quick reference**, not comprehensive documentation

## Critical: Model Configuration

**⚠️ ALWAYS USE: `anthropic/claude-haiku-4-5-20251001`**

Do NOT use claude-3-5-sonnet, claude-opus, or any other model. Harbor is configured to use Haiku for all benchmarks.

Example:
```bash
harbor run --model anthropic/claude-haiku-4-5-20251001 ...
```

---

## Current Status (Phase 3: Big Code MCP Comparison Execution)

**Phase 1 Completed (Dec 19 2025):**
- ✅ Built custom task suite infrastructure (`benchmarks/big_code_mcp/`)
- ✅ Implemented comparison framework (`scripts/run_mcp_comparison.sh`)
- ✅ Enhanced MCP agent to auto-inject task guidance (`agents/claude_sourcegraph_mcp_agent.py`)
- ✅ Created validation script for result integrity

**Phase 2 Completed (Dec 20 2025):**
- ✅ Created 4 production-ready big code MCP tasks from Trevor's research
- ✅ Added reward.json evaluation criteria for all 4 tasks
- ✅ Built run_big_code_comparison.sh wrapper
- ✅ Created extract_big_code_metrics.py for metric extraction
- ✅ Verified github_mined comparisons work (sgt-001: reward=1.0)

**Phase 3 In Progress (Dec 20 2025):**
- Executing all 4 big code MCP comparisons: vsc-001, servo-001, k8s-001, trt-001
- **CRITICAL FIX FOUND:** Must `export` credentials after sourcing .env.local
- Validated on github_mined (sgt-001 now passing with correct exports)
- Ready to run all 4 big code tasks with proper credential passing

**Critical Credential Requirement:**
```bash
# WRONG (just sourcing):
source .env.local

# CORRECT (must export):
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
# Now pass to harbor with --ek "KEY=$KEY" flags
```

**Key Learnings:** 
1. Deep Search MCP times out on >2GB codebases. Use full Sourcegraph endpoint: `https://sourcegraph.sourcegraph.com/.api/mcp/v1`
2. Harbor requires credentials EXPORTED in current shell, not just sourced
3. `--ek` flag requires `key=value` format, not separate args

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

## Comparison Results Best Practices

### Naming Conventions

Use **timestamped directory names** to prevent confusion with retries:

```
jobs/comparison-YYYYMMDD-HHMM/
  ├── baseline/     (baseline agent results)
  └── mcp/          (MCP agent results)
```

**DO NOT use fixed names** like `comparison-20251219-clean` without explaining what "clean" means. This caused confusion when re-runs with API key failures were labeled "clean" while the actually-valid original runs had different names.

### Validation Checklist

Before analyzing any comparison results, ALWAYS:

1. **Run validation script**: `python scripts/validate_comparison_results.py baseline/ mcp/`
2. **Check for API key errors**: Look for "Invalid API key" in trajectory messages
3. **Verify token counts**: Should be >0 for all valid runs (0 tokens + 6 steps = likely API failure)
4. **Confirm task completeness**: All 10 tasks should have trajectories
5. **Cross-reference timestamps**: Baseline and MCP runs should be from same session (prevents env var loss)

### Data Integrity

The `comparison-20251219-clean/` directory is corrupted and should NOT be used. It was a re-run attempt that failed due to lost API credentials. The real data is in:
- `baseline-10task-20251219/` (10/10 tasks, 34.8M tokens)
- `mcp-10task-20251219/` (9/10 tasks, 40.5M tokens, sgt-003 missing)

## Sourcegraph MCP Agent Implementation

### ClaudeCodeSourcegraphMCPAgent Pattern

**File**: `agents/claude_sourcegraph_mcp_agent.py`
**Import**: `agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent`

The agent follows the practical approach of extending Harbor's built-in `ClaudeCode` agent without modifying the installed package:

1. **Lazy Imports**: `agents/__init__.py` avoids importing Harbor at module load time
2. **Credential Management**: Reads `SOURCEGRAPH_INSTANCE` and `SOURCEGRAPH_ACCESS_TOKEN` from environment
3. **Configuration**: Generates `.mcp.json` with HTTP server configuration pointing to Sourcegraph
4. **File Upload**: Uploads config to task container at `/app/.mcp.json`
5. **Graceful Degradation**: Logs warning if credentials missing but agent continues

**Usage**:

```bash
# Set credentials
export SOURCEGRAPH_INSTANCE="sourcegraph.com"
export SOURCEGRAPH_ACCESS_TOKEN="your-token"

# Run with agent
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1
```

See `docs/MCP_SETUP.md` for full setup and troubleshooting guide.

---

## Development & Operations

**See development guide:** `docs/DEVELOPMENT.md`

- Setting up new agent implementations
- Running benchmarks and comparing performance
- Debugging agent execution
- Development commands and code quality standards

**See troubleshooting guide:** `docs/TROUBLESHOOTING.md` for agent initialization, benchmark execution, container, and infrastructure issues

### Documentation Maintenance

When working on CodeContextBench, keep these docs in sync with your changes:

- **docs/ARCHITECTURE.md** - Update when directory structure, file organization, or agent architecture changes
- **docs/DEVELOPMENT.md** - Update when adding new development workflows, commands, or setup procedures
- **docs/TROUBLESHOOTING.md** - Update whenever you encounter and fix an issue not already documented
- **AGENTS.md** - Keep at ~500 lines max; move extensive documentation to `docs/`

**Workflow:**

1. Complete your work and commit code changes
2. Update corresponding docs in `docs/` to reflect what you did
3. Commit documentation updates together with code

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
- **Execution traces** → stored in bead metadata

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

- Clean repository root (no clutter)
- Clear separation between ephemeral and permanent documentation
- Beads are the source of truth, not ephemeral docs
- Preserves planning history for archeological research (in history/ dir)
- Reduces noise when browsing the project

### Important Rules

- Use bd for ALL task tracking and status
- Always use `--json` flag for programmatic use
- Link discovered work with `discovered-from` dependencies
- Check `bd ready` before asking "what should I work on?"
- Store AI planning/design docs in `history/` directory only
- Do NOT create markdown TODO lists in root
- Do NOT create status/progress markdown files in root
- Do NOT use external issue trackers
- Do NOT duplicate tracking systems
- Do NOT clutter repo root with planning, status, or progress documents

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

6. **Clean up root directory** - Remove any temporary files that shouldn't be in the root directory:

   ```bash
   # Check for files that don't belong in root
   ls -la *.json *.py 2>/dev/null | grep -v setup.py

   # Remove temporary configs, test scripts, and testing artifacts
   # Root should only contain:
   #   - README.md, AGENTS.md (documentation)
   #   - setup.py, pyproject.toml (project config)
   #   - LICENSE, .gitignore, .gitattributes (repo config)
   #   - Directories: src/, tests/, docs/, configs/, agents/, runners/, etc.
   #
   # DO NOT add to root:
   #   - harbor-config-*.json (use configs/ or history/)
   #   - test_*.py (use tests/)
   #   - STATUS.md, PROGRESS.md, PLAN.md (use history/ or .beads/)
   #   - IMPLEMENTATION.md, ARCHITECTURE_NOTES.md (use docs/)
   #   - Any temporary .mcp.json, .env.* files (use .claude/ or configs/)

   # Verify no stray files
   git status  # Should show no untracked root-level .json or .py files
   ```

7. **Clean up git state** - Clear old stashes and prune dead remote branches:

   ```bash
   git stash clear                    # Remove old stashes
   git remote prune origin            # Clean up deleted remote branches
   ```

8. **Verify clean state** - Ensure all changes are committed and pushed, no untracked files remain:

   ```bash
   git status
   git log --oneline -5
   ```

9. **Choose a follow-up issue for next session**
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

# 6. Clean up root directory
ls -la *.json *.py 2>/dev/null | grep -v setup.py  # Check for stray files
# Remove any temporary configs/scripts if they exist
git status  # Verify no untracked root files

# 7. Clean git state
git stash clear
git remote prune origin

# 8. Verify
git status
bd ready  # See what's ready to work on

# 9. Report back to user
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
