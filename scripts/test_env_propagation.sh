#!/bin/bash
# Test if exported environment variables are properly passed to harbor run
# This reproduces the env var issue from the failed MCP comparison

set -e

echo "=== Testing Environment Variable Propagation ==="
echo ""

# Set test variables
export TEST_API_KEY="test-key-12345"
export TEST_SG_TOKEN="sg-token-abcde"

echo "Step 1: Variables exported in shell"
echo "  TEST_API_KEY=$TEST_API_KEY"
echo "  TEST_SG_TOKEN=$TEST_SG_TOKEN"
echo ""

# Create a test script that checks for these vars
cat > /tmp/check_env.sh << 'EOF'
#!/bin/bash
echo "=== Inside Container ==="
echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-NOT_SET}"
echo "TEST_API_KEY=${TEST_API_KEY:-NOT_SET}"
echo "TEST_SG_TOKEN=${TEST_SG_TOKEN:-NOT_SET}"
echo "SOURCEGRAPH_ACCESS_TOKEN=${SOURCEGRAPH_ACCESS_TOKEN:-NOT_SET}"
EOF

chmod +x /tmp/check_env.sh

echo "Step 2: Running bash script to check exported vars"
bash /tmp/check_env.sh
echo ""

echo "=== Conclusion ==="
echo "If variables show NOT_SET above, subprocess inheritance is the issue."
echo "Harbor containers may require explicit environment passing."
