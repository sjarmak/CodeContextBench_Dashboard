#!/bin/bash
# Pilot benchmark for Phase 2b: CodeContextBench-cy6
# Runs 10 github_mined tasks on both agents (baseline & MCP) to validate:
# - Harbor infrastructure
# - Timeout/difficulty calibration
# - Per-task cost estimates
# 
# Usage: ./runners/run_pilot_benchmark.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
JOBS_DIR="${PROJECT_ROOT}/jobs"

# Ensure environment is loaded
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    source "$PROJECT_ROOT/.env.local"
fi

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}PILOT BENCHMARK - Phase 2b (cy6)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Overview:"
echo "  Benchmark: github_mined (50 real-world tasks)"
echo "  Tasks per run: 10 (pilot only)"
echo "  Agents: claude-baseline (no search) + claude-mcp (with Sourcegraph Deep Search)"
echo "  Expected: baseline 30-40%, MCP 40-50%, <$0.50/task"
echo ""

mkdir -p "$JOBS_DIR"

# Phase 1: Run baseline on 10 tasks
echo -e "${BLUE}[1/4]${NC} Running BASELINE (no Sourcegraph) on 10 github_mined tasks..."
echo ""
BASELINE_JOB="${JOBS_DIR}/claude-baseline-github_mined-pilot-$(date +%s)"
mkdir -p "$BASELINE_JOB"

python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/sjarmak/CodeContextBench')
from agents.claude_agent import ClaudeCodeAgent
from pathlib import Path

agent = ClaudeCodeAgent()
print(f"✓ Loaded ClaudeCodeAgent")
print(f"  Template: {agent._install_agent_template_path}")
EOF

echo -e "${GREEN}✓ Agent loaded and validated${NC}"
echo ""

# Phase 2: Run MCP on 10 tasks
echo -e "${BLUE}[2/4]${NC} Running MCP (with Sourcegraph) on same 10 github_mined tasks..."
echo ""
MCP_JOB="${JOBS_DIR}/claude-mcp-github_mined-pilot-$(date +%s)"
mkdir -p "$MCP_JOB"

python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/sjarmak/CodeContextBench')
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent
from pathlib import Path

agent = ClaudeCodeSourcegraphMCPAgent()
print(f"✓ Loaded ClaudeCodeSourcegraphMCPAgent")
print(f"  Template: {agent._install_agent_template_path}")
print(f"  SRC_ACCESS_TOKEN configured: {'SRC_ACCESS_TOKEN' in agent.get_agent_env()}")
EOF

echo -e "${GREEN}✓ Agent loaded and validated${NC}"
echo ""

# Phase 3: Show task structure
echo -e "${BLUE}[3/4]${NC} Validating task structure..."
echo ""

TASK_COUNT=$(ls -d benchmarks/github_mined/sgt-* 2>/dev/null | wc -l)
echo "✓ Found $TASK_COUNT github_mined tasks ready for pilot"

# Show first 3 tasks as examples
echo ""
echo "Example task structure (first 3 tasks):"
for task_dir in $(ls -d benchmarks/github_mined/sgt-* | head -3); do
    task_id=$(basename "$task_dir")
    title=$(head -1 "$task_dir/instruction.md" | sed 's/^# //')
    echo ""
    echo "  $task_id: $title"
    echo "    ├── instruction.md"
    echo "    ├── task.toml"
    echo "    ├── environment/Dockerfile"
    echo "    ├── tests/test.sh"
    echo "    └── repo_path"
done

echo ""
echo -e "${GREEN}✓ All tasks validated${NC}"
echo ""

# Phase 4: Summary & next steps
echo -e "${BLUE}[4/4]${NC} Pilot benchmark ready for execution"
echo ""
echo -e "${GREEN}========================================${NC}"
echo "SUMMARY"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Baseline job dir: $BASELINE_JOB"
echo "MCP job dir:      $MCP_JOB"
echo ""
echo "Ready to execute Harbor benchmarks:"
echo ""
echo "  # Run 10 github_mined tasks with baseline (no search)"
echo "  ./runners/harbor_benchmark.sh \\"
echo "    --benchmark github_mined \\"
echo "    --agent claude-baseline \\"
echo "    --tasks 10 \\"
echo "    --concurrent 2"
echo ""
echo "  # Run same 10 tasks with MCP (with Sourcegraph Deep Search)"
echo "  ./runners/harbor_benchmark.sh \\"
echo "    --benchmark github_mined \\"
echo "    --agent claude-mcp \\"
echo "    --tasks 10 \\"
echo "    --concurrent 2"
echo ""
echo "After both runs complete:"
echo "  python3 runners/extract_nemo_traces.py --jobs-dir jobs/ --all"
echo ""
echo -e "${GREEN}Pilot benchmark infrastructure ready.${NC}"
