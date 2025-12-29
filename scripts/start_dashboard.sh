#!/bin/bash
# Start CodeContextBench Dashboard with proper environment setup

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

# Load environment variables
if [ -f ".env.local" ]; then
    echo "Loading environment from .env.local..."
    source .env.local

    # CRITICAL: Export variables for Harbor subprocesses
    export ANTHROPIC_API_KEY
    export SOURCEGRAPH_ACCESS_TOKEN
    export SOURCEGRAPH_URL
    export BASELINE_MCP_TYPE

    echo "✓ Environment variables exported"
else
    echo "ERROR: .env.local not found!"
    exit 1
fi

# Start dashboard
echo "Starting dashboard..."
streamlit run dashboard/app.py
