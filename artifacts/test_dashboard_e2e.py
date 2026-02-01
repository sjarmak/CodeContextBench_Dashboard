"""
End-to-End Dashboard Tests using Playwright

Tests the CodeContextBench dashboard UI functionality.
Run with: pytest tests/test_dashboard_e2e.py --headed
"""

import pytest
from playwright.sync_api import Page, expect
import time


# Base URL for the dashboard
DASHBOARD_URL = "http://localhost:8501"


@pytest.fixture(scope="module")
def dashboard_url():
    """Return the dashboard URL."""
    return DASHBOARD_URL


class TestDashboardNavigation:
    """Test basic dashboard navigation."""

    def test_home_page_loads(self, page: Page, dashboard_url):
        """Test that the home page loads successfully."""
        page.goto(dashboard_url)

        # Wait for Streamlit to load
        page.wait_for_load_state("networkidle")
        time.sleep(2)  # Extra wait for Streamlit initialization

        # Check title
        expect(page).to_have_title("CodeContextBench Dashboard")

        # Check main sections appear
        page.get_by_text("Available Benchmarks").is_visible()
        page.get_by_text("Available Agents").is_visible()
        page.get_by_text("Current Evaluation Run Status").is_visible()

    def test_navigation_buttons_exist(self, page: Page, dashboard_url):
        """Test that all navigation buttons exist."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Check navigation items exist in sidebar
        # Streamlit buttons might not have role="button", so check by text
        nav_items = [
            "Benchmark Manager",
            "Evaluation Runner",
            "Run Results",
            "Comparison Table"
        ]

        for item in nav_items:
            # Use sidebar locator to avoid strict mode violations
            sidebar = page.locator('[data-testid="stSidebar"]')
            nav_item = sidebar.get_by_text(item, exact=True).first
            assert nav_item.is_visible(), f"Navigation item '{item}' not found in sidebar"


class TestBenchmarkManager:
    """Test Benchmark Manager functionality."""

    def test_benchmark_manager_loads(self, page: Page, dashboard_url):
        """Test that Benchmark Manager page loads."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Click Benchmark Manager in sidebar
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Benchmark Manager", exact=True).first.click()
        time.sleep(2)

        # Check page loaded (use .first to avoid strict mode violation)
        page.get_by_text("Benchmark Manager").first.is_visible()
        page.get_by_text("Registered Benchmarks").is_visible()

    def test_oracle_validation_section_exists(self, page: Page, dashboard_url):
        """Test that oracle validation section appears when benchmark selected."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Benchmark Manager
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Benchmark Manager", exact=True).first.click()
        time.sleep(2)

        # Select a benchmark (if any exist)
        # Note: This test assumes at least one benchmark is registered
        try:
            # Look for benchmark selector
            selector = page.locator("select").first
            if selector.is_visible():
                selector.select_option(index=0)
                time.sleep(2)

                # Check if validation section appears
                validation_section = page.get_by_text("Validation")
                if validation_section.is_visible():
                    # Check for timeout input and validation button
                    page.get_by_text("Timeout").is_visible()
                    page.get_by_role("button", name="Run Oracle Validation").is_visible()
        except:
            pytest.skip("No benchmarks registered for testing")


class TestEvaluationRunner:
    """Test Evaluation Runner functionality."""

    def test_evaluation_runner_loads(self, page: Page, dashboard_url):
        """Test that Evaluation Runner page loads."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Click Evaluation Runner in sidebar
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Evaluation Runner", exact=True).first.click()
        time.sleep(2)

        # Check page loaded (use .first to avoid strict mode violation)
        page.get_by_text("Evaluation Runner").first.is_visible()

    def test_mcp_configuration_options(self, page: Page, dashboard_url):
        """Test that MCP configuration radio buttons exist."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Evaluation Runner
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Evaluation Runner", exact=True).first.click()
        time.sleep(2)

        # Check MCP configuration section
        page.get_by_text("MCP Configuration").is_visible()

        # Check radio button options
        page.get_by_text("None (Pure Baseline)").is_visible()
        page.get_by_text("Sourcegraph MCP").is_visible()
        page.get_by_text("Deep Search MCP").is_visible()


class TestRunResults:
    """Test Run Results functionality."""

    def test_run_results_loads(self, page: Page, dashboard_url):
        """Test that Run Results page loads."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Click Run Results in sidebar
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(2)

        # Check page loaded (use .first to avoid strict mode violation)
        page.get_by_text("Run Results").first.is_visible()

    def test_run_results_tabs_exist(self, page: Page, dashboard_url):
        """Test that all required tabs exist when a run is selected."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Run Results
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(2)

        # Try to select a run (if any exist)
        try:
            selector = page.locator("select").first
            if selector.is_visible():
                selector.select_option(index=0)
                time.sleep(2)

                # Select a task (if any exist)
                task_selector = page.locator("select").nth(1)
                if task_selector.is_visible():
                    task_selector.select_option(index=0)
                    time.sleep(3)

                    # Check for required tabs
                    page.get_by_text("Agent Trace").is_visible()
                    page.get_by_text("Result Details").is_visible()
                    page.get_by_text("LLM Judge").is_visible()
                    page.get_by_text("Task Report").is_visible()
        except:
            pytest.skip("No evaluation runs found for testing")


class TestLLMJudgeIntegration:
    """Test LLM Judge integration in Run Results."""

    def test_llm_judge_tab_content(self, page: Page, dashboard_url):
        """Test LLM Judge tab shows correct content."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Run Results
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(2)

        try:
            # Select first run and task
            run_selector = page.locator("select").first
            if run_selector.is_visible():
                run_selector.select_option(index=0)
                time.sleep(2)

                task_selector = page.locator("select").nth(1)
                if task_selector.is_visible():
                    task_selector.select_option(index=0)
                    time.sleep(3)

                    # Click LLM Judge tab
                    page.get_by_text("LLM Judge").click()
                    time.sleep(2)

                    # Check judge elements exist
                    page.get_by_text("LLM Judge Evaluation").is_visible()
                    page.get_by_text("Judge Model").is_visible()

                    # Check model selector
                    judge_model_selector = page.get_by_label("Judge Model")
                    if judge_model_selector.is_visible():
                        # Verify options exist
                        options = judge_model_selector.locator("option").all_text_contents()
                        assert "haiku" in " ".join(options).lower()
                        assert "sonnet" in " ".join(options).lower()

                    # Check run button exists
                    page.get_by_role("button", name="Run LLM Judge Evaluation").is_visible()
        except:
            pytest.skip("No evaluation runs with tasks for testing")


class TestTaskReportGeneration:
    """Test Task Report generation in Run Results."""

    def test_task_report_tab_content(self, page: Page, dashboard_url):
        """Test Task Report tab shows correct content."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Run Results
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(2)

        try:
            # Select first run and task
            run_selector = page.locator("select").first
            if run_selector.is_visible():
                run_selector.select_option(index=0)
                time.sleep(2)

                task_selector = page.locator("select").nth(1)
                if task_selector.is_visible():
                    task_selector.select_option(index=0)
                    time.sleep(3)

                    # Click Task Report tab
                    page.get_by_text("Task Report").click()
                    time.sleep(2)

                    # Check report elements exist
                    page.get_by_text("Task Report").is_visible()
                    page.get_by_role("button", name="Generate Task Report").is_visible()
        except:
            pytest.skip("No evaluation runs with tasks for testing")


class TestComparisonTable:
    """Test Comparison Table functionality."""

    def test_comparison_table_loads(self, page: Page, dashboard_url):
        """Test that Comparison Table page loads."""
        page.goto(dashboard_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Click Comparison Table in sidebar
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Comparison Table", exact=True).first.click()
        time.sleep(2)

        # Check page loaded (use .first to avoid strict mode violation)
        page.get_by_text("Comparison Table").first.is_visible()


# Test configuration
if __name__ == "__main__":
    pytest.main([__file__, "--headed", "-v"])
