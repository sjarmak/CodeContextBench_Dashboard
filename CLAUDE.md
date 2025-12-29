# Claude Instructions for CodeContextBench

Instructions for AI assistants (Claude) working on this codebase.

**See also:** `AGENTS.md` for complete workflows and patterns.

---

## CRITICAL: Pre-Flight Checks

### 1. Secret Management
**NEVER commit secrets.** Pre-commit hook blocks: `sgp_`, `SOURCEGRAPH_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, `.env`, `.env.local`, `.mcp.json`

If you accidentally commit a secret:
1. **STOP IMMEDIATELY**
2. Rotate the credential
3. Alert the user
4. Use `git filter-repo` if needed

### 2. Model Configuration
**ALWAYS USE:** `anthropic/claude-haiku-4-5-20251001`

```bash
harbor run --model anthropic/claude-haiku-4-5-20251001 ...
```

### 3. Environment Setup for Harbor

**IMPORTANT: Use Harbor Fork**

This project uses a forked version of Harbor with SWE-bench support:
- **Repository:** `sjarmak/harbor`
- **Installation:** `pip install -e /Users/sjarmak/harbor`
- **Key changes:** SWEBenchVerifier class for correct parser output capture

Before running any harbor commands:

```bash
# Step 1: Source environment
source .env.local

# Step 2: EXPORT variables (critical for subprocesses!)
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Step 3a: For most benchmarks
harbor run --path <benchmark-path> \
  --agent-import-path <agent-import> \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Step 3b: For SWE-bench - MUST use Daytona
export DAYTONA_API_KEY
harbor run --dataset swebench-verified@1.0 \
  --task-name <task-name> \
  --agent oracle \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  -n 1
```

**Why Daytona for SWE-bench?**
- SWE-bench parser requires x86_64 architecture
- Local Docker on ARM Mac uses QEMU emulation which causes segfaults
- Daytona provides real x86_64 cloud VMs (6x faster, no emulation issues)

**Why export?** Harbor spawns subprocesses that won't see sourced variables.

---

## Design Principles (Mandatory)

Follow these principles for ALL code changes:

### 1. Minimal, Focused Changes
- One feature or fix per commit
- No speculative features
- As small as possible

### 2. Adversarial Review
Before closing complex work, ask:
- What could break?
- Have I tested failure cases?
- What are the side effects?
- Would I approve this if another agent wrote it?

### 3. Automated Tests Per Commit
- Every commit MUST have tests
- Tests must be specific to the change
- Use real code, not mocks
- If you can't test it, redesign it

### 4. Clear, Descriptive Naming
- Functions: `validate_task_completion()` not `check()`
- Classes: `TaskValidator` not `Helper`
- Files: `task_validator.py` not `utils.py`

### 5. Modular Design
- Single responsibility per module
- Dependencies explicit (inject, don't create)
- Loose coupling

### 6. Root Directory is Sacred

**What belongs in root (ONLY):**
- Core docs: `README.md`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`
- Config: `setup.py`, `pyproject.toml`, `.gitignore`, `.gitattributes`
- Essential directories: `src/`, `tests/`, `docs/`, `agents/`, `runners/`, `benchmarks/`, `scripts/`, `infrastructure/`, `.beads/`, `configs/`

**What NEVER goes in root:**
- Status files (STATUS.md, PROGRESS.md) → `history/`
- Planning docs (PLAN.md, DESIGN.md) → `history/`
- JSON outputs → `artifacts/` or `jobs/`
- Temporary scripts → `scripts/` or `runners/`

**Check before every commit:**
```bash
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|CLAUDE|setup|pyproject|LICENSE|\.)"
# Should return nothing
```

---

## Project Context

**What:** CodeContextBench evaluates how Sourcegraph code intelligence tools improve coding agent output.

**Architecture:** See `docs/ARCHITECTURE.md`

**Key Components:**
- **Agents:** `agents/` - Agent implementations (baseline and MCP variants)
- **Benchmarks:** `benchmarks/` - Task suites for evaluation
- **Runners:** `runners/` - Execution harness
- **Tests:** `tests/` - Test suite

---

## Agent Variants

Five agents for MCP impact comparison:

| Agent | Class | File | Purpose |
|-------|-------|------|---------|
| Baseline | `BaselineClaudeCodeAgent` | `agents/claude_baseline_agent.py` | Control: NO MCP |
| Strategic Deep Search | `StrategicDeepSearchAgent` | `agents/mcp_variants.py` | MCP + targeted Deep Search |
| Deep Search Focused | `DeepSearchFocusedAgent` | `agents/mcp_variants.py` | MCP with deep-search-only endpoint |
| MCP No Deep Search | `MCPNonDeepSearchAgent` | `agents/mcp_variants.py` | MCP keyword/NLS only |
| Full Toolkit | `FullToolkitAgent` | `agents/mcp_variants.py` | MCP with all tools |

**Usage:**
```bash
# Run single agent
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Run baseline
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

---

## Issue Tracking with bd (beads)

**ALL issue tracking uses bd.** No markdown TODOs.

### Essential Commands

```bash
bd ready                                    # Find unblocked work
bd update <id> --status in_progress         # Claim task
bd close <id> --reason "Completed: ..."     # Complete work
bd create "Title" -t task -p 2              # Create new issue
bd list --json | jq '.'                     # List all issues
```

### Workflow (Critical)

1. `bd ready` - find work
2. `bd update <id> --status in_progress` - claim it
3. Read requirement carefully
4. **Write test that proves requirement works**
5. Implement to make test pass
6. Verify: `python -m pytest tests/ -q`
7. Commit with bead ID in message
8. **Close ONLY when tests PROVE completion**

### Key Principles

- Create specific tests for bead requirements
- Use real implementations, not mocks
- Only close when tests prove it works
- Keep `in_progress` if work remains
- Link discovered work: `bd create "Bug" -p 1 --deps discovered-from:<id>`

### Issue Types & Priorities

**Types:** `bug`, `feature`, `task`, `epic`, `chore`

**Priorities:**
- P0: Critical (security, data loss)
- P1: High (major features)
- P2: Medium (default)
- P3: Low (polish)
- P4: Backlog

---

## Experiment Management

**CRITICAL: Every experiment MUST have a MANIFEST.md file.**

### Naming Convention
```
<experiment-type>-<focus>-<YYYYMMDD>[-<variant>]
```

**Good:**
- `mcp-prompt-experiment-20251222`
- `bigcode-comparison-20251220`
- `agent-ablation-deepsearch-20251223`

**Bad:**
- `test-run-20251220` (what was tested?)
- `2025-12-20__08-43-21` (raw timestamp only)

### Required Structure
```
jobs/my-experiment-20251223/
├── MANIFEST.md          # REQUIRED: hypothesis, config, results
├── config.json          # Experiment configuration
├── REPORT.md            # Results summary
├── baseline/            # Per-agent results
├── aggressive/
└── strategic/
```

### MANIFEST.md Required Fields
1. **Hypothesis** - What you're testing
2. **Configuration** - Model, benchmark, tasks, agents
3. **Results Summary** - Success rates, key metrics
4. **Key Findings** - What was learned

**See:** `docs/EXPERIMENT_MANAGEMENT.md` for complete guide.

---

## Landing the Plane (Session Close)

When ending a session:

### 1. Review In-Progress Beads
```bash
bd list --json | jq '.[] | select(.status == "in_progress") | {id, title}'
```

For each bead:
- ✓ Specific test exists and passes
- ✓ No regressions (`python -m pytest tests/ -q`)
- ✓ All changes committed

**Close only if ALL criteria met. Leave open otherwise.**

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
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|CLAUDE|setup|pyproject|LICENSE|\.)"
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

## Common Operations

### Docker Cleanup
```bash
# Pre-benchmark cleanup (safe)
bash scripts/docker-cleanup.sh

# Full cleanup (stops all running tasks)
docker stop $(docker ps -q) && docker system prune -a -f

# Monitor
docker system df
docker ps -a -s
```

### Podman Cleanup (Harbor)
```bash
# Clear lingering Harbor containers
bash scripts/podman_cleanup.sh
```

### Deep Search CLI (ds)
```bash
ds start --question "Question about codebase" | jq -r '.id'
ds ask --id <id> --question "Follow-up question"
ds list --first 5
```

**Requires:** `SOURCEGRAPH_ACCESS_TOKEN` environment variable

---

## Documentation Maintenance

Update when you change:
- `docs/ARCHITECTURE.md` - Structure changes
- `docs/DEVELOPMENT.md` - Workflow changes
- `docs/EXPERIMENT_MANAGEMENT.md` - Experiment patterns
- `docs/OBSERVABILITY.md` - Observability/metrics features
- `docs/TROUBLESHOOTING.md` - When you fix issues
- `benchmarks/README.md` - Benchmark changes

---

## Quick Reference

**Find work:**
```bash
bd ready
```

**Run benchmark:**
```bash
# Standard benchmarks
source .env.local && \
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL && \
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# SWE-bench (requires Daytona)
source .env.local && \
export ANTHROPIC_API_KEY DAYTONA_API_KEY && \
harbor run --dataset swebench-verified@1.0 \
  --task-name astropy__astropy-12907 \
  --agent oracle \
  --model anthropic/claude-haiku-4-5-20251001 \
  --env daytona \
  -n 1
```

**Test:**
```bash
python -m pytest tests/ -q
```

**Check root cleanliness:**
```bash
ls -1 | grep -E "\.(md|json|py|sh|txt)$" | grep -v -E "^(README|AGENTS|CLAUDE|setup|pyproject|LICENSE|\.)"
```

---

## Anti-Patterns to Avoid

❌ Committing without tests
❌ Closing beads when tests don't prove completion
❌ Creating files in root directory
❌ Using mocks instead of real implementations
❌ Speculative features or "improvements"
❌ Vague function/class names (e.g., `Helper`, `Utils`)
❌ Running harbor without exporting env vars
❌ Creating experiments without MANIFEST.md
❌ Forgetting to use the correct model

---

## When in Doubt

1. **Read AGENTS.md** - More detailed workflows
2. **Check docs/** - Architecture, development, troubleshooting
3. **Ask the user** - Better to clarify than assume
4. **Write a test** - If you can't test it, redesign it
5. **Keep it simple** - Minimal changes, clear code
