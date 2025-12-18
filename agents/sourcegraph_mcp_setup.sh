#!/bin/bash
# Sourcegraph MCP setup helper for task Dockerfiles
#
# Usage in Dockerfile:
#   COPY agents/sourcegraph_mcp_setup.sh /tmp/
#   RUN /tmp/sourcegraph_mcp_setup.sh
#
# This creates .mcp.json in /workspace with Sourcegraph MCP configuration
# Claude Code automatically discovers and uses this configuration

set -e

# Get configuration from environment variables
MCP_URL="${SOURCEGRAPH_MCP_URL:-}"
MCP_TOKEN="${SOURCEGRAPH_ACCESS_TOKEN:-}"

# If either is missing, silently skip (MCP not configured)
if [ -z "$MCP_URL" ] || [ -z "$MCP_TOKEN" ]; then
    echo "ℹ️  Sourcegraph MCP not configured (SOURCEGRAPH_MCP_URL or SOURCEGRAPH_ACCESS_TOKEN missing)"
    exit 0
fi

# Create /workspace if it doesn't exist
mkdir -p /workspace

# Write .mcp.json configuration
cat > /workspace/.mcp.json <<EOF
{
  "mcpServers": {
    "sourcegraph": {
      "type": "http",
      "url": "$MCP_URL",
      "headers": {
        "Authorization": "token $MCP_TOKEN"
      }
    }
  }
}
EOF

echo "✓ Created /workspace/.mcp.json for Sourcegraph MCP integration"
