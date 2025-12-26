"""
Diagnose dashboard issues with Playwright
"""
import time
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://localhost:8501"

def diagnose():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        print("=" * 80)
        print("DASHBOARD DIAGNOSTICS")
        print("=" * 80)

        # Navigate to dashboard
        print("\n1. Loading dashboard...")
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Check Run Results
        print("\n2. Navigating to Run Results...")
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(3)

        # Check for errors on page
        errors = page.locator('[data-testid="stException"]').all()
        if errors:
            print(f"   ❌ Found {len(errors)} errors on Run Results page")
            for i, error in enumerate(errors):
                print(f"   Error {i+1}: {error.text_content()[:200]}")
        else:
            print("   ✓ No errors on Run Results page")

        # Check if there are any runs
        run_selects = page.locator("select").all()
        if run_selects:
            print(f"   ✓ Found {len(run_selects)} select dropdowns")

            # Select first run
            first_select = run_selects[0]
            options = first_select.locator("option").all_text_contents()
            print(f"   Available runs: {options[:3]}")

            if len(options) > 0:
                first_select.select_option(index=0)
                time.sleep(2)
                print("   ✓ Selected first run")

                # Check for task selector
                if len(run_selects) > 1:
                    task_select = run_selects[1]
                    task_options = task_select.locator("option").all_text_contents()
                    print(f"   Available tasks: {task_options}")

                    if len(task_options) > 0:
                        task_select.select_option(index=0)
                        time.sleep(3)
                        print("   ✓ Selected first task")

                        # Check reward display
                        page_text = page.locator("body").text_content()
                        if "Result" in page_text:
                            # Try to find the result value
                            result_section = page.locator("text=Result").locator("..").locator("..")
                            if result_section.count() > 0:
                                result_text = result_section.first.text_content()
                                print(f"   Result section: {result_text[:100]}")

                        # Check for warnings
                        warnings = page.locator('[data-testid="stAlert"]').all()
                        if warnings:
                            print(f"   ⚠ Found {len(warnings)} warnings:")
                            for i, warning in enumerate(warnings):
                                warning_text = warning.text_content()
                                print(f"     Warning {i+1}: {warning_text[:150]}")

        # Check Comparison Table
        print("\n3. Navigating to Comparison Table...")
        sidebar.get_by_text("Comparison Table", exact=True).first.click()
        time.sleep(3)

        # Check for errors
        comp_errors = page.locator('[data-testid="stException"]').all()
        if comp_errors:
            print(f"   ❌ Found {len(comp_errors)} errors on Comparison Table")
            for i, error in enumerate(comp_errors):
                error_text = error.text_content()
                print(f"   Error {i+1}:")
                print(f"   {error_text[:500]}")
        else:
            print("   ✓ No errors on Comparison Table")

        comp_warnings = page.locator('[data-testid="stAlert"]').all()
        if comp_warnings:
            print(f"   ⚠ Found {len(comp_warnings)} warnings:")
            for i, warning in enumerate(comp_warnings):
                print(f"     {warning.text_content()[:150]}")

        print("\n4. Checking database state...")
        # This will be visible in the terminal where dashboard is running
        page.goto(f"{DASHBOARD_URL}?check_db=1")
        time.sleep(2)

        print("\n" + "=" * 80)
        print("Diagnostics complete. Press Enter to close browser...")
        input()

        browser.close()

if __name__ == "__main__":
    diagnose()
