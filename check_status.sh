#!/bin/bash
for task in big-code-vsc-001 big-code-servo-001 big-code-k8s-001 big-code-trt-001; do
  b=$(find jobs/bigcode-comparison-20251220-1014/$task/baseline -name "trajectory.json" 2>/dev/null | wc -l)
  m=$(find jobs/bigcode-comparison-20251220-1014/$task/mcp -name "trajectory.json" 2>/dev/null | wc -l)
  printf "%-25s baseline: %d/1  mcp: %d/1\n" "$task" "$b" "$m"
done
echo "Total: $(find jobs/bigcode-comparison-20251220-1014 -name "trajectory.json" | wc -l)/8"
