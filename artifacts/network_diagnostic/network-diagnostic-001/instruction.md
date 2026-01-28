# Network Connectivity Diagnostic

Test network connectivity from this Harbor environment to Sourcegraph.

## Task

Create and run a bash script that tests connectivity to Sourcegraph API endpoints.

### Requirements

1. Create `/testbed/run_diagnostic.sh` with the following tests:
   - DNS resolution for `sourcegraph.sourcegraph.com`
   - HTTPS connectivity to `https://sourcegraph.sourcegraph.com`
   - MCP endpoint: `https://sourcegraph.sourcegraph.com/.api/mcp/v1`
   - GraphQL API: `https://sourcegraph.sourcegraph.com/.api/graphql`
   - General internet test: `https://www.google.com`
   - Display DNS configuration from `/etc/resolv.conf`

2. Make the script executable with `chmod +x`

3. Run the script and save ALL output to `/testbed/network_diagnostic_results.txt`

### Success Criteria

- Script created and executable
- Results file exists with test output
- Results show whether each endpoint is reachable
