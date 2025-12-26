# End-to-End Dashboard Tests

Automated browser tests for the CodeContextBench dashboard using Playwright.

## Setup

```bash
# Install dependencies (already done)
pip install playwright pytest-playwright
playwright install chromium
```

## Running Tests

### Prerequisites

**Dashboard must be running:**
```bash
streamlit run dashboard/app.py
```

### Run All Tests

```bash
# Headless mode (no browser window)
pytest tests/test_dashboard_e2e.py -v

# Headed mode (see browser)
pytest tests/test_dashboard_e2e.py --headed -v

# Run specific test class
pytest tests/test_dashboard_e2e.py::TestLLMJudgeIntegration -v

# Run specific test
pytest tests/test_dashboard_e2e.py::TestLLMJudgeIntegration::test_llm_judge_tab_content -v
```

### Debugging Tests

```bash
# Slow motion (600ms delay between actions)
pytest tests/test_dashboard_e2e.py --headed --slowmo=600 -v

# Take screenshots on failure
pytest tests/test_dashboard_e2e.py --screenshot=on --video=on -v

# Keep browser open on failure
pytest tests/test_dashboard_e2e.py --headed --pause-on-failure -v
```

## Test Coverage

### ✅ Navigation Tests
- `TestDashboardNavigation`
  - Home page loads
  - All navigation buttons exist and are clickable

### ✅ Benchmark Manager Tests
- `TestBenchmarkManager`
  - Page loads correctly
  - Oracle validation section appears when benchmark selected
  - Validation controls exist

### ✅ Evaluation Runner Tests
- `TestEvaluationRunner`
  - Page loads correctly
  - MCP configuration options exist
  - Radio buttons for baseline/sourcegraph/deepsearch

### ✅ Run Results Tests
- `TestRunResults`
  - Page loads correctly
  - All required tabs exist (Agent Trace, Result Details, LLM Judge, Task Report)

### ✅ LLM Judge Integration Tests
- `TestLLMJudgeIntegration`
  - LLM Judge tab content loads
  - Judge model selector exists with correct options
  - Run button exists

### ✅ Task Report Tests
- `TestTaskReportGeneration`
  - Task Report tab content loads
  - Generate button exists
  - Export buttons exist (tested when report generated)

### ✅ Comparison Table Tests
- `TestComparisonTable`
  - Page loads correctly

## Test Data Requirements

Some tests require existing data:
- **Benchmark Manager tests:** Require at least one registered benchmark
- **Run Results tests:** Require at least one completed evaluation run
- **LLM Judge tests:** Require completed runs with tasks

**To generate test data:**
```bash
# Run oracle validation on hello_world_test
# This creates a minimal completed run for testing
```

## Common Issues

### "No evaluation runs found"
Some tests skip if no data exists. This is expected. Run an evaluation first.

### "Element not found"
Streamlit's dynamic rendering can cause timing issues. Tests include `time.sleep()` calls for stability. Increase delays if needed.

### Port already in use
Dashboard must be on port 8501. Check with:
```bash
lsof -i :8501
```

## CI/CD Integration

For GitHub Actions:
```yaml
- name: Run E2E Tests
  run: |
    streamlit run dashboard/app.py &
    sleep 10  # Wait for dashboard to start
    pytest tests/test_dashboard_e2e.py -v
    kill %1  # Stop dashboard
```

## Writing New Tests

1. Add test class to `test_dashboard_e2e.py`
2. Use `page.goto(dashboard_url)` to start
3. Include `time.sleep()` after navigation/clicks
4. Use `page.get_by_role()` or `page.get_by_text()` for selectors
5. Skip tests gracefully if data doesn't exist

Example:
```python
def test_new_feature(self, page: Page, dashboard_url):
    page.goto(dashboard_url)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Your test code here
    page.get_by_text("My Feature").click()
    time.sleep(1)

    # Assertions
    page.get_by_text("Expected Result").is_visible()
```
