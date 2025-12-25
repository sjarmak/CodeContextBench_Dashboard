#!/bin/bash
# Quick start script for CodeContextBench Dashboard

echo "🚀 Launching CodeContextBench Dashboard..."
echo ""

# Check if streamlit is installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "❌ Error: streamlit not installed"
    echo "Installing dashboard requirements..."
    pip install streamlit plotly pandas
    echo ""
fi

# Launch dashboard
streamlit run dashboard/app.py
