# CodeContextBench - Nightly Review Focus Areas

The nightly loop produces a research report each night at `reports/nightly/YYYY-MM-DD-review.md`.
These are the areas it should focus on:

## Benchmark Setup
- Review adapter configs, verifier weights, and scoring approaches for all benchmarks
- Flag stale references, outdated configs, or mismatches between templates and actual execution
- Evaluate whether agent variants are sufficiently differentiated for meaningful comparison

## Dashboard & UI Flows
- Identify missing views or features in the Streamlit dashboard
- Propose specific UI flows for common workflows (comparing runs, drilling into traces, viewing token usage)
- Sketch how remote experiment triggering from the dashboard could work

## Evaluation Quality
- Assess blind spots in verifier scoring (e.g. LoCoBench keyword overlap weighting)
- Compare our evaluation approach against SWE-bench, LBPP, and other established benchmarks
- Suggest improvements to how agent performance is measured

## Research
- Surface relevant papers, tools, or benchmark techniques
- Identify new evaluation methodologies worth adopting
- Propose new benchmark task categories or agent strategies
