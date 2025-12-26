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
set -a  # Automatically export all variables
source .env.local
set +a

# Verify API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set in .env.local"
    exit 1
fi

echo ""
echo "✓ Environment variables loaded and exported:"
echo "  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:15}... (${#ANTHROPIC_API_KEY} chars)"
if [ -n "$SOURCEGRAPH_ACCESS_TOKEN" ]; then
    echo "  SOURCEGRAPH_ACCESS_TOKEN: ${SOURCEGRAPH_ACCESS_TOKEN:0:15}... (${#SOURCEGRAPH_ACCESS_TOKEN} chars)"
fi
if [ -n "$SOURCEGRAPH_URL" ]; then
    echo "  SOURCEGRAPH_URL: $SOURCEGRAPH_URL"
fi

# Verify they're actually exported
if ! env | grep -q "ANTHROPIC_API_KEY"; then
    echo "ERROR: ANTHROPIC_API_KEY not in environment!"
    exit 1
fi

echo ""
echo "Starting dashboard on http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

# Start Streamlit dashboard with explicit environment
exec streamlit run dashboard/app.py
