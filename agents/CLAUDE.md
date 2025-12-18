# Claude Code Integration Guide

## Sourcegraph MCP Available

When using `ClaudeCodeSourcegraphMCPAgent`, Sourcegraph Deep Search is available via Model Context Protocol (MCP).

### Using Sourcegraph Deep Search

For code understanding and context gathering, use the `deep_search` tool:

```
Use the deep_search tool to understand the codebase structure:
- Query for function/class definitions
- Find usage patterns
- Understand module relationships
- Locate test files and examples
```

### Example Queries

For understanding code before making changes:
- "Find the definition of [function_name] and show how it's used"
- "What modules import [module_name]?"
- "Find all test files for [module_name]"
- "Where is [constant_name] defined and what references it?"

### Benefits

- Faster codebase comprehension
- Better accuracy for cross-file changes
- Understanding of test patterns
- Discovery of related code

## Running Tasks with Harbor + MCP

To run tasks with Sourcegraph MCP integration using Harbor:

### Setup

1. **Ensure environment variables are set:**
   ```bash
   export ANTHROPIC_API_KEY="your-anthropic-key"
   export SOURCEGRAPH_ACCESS_TOKEN="sgp_your-sourcegraph-token"
   export SOURCEGRAPH_MCP_URL="https://sourcegraph.sourcegraph.com/.api/mcp/v1"
   ```

2. **Activate Harbor environment:**
   ```bash
   source .venv-harbor/bin/activate
   source infrastructure/load-env.sh
   ```

### Running Tasks

Use the `ClaudeCodeSourcegraphMCPAgent` with Harbor:

```bash
harbor run \
  --path benchmarks/github_mined_pilot/sgt-002 \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 \
  --env daytona \
  --ek SOURCEGRAPH_ACCESS_TOKEN="$SOURCEGRAPH_ACCESS_TOKEN" \
  --ek SOURCEGRAPH_MCP_URL="$SOURCEGRAPH_MCP_URL" \
  --jobs-dir jobs/mcp-test
```

### How It Works

1. Agent receives `SOURCEGRAPH_ACCESS_TOKEN` and `SOURCEGRAPH_MCP_URL` via `--ek` flags
2. Before Claude Code starts, agent creates `/workspace/.mcp.json` with MCP configuration
3. Claude Code auto-discovers .mcp.json on startup
4. MCP guidance is prepended to task instructions
5. Claude can use Sourcegraph Deep Search for code understanding

### Example Task Execution

Tasks include full repository context. The agent will:
1. Use Deep Search to understand codebase structure
2. Read files to examine implementations
3. Make targeted changes based on understanding
4. Test changes against task requirements

### Comparing Baseline vs. MCP

Run both agents to compare performance:

```bash
# Baseline (no Sourcegraph)
harbor run --path benchmarks/github_mined_pilot/sgt-002 \
  --agent claude-code \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 --env daytona \
  --jobs-dir jobs/baseline

# MCP-enabled
harbor run --path benchmarks/github_mined_pilot/sgt-002 \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 --env daytona \
  --ek SOURCEGRAPH_ACCESS_TOKEN="$SOURCEGRAPH_ACCESS_TOKEN" \
  --ek SOURCEGRAPH_MCP_URL="$SOURCEGRAPH_MCP_URL" \
  --jobs-dir jobs/mcp-enabled
```
