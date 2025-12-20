#!/bin/bash
# Direct Claude Code comparison (no Harbor benchmark wrapper)
# Runs baseline vs MCP agent on a single task directory
# Captures trajectory/execution logs for analysis

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <task_dir>"
    echo ""
    echo "Example:"
    echo "  $0 benchmarks/big_code_mcp/big-code-vsc-001"
    exit 1
fi

TASK_DIR="$1"
TASK_NAME=$(basename "$TASK_DIR")

if [ ! -d "$TASK_DIR" ]; then
    echo "ERROR: Task directory not found: $TASK_DIR"
    exit 1
fi

if [ ! -f "$TASK_DIR/instruction.md" ]; then
    echo "ERROR: instruction.md not found in $TASK_DIR"
    exit 1
fi

echo "=========================================="
echo "Direct Claude Code Comparison"
echo "Task: $TASK_NAME"
echo "=========================================="
echo ""

source .env.local

# Verify credentials
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    exit 1
fi

if [ -z "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "ERROR: SOURCEGRAPH_ACCESS_TOKEN not set"
    exit 1
fi

echo "✓ ANTHROPIC_API_KEY is set"
echo "✓ SOURCEGRAPH_ACCESS_TOKEN is set"
echo "✓ SOURCEGRAPH_URL: ${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}"
echo ""

export ANTHROPIC_API_KEY
export SOURCEGRAPH_URL="${SOURCEGRAPH_URL:-https://sourcegraph.sourcegraph.com}"
export SOURCEGRAPH_ACCESS_TOKEN

# Create timestamped directory
TIMESTAMP=$(date +%Y%m%d-%H%M)
JOBS_DIR="jobs/comparison-${TIMESTAMP}"
mkdir -p "${JOBS_DIR}/baseline" "${JOBS_DIR}/mcp"

echo "Results will be saved to: $JOBS_DIR/"
echo ""

# Read instruction
INSTRUCTION=$(cat "$TASK_DIR/instruction.md")

# Run baseline (no MCP)
echo ">>> BASELINE: Running Claude Code (no MCP guidance)..."
echo "Task: $TASK_NAME"
echo ""

cd "$TASK_DIR"
touch "${JOBS_DIR}/baseline/output.txt"
claude \
  "${INSTRUCTION}" \
  --permission-mode acceptEdits \
  --allowedTools "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput" \
  > "${JOBS_DIR}/baseline/output.txt" 2>&1 &

BASELINE_PID=$!
echo "Baseline PID: $BASELINE_PID"

# Wait for baseline with timeout (15 minutes)
TIMEOUT_SECS=900
start_time=$(date +%s)

while kill -0 $BASELINE_PID 2>/dev/null; do
    elapsed=$(($(date +%s) - start_time))
    if [ $elapsed -gt $TIMEOUT_SECS ]; then
        echo "⚠ Baseline timeout after ${TIMEOUT_SECS}s, killing..."
        kill -9 $BASELINE_PID 2>/dev/null || true
        break
    fi
    sleep 5
done

BASELINE_EXIT=$?
echo "Baseline exit code: $BASELINE_EXIT"
echo ""

# Run MCP (with Sourcegraph guidance)
echo ">>> MCP: Running Claude Code (with Sourcegraph MCP guidance)..."
echo "Task: $TASK_NAME"
echo ""

# Inject MCP config
mkdir -p /tmp/mcp_setup
cat > /tmp/mcp_setup/.mcp.json << EOF
{
  "mcpServers": {
    "sourcegraph": {
      "type": "http",
      "url": "${SOURCEGRAPH_URL}/.api/mcp/v1",
      "headers": {
        "Authorization": "token ${SOURCEGRAPH_ACCESS_TOKEN}"
      }
    }
  }
}
EOF

# Add MCP guidance to instruction
MCP_INSTRUCTION="${INSTRUCTION}

---

## IMPORTANT: Use Sourcegraph MCP for Broad Searches

This is a large codebase. If a search spans more than a narrow, well-defined set of directories, you **MUST** use Sourcegraph MCP search tools (sg_keyword_search, sg_nls_search, sg_deepsearch):

- ✅ Use MCP for broad architectural queries
- ✅ Use MCP to find all references across the codebase
- ✅ Use MCP to understand patterns and conventions at scale
- ❌ Do NOT use local grep or rg for cross-module searches
- ❌ Local tools only for narrow, single-directory scopes

You have access to Sourcegraph MCP with full codebase context. Use it."

touch "${JOBS_DIR}/mcp/output.txt"
claude \
  "${MCP_INSTRUCTION}" \
  --permission-mode acceptEdits \
  --allowedTools "Bash,Read,Edit,Write,Grep,Glob,Skill,TodoWrite,Task,TaskOutput" \
  > "${JOBS_DIR}/mcp/output.txt" 2>&1 &

MCP_PID=$!
echo "MCP PID: $MCP_PID"

# Wait for MCP with timeout (15 minutes)
start_time=$(date +%s)

while kill -0 $MCP_PID 2>/dev/null; do
    elapsed=$(($(date +%s) - start_time))
    if [ $elapsed -gt $TIMEOUT_SECS ]; then
        echo "⚠ MCP timeout after ${TIMEOUT_SECS}s, killing..."
        kill -9 $MCP_PID 2>/dev/null || true
        break
    fi
    sleep 5
done

MCP_EXIT=$?
echo "MCP exit code: $MCP_EXIT"
echo ""

cd - > /dev/null

# Extract metrics
echo "=========================================="
echo "Results Summary"
echo "=========================================="
echo ""
echo "Baseline output saved to: ${JOBS_DIR}/baseline/output.txt"
echo "MCP output saved to: ${JOBS_DIR}/mcp/output.txt"
echo ""
echo "To analyze results:"
echo "  cat ${JOBS_DIR}/baseline/output.txt | tail -50"
echo "  cat ${JOBS_DIR}/mcp/output.txt | tail -50"
echo ""
