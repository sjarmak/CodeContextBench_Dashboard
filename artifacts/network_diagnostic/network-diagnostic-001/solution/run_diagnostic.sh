#!/bin/bash
# Network diagnostic script for Sourcegraph MCP connectivity

echo "=== Network Diagnostic Results ==="
echo ""

echo "1. DNS Resolution Test:"
nslookup sourcegraph.sourcegraph.com || echo "DNS resolution failed"
echo ""

echo "2. HTTPS Connectivity Test:"
curl -I https://sourcegraph.sourcegraph.com 2>&1 | head -20
echo ""

echo "3. MCP Endpoint Test:"
curl -I https://sourcegraph.sourcegraph.com/.api/mcp/v1 2>&1 | head -20
echo ""

echo "4. GraphQL API Test:"
curl -I https://sourcegraph.sourcegraph.com/.api/graphql 2>&1 | head -20
echo ""

echo "5. General Internet Connectivity Test:"
curl -I https://www.google.com 2>&1 | head -20
echo ""

echo "6. DNS Configuration:"
cat /etc/resolv.conf
echo ""

echo "=== Diagnostic Complete ==="
