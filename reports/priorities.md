# CodeContextBench - Prioritized Backlog

## Priority 1
Implement cost tracking and reporting. Parse token usage from claude-code.txt logs, aggregate costs per experiment/agent/benchmark, and surface cost comparisons in the Streamlit dashboard.

## Priority 2
Add trend tracking to the dashboard. Show performance trends across experiment runs over time, so improvements or regressions from agent/benchmark changes are visible at a glance.

## Priority 3
Add results download and storage automation. After a GCP VM experiment completes, automatically sync results from the VM back to local, ingest into SQLite, and update the dashboard.

## Priority 4
Expand agent configurations with additional MCP strategies. Add new agent variants that test different Deep Search invocation patterns (e.g., search-first vs search-on-failure, single vs multi-query).

## Priority 5
Add remote experiment triggering from the Streamlit dashboard. Add a UI that SSHs into the existing GCP VM, starts a benchmark run with a selected agent/benchmark combination, streams progress back to the dashboard, and syncs results when complete.

## Priority 6
Implement task selection scripts per benchmark. Each benchmark needs a script that uses the MCP-Value Scorer to select the highest-value tasks for evaluation runs, filtering by difficulty, MCP relevance, and estimated cost.
