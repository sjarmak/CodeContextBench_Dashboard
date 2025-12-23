#!/bin/bash

# Monitor SWEBench MCP comparison experiment progress

RESULTS_DIR="${1:-results/swebench_comparison_20251222-220401}"

echo "Monitoring experiment: $RESULTS_DIR"
echo ""

while true; do
    clear
    echo "SWEBench MCP Comparison - Progress Monitor"
    echo "=========================================="
    echo "Results Directory: $RESULTS_DIR"
    echo "Last updated: $(date)"
    echo ""
    
    # Count results files
    json_files=$(find "$RESULTS_DIR" -name "*.json" 2>/dev/null | wc -l)
    log_files=$(find "$RESULTS_DIR" -name "*.log" 2>/dev/null | wc -l)
    
    echo "Files created: $json_files JSON, $log_files logs"
    echo ""
    
    # List created files
    if [ $json_files -gt 0 ]; then
        echo "JSON Results:"
        ls -lh "$RESULTS_DIR"/*.json 2>/dev/null | awk '{print "  " $9, "(" $5 ")"}'
        echo ""
    fi
    
    # Check for summary
    if [ -f "$RESULTS_DIR/summary.json" ]; then
        echo "Summary available:"
        python3 -c "
import json
try:
    with open('$RESULTS_DIR/summary.json') as f:
        data = json.load(f)
    for agent in data.get('agents', []):
        status = '✓' if agent.get('success') else '✗'
        print(f\"  {status} {agent['display']}\")
except:
    pass
" 2>/dev/null
        echo ""
    fi
    
    # Check running processes
    echo "Running processes:"
    ps aux | grep -E "harbor run|python3.*run_swebench" | grep -v grep | awk '{print "  " $11 " (PID: " $2 ")"}'
    
    echo ""
    echo "Press Ctrl+C to stop monitoring"
    sleep 10
done
