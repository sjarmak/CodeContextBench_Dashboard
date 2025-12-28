# SWE-Bench MCP Ablation Study Configurations

This directory contains configurations for running ablation studies on SWE-bench tasks
with and without MCP (Model Context Protocol) servers.

## Configurations

### 1. Baseline (No MCP)
- **File**: `baseline.yaml`
- **Description**: Pure mini-swe-agent with no additional context
- **Use case**: Baseline performance measurement

### 2. Sourcegraph MCP
- **File**: `sourcegraph_mcp.yaml`
- **Description**: Mini-swe-agent with Sourcegraph code search context
- **Use case**: Measure impact of code search on SWE-bench performance

### 3. Deep Search MCP
- **File**: `deepsearch_mcp.yaml`
- **Description**: Mini-swe-agent with web search capabilities
- **Use case**: Measure impact of documentation/web search on performance

## Usage

### Command-Line (Quick Tests)

```bash
# Baseline (no MCP)
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/swe-bench-task

# With Sourcegraph MCP
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/swe-bench-task \
  --agent-kwarg 'mcp_servers={"sourcegraph":{"command":"npx","args":["-y","@sourcegraph/cody"]}}'

# With Deep Search MCP
harbor trials start \
  --agent-import-path mini_swe_agent_mcp:MiniSweAgentMCP \
  -m anthropic/claude-sonnet-4 \
  -p path/to/swe-bench-task \
  --agent-kwarg 'mcp_servers={"deepsearch":{"command":"uvx","args":["mcp-server-fetch"]}}'
```

### Using Config Files (Recommended for Benchmarks)

```bash
# Baseline
harbor trials start -c swe_bench_configs/baseline.yaml -p path/to/task

# Sourcegraph MCP
export SOURCEGRAPH_ENDPOINT="https://sourcegraph.com"
export SOURCEGRAPH_TOKEN="your-token"
harbor trials start -c swe_bench_configs/sourcegraph_mcp.yaml -p path/to/task

# Deep Search MCP
harbor trials start -c swe_bench_configs/deepsearch_mcp.yaml -p path/to/task
```

### Running Full Benchmark Sweeps

For SWE-bench Verified or Pro:

```bash
# Run all three configurations on a dataset
for config in baseline sourcegraph_mcp deepsearch_mcp; do
  harbor sweeps run \
    --config swe_bench_configs/${config}.yaml \
    --dataset path/to/swe-bench-verified \
    --trials-dir trials/${config}
done
```

## Ablation Study Analysis

After running trials, compare results:

```bash
# View baseline results
harbor trials list --trials-dir trials/baseline

# View Sourcegraph MCP results
harbor trials list --trials-dir trials/sourcegraph_mcp

# View Deep Search MCP results
harbor trials list --trials-dir trials/deepsearch_mcp
```

## Environment Setup

### Sourcegraph MCP
Requires Sourcegraph access token:
```bash
export SOURCEGRAPH_ENDPOINT="https://sourcegraph.com"
export SOURCEGRAPH_TOKEN="sgp_your_token_here"
```

### Deep Search MCP
Install the MCP server:
```bash
uvx mcp-server-fetch
```

## MCP Server Configuration Format

MCP servers are configured in the agent kwargs as:

```yaml
agent:
  kwargs:
    mcp_servers:
      server_name:
        command: "executable"
        args:
          - "arg1"
          - "arg2"
        env:  # optional
          VAR_NAME: "value"
```

Or via command line:
```bash
--agent-kwarg 'mcp_servers={"server_name":{"command":"cmd","args":["arg1"]}}'
```

## Notes

- The baseline configuration is identical to regular mini-swe-agent
- MCP servers run in the agent environment and provide additional context
- Results can be compared to measure the impact of different context sources
- All configurations use the same underlying mini-swe-agent implementation
