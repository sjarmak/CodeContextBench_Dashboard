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
# Optional: clear out lingering Harbor containers in Podman
bash scripts/podman_cleanup.sh
```
This helper stops/removes any `hb__` containers so new evaluations start with a
clean Podman workspace.

```bash
# Step 1: Source environment file
source .env.local

# Step 2: EXPORT variables to subprocesses (this is critical!)
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Step 3: Now run harbor commands (baseline example)
harbor run --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
# Recommended: always include explicit agent + model flags
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
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

## Agent File Organization

**Production Agents:**
- `agents/claude_baseline_agent.py` - BaselineClaudeCodeAgent
- `agents/mcp_variants.py` - 4 MCP variants (Strategic Deep Search, Deep Search Focused, No Deep Search, Full Toolkit)

**Compatibility/Deprecated:**
- `agents/claude_sourcegraph_mcp_agent.py` - Deprecated alias to DeepSearchFocusedAgent (kept for backward compat)

---

## Benchmark Agents

Five agents for comparing MCP impact on coding task performance:

| Agent | Class | File | Purpose |
|-------|-------|------|---------|
| Baseline Claude Code | `BaselineClaudeCodeAgent` | `agents/claude_baseline_agent.py` | Control: Claude Code with autonomous mode, NO MCP |
| Strategic Deep Search *(recommended)* | `StrategicDeepSearchAgent` | `agents/mcp_variants.py` | MCP + targeted Deep Search usage |
| Deep Search Focused | `DeepSearchFocusedAgent` | `agents/mcp_variants.py` | MCP with a dedicated deep-search-only endpoint. |
| MCP No Deep Search | `MCPNonDeepSearchAgent` | `agents/mcp_variants.py` | MCP with keyword/NLS search only (Deep Search disabled) |
| Full Toolkit | `FullToolkitAgent` | `agents/mcp_variants.py` | MCP with all tools, neutral prompting (control) |

**Design:**
- **Baseline**: Tests Claude Code's autonomous capabilities without MCP
- **Strategic Deep Search**: Measures MCP value when Deep Search is used only at key checkpoints
- **Deep Search Focused**: Tests the value of a dedicated deep-search-only MCP endpoint.
- **No Deep Search**: Tests if simpler MCP tools (keyword/NLS) are sufficient
- **Full Toolkit**: Tests agent's natural tool choice with all options available

**Usage:**
```bash
# Run single agent variant
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Run baseline agent
harbor run \
  --path benchmarks/big_code_mcp/big-code-vsc-001 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1

# Run all variants comparison
./scripts/run_mcp_comparison.sh benchmarks/big_code_mcp/big-code-vsc-001
```

**See:** [benchmarks/README.md](benchmarks/README.md) for complete benchmark listing and comparison matrix.

**Reference:** CodeContextBench-1md

---

## Benchmarks & Comparison Matrix

| Benchmark | MCP Value | Task Count | Setup Time | Best For |
|-----------|-----------|-----------|-----------|----------|
| big_code_mcp | ⭐⭐⭐⭐⭐ (high) | 4 | 5min | MCP capability testing |
| github_mined | ⭐⭐ (low) | 25 | 2min | General agent capability |
| dependeval | ⭐⭐⭐ (medium) | 9 | 10min | Multi-file reasoning |
| 10figure | ⭐⭐⭐⭐ (high) | 4 | 20min | Large codebase understanding |
| dibench | ⭐⭐⭐ (medium) | Variable | 15min | Dependency inference |
| repoqa | ⭐⭐⭐⭐ (high) | Variable | 10min | Tool-sensitive MCP eval |

**See:** [benchmarks/README.md](benchmarks/README.md#benchmark-comparison-matrix) for full details and setup instructions.

---

## Experiment Management

**CRITICAL: Every experiment MUST have a MANIFEST.md file.**

See `docs/EXPERIMENT_MANAGEMENT.md` for complete guide.

### Experiment Naming Convention

```
<experiment-type>-<focus>-<YYYYMMDD>[-<variant>]
```

**Good names:**
```
mcp-prompt-experiment-20251222          # Prompt strategy comparison
bigcode-comparison-20251220             # Big code benchmark comparison
agent-ablation-deepsearch-20251223      # Deep Search ablation study
```

**Bad names (avoid):**
```
test-run-20251220                       # What was tested?
2025-12-20__08-43-21                    # Raw timestamp only
single-task-correct                     # Not dated, unclear purpose
```

### Required Experiment Structure

```
jobs/my-experiment-20251223/
├── MANIFEST.md                         # REQUIRED: Hypothesis, config, results
├── config.json                         # Experiment configuration
├── REPORT.md                           # Results summary
├── baseline/                           # Per-agent results
├── aggressive/
└── strategic/
```

### MANIFEST.md Required Fields

Every experiment manifest must include:
1. **Hypothesis** - What you're testing
2. **Configuration** - Model, benchmark, tasks, agents
3. **Results Summary** - Success rates, key metrics
4. **Key Findings** - What was learned

### After Running Experiments

1. Move raw harbor output to experiment directory
2. Run analysis: `python3 scripts/analyze_mcp_experiment.py jobs/<experiment>/`
3. Update MANIFEST.md with results
4. Clean up orphaned timestamp directories

### Agent Short Names

| Short Name | Agent Class |
|------------|-------------|
| `baseline` | `BaselineClaudeCodeAgent` |
| `aggressive` | `DeepSearchFocusedAgent` |
| `strategic` | `StrategicDeepSearchAgent` |
| `nodeep` | `MCPNonDeepSearchAgent` |
| `full-toolkit` | `FullToolkitAgent` |

---

## Development & Operations

**Guides:**
- `docs/DEVELOPMENT.md` - Setup, commands, agent implementation, testing
- `docs/EXPERIMENT_MANAGEMENT.md` - Experiment naming, structure, analysis
- `docs/OBSERVABILITY.md` - Observability, metrics collection, enterprise metrics
- `docs/TROUBLESHOOTING.md` - Common issues
- `benchmarks/README.md` - Benchmark guide

## ARM64 Mac + Local MCP: QEMU Segfault Workaround

**Problem:** Running benchmarks locally on ARM64 Macs causes verifier parser segfault, even when tests pass.

**Solution:** Patch test.sh files to exit cleanly before parser runs:

```bash
# One-time setup: patch all benchmark tasks
python scripts/patch_test_sh_qemu_safe.py benchmarks/swebench_pro/tasks/

# Then run normally (with local MCP, on ARM64)
source .env.local && \
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL && \
harbor run --path benchmarks/swebench_pro/tasks/instance_<task> \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001 \
  -n 1
```

**Details:** See `history/QEMU_SEGFAULT_FIX.md` for technical background and validation methodology for white papers.

**Documentation Maintenance:**
- Update `docs/ARCHITECTURE.md` when structure changes
- Update `docs/DEVELOPMENT.md` when workflows change
- Update `docs/EXPERIMENT_MANAGEMENT.md` when experiment patterns change
- Update `docs/OBSERVABILITY.md` when observability/metrics features change
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

**Requires:** `SOURCEGRAPH_ACCESS_TOKEN` environment variable (CLI also accepts legacy `SRC_ACCESS_TOKEN`)

**Basic usage:**
```bash
ds start --question "Question about codebase" | jq -r '.id'
ds ask --id <id> --question "Follow-up question"
ds list --first 5
```

Use `--async` for complex questions on large codebases.
