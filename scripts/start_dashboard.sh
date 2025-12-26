#!/bin/bash
# Start the CodeContextBench dashboard with proper environment variables
#
# Usage: bash scripts/start_dashboard.sh

set -e

# Check for .env.local file
if [ ! -f ".env.local" ]; then
    echo "ERROR: .env.local file not found"
    echo ""
    echo "Create .env.local with your API credentials."
    echo "See dashboard/USAGE.md for setup instructions."
    exit 1
fi

# Source environment variables
echo "Loading environment from .env.local..."
source .env.local

# Export variables so child processes (Harbor) can access them
export ANTHROPIC_API_KEY
export SOURCEGRAPH_ACCESS_TOKEN
export SOURCEGRAPH_URL

# Verify API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set in .env.local"
    exit 1
fi

echo "✓ Environment variables loaded"
echo "✓ ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."
echo "✓ SOURCEGRAPH_ACCESS_TOKEN: ${SOURCEGRAPH_ACCESS_TOKEN:0:10}..."
echo ""
echo "Starting dashboard on http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

# Start Streamlit dashboard
streamlit run dashboard/app.py
