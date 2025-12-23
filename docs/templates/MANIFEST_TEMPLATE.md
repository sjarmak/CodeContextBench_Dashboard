# Experiment: [TITLE]

**Date:** YYYY-MM-DD
**Status:** Planning | Running | Complete | Failed | Abandoned
**Owner:** [name or agent session]

## Hypothesis

[State what you're testing and what you expect to find.]

Example: "Deep Search prompting will reduce task completion time by 30% compared to baseline, by enabling faster context gathering in large codebases."

## Configuration

- **Model:** anthropic/claude-haiku-4-5-20251001
- **Benchmark:** [big_code_mcp | github_mined | dependeval | etc.]
- **Tasks:** [list specific tasks or "all"]
- **Agents:** [baseline, aggressive, strategic, etc.]
- **Runs per config:** [1 | 3 | 5]

## Variables

| Variable | Values Tested | Notes |
|----------|---------------|-------|
| Prompt style | baseline, aggressive | |
| Model | haiku-4-5 | |
| Deep Search enabled | yes/no | |

## Results Summary

*Fill in after experiment completes.*

| Agent | Success Rate | Avg Time | Deep Search Calls | Notes |
|-------|--------------|----------|-------------------|-------|
| baseline | - | - | 0 | Control |
| aggressive | - | - | - | |
| strategic | - | - | - | |

## Key Findings

*Fill in after experiment completes.*

1. Finding 1
2. Finding 2
3. Finding 3

## Raw Outputs

- `config.json` - Experiment configuration
- `*/metrics_report.json` - Per-agent metrics
- `REPORT.md` - Auto-generated comparison report
- `analysis.json` - Detailed analysis output

## Follow-up

- [ ] Next experiment to run based on findings
- [ ] Issues to investigate
- [ ] Improvements to agent prompts

## Notes

[Any additional context, observations, or issues encountered during the experiment.]
