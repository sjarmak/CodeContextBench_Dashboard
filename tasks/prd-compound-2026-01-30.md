# PRD: Unified Experiment Comparison Pipeline with Statistical Rigor

## Introduction

The project's core deliverable is comparing coding agent performance with and without MCP tools. The current comparison infrastructure is fragmented across multiple modules (`runners/compare_results.py`, `runners/aggregator.py`, `src/analysis/comparator.py`) with no unified entry point, no task alignment across heterogeneous runs, no reward normalization across benchmarks, and no pairwise bootstrap testing. The Jan-25 benchmark results demonstrated this gap: raw mean comparisons showed a misleading +0.9% delta on LoCoBench, but without confidence intervals there is no way to distinguish signal from noise. This feature closes the gap between "run benchmarks" and "make research claims."

## Goals

- Provide a single CLI command and Python module that compares two experiment directories end-to-end
- Automatically align tasks across runs, filtering to the common set with transparent reporting of exclusions
- Normalize rewards across benchmark types (big_code_mcp, LoCoBench, SWE-bench) to a 0-1 scale for valid cross-benchmark aggregation
- Compute pairwise bootstrap confidence intervals, p-values, and effect sizes
- Break down results by task category to identify where MCP tools help most
- Correlate MCP tool usage with reward deltas per task
- Output both a human-readable Markdown report and a machine-readable JSON file suitable for dashboard ingestion
- Deprecate the ad-hoc `runners/compare_results.py` in favor of the new module

## Non-Goals

- Replacing the existing `src/analysis/comparator.py` database-driven comparison (that module serves the dashboard's live analysis; this feature targets offline CLI comparison of run directories)
- Building a new dashboard view (the existing `analysis_comparison.py` will be extended to consume the new JSON output in a separate effort)
- Real-time comparison during benchmark execution
- Automated experiment discovery (user provides two directories explicitly)

## Technical Context

### Existing Infrastructure

| Module | Purpose | Limitation |
|--------|---------|------------|
| `runners/compare_results.py` (258 lines) | Ad-hoc text comparison | No stats, no JSON, no task alignment |
| `runners/aggregator.py` (264 lines) | Cross-run aggregation | No pairwise deltas, no significance tests |
| `src/analysis/comparator.py` (378 lines) | Database-driven comparison | Requires SQLite ingestion, not filesystem-first |
| `src/analysis/statistical_analyzer.py` (595 lines) | Significance testing | Uses t-tests/Fisher's exact, not bootstrap; tied to database |
| `src/benchmark/trace_parser.py` (257 lines) | Tool call extraction | No correlation with rewards |

### Dependencies

- `scipy` (already used in `statistical_analyzer.py`, but missing from `dashboard/requirements.txt`)
- `numpy` (available via scipy dependency)
- No new dependencies required; `scipy.stats.bootstrap` or manual bootstrap with numpy

### Key Data Structures

Each experiment directory contains task subdirectories with `result.json` files. A result.json includes fields: `reward` (float), `passed` (bool), `verifier_result` (dict or null), `agent_info` (dict or null), timing fields (`started_at`, `finished_at`) at top level. Task identity is derived from the directory name or `config.json`'s `task.path` field (needed because directory names are truncated with hash suffixes).

---

## User Stories

### US-001: Add scipy to project dependencies

**Description:** As a developer, I need `scipy` listed in the project's requirements so that statistical analysis modules work without manual installation.

**Acceptance Criteria:**
- [ ] `scipy>=1.11.0` is added to `dashboard/requirements.txt`
- [ ] `scipy>=1.11.0` is added to `pyproject.toml` if a `[project.dependencies]` or `[tool.poetry.dependencies]` section exists
- [ ] `pip install -r dashboard/requirements.txt` succeeds without errors
- [ ] Typecheck passes

---

### US-002: Create task alignment module

**Description:** As a researcher, I need to automatically match tasks across two experiment directories so that comparisons only include tasks present in both runs, with a clear report of what was excluded.

**Acceptance Criteria:**
- [ ] New file `src/analysis/experiment_comparator.py` with a `TaskAligner` class
- [ ] `TaskAligner.align(baseline_dir: Path, treatment_dir: Path)` returns a dataclass containing: `common_tasks` (list of task IDs), `baseline_only` (list), `treatment_only` (list), `total_baseline`, `total_treatment`
- [ ] Task ID resolution reads `config.json`'s `task.path` field when present, falling back to directory name
- [ ] Handles `result.json` files that are missing or contain `null` for key fields (uses `data.get("key") or default` pattern)
- [ ] Unit tests cover: identical task sets, disjoint task sets, partial overlap, missing config.json, null fields in result.json
- [ ] Typecheck passes

---

### US-003: Create reward normalization module

**Description:** As a researcher, I need rewards normalized to a 0-1 scale across benchmark types so that cross-benchmark aggregation produces valid results.

**Acceptance Criteria:**
- [ ] `RewardNormalizer` class added to `src/analysis/experiment_comparator.py`
- [ ] `normalize(reward: float, benchmark_type: str) -> float` returns a value in [0.0, 1.0]
- [ ] Normalization rules documented as constants: LoCoBench (already 0-1, passthrough), SWE-bench (binary 0/1, passthrough), big_code_mcp (map from raw scale to 0-1 using min-max from benchmark metadata)
- [ ] `benchmark_type` is inferred from the task directory path or config.json metadata
- [ ] Unknown benchmark types raise `ValueError` with a descriptive message
- [ ] Unit tests cover each benchmark type and the unknown-type error case
- [ ] Typecheck passes

---

### US-004: Implement pairwise bootstrap statistical testing

**Description:** As a researcher, I need pairwise bootstrap significance testing with confidence intervals so I can determine whether observed reward deltas are statistically meaningful.

**Acceptance Criteria:**
- [ ] `BootstrapResult` dataclass with fields: `mean_delta`, `ci_lower`, `ci_upper`, `p_value`, `effect_size` (Cohen's d), `effect_interpretation` (negligible/small/medium/large), `n_resamples`, `n_tasks`
- [ ] `pairwise_bootstrap(baseline_rewards: list[float], treatment_rewards: list[float], n_resamples: int = 10000, confidence: float = 0.95) -> BootstrapResult` function
- [ ] Bootstrap resamples paired differences (not independent), preserving task pairing
- [ ] p-value computed as the proportion of bootstrap deltas that cross zero
- [ ] Effect size computed as Cohen's d on the paired differences
- [ ] Effect interpretation follows standard thresholds: |d| < 0.2 negligible, < 0.5 small, < 0.8 medium, >= 0.8 large
- [ ] Deterministic results when `random_seed` parameter is provided (for testing)
- [ ] Unit tests cover: identical rewards (delta=0), large positive delta, large negative delta, single-task edge case, seed reproducibility
- [ ] Typecheck passes

---

### US-005: Implement per-category breakdown

**Description:** As a researcher, I need results grouped by task category (architectural_understanding, bug_investigation, etc.) so I can identify where MCP tools provide the most value.

**Acceptance Criteria:**
- [ ] `CategoryBreakdown` dataclass with fields: `category` (str), `n_tasks` (int), `baseline_mean` (float), `treatment_mean` (float), `mean_delta` (float), `bootstrap` (BootstrapResult or None — None when n_tasks < 5)
- [ ] `compute_category_breakdown(aligned_results: list, categories: dict[str, str]) -> list[CategoryBreakdown]` function
- [ ] Task category is extracted from config.json metadata or inferred from the task directory path
- [ ] Categories with fewer than 5 tasks skip bootstrap (insufficient data) but still report raw means
- [ ] Results sorted by absolute mean_delta descending (most impactful categories first)
- [ ] An "all" pseudo-category is included with the aggregate result
- [ ] Unit tests cover: multiple categories, single-category, category with < 5 tasks, missing category metadata
- [ ] Typecheck passes

---

### US-006: Implement tool usage correlation analysis

**Description:** As a researcher, I need to correlate MCP tool call counts with reward deltas per task so I can assess whether more tool usage leads to better outcomes.

**Acceptance Criteria:**
- [ ] `ToolCorrelation` dataclass with fields: `spearman_rho` (float), `spearman_p_value` (float), `n_tasks` (int), `interpretation` (str), `per_task` (list of dicts with task_id, tool_calls, reward_delta)
- [ ] `compute_tool_correlation(treatment_results: list, reward_deltas: dict[str, float]) -> ToolCorrelation` function
- [ ] Tool call count is extracted from result.json's `agent_info` or the trace file's tool usage summary
- [ ] Spearman rank correlation used (not Pearson) because the relationship may be nonlinear
- [ ] Interpretation string generated: "strong positive" (rho > 0.5), "moderate positive" (0.3-0.5), "weak/no correlation" (-0.3 to 0.3), "moderate negative" (-0.5 to -0.3), "strong negative" (< -0.5)
- [ ] Returns None gracefully when treatment run has no tool call data (baseline-only scenario)
- [ ] Unit tests cover: positive correlation, no correlation, missing tool data, fewer than 3 tasks
- [ ] Typecheck passes

---

### US-007: Build the ExperimentComparison orchestrator

**Description:** As a researcher, I need a single orchestrator class that combines task alignment, normalization, bootstrap testing, category breakdown, and tool correlation into one comparison pipeline.

**Acceptance Criteria:**
- [ ] `ExperimentComparison` class in `src/analysis/experiment_comparator.py` with method `compare(baseline_dir: Path, treatment_dir: Path) -> ComparisonReport`
- [ ] `ComparisonReport` dataclass with fields: `baseline_dir`, `treatment_dir`, `alignment` (TaskAligner result), `overall_bootstrap` (BootstrapResult), `category_breakdown` (list[CategoryBreakdown]), `tool_correlation` (ToolCorrelation or None), `generated_at` (ISO timestamp), `config` (dict of parameters used)
- [ ] Constructor accepts optional parameters: `n_resamples` (default 10000), `confidence` (default 0.95), `random_seed` (default None), `min_category_size` (default 5)
- [ ] `ComparisonReport.to_dict() -> dict` for JSON serialization
- [ ] `ComparisonReport.to_markdown() -> str` for human-readable output
- [ ] Pipeline stops early with a clear error if alignment produces 0 common tasks
- [ ] All null/None fields in result.json are handled defensively (no AttributeError on None)
- [ ] Unit tests cover: full pipeline with mock data, zero-overlap error, single-task edge case, to_dict round-trip, to_markdown output format
- [ ] Typecheck passes

---

### US-008: Create Markdown report formatter

**Description:** As a researcher, I need the comparison output formatted as a Markdown report suitable for pasting into research documents or nightly reports.

**Acceptance Criteria:**
- [ ] `ComparisonReport.to_markdown()` produces a complete Markdown document with sections:
  - **Summary**: baseline dir, treatment dir, date, number of common tasks, number excluded
  - **Overall Result**: mean delta with 95% CI, p-value, effect size with interpretation, pass/fail significance at alpha=0.05
  - **Per-Category Breakdown**: table with columns: Category, N, Baseline Mean, Treatment Mean, Delta, 95% CI, Significant?
  - **Tool Usage Correlation**: Spearman rho, p-value, interpretation sentence, scatter plot data reference
  - **Excluded Tasks**: lists of baseline-only and treatment-only task IDs (collapsed if > 10 items)
- [ ] Numbers formatted to 4 decimal places for rewards, 2 decimal places for percentages
- [ ] Significance marked with asterisks: * p<0.05, ** p<0.01, *** p<0.001
- [ ] Unit test verifies output contains all required section headers and table formatting
- [ ] Typecheck passes

---

### US-009: Create JSON output formatter

**Description:** As a developer, I need the comparison output as a structured JSON file so the dashboard and nightly compound loop can ingest results programmatically.

**Acceptance Criteria:**
- [ ] `ComparisonReport.to_dict()` returns a dict that is JSON-serializable (no Path objects, no numpy types)
- [ ] JSON schema includes: `version` (string, "1.0.0"), `generated_at` (ISO 8601), `config` (parameters used), `alignment` (counts and task lists), `overall` (bootstrap result dict), `categories` (list of category dicts), `tool_correlation` (correlation dict or null), `metadata` (baseline_dir, treatment_dir as strings)
- [ ] `ComparisonReport.save_json(path: Path)` writes the JSON file with 2-space indentation
- [ ] `ComparisonReport.load_json(path: Path) -> ComparisonReport` class method reconstructs the report from JSON (for dashboard loading)
- [ ] Round-trip test: `save_json` then `load_json` produces equivalent data
- [ ] Typecheck passes

---

### US-010: Create CLI wrapper script

**Description:** As a researcher, I need a CLI command to run experiment comparisons from the terminal with configurable parameters.

**Acceptance Criteria:**
- [ ] New file `scripts/compare_experiments.py` (~100 lines)
- [ ] Usage: `python scripts/compare_experiments.py <baseline_dir> <treatment_dir> [options]`
- [ ] Options: `--output-dir` (default: current directory), `--format` (markdown, json, both; default: both), `--resamples` (default: 10000), `--confidence` (default: 0.95), `--seed` (optional), `--min-category-size` (default: 5)
- [ ] Uses `argparse` for argument parsing
- [ ] Validates that both directories exist before starting comparison
- [ ] Prints summary to stdout and writes full report to output files
- [ ] Exit code 0 on success, 1 on error with descriptive message to stderr
- [ ] Typecheck passes

---

### US-011: Deprecate runners/compare_results.py

**Description:** As a developer, I need the old comparison script deprecated with a pointer to the new module so no one accidentally uses the statistically naive version.

**Acceptance Criteria:**
- [ ] `runners/compare_results.py` has a deprecation warning added at the top of `main()`: `warnings.warn("compare_results.py is deprecated. Use scripts/compare_experiments.py instead.", DeprecationWarning, stacklevel=2)`
- [ ] A comment block at the top of the file explains the deprecation and points to the replacement
- [ ] No functional changes to the existing code (preserving backward compatibility for any existing automation)
- [ ] Typecheck passes

---

## Edge Cases and Constraints

### Data Quality
- **Null fields in result.json**: Harbor result.json frequently contains `null` for `verifier_result`, `agent_info`, `agent_result`. All access must use `data.get("key") or default` pattern, not `data.get("key", default)`.
- **Truncated directory names**: Task directory names are truncated with hash suffixes (e.g., `c_api_graphql_expert_079_archite__pm9xcPn`). The real task name lives in `config.json` at the `task.path` field. Task alignment must resolve names via config.json.
- **Missing config.json**: Some older runs may lack config.json. Fall back to directory name matching.
- **Empty result.json**: Files that exist but contain no data or invalid JSON must be skipped with a warning, not crash the pipeline.

### Statistical Constraints
- **Minimum sample size**: Bootstrap with fewer than 5 paired tasks is unreliable. The pipeline should warn (not error) and report raw means without CI for small samples.
- **Tied values**: Many rewards are binary (0 or 1). The bootstrap and Spearman correlation must handle tied values correctly (scipy handles this by default).
- **Zero variance**: If all rewards in a group are identical (e.g., all 0 or all 1), Cohen's d is undefined. Return 0.0 with a note.

### Performance Constraints
- **Large experiment directories**: An experiment may contain 500+ task directories. Directory scanning should be efficient (single pass, no redundant reads).
- **Bootstrap computation**: 10,000 resamples on 500 tasks is fast (~0.1s with numpy vectorization). No performance concern.

### Compatibility Constraints
- **Benchmark scale differences**: big_code_mcp uses a different reward scale than LoCoBench (0-1) and SWE-bench (binary). Normalization must be applied before any cross-benchmark aggregation.
- **Python 3.10+**: Use dataclasses and type hints compatible with Python 3.10+ (no `type` keyword aliases).

## Design Considerations

- All new code goes in `src/analysis/experiment_comparator.py` (~300 lines for the module) with the CLI wrapper in `scripts/compare_experiments.py` (~100 lines)
- Use `@dataclass(frozen=True)` for all result types to enforce immutability per project coding standards
- No mutation of input data structures; all transformations produce new objects
- Functions should be small (< 50 lines each) and testable in isolation
- The module should be usable as both a library (imported by dashboard or nightly loop) and a CLI tool

## Success Metrics

- Running `python scripts/compare_experiments.py dir_a dir_b` produces a complete Markdown report and JSON file without errors
- The Markdown report contains confidence intervals and significance markers for all comparisons
- Task alignment correctly handles the Jan-25 scenario where baseline and treatment have different task sets
- Bootstrap results are reproducible when a seed is provided
- The JSON output is successfully loadable by `ComparisonReport.load_json()`
