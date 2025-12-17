# Tool Profiles Configuration

Tool profiles define which tools and capabilities are available in different benchmark agent configurations. Each profile represents a different level of code intelligence support.

## Available Profiles

### Profile: `none` (Baseline)
**No code search or intelligence tools**

- **MCP Enabled**: No
- **Tool Count**: 5 tools
- **Use Case**: Baseline Claude Code without any Sourcegraph integration
- **Tools**:
  - `file_read` - Read files (cat, head, tail)
  - `file_write` - Write to files
  - `file_list` - List files/directories (ls, find)
  - `bash_execute` - Execute bash commands
  - `git_operations` - Git operations (diff, log, status)

### Profile: `search_only` (Basic Search)
**File operations + basic code search (no code intelligence)**

- **MCP Enabled**: No
- **Tool Count**: 6 tools
- **Use Case**: Pattern matching and basic grep-like search without semantic understanding
- **Tools**:
  - All from `none` profile, plus:
  - `basic_search` - Pattern matching, grep-style text search

### Profile: `code_intel` (Code Intelligence)
**File operations + search + code intelligence features**

- **MCP Enabled**: Yes
- **Tool Count**: 9 tools
- **Use Case**: Symbol navigation, type-aware search, definition finding
- **Tools**:
  - All from `search_only` profile, plus:
  - `symbol_search` - Find symbol definitions and references
  - `code_navigation` - Jump to definition, find references
  - `semantic_search` - Type-aware, scope-aware code search

### Profile: `deep_search` (Full Deep Search)
**Full Sourcegraph Deep Search integration via MCP server**

- **MCP Enabled**: Yes
- **Tool Count**: 12 tools
- **Use Case**: Advanced codebase understanding with Deep Search context
- **Tools**:
  - All from `code_intel` profile, plus:
  - `sourcegraph_deep_search` - MCP: Advanced Deep Search with context
  - `sourcegraph_context` - MCP: Gather codebase context
  - `sourcegraph_insights` - MCP: Code quality insights

## Tool Hierarchy

Profiles are designed with a progressive hierarchy where each level includes all tools from previous levels:

```
none (5 tools)
  ↓
search_only (6 tools)
  ↓
code_intel (9 tools)
  ↓
deep_search (12 tools)
```

## Using Tool Profiles

### In Code

```python
from configs.tool_profiles import get_profile, list_profiles

# Get a specific profile
profile = get_profile("deep_search")
print(f"Tools: {profile.tools}")
print(f"MCP Enabled: {profile.mcp_enabled}")

# List all profiles
all_profiles = list_profiles()
print(f"Available: {all_profiles}")

# Get profile info
info = get_profile_info("code_intel")
print(f"Tools: {info['tool_count']}")
print(f"Env Vars: {info['environment_vars']}")

# Find MCP-enabled profiles
mcp_profiles = get_mcp_profiles()
print(f"MCP profiles: {mcp_profiles}")
```

### In Harbor Configuration

Update `infrastructure/harbor-config.yaml` to reference tool profiles:

```yaml
agents:
  claude-baseline:
    tool_profile: "none"
    model: claude-3-5-sonnet

  claude-search:
    tool_profile: "search_only"
    model: claude-3-5-sonnet

  claude-code-intel:
    tool_profile: "code_intel"
    model: claude-3-5-sonnet
    mcp_enabled: true

  claude-deep-search:
    tool_profile: "deep_search"
    model: claude-3-5-sonnet
    mcp_enabled: true
```

## Environment Variables

Tool profiles manage environment variables per profile:

| Profile | SRC_ACCESS_TOKEN | SOURCEGRAPH_URL | MCP_CONFIG |
|---------|------------------|-----------------|-----------|
| `none` | (empty) | (empty) | - |
| `search_only` | Required | Required | - |
| `code_intel` | Required | Required | - |
| `deep_search` | Required | Required | Required |

### Variable Expansion

Profile configurations use variable expansion for environment variables:

- `${VAR_NAME}` - Reference environment variable
- `${VAR_NAME:-default}` - Reference with default value

Example:
```python
profile.environment_vars = {
    "SRC_ACCESS_TOKEN": "${SRC_ACCESS_TOKEN}",  # From shell env
    "SOURCEGRAPH_URL": "${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}"  # With default
}
```

## Extending Profiles

To add a new profile:

```python
# In configs/tool_profiles.py
MY_PROFILE = ToolProfile(
    name="my-profile",
    description="My custom tool profile",
    tools=[...],
    environment_vars={...},
    mcp_enabled=True,
)

PROFILES["my-profile"] = MY_PROFILE
```

## Testing Tool Profiles

Run the test suite to validate profiles:

```bash
# Test profile structure and hierarchy
python tests/test_tool_profiles.py -v

# Verify profile configuration
python -m configs.tool_profiles
```

## MCP Configuration

Profiles with `mcp_enabled=True` require MCP server configuration:

1. **MCP Server**: Sourcegraph MCP server must be running
2. **Configuration**: Pass MCP config via environment or Harbor flags
3. **Credentials**: SRC_ACCESS_TOKEN required for authentication

See `infrastructure/PODMAN.md` for MCP setup instructions.

## Design Principles

1. **Progressive Enhancement**: Each profile includes all tools from lower levels
2. **Clear Differentiation**: Each profile targets a specific use case
3. **MCP Separation**: Non-MCP profiles never require MCP setup
4. **Tool Transparency**: Tools list explicitly documents capabilities
5. **Environment Clarity**: Environment variables clearly indicate requirements

## Related Documentation

- **Harbor Configuration**: `infrastructure/harbor-config.yaml`
- **MCP Setup**: `infrastructure/PODMAN.md`
- **Agent Implementation**: `agents/`
- **Observability**: `observability/manifest_writer.py` uses profiles for metrics
