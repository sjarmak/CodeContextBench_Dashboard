# CodeContextBench Agent Workflow Guide

Quick reference for agent-specific patterns, workflows, and best practices.

**Target:** ~500 lines max. Move detailed docs to `docs/` directory.

---

## CRITICAL: Secret Management

**IF YOU COMMIT A SECRET, ROTATE IT IMMEDIATELY**

Pre-commit hook blocks: `sgp_`, `SOURCEGRAPH_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, `.env`, `.env.local`, `.mcp.json`

If a secret gets committed:
1. Rotate the credential immediately
2. Use `git filter-repo` to purge from history if needed

---

## CRITICAL: Model Configuration

**ALWAYS USE:** `anthropic/claude-haiku-4-5-20251001`

```bash
harbor run --model anthropic/claude-haiku-4-5-20251001 ...
```

---

## CRITICAL: Running Harbor Commands

**YOU MUST export credentials or harbor will fail:**

```bash
# Step 1: Source environment file
source .env.local

# Step 2: EXPORT variables to subprocesses (this is critical!)
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Step 3: Now run harbor commands
harbor run --path benchmarks/big_code_mcp/big-code-vsc-001 --agent claude-code -n 1
```

**Why?** Harbor spawns subprocesses that won't see sourced variables. You MUST export them.

---

## Docker Disk Space Management

Harbor task containers accumulate disk space quickly.

**Pre-Benchmark Cleanup (Safe):**
```bash
bash scripts/docker-cleanup.sh
```

**Full Cleanup (Stops All Running Tasks):**
```bash
docker stop $(docker ps -q) && docker system prune -a -f
```

**Monitor:**
```bash
docker system df              # Current usage
docker ps -a -s               # Container sizes
```

---

## Project Overview

CodeContextBench evaluates how Sourcegraph code intelligence tools improve coding agent output. It supports multiple agent implementations running against standardized benchmark task sets.

**See:** `docs/ARCHITECTURE.md` for detailed architecture.

---

## Design Principles (Mandatory)

### 1. Minimal, Focused Changes
- Each commit = one feature or fix
- No speculative features
- As small as possible

### 2. Adversarial Review
Before closing a bead with complex changes:
- What could break?
- Test failure cases
- Look for side effects
- Would you approve this if another agent wrote it?

### 3. Automated Tests Per Commit
- Every commit must have tests
- Tests must be specific to the change
- Use real code, not mocks
- If you can't test it, redesign it

### 4. Clear, Descriptive Naming
- Functions: `validate_task_completion()` not `check()`
- Classes: `TaskValidator` not `Helper`
- Files: `task_validator.py` not `utils.py`

### 5. Modular, Independently Testable Design
- Single responsibility per module
- Dependencies explicit (inject, don't create)
- Loose coupling

### 6. Root Directory is Sacred

**What belongs in root (ONLY):**
- `README.md`, `AGENTS.md`, `LICENSE`, `.gitignore`, `.gitattributes`
- `setup.py`, `pyproject.toml`
- Essential directories: `src/`, `tests/`, `docs/`, `agents/`, `runners/`, `benchmarks/`, `scripts/`, `infrastructure/`, `.beads/`, `configs/`

**What NEVER goes in root:**
- Status files (STATUS.md, PROGRESS.md) → `history/`
- Planning docs (PLAN.md, DESIGN.md) → `history/`
- JSON outputs → `artifacts/` or `jobs/`
- Temporary scripts → `scripts/` or `runners/`

**Check before every session:**
```bash
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|setup|pyproject|LICENSE|\.)"
# Should return nothing
```

---

## Sourcegraph MCP Agent

**File:** `agents/claude_sourcegraph_mcp_agent.py`

Extends Harbor's `ClaudeCode` agent with Sourcegraph MCP integration:
1. Lazy imports (no Harbor at module load)
2. Reads `SOURCEGRAPH_INSTANCE` and `SOURCEGRAPH_ACCESS_TOKEN` from env
3. Generates `.mcp.json` with HTTP server config
4. Uploads to task container at `/app/.mcp.json`

**Usage:**
```bash
export SOURCEGRAPH_INSTANCE="sourcegraph.com"
export SOURCEGRAPH_ACCESS_TOKEN="your-token"

harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  -n 1
```

**See:** `docs/MCP_SETUP.md` for full setup guide.

---

## MCP Agent Variants (A/B Testing)

**File:** `agents/mcp_variants.py`

Three agent variants for testing different tool combinations:

| Variant | Class | Purpose |
|---------|-------|---------|
| Deep Search Focused | `DeepSearchFocusedAgent` | Aggressively prompts to use `sg_deepsearch` FIRST |
| MCP No Deep Search | `MCPNonDeepSearchAgent` | Uses `sg_keyword_search`/`sg_nls_search` only |
| Full Toolkit | `FullToolkitAgent` | All tools, neutral prompting (control) |

**Usage:**
```bash
# Run single variant
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:DeepSearchFocusedAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Run all variants comparison
./scripts/run_mcp_variants_comparison.sh benchmarks/big_code_mcp/big-code-vsc-001
```

**Reference:** CodeContextBench-1md

---

## Development & Operations

**Guides:**
- `docs/DEVELOPMENT.md` - Setup, commands, agent implementation
- `docs/TROUBLESHOOTING.md` - Common issues
- `docs/BENCHMARK_EXECUTION.md` - RepoQA, Big Code task execution

**Documentation Maintenance:**
- Update `docs/ARCHITECTURE.md` when structure changes
- Update `docs/DEVELOPMENT.md` when workflows change
- Update `docs/TROUBLESHOOTING.md` when you fix issues

---

## Issue Tracking with bd (beads)

**This project uses bd for ALL issue tracking.** No markdown TODOs.

### Quick Start

```bash
bd ready                                    # Find unblocked work
bd update <id> --status in_progress         # Claim task
bd close <id> --reason "Completed: ..."     # Complete work
bd create "Title" -t task -p 2              # Create new issue
```

### Issue Types & Priorities

**Types:** `bug`, `feature`, `task`, `epic`, `chore`

**Priorities:**
- P0: Critical (security, data loss)
- P1: High (major features)
- P2: Medium (default)
- P3: Low (polish)
- P4: Backlog

### Workflow

1. `bd ready` - find work
2. `bd update <id> --status in_progress` - claim it
3. Read requirement carefully
4. Write test that proves requirement works
5. Implement to make test pass
6. Verify: `python -m pytest tests/ -q`
7. Commit with bead ID
8. Close only when tests PROVE completion

### Key Principles

- Create specific tests for bead requirements
- Use real implementations, not mocks
- Only close when tests prove it works
- Keep in `in_progress` if work remains
- Link discovered work: `bd create "Bug" -p 1 --deps discovered-from:<id>`

---

## Landing the Plane

When ending a session:

### 1. Review In-Progress Beads
```bash
bd list --json | jq '.[] | select(.status == "in_progress") | {id, title}'
```

For each bead, verify:
- Specific test exists and passes
- No regressions (`python -m pytest tests/ -q`)
- All changes committed

Close only if ALL criteria met. Leave open otherwise.

### 2. File Remaining Work
```bash
bd create "Remaining task" -t task -p 2
```

### 3. Run Tests
```bash
python -m pytest tests/ -q
```

### 4. Commit & Sync
```bash
git add .
git commit -m "Session close: <summary>"
git pull --rebase
bd sync
```

### 5. Clean Root Directory
```bash
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|setup|pyproject|LICENSE|\.)"
# Move any files found to appropriate directories
```

### 6. Clean Git State
```bash
git stash clear
git remote prune origin
git status
```

### 7. Report to User
- Closed beads
- Open beads (and why)
- New issues filed
- Recommended next session prompt

**Key insight:** Closing beads too early creates false confidence. When in doubt, leave it open.

---

## Deep Search CLI (ds)

External tool for programmatic Sourcegraph Deep Search access.

**Requires:** `SRC_ACCESS_TOKEN` environment variable

**Basic usage:**
```bash
ds start --question "Question about codebase" | jq -r '.id'
ds ask --id <id> --question "Follow-up question"
ds list --first 5
```

Use `--async` for complex questions on large codebases.
