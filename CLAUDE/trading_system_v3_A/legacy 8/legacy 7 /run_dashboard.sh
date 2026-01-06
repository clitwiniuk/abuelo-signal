#!/bin/bash
# Launcher for Live Debug Dashboard

# Navigate to project root
cd "$(dirname "$0")"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit not found. Installing..."
    pip install streamlit plotly
fi

# Run dashboard
echo "🚀 Starting Live Dashboard on localhost..."
echo "Press Ctrl+C to stop"
streamlit run dashboard/live_dashboard.py
