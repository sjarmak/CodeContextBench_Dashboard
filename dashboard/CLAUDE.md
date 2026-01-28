# Dashboard Development Guidelines

## Code Style

### No Emojis
Do NOT use emojis anywhere in the dashboard UI or code. This includes:
- Streamlit text, labels, buttons, tabs, expanders
- Status indicators (use "Yes"/"No" or text badges instead)
- Icons in headers or titles
- Comments or docstrings

Use text-based alternatives:
- Instead of checkmarks/X marks: "Yes", "No", "Pass", "Fail"
- Instead of warning icons: "[Warning]", "[Critical]", "[Medium]"
- Instead of folder/file icons: just use the text
- Instead of user/assistant icons: "[User]", "[Assistant]"

### File Organization
- Keep views in `views/` directory
- Keep reusable components in `utils/` or `components/`
- Each view should be a single file under 800 lines

### Streamlit Patterns
- Use `st.session_state` for persistent state
- Prefix widget keys with view name to avoid collisions
- Use `st.cache_data` for expensive computations
- Prefer `st.dataframe` over `st.table` for large data

## Data Sources

The dashboard reads from:
- `~/evals/custom_agents/agents/claudecode/runs/` - External evaluation results (configurable via `CCB_EXTERNAL_RUNS_DIR`)
- `data/metrics.db` - Analysis metrics database
- `data/codecontextbench.db` - Benchmark registry
- `configs/` - Configuration files

## Testing

Run dashboard tests with:
```bash
pytest dashboard/tests/
```
