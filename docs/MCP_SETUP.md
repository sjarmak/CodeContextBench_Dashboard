# Sourcegraph MCP Setup for Claude Code Agent

⚠️ **DEPRECATED** - See [agents/README.md](../agents/README.md) for current agent configuration and setup instructions.

**Note:** This document is kept for reference/history only. MCP agent setup is now documented in `agents/README.md`.

---

This guide explains how to configure the Claude Code agent with Sourcegraph Deep Search via MCP (Model Context Protocol) for use in Harbor benchmarks.

## Overview

The `ClaudeCodeSourcegraphMCPAgent` extends Harbor's built-in `ClaudeCode` agent to add Sourcegraph MCP server configuration. This allows Claude to access Deep Search queries during task execution.

## Prerequisites

1. **Sourcegraph Instance**: Access to a Sourcegraph instance (SaaS at sourcegraph.com or self-hosted)
2. **Access Token**: A personal or bot token from your Sourcegraph instance
3. **Claude API Key**: Anthropic API key for Claude model access
4. **Harbor Installation**: CodeContextBench with Harbor available via `uv run harbor`

## Setup Steps

### 1. Get Sourcegraph Credentials

**For Sourcegraph.com (SaaS):**
1. Go to https://sourcegraph.sourcegraph.com
2. Click your avatar → Settings → Access tokens
3. Create a new token with appropriate scopes
4. Copy the token value

**For Self-Hosted Sourcegraph:**
1. Navigate to your instance's Settings → Access tokens
2. Create a new token
3. Copy the token value

### 2. Set Environment Variables

```bash
# Required environment variables
export ANTHROPIC_API_KEY="your-anthropic-key-here"
export SOURCEGRAPH_INSTANCE="sourcegraph.com"  # Without https://
export SOURCEGRAPH_ACCESS_TOKEN="your-token-here"

# Optional: if using self-hosted Sourcegraph
export SOURCEGRAPH_INSTANCE="your-instance.com"
```

### 3. Create Harbor Configuration

Use the provided example or create your own:

```bash
# Use the example configuration
cp harbor-config-mcp-example.json harbor-config.json

# Or create custom config for your benchmark
```

Example `harbor-config.json`:

```json
{
  "environment": {
    "type": "docker"
  },
  "agents": [
    {
      "import_path": "agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent",
      "model_name": "anthropic/claude-3-5-sonnet-20241022",
      "name": "claude-mcp"
    }
  ],
  "datasets": [
    {
      "path": "benchmarks/github_mined",
      "filter": {
        "task_names": ["sgt-001"]
      }
    }
  ],
  "execution": {
    "timeout_seconds": 600,
    "max_retries": 1
  }
}
```

### 4. Run Harbor with MCP Agent

```bash
# Run with your configuration
uv run harbor jobs start --config harbor-config.json

# Or specify agent on command line
harbor run \
  --path benchmarks/github_mined \
  --agent-import-path agents.claude_sourcegraph_mcp_agent:ClaudeCodeSourcegraphMCPAgent \
  --model anthropic/claude-3-5-sonnet-20241022 \
  -n 1 \
  --task-name sgt-001
```

## How It Works

### Setup Phase

When the agent initializes:

1. **Environment Check**: Reads `SOURCEGRAPH_INSTANCE` and `SOURCEGRAPH_ACCESS_TOKEN`
2. **MCP Config Creation**: Generates `.mcp.json` with HTTP server configuration
3. **File Upload**: Uploads config to task container at `/app/.mcp.json`
4. **Logging**: Confirms setup success (or warns if credentials missing)

### MCP Configuration

The agent creates an HTTP-based MCP server configuration:

```json
{
  "mcpServers": {
    "sourcegraph": {
      "type": "http",
      "url": "https://sourcegraph.com/.api/mcp/v1",
      "headers": {
        "Authorization": "token YOUR_TOKEN_HERE"
      }
    }
  }
}
```

Claude uses this configuration to:
- Make authenticated requests to Sourcegraph
- Perform Deep Search queries
- Access codebase analysis tools

## Verification

### 1. Check Agent Loads

```bash
python -c "from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent; print('✓ Agent loaded')"
```

### 2. Validate Setup

```bash
# Check that credentials are set
echo "Instance: $SOURCEGRAPH_INSTANCE"
echo "Token: ${SOURCEGRAPH_ACCESS_TOKEN:0:10}..."  # Show first 10 chars
```

### 3. Test Full Pipeline

```bash
# Run validation script
python runners/validate_benchmark_setup.py
```

## Troubleshooting

### "Sourcegraph MCP not configured" Warning

**Cause**: Missing environment variables  
**Solution**: 
```bash
export SOURCEGRAPH_INSTANCE="sourcegraph.com"
export SOURCEGRAPH_ACCESS_TOKEN="your-token"
```

### "Authorization failed" Errors During Execution

**Cause**: Invalid token or wrong instance  
**Solution**:
1. Verify token is valid in Sourcegraph settings
2. Check instance URL doesn't have `https://` prefix
3. Verify token has appropriate scopes

### MCP Server Connection Errors

**Cause**: Network issues or MCP server unavailable  
**Solution**:
1. Verify internet connectivity
2. Test token manually: `curl -H "Authorization: token $SOURCEGRAPH_ACCESS_TOKEN" https://sourcegraph.com/.api/mcp/v1`
3. Check Sourcegraph instance status

### Agent Not Using Deep Search

**Cause**: Agent not instructed to use Deep Search  
**Solution**: Ensure task instructions or system prompt mentions Deep Search capabilities

## Implementation Details

### File Structure

```
agents/
├── __init__.py                              # Package initialization
├── claude_sourcegraph_mcp_agent.py         # MCP agent implementation
└── claude_code_mcp.py                      # Legacy MCP implementation
```

### Agent Class

**Class**: `ClaudeCodeSourcegraphMCPAgent`  
**Base**: `harbor.agents.installed.claude_code.ClaudeCode`  
**Location**: `agents/claude_sourcegraph_mcp_agent.py`

**Key Method**: `setup(environment: BaseEnvironment) -> None`
- Reads Sourcegraph credentials from environment
- Creates MCP configuration file
- Uploads config to task container
- Calls parent class setup

### Configuration Flow

```
Environment Variables
    ↓
setup() method
    ↓
Generate .mcp.json
    ↓
Upload to Container
    ↓
Claude Ready for Deep Search
```

## Advanced Configuration

### Multiple MCP Servers

To add additional MCP servers (e.g., GitHub), modify the agent:

```python
# In setup() method, expand mcpServers:
mcp_config = {
    "mcpServers": {
        "sourcegraph": {
            "type": "http",
            "url": f"https://{sg_instance}/.api/mcp/v1",
            "headers": {"Authorization": f"token {sg_token}"}
        },
        "github": {
            "type": "http",
            "url": "https://api.github.com/mcp/v1",
            "headers": {"Authorization": f"token {os.environ.get('GITHUB_TOKEN')}"}
        }
    }
}
```

### Custom MCP Configuration

To use a custom MCP setup, create a subclass:

```python
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent

class CustomMCPAgent(ClaudeCodeSourcegraphMCPAgent):
    async def setup(self, environment: BaseEnvironment) -> None:
        # Custom MCP config logic
        await super().setup(environment)
```

## Best Practices

1. **Rotate Tokens Regularly**: Change access tokens periodically for security
2. **Use Bot Tokens**: Create dedicated bot tokens for CI/automation
3. **Limit Scopes**: Give tokens minimum required permissions
4. **Monitor Usage**: Check Sourcegraph audit logs for agent access
5. **Handle Errors Gracefully**: Agent logs warnings if MCP not configured but continues
6. **Test Before Production**: Run single-task validation before full benchmarks

## See Also

- [Harbor Agent Documentation](ARCHITECTURE.md#agents)
- [Sourcegraph MCP Protocol](https://sourcegraph.com/docs/mcp)
- [Deep Search Documentation](https://sourcegraph.com/docs/cody#deep-search)
- [CodeContextBench Benchmarking Guide](BENCHMARKING_GUIDE.md)
