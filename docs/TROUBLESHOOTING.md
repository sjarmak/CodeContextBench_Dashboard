# Troubleshooting Guide

## Agent Issues

### Agent fails to initialize

- Check `ANTHROPIC_API_KEY` environment variable is set
- For Claude+MCP: verify `SOURCEGRAPH_ACCESS_TOKEN` (or legacy `SRC_ACCESS_TOKEN`) is set
- Check Sourcegraph URL: `echo $SOURCEGRAPH_URL`
- Run test: `python -m pytest tests/test_agent_env_injection.py -v`

### Agent command not executing

- Verify repository exists at specified path
- Check git is initialized: `git status` in repo directory
- Check agent can write to `/logs/agent/` in container
- Review agent logs: `cat jobs/run-*/logs/agent.log`

### Wrong results format

- Check task instruction is being passed correctly
- Verify task.yaml has correct task_id and type
- Run task schema validation: `python tests/test_task_schema.py`

## Benchmark Execution

### Benchmark tasks don't find context files

- Validate task directory structure exists
- Check all 5 required files present:
  - instruction.md
  - task.toml
  - task.yaml
  - environment/Dockerfile
  - tests/test.sh
- Verify file paths in task.yaml are correct (use absolute paths in container)

### Patch validation fails

- Check patch file exists: `ls -la /logs/agent/patch.diff`
- Verify patch is not empty: `wc -l /logs/agent/patch.diff`
- Check validate_patch.py can find corpus: `ls /10figure/tasks/`
- Review validation output: `cat /logs/verifier/validation_result.json`

### Results fail validation

- Review task schema in `src/benchmark/task_schema.py`
- Check for required fields: agent_name, task_id, status, timestamp
- Validate JSON structure: `python -m json.tool jobs/run-*/result.json`
- Check reward score extracted correctly: `jq '.verifier_result.rewards.reward' result.json`

## Container & Infrastructure

### Harbor command not found

- Install Harbor: `pip install harbor-cli`
- Check PATH: `echo $PATH`
- Verify installation: `which harbor`

### Podman/Docker not found

- Check container runtime: `podman ps` or `docker ps`
- For Podman: Install from https://podman.io
- For Docker: Install from https://docker.com
- Verify daemon running: `podman info` or `docker info`

### Container execution issues

- Check container logs: `podman logs <container>` or `docker logs <container>`
- List containers: `podman ps -a` or `docker ps -a`
- Check image exists: `podman images` or `docker images | grep harbor-10figure`
- Verify mounts: `podman inspect <container> | grep Mounts`

### Harbor task start fails with "no such file or directory"

This typically means a required directory is missing from the task structure.

**Common missing directories:**

- `solution/` - Harbor expects a solution directory with at least `solve.sh`
- `tests/` - Must contain `test.sh`

**Fix:**

```bash
# Create solution directory with placeholder
mkdir -p benchmarks/<benchmark>/<task>/solution
echo '#!/bin/bash' > benchmarks/<benchmark>/<task>/solution/solve.sh
echo '# Solution placeholder' >> benchmarks/<benchmark>/<task>/solution/solve.sh
```

### RewardFileNotFoundError during Harbor runs

The test.sh script must write a reward file at `/logs/verifier/reward.txt`.

**Fix test.sh:**

```bash
#!/bin/bash
set -e
mkdir -p /logs/verifier

# ... run tests ...

# Write reward (0.0 to 1.0)
echo "1.0" > /logs/verifier/reward.txt
```

### QEMU Parser Segfault on ARM64 Macs

**Symptoms:**
```
qemu: uncaught target signal 11 (Segmentation fault) - core dumped
/tests/test.sh: line 151: 13151 Segmentation fault (core dumped) uv run parser.py
```

**Cause:** Running SWE-bench verifications on Apple Silicon (ARM64) Macs using QEMU x86_64 emulation causes segfaults during result parsing, even when all tests pass.

**Warning signs:**
```
RuntimeWarning: numpy.ndarray size changed, may indicate binary incompatibility.
Expected 80 from C header, got 96 from PyObject
```

**Solution:** Use Daytona environment instead of local Docker:

```bash
# Use --env daytona flag to run on real x86_64 cloud VMs
harbor run --path <benchmark-path> \
  --agent-import-path <agent> \
  --env daytona \
  -n 1
```

**Why Daytona?**
- Real x86_64 cloud VMs (no QEMU emulation)
- 6x faster than local Docker
- Correct numpy/C extension compatibility
- No post-test parser crashes

**Affected:** All agents and benchmarks on ARM64 Macs. This is not agent-specific.

### Cached Docker images causing stale workspace

If workspace content doesn't match what's in Dockerfile's `git clone`:

```bash
# Force rebuild
harbor run --path <task-path> --force-build

# Or clear cache manually
docker system prune -a
podman system prune -a
```

### Job directory permissions

- Check jobs directory writable: `ls -la jobs/`
- Verify Harbor can write: `touch jobs/test.txt`
- Check file ownership after run: `ls -la jobs/run-*`

## Result Aggregation

### No results found

- Check jobs directory has run subdirectories: `ls jobs/`
- Verify result.json files exist: `find jobs -name result.json`
- Check aggregator path: `python runners/aggregator.py --runs jobs/`

### Aggregation fails

- Validate JSON in all result files: `python -m json.tool jobs/*/result.json`
- Check for required fields in each result
- Run with verbose output: `python runners/aggregator.py --runs jobs/ -v`

### Comparison shows no differences

- Verify both baseline and treatment runs completed
- Check result counts: baseline vs treatment should have same task count
- Inspect individual results for differences
- Check aggregator filtering logic

## Git & Beads

### Beads sync issues

- Check issues.jsonl exists: `ls .beads/issues.jsonl`
- Verify git tracking: `git ls-files .beads/`
- Force sync: `bd sync`
- Check for conflicts: `git status .beads/`

### Duplicate issue IDs

- Check for manual edits to issues.jsonl
- Verify bd CLI version: `bd --version`
- Clear cache and retry: `bd ready --json`

## Dashboard Issues

### Current Runs shows "Waiting for output..."

**Symptoms:**
- Elapsed time stuck at 2 seconds
- "Waiting for output..." instead of live logs
- Run started but no output appears

**Root Cause:**
The log file handle was closed immediately after starting the subprocess, preventing output from being written.

**Fix Applied:**
Changed `dashboard/views/evaluation_runner.py` to keep file handle open:

```python
# Open file without context manager so it stays open for subprocess
log_fd = open(log_file, "w", buffering=1)  # Line buffering
process = subprocess.Popen(
    command,
    shell=True,
    stdout=log_fd,
    stderr=subprocess.STDOUT,
    text=True
)
```

**Verification:**
- Start profile from "Evaluation Runner → Profile Run"
- Navigate to "Current Runs" tab
- Elapsed time should update continuously
- Live output should show command output
- Run should persist across page refreshes

### Dashboard timeout on long runs

**Symptoms:**
- "Command timed out after 1 hour"
- Profile runner stops mid-execution

**Solution:**
Use CLI instead of dashboard for long-running profiles:

```bash
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
python scripts/benchmark_profile_runner.py --profiles swebench_ablation
```

Or use tmux for background execution:

```bash
tmux new -s profile_run
# Inside tmux: run the profile
# Detach: Ctrl+b, then d
# Re-attach: tmux attach -t profile_run
```

### Runs disappear on dashboard refresh

**Symptoms:**
- Started run no longer visible after refresh
- Cannot monitor long-running evaluations

**Solution:**
Dashboard now uses persistent tracking with `RunTracker`:
- Run metadata stored in `.dashboard_runs/` directory
- Process PIDs tracked using psutil
- Runs survive dashboard restarts
- Navigate to "Current Runs" tab to see all tracked runs

**Cleanup:**
```bash
# Remove old completed runs (keeps 10 most recent)
# Use "Cleanup Old Runs" button in dashboard
# Or manually: rm -rf .dashboard_runs/*.json
```

## Repository Hygiene

### Status documents appearing in root

- Move to `history/` directory instead
- Update documentation at `history/<filename>`
- Use beads for tracking status
- Check root for: STATUS.md, PROGRESS.md, \*\_STATUS.md files

### AGENTS.md too large

- Break into separate docs in `docs/` directory
- Keep AGENTS.md as quick reference (~500 lines)
- Link to detailed documentation
- Archive old versions to `history/`
