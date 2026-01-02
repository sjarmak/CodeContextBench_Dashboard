# Phase 5: Dashboard Analysis Layer Integration

## Objective

Integrate Phase 4 analysis components (Statistical Testing, Time-Series Analysis, Cost Analysis) into the existing Streamlit dashboard to provide interactive visualization and exploration of experiment results.

## Deliverables

### Phase 5.1: Analysis View Core (Weeks 1-2)

**New Dashboard Views**:
1. **Analysis Hub** (main analysis entry point)
   - Experiment selector dropdown
   - Database status check (metrics.db)
   - Available analyses checklist
   - Quick-start workflow guide

2. **Experiment Comparison View**
   - Agent performance comparison table (pass rate, duration, MCP calls)
   - Side-by-side agent metrics
   - Cost metrics overlay
   - Statistical significance indicators (p-values, effect sizes)
   - Export comparison as JSON

3. **Statistical Analysis View**
   - Significant vs non-significant test results
   - Effect size visualization (Cohen's d, Cramér's V)
   - Power assessment display
   - Per-metric significance badges
   - Confidence level controls

**File Structure**:
```
dashboard/views/
├── analysis_hub.py              # New: Main analysis entry point
├── analysis_comparison.py        # New: Agent comparison with stats
├── analysis_statistical.py       # New: Statistical test results
└── [existing views preserved]
```

**Lines of Code Target**: ~500 (analysis_hub) + ~700 (comparison) + ~600 (statistical)

### Phase 5.2: Time-Series & Cost Views (Weeks 2-3)

**New Dashboard Views**:
1. **Time-Series Analysis View**
   - Multi-experiment trend visualization (line chart)
   - Agent trend filtering
   - Metric selector (pass_rate, duration, MCP calls, cost)
   - Anomaly highlighting
   - Best/worst improving metrics display
   - Trend slope and confidence display

2. **Cost Analysis View**
   - Total experiment cost and token summary
   - Agent cost rankings (cheap/expensive/efficient)
   - Cost per success metrics
   - Cost regressions warning display
   - Model pricing breakdown (Haiku vs Sonnet vs Opus)
   - Cost vs performance trade-off scatter plot

3. **Failure Analysis View** (existing component, enhanced)
   - Failure pattern distribution
   - Category-specific failure breakdown
   - Difficulty vs failure correlation
   - Suggested fixes display
   - Agent comparison on failure rate

**File Structure**:
```
dashboard/views/
├── analysis_timeseries.py       # New: Time-series trends
├── analysis_cost.py             # New: Cost analysis & rankings
└── [enhanced failure view if needed]
```

**Lines of Code Target**: ~650 (timeseries) + ~700 (cost)

### Phase 5.3: Dashboard Navigation & Integration (Week 3-4)

**Updates**:
1. **Enhanced Navigation** (dashboard/app.py)
   - New "Analysis" section in sidebar
   - Subpages: Comparison, Statistical, Time-Series, Cost, Recommendations
   - Database connectivity check on load
   - Experiment context preservation across views

2. **Database Integration Layer** (new utility)
   - Database existence check
   - Experiment list loading
   - Caching for performance
   - Error handling for missing data

3. **Shared Components** (dashboard/utils/)
   - Experiment selector
   - Agent multi-select filter
   - Metric selector
   - Confidence level slider
   - JSON export button
   - Result summary cards

**File Structure**:
```
dashboard/
├── app.py                       # Updated: New analysis routes
├── utils/
│   ├── database.py             # New: DB utilities
│   ├── analysis_loader.py      # New: Load Phase 4 results
│   └── common_components.py    # New: Shared UI elements
└── views/
    ├── analysis_hub.py
    ├── analysis_comparison.py
    ├── analysis_statistical.py
    ├── analysis_timeseries.py
    ├── analysis_cost.py
    └── [existing views]
```

**Lines of Code Target**: ~150 (app.py updates) + ~250 (database utils) + ~300 (common components)

### Phase 5.4: Visualization & UX (Week 4)

**Visualizations**:
1. **Comparison Tables**
   - Formatters for percentage/duration display
   - Conditional highlighting (better/worse agents)
   - Sortable columns
   - Export as CSV/JSON

2. **Statistical Results**
   - Significance badges (✓/✗ with p-value)
   - Effect size bars (Cohen's d magnitude)
   - Interpretation text (human-readable)
   - Confidence level indicator

3. **Charts**
   - Line charts: Time-series trends (Plotly)
   - Bar charts: Agent rankings (costs, pass rates)
   - Scatter plots: Cost vs performance
   - Heatmaps: Metric by agent matrix

4. **Summary Cards**
   - Best agent (overall, by metric)
   - Worst agent
   - Most efficient (cost/success)
   - Trending metrics (up/down arrows)
   - Anomalies detected badge

**Chart Libraries**:
- Streamlit native (tables, metrics)
- Plotly (interactive charts)
- Matplotlib (simple plots)

**Lines of Code Target**: ~500 (visualization utilities)

### Phase 5.5: Testing & Validation (Week 4-5)

**Test Coverage**:
1. **Component Tests** (Streamlit-compatible)
   - Database loader tests
   - Analysis result parsing tests
   - Visualization component tests

2. **Integration Tests**
   - End-to-end view loading
   - Data filtering and export
   - Error handling (missing DB, empty experiments)

3. **Manual Validation**
   - All views load correctly
   - Metrics display accurately
   - Charts render without errors
   - Export functionality works
   - Cross-view navigation smooth

**Test Files**:
```
dashboard/tests/
├── test_analysis_hub.py
├── test_analysis_views.py
├── test_database_utils.py
└── test_visualization.py
```

**Lines of Code Target**: ~300 (tests)

## Architecture

### Data Flow

```
metrics.db → AnalysisLoader → Analysis Objects → Streamlit Views → Browser UI
```

### Analysis Loader Pattern

```python
# dashboard/utils/analysis_loader.py
class AnalysisLoader:
    def __init__(self, db_path: Path):
        self.db = MetricsDatabase(db_path)
    
    def load_comparison(self, exp_id, baseline=None):
        """Load comparison results using ExperimentComparator"""
        comparator = ExperimentComparator(self.db)
        return comparator.compare_experiment(exp_id, baseline_agent=baseline)
    
    def load_statistical(self, exp_id, baseline=None, confidence=0.95):
        """Load statistical results"""
        analyzer = StatisticalAnalyzer(self.db)
        return analyzer.analyze_comparison(exp_id, baseline_agent=baseline, ...)
    
    def load_timeseries(self, exp_ids, agents=None):
        """Load time-series trends"""
        analyzer = TimeSeriesAnalyzer(self.db)
        return analyzer.analyze_multi_agent_trends(exp_ids, agent_names=agents)
    
    def load_cost(self, exp_id, baseline=None):
        """Load cost analysis"""
        analyzer = CostAnalyzer(self.db)
        return analyzer.analyze_experiment(exp_id, baseline_agent=baseline)
```

### View Pattern

All views follow this pattern:
```python
# dashboard/views/analysis_comparison.py
def show_analysis_comparison():
    st.title("Agent Comparison")
    
    # Load experiment selector
    exp_id = st.selectbox("Experiment", list_experiments())
    baseline = st.selectbox("Baseline Agent", list_agents(exp_id))
    
    # Load analysis
    loader = AnalysisLoader(get_db_path())
    result = loader.load_comparison(exp_id, baseline)
    
    # Display results
    display_comparison_table(result)
    display_cost_metrics(result)
    display_statistical_significance(result)
    
    # Export
    if st.button("Export as JSON"):
        st.download_button(..., data=json.dumps(result.to_dict()))
```

## Integration with Phase 4 Components

| Phase 4 Component | Dashboard View | Integration |
|------------------|---|---|
| ExperimentComparator | Comparison View | Main comparison table + cost overlay |
| StatisticalAnalyzer | Statistical View | Significance badges + effect sizes |
| TimeSeriesAnalyzer | Time-Series View | Line charts + trend summary |
| CostAnalyzer | Cost View | Rankings + efficiency metrics |
| FailureAnalyzer | Failure View | Pattern distribution + suggestions |
| RecommendationEngine | Recommendation Panel | Quick wins + priority items |

## Metrics Summary

| Aspect | Scope |
|--------|-------|
| New Views | 6 (hub, comparison, statistical, timeseries, cost, enhanced failure) |
| New Files | 8 (app.py update, 6 views, utils) |
| Shared Components | 4 (selector, filter, export, cards) |
| New Tests | 4 test modules, ~300 lines |
| Total New Code | ~4500 lines |
| Estimated Time | 4-5 weeks |

## Workflow

### User Journey

1. **Start**: Open dashboard → click "Analysis" in sidebar
2. **Hub**: See available experiments, analysis components status
3. **Select Experiment**: Choose experiment to analyze
4. **Compare Agents**: View comparison with cost + statistical overlays
5. **Check Significance**: See which differences are significant
6. **Track Trends**: Monitor improvements across multiple experiments
7. **Analyze Costs**: Identify expensive agents, cost regressions
8. **Review Failures**: Understand failure patterns by category
9. **Export**: Download analysis as JSON for reports

## Success Criteria

- ✓ All Phase 4 analysis components load in dashboard
- ✓ Metrics display correctly matching CLI output
- ✓ Charts render without errors
- ✓ Export to JSON works for all views
- ✓ Cross-view navigation is smooth
- ✓ No regression in existing dashboard functionality
- ✓ Performance: Views load in <2s
- ✓ All tests passing (existing + new)

## File Structure

```
dashboard/
├── app.py                              (updated: +analysis routes)
├── utils/
│   ├── __init__.py
│   ├── database.py                     (new: DB utilities)
│   ├── analysis_loader.py             (new: Phase 4 integration)
│   ├── common_components.py           (new: Shared UI)
│   └── [existing utils]
├── views/
│   ├── analysis_hub.py                (new)
│   ├── analysis_comparison.py         (new)
│   ├── analysis_statistical.py        (new)
│   ├── analysis_timeseries.py         (new)
│   ├── analysis_cost.py               (new)
│   ├── analysis_failure.py            (new/enhanced)
│   └── [existing views preserved]
└── tests/
    ├── test_analysis_hub.py           (new)
    ├── test_analysis_views.py         (new)
    ├── test_database_utils.py         (new)
    └── test_visualization.py          (new)
```

## Implementation Order

1. **Step 1**: Create AnalysisLoader utility + tests
2. **Step 2**: Build Analysis Hub view
3. **Step 3**: Build Comparison view (with stats + cost)
4. **Step 4**: Build Statistical view
5. **Step 5**: Build Time-Series view
6. **Step 6**: Build Cost view
7. **Step 7**: Enhance Failure view
8. **Step 8**: Update app.py navigation
9. **Step 9**: Add shared UI components
10. **Step 10**: Full integration testing

## Phase 5 Completion Definition

Phase 5 is complete when:
- All new views load without errors
- All Phase 4 analysis components are accessible via dashboard
- Metrics display match CLI output
- Tests pass (existing + new)
- Dashboard performance is acceptable (<2s load time)
- No regressions in existing dashboard functionality
