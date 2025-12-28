# MCP Baseline Setup for CodeContextBench

## ✅ Setup Complete

The MCP ablation study framework is now set up in CodeContextBench and ready for SWE-bench testing.

## 📁 Files Added

```
CodeContextBench/
├── mini_swe_agent_mcp.py              # MCP-enabled agent wrapper
├── test_mcp_setup.py                  # Verification script
├── swe_bench_configs/
│   ├── baseline.yaml                  # No MCP configuration
│   ├── sourcegraph_mcp.yaml           # Sourcegraph code search
│   ├── deepsearch_mcp.yaml            # Web search
│   └── README.md                      # Configuration docs
├── MCP_ABLATION_SETUP.md              # Usage guide
├── MCP_SETUP_VERIFICATION.md          # Verification results
└── MCP_BASELINE_SETUP_SUMMARY.md      # This file
```

## 🎯 What This Enables

You can now run SWE-bench evaluations with three configurations:

1. **Baseline** - mini-swe-agent with no additional context
2. **Sourcegraph MCP** - mini-swe-agent + code search context
3. **Deep Search MCP** - mini-swe-agent + web search context

This allows clean ablation studies to measure the impact of MCP on SWE-bench performance.

## 🚀 Quick Start

### 1. Verify Setup

```bash
cd ~/CodeContextBench
source .env.local && export ANTHROPIC_API_KEY
cd ~/harbor && ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" uv run python ~/CodeContextBench/test_mcp_setup.py
```

**Expected output**: `✅ ALL TESTS PASSED!`

### 2. Run Baseline Test

```bash
cd ~/CodeContextBench
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/swe-bench/task \
  --trials-dir results/baseline
```

### 3. Run with Sourcegraph MCP

```bash
export SOURCEGRAPH_ENDPOINT="https://sourcegraph.com"
export SOURCEGRAPH_TOKEN="your_token"

harbor trials start \
  -c swe_bench_configs/sourcegraph_mcp.yaml \
  -p path/to/swe-bench/task \
  --trials-dir results/sourcegraph-mcp
```

### 4. Run with Deep Search MCP

```bash
harbor trials start \
  -c swe_bench_configs/deepsearch_mcp.yaml \
  -p path/to/swe-bench/task \
  --trials-dir results/deepsearch-mcp
```

## 📊 Metrics Collection

All trials generate ATIF-formatted trajectories with:

- **Token Usage**: Prompt tokens, completion tokens, cached tokens
- **Tool Use**: Count and type of tools called
- **Timing**: Time between actions, total time
- **Cost**: Total cost in USD
- **Success**: Whether the task passed verification

### Example: Extract Metrics

```python
import json
from pathlib import Path

trial_dir = Path("results/baseline/test-trial")
trajectory_path = trial_dir / "agent" / "trajectory.json"

with open(trajectory_path) as f:
    traj = json.load(f)

# Get final metrics
metrics = traj["final_metrics"]
print(f"Total tokens: {metrics['total_prompt_tokens'] + metrics['total_completion_tokens']}")
print(f"Cached tokens: {metrics['total_cached_tokens']}")
print(f"Cost: ${metrics['total_cost_usd']:.3f}")
print(f"Steps: {metrics['total_steps']}")

# Tool usage
tools = {}
for step in traj["steps"]:
    for tool_call in step.get("tool_calls", []):
        name = tool_call["function_name"]
        tools[name] = tools.get(name, 0) + 1

print("\nTool usage:")
for tool, count in sorted(tools.items()):
    print(f"  {tool}: {count}")
```

## ⚠️ Current Limitation

**Note**: mini-swe-agent doesn't have native MCP support yet (as of Dec 2025).

The setup:
- ✅ Correctly generates MCP configurations
- ✅ Prepares config files for MCP servers
- ⏳ Waits for mini-swe-agent to add MCP support

**Workaround options**:
1. Use `claude-code` agent (already has MCP)
2. Patch mini-swe-agent locally to add MCP support
3. Wait for official MCP support in mini-swe-agent

## 📈 Running Full Benchmarks

### SWE-bench Verified

```bash
cd ~/CodeContextBench

# Run all three configurations
for config in baseline sourcegraph_mcp deepsearch_mcp; do
  echo "Running ${config}..."
  harbor sweeps run \
    --config swe_bench_configs/${config}.yaml \
    --dataset path/to/swe-bench-verified \
    --trials-dir results/swe-bench-verified/${config}
done
```

### Compare Results

```bash
# View results
harbor trials list --trials-dir results/swe-bench-verified/baseline
harbor trials list --trials-dir results/swe-bench-verified/sourcegraph_mcp
harbor trials list --trials-dir results/swe-bench-verified/deepsearch_mcp

# Export for analysis
harbor traces export --trials-dir results/swe-bench-verified/baseline
```

## 🔍 Verification Status

✅ **Tests Passed**: All 4 verification tests passing
✅ **Configurations Ready**: Baseline, Sourcegraph MCP, Deep Search MCP
✅ **Metrics Collection**: ATIF trajectories with full metrics
✅ **CLI Integration**: Works with `--agent-import-path`
✅ **YAML Configs**: Ready-to-use config files

## 📝 Next Actions

1. **Choose your approach**:
   - Wait for mini-swe-agent MCP support (setup ready)
   - Use claude-code agent (has MCP now)
   - Patch mini-swe-agent locally

2. **Run baseline tests** to establish performance

3. **Run MCP variants** once support is available

4. **Analyze trajectories** to compare:
   - Token usage (with/without MCP)
   - Tool call patterns
   - Success rates
   - Costs

## 🎓 Documentation

- **MCP_ABLATION_SETUP.md** - Complete usage guide
- **MCP_SETUP_VERIFICATION.md** - Test results and metrics
- **swe_bench_configs/README.md** - Configuration details

## ✨ Key Benefits

1. **Clean ablation studies** - Same agent, just +/- MCP
2. **No harbor modifications** - Uses `--agent-import-path`
3. **Comprehensive metrics** - Full ATIF trajectories
4. **Ready for benchmarks** - Config files prepared
5. **Easy to extend** - Add more MCP servers easily

The infrastructure is in place for rigorous comparison of MCP impact on SWE-bench performance!
