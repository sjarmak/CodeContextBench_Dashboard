# Mini SWE Agent MCP Ablation Study Setup

This setup allows you to run SWE-bench evaluations with mini-swe-agent in three configurations:
1. **Baseline** - No MCP (pure mini-swe-agent)
2. **Sourcegraph MCP** - With code search context
3. **Deep Search MCP** - With web search context

## Quick Start

### 1. Setup

The `mini_swe_agent_mcp.py` file in this directory provides an MCP-enabled wrapper around mini-swe-agent. It works with your existing uv-installed harbor - no custom harbor installation needed!

```bash
# Verify the agent loads correctly
cd ~/harbor
uv run python -c "
import sys
sys.path.insert(0, '/Users/sjarmak/code-intel-digest')
import mini_swe_agent_mcp
print('✓ Agent ready')
"
```

### 2. Run Baseline (No MCP)

```bash
cd /Users/sjarmak/code-intel-digest

# Using config file (recommended)
harbor trials start \
  -c swe_bench_configs/baseline.yaml \
  -p path/to/swe-bench/task

# Or via command line
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/swe-bench/task
```

### 3. Run with Sourcegraph MCP

```bash
# Set up Sourcegraph credentials
export SOURCEGRAPH_ENDPOINT="https://sourcegraph.com"
export SOURCEGRAPH_TOKEN="your_token"

# Run
harbor trials start \
  -c swe_bench_configs/sourcegraph_mcp.yaml \
  -p path/to/swe-bench/task
```

### 4. Run with Deep Search MCP

```bash
harbor trials start \
  -c swe_bench_configs/deepsearch_mcp.yaml \
  -p path/to/swe-bench/task
```

## Running Full Benchmarks

### SWE-bench Verified

```bash
# Directory structure
cd /Users/sjarmak/code-intel-digest

# Run all three configurations
for config in baseline sourcegraph_mcp deepsearch_mcp; do
  echo "Running ${config}..."
  harbor sweeps run \
    --config swe_bench_configs/${config}.yaml \
    --dataset path/to/swe-bench-verified \
    --trials-dir trials/swe-bench-verified/${config}
done
```

### SWE-bench Pro

```bash
for config in baseline sourcegraph_mcp deepsearch_mcp; do
  echo "Running ${config} on SWE-bench Pro..."
  harbor sweeps run \
    --config swe_bench_configs/${config}.yaml \
    --dataset path/to/swe-bench-pro \
    --trials-dir trials/swe-bench-pro/${config}
done
```

## How It Works

1. **Agent Import Path**: Harbor's `--agent-import-path` feature loads the custom agent from `mini_swe_agent_mcp.py` without modifying harbor itself

2. **MCP Configuration**: MCP servers are passed via agent kwargs:
   - From CLI: `--agent-kwarg 'mcp_servers={"name":{"command":"..."}}'`
   - From YAML: Under `agent.kwargs.mcp_servers`

3. **Ablation Studies**: Same agent code, just with/without MCP configuration makes for clean comparisons

## File Structure

```
code-intel-digest/
├── mini_swe_agent_mcp.py          # Custom agent with MCP support
├── swe_bench_configs/
│   ├── baseline.yaml              # No MCP configuration
│   ├── sourcegraph_mcp.yaml       # Sourcegraph code search
│   ├── deepsearch_mcp.yaml        # Web search
│   └── README.md                  # Detailed config docs
└── trials/                         # Results will go here
    ├── swe-bench-verified/
    │   ├── baseline/
    │   ├── sourcegraph_mcp/
    │   └── deepsearch_mcp/
    └── swe-bench-pro/
        ├── baseline/
        ├── sourcegraph_mcp/
        └── deepsearch_mcp/
```

## Customizing MCP Servers

Add your own MCP server by editing the YAML config or using `--agent-kwarg`:

```yaml
agent:
  kwargs:
    mcp_servers:
      my_custom_mcp:
        command: "path/to/mcp-server"
        args:
          - "--option"
          - "value"
        env:
          API_KEY: "${MY_API_KEY}"
```

Or via CLI:
```bash
--agent-kwarg 'mcp_servers={"custom":{"command":"mcp-server","args":["--opt"]}}'
```

## MCP Servers Reference

### Sourcegraph
- **Command**: `npx -y @sourcegraph/cody-context-filters-mcp`
- **Provides**: Code search, repository context, symbol lookup
- **Setup**: Requires `SOURCEGRAPH_ENDPOINT` and `SOURCEGRAPH_TOKEN`

### Deep Search (mcp-server-fetch)
- **Command**: `uvx mcp-server-fetch`
- **Provides**: Web search, documentation lookup
- **Setup**: May require API keys depending on search backend

## Analyzing Results

```bash
# Compare baseline vs MCP configurations
harbor trials list --trials-dir trials/swe-bench-verified/baseline
harbor trials list --trials-dir trials/swe-bench-verified/sourcegraph_mcp
harbor trials list --trials-dir trials/swe-bench-verified/deepsearch_mcp

# Export for analysis
harbor traces export --trials-dir trials/swe-bench-verified/baseline
```

## Troubleshooting

### "Module not found: harbor"
Make sure you're running harbor from the uv environment:
```bash
cd ~/harbor
uv run harbor trials start ...
```

Or ensure the agent file is in your working directory:
```bash
cd /Users/sjarmak/code-intel-digest
harbor trials start --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP ...
```

### "Invalid mcp_servers JSON"
Check your JSON syntax in `--agent-kwarg`. Use single quotes around the JSON and escape inner quotes properly:
```bash
--agent-kwarg 'mcp_servers={"name":{"command":"cmd"}}'
```

### MCP Server Not Starting
Check logs in `trials/<trial-name>/agent/mcp-setup.txt` to see which MCP servers were configured.

## Notes

- **Baseline is identical to regular mini-swe-agent** - passing no `mcp_servers` kwarg makes it behave exactly like the original
- **Clean ablation comparisons** - Same agent, same model, only MCP configuration differs
- **No harbor modification needed** - Uses `--agent-import-path` to load custom agent
- **Future-proof** - When mini-swe-agent adds native MCP support, this wrapper can be updated easily
