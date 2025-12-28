# MCP Setup Verification Results

## ✅ Tests Passed

All setup tests completed successfully! Here's what was verified:

### Test 1: Baseline Agent (No MCP)
- ✅ Agent loads correctly
- ✅ No MCP servers configured
- ✅ Generates 1 command (just mini-swe-agent)

### Test 2: Sourcegraph MCP Agent
- ✅ Agent loads with MCP configuration
- ✅ MCP servers: `sourcegraph`
- ✅ Generates 3 commands:
  1. Create MCP config file
  2. Log MCP setup
  3. Run mini-swe-agent

### Test 3: Deep Search MCP Agent
- ✅ Agent loads with MCP configuration
- ✅ MCP servers: `deepsearch`
- ✅ Generates 3 commands (same pattern as Sourcegraph)

### Test 4: JSON Parsing (CLI Simulation)
- ✅ Correctly parses JSON strings from `--agent-kwarg`
- ✅ Works as expected for command-line usage

## 📊 Configuration Comparison

| Configuration | Commands Generated | MCP Servers | Additional Setup |
|--------------|-------------------|-------------|------------------|
| **Baseline** | 1 | None | No |
| **Sourcegraph MCP** | 3 | sourcegraph | Yes (config + log) |
| **Deep Search MCP** | 3 | deepsearch | Yes (config + log) |

## ⚠️ Important Note: MCP Integration Status

**Current Status**: The agent wrapper is fully functional and correctly generates MCP configurations, BUT:

1. **mini-swe-agent doesn't natively support MCP yet** (as of Dec 2025)
2. The wrapper **prepares MCP configuration** in `/logs/agent/mcp_config.json`
3. The configuration is **ready for when mini-swe-agent adds MCP support**

### What Works Now
- ✅ Agent configuration and selection
- ✅ MCP server configuration parsing
- ✅ MCP config file generation
- ✅ All three configurations (baseline, Sourcegraph, Deep Search) load correctly
- ✅ Command generation works as expected

### What Needs mini-swe-agent MCP Support
- ⏳ Actually passing MCP context to the LLM
- ⏳ Using Sourcegraph for code search
- ⏳ Using Deep Search for web searches

### Workarounds (until native MCP support)

**Option 1**: Patch mini-swe-agent locally
```python
# In mini-swe-agent's main loop, check for MCP config
if mcp_config_path := os.getenv("MINI_SWE_AGENT_MCP_CONFIG"):
    # Load and use MCP servers
    pass
```

**Option 2**: Use a different agent that already supports MCP
- Try with `claude-code` agent (already has MCP support)
- Or wrap another MCP-compatible agent

**Option 3**: Wait for mini-swe-agent MCP support
- The wrapper is ready to use once support is added
- Just update mini-swe-agent version when available

## 🚀 Usage for Ablation Studies

Even without native MCP support in mini-swe-agent yet, you can:

### 1. Test the Setup
```bash
source .env.local && export ANTHROPIC_API_KEY
cd ~/harbor && uv run python /Users/sjarmak/code-intel-digest/test_mcp_setup.py
```

### 2. Compare Agent Configurations
```bash
# Baseline (what you have now)
harbor trials start \
  --agent mini-swe-agent \
  -m anthropic/claude-sonnet-4 \
  -p path/to/task

# With MCP wrapper (ready for future MCP support)
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/task \
  --agent-kwarg 'mcp_servers={"sourcegraph":{"command":"npx","args":["-y","@sourcegraph/cody"]}}'
```

### 3. Analyze Trajectories (When MCP is supported)

The agent generates ATIF-formatted trajectories with:
- **Tool use**: Which tools were called and how many times
- **Token usage**: Prompt tokens, completion tokens, cached tokens
- **Timing**: Time between actions, total time
- **Cost**: Total cost in USD

To analyze:
```python
import json

# Load trajectory
with open("trials/baseline-test/agent/trajectory.json") as f:
    trajectory = json.load(f)

# Get metrics
final_metrics = trajectory["final_metrics"]
print(f"Total prompt tokens: {final_metrics['total_prompt_tokens']}")
print(f"Total completion tokens: {final_metrics['total_completion_tokens']}")
print(f"Total cost: ${final_metrics['total_cost_usd']}")
print(f"Total steps: {final_metrics['total_steps']}")

# Analyze tool usage
tool_counts = {}
for step in trajectory["steps"]:
    if step.get("tool_calls"):
        for tool_call in step["tool_calls"]:
            tool_name = tool_call["function_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

print("\nTool usage:")
for tool, count in sorted(tool_counts.items()):
    print(f"  {tool}: {count}")

# Time analysis
import datetime
step_times = []
for i, step in enumerate(trajectory["steps"]):
    if i > 0:
        prev_time = datetime.datetime.fromisoformat(trajectory["steps"][i-1]["timestamp"])
        curr_time = datetime.datetime.fromisoformat(step["timestamp"])
        delta = (curr_time - prev_time).total_seconds()
        step_times.append(delta)

if step_times:
    print(f"\nAverage time between steps: {sum(step_times)/len(step_times):.2f}s")
    print(f"Max time between steps: {max(step_times):.2f}s")
    print(f"Min time between steps: {min(step_times):.2f}s")
```

## 📁 Generated Artifacts

When you run trials, you'll find:

```
trials/
└── baseline-test/
    ├── agent/
    │   ├── mini-swe-agent.trajectory.json  # Mini-swe-agent format
    │   ├── trajectory.json                 # ATIF format (for analysis)
    │   ├── mcp_config.json                 # MCP configuration (if MCP enabled)
    │   ├── mcp-setup.txt                   # MCP setup log
    │   └── install.sh                      # Agent installation script
    ├── environment/
    │   └── ...                             # Docker environment files
    └── result.json                         # Trial result summary
```

## 🔍 Metrics You Can Extract

### From `trajectory.json` (ATIF format):

1. **Token Usage**:
   - `final_metrics.total_prompt_tokens`
   - `final_metrics.total_completion_tokens`
   - `final_metrics.total_cached_tokens`

2. **Cost**:
   - `final_metrics.total_cost_usd`

3. **Tool Usage**:
   - Count of each `tool_calls[].function_name` across all steps
   - Tool call arguments and results

4. **Timing**:
   - Parse `timestamp` field from each step
   - Calculate time between actions
   - Total time: first step to last step

5. **Model Info**:
   - `agent.model_name`
   - `agent.version`

6. **Success/Failure**:
   - Check `verifier_result` in `result.json`
   - Check if task was completed successfully

## 📈 Example Ablation Comparison

Once MCP support is added (or if using a different MCP-capable agent):

| Metric | Baseline | + Sourcegraph | + Deep Search |
|--------|----------|---------------|---------------|
| **Total Tokens** | 10,500 | 12,300 (+17%) | 11,800 (+12%) |
| **Cached Tokens** | 2,100 | 3,500 (+67%) | 2,800 (+33%) |
| **Tool Calls** | 15 | 22 (+47%) | 18 (+20%) |
| **Total Time** | 45s | 52s (+16%) | 48s (+7%) |
| **Cost (USD)** | $0.12 | $0.15 (+25%) | $0.14 (+17%) |
| **Success Rate** | 65% | 78% (+13pp) | 72% (+7pp) |

## ✅ Next Steps

1. **Option A: Use with MCP-capable agent**
   ```bash
   # Use claude-code which already supports MCP
   harbor trials start --agent claude-code ...
   ```

2. **Option B: Patch mini-swe-agent**
   - Fork mini-swe-agent
   - Add MCP support
   - Update the wrapper to use your fork

3. **Option C: Wait and prepare**
   - Monitor mini-swe-agent repo for MCP support
   - Your setup is ready to use immediately when it's added
   - All configurations are tested and working

## 🎯 Current Verification Status

✅ **Setup Complete**: Agent wrapper is functional and ready
✅ **Tests Passing**: All three configurations verified
✅ **Config Format**: MCP configurations parse and generate correctly
⏳ **MCP Support**: Waiting for mini-swe-agent to add MCP support
✅ **Ready for Benchmarks**: Can run comparisons once MCP is supported

The infrastructure is in place for clean ablation studies comparing:
- Baseline vs Sourcegraph MCP vs Deep Search MCP
- All using the same underlying agent
- Easy to compare metrics from generated trajectories
