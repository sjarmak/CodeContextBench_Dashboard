# Running SWE-Bench Ablation Study

## Quick Start (Recommended: CLI)

The dashboard has a 1-hour timeout. For SWE-Bench tasks, **use CLI** for better control:

```bash
# Source environment
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

# Run the ablation profile
python scripts/benchmark_profile_runner.py --profiles swebench_ablation
```

This will run all 3 agents (baseline, sourcegraph_mcp, deepsearch_mcp) on the configured tasks.

## What Gets Run

**Profile:** `swebench_ablation` (from `configs/benchmark_profiles.yaml`)

**Agents:**
1. Mini SWE Agent (Baseline) - No MCP
2. Mini SWE Agent + Sourcegraph MCP - Full code intelligence
3. Mini SWE Agent + Deep Search MCP - Semantic search only

**Tasks:** 2 SWE-Bench Pro test tasks:
- `instance_ansible-ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2`
- `instance_flipt-io__flipt-42379dbccb539be2e97aec78e6c28df93b0b3d8e-v6a7a03632a77d6aa36ccc00c3ab1aa2c40a0d6c2`

## Expected Duration

- **Per task per agent:** 10-30 minutes (depends on task complexity)
- **Total for 2 tasks × 3 agents:** ~1-3 hours

## Monitoring Progress

```bash
# Watch output directory
watch -n 5 'ls -lh jobs/benchmark_profiles/swebench_ablation/*/swebench_pro/'

# Check Harbor logs
tail -f jobs/benchmark_profiles/swebench_ablation/*/swebench_pro/*/*/*_harbor.log

# Monitor Docker containers
watch -n 5 'docker ps'
```

## Dry Run First (Recommended)

Preview what will run without executing:

```bash
python scripts/benchmark_profile_runner.py --profiles swebench_ablation --dry-run
```

Output:
```
Dry run complete. Outputs would be staged in:
  - swebench_ablation: jobs/benchmark_profiles/swebench_ablation/20251228-093929
```

## Run in Background (tmux/screen)

For long-running jobs, use tmux:

```bash
# Start tmux session
tmux new -s swe_ablation

# Inside tmux, run the profile
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
python scripts/benchmark_profile_runner.py --profiles swebench_ablation

# Detach: Ctrl+b, then d
# Re-attach later: tmux attach -t swe_ablation
```

## Custom Configuration

Edit `configs/benchmark_profiles.yaml` to change:

```yaml
swebench_ablation:
  description: SWE-Bench Pro MCP ablation study
  benchmarks:
    - id: swebench_pro
      jobs_subdir: swebench_pro
      task_names:
        - instance_ansible-ansible-0ea40e09...  # Add/remove tasks
        - instance_flipt-io__flipt-4237...
      harbor:
        timeout_multiplier: 3.0  # Adjust timeout (3x default)
  agents:
    - name: baseline
      display_name: Mini SWE Agent (Baseline)
      agent_import_path: mini_swe_agent_mcp:MiniSweAgentBaseline
    # Add more agents or remove some
```

## Results Location

Results will be in:
```
jobs/benchmark_profiles/swebench_ablation/<timestamp>/swebench_pro/
├── baseline/
│   ├── <task1>/
│   └── <task2>/
├── sourcegraph_mcp/
│   ├── <task1>/
│   └── <task2>/
└── deepsearch_mcp/
    ├── <task1>/
    └── <task2>/
```

Each task directory contains:
- `<timestamp>/` - Trial results
- `trajectory.json` - Agent actions (ATIF format)
- `reward.txt` - Score/success
- Agent logs

## Analysis

After completion, analyze results:

```bash
# Compare success rates
grep -r "reward" jobs/benchmark_profiles/swebench_ablation/*/swebench_pro/*/

# Check which agent performed best
for agent in baseline sourcegraph_mcp deepsearch_mcp; do
  echo "=== $agent ==="
  find jobs/benchmark_profiles/swebench_ablation/*/swebench_pro/$agent -name "reward.txt" -exec cat {} \;
done
```

## Troubleshooting

### "Command timed out"
**Solution:** Use CLI instead of dashboard. CLI has no timeout.

### "Docker build failed"
**Solution:** SWE-Bench tasks use pre-built images. Check Docker is running and has internet access.

### "ANTHROPIC_API_KEY not set"
**Solution:**
```bash
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL
```

### "Task not found"
**Solution:** Ensure tasks exist:
```bash
ls benchmarks/swebench_pro/tasks/instance_ansible-ansible-0ea40e09...
```

### Agent produces no output
**Solution:** Check agent logs:
```bash
find jobs/benchmark_profiles -name "*_harbor.log" -exec tail -50 {} \;
```

## Single Task Test

Test one agent on one task first:

```bash
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

harbor trials start \
  --path benchmarks/swebench_pro/tasks/instance_ansible-ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2 \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentBaseline \
  --model anthropic/claude-haiku-4-5-20251001
```

If this works, the full ablation should work too.
