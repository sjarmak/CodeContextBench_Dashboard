# Troubleshooting Guide

## Agent Issues

### Agent fails to initialize
- Check `ANTHROPIC_API_KEY` environment variable is set
- For Claude+MCP: verify `SRC_ACCESS_TOKEN` is set
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

## Repository Hygiene

### Status documents appearing in root
- Move to `history/` directory instead
- Update documentation at `history/<filename>`
- Use beads for tracking status
- Check root for: STATUS.md, PROGRESS.md, *_STATUS.md files

### AGENTS.md too large
- Break into separate docs in `docs/` directory
- Keep AGENTS.md as quick reference (~500 lines)
- Link to detailed documentation
- Archive old versions to `history/`
