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

## Harbor Result Format (Critical)

Harbor's `result.json` has timing fields at the **top level**, NOT nested in a `timing` dict:
```python
# WRONG: result.get("timing", {}).get("started_at")
# CORRECT:
started_at = result.get("started_at", "")
finished_at = result.get("finished_at", "")
```

Key field locations in Harbor result.json:
- `task_name` — top level (not `task_id`)
- `agent_info.name` — agent name
- `agent_info.model_info.name` — model name
- `verifier_result.rewards` — verifier scores
- `started_at` / `finished_at` — top-level ISO timestamps
- `agent_execution.started_at` / `agent_execution.finished_at` — agent-specific timing

## Data Model Alignment (Gotcha)

Analysis views MUST match the actual data model classes. Common mismatches found:

| View expects | Actual model attribute |
|---|---|
| `result.agent_results` | `result.agent_metrics` |
| `result.agent_deltas` | `result.deltas` |
| `result.anomalies` | `result.total_anomalies` |
| `result.best_improving` (dict) | `result.best_improving_metric` (TimeSeriesTrend) |
| `result.agent_trends` (dict) | `result.trends` (nested: metric -> agent -> TimeSeriesTrend) |
| `trend.get("direction")` | `trend.direction.value` (enum) |

Always verify data model classes in `src/analysis/` before writing view code.

## Streamlit Gotchas

### Duplicate Widget Keys
Streamlit raises `StreamlitDuplicateElementKey` if two widgets share a key. Prefix keys by context:
- Sidebar navigation: `nav_` prefix
- Hub buttons: `hub_goto_` prefix
- Analysis configs: `analysis_` prefix

### Sidebar Content Invisible
Content added to `st.sidebar` appears **below** the navigation menu and may require scrolling. For analysis configuration panels, prefer rendering in the **main content area** using `st.columns()` layout instead of the sidebar.

### NavigationContext API
The `NavigationContext` class uses `push()` not `navigate_to()`. Always check the actual method names in `dashboard/utils/navigation.py`.

## Filesystem vs Database Pattern

Prefer **filesystem scanning** over database queries for displaying experiment results:
- Experiments live in `~/evals/custom_agents/agents/claudecode/runs/`
- Paired experiments have `baseline/` + `deepsearch/` subdirs — split into separate selectable entries
- Compute metrics on-the-fly from task-level `result.json` files
- No database ingestion step required
- `comparison_config.py` demonstrates this pattern

## Color Theme

Streamlit theme is configured in `dashboard/.streamlit/config.toml`:
- Primary color: `#4a9eff` (blue, NOT Streamlit's default orange)
- Use dark grey (`#555555`) for negative indicators (fail, error, worst) instead of red/orange

## Testing

Run dashboard tests with:
```bash
pytest dashboard/tests/
```
