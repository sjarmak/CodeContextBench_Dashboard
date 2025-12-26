"""
Test SWE-bench task selector in dashboard
"""
import sys
from playwright.sync_api import sync_playwright
import time

def test_task_selector():
    """Verify SWE-bench shows task multiselect."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to dashboard
        page.goto("http://localhost:8502")
        time.sleep(5)

        # Navigate to Evaluation Runner
        try:
            page.get_by_text("Evaluation Runner").click()
            time.sleep(3)
        except Exception as e:
            print(f"Failed to click Evaluation Runner: {e}")
            browser.close()
            sys.exit(1)

        # Select SWE-bench Verified
        selectboxes = page.locator('[data-baseweb="select"]').all()
        if len(selectboxes) > 0:
            benchmark_selectbox = selectboxes[0]
            benchmark_selectbox.click()
            time.sleep(1)

            # Find and click SWE-bench Verified
            menu_options = page.locator('[role="option"]').all()
            for option in menu_options:
                if "SWE-bench Verified" in option.text_content():
                    print("✓ Clicking SWE-bench Verified")
                    option.click()
                    break

            time.sleep(3)

            # Wait for instances to load
            print("Waiting for instances to load...")
            time.sleep(5)

            # Check for success message
            page_text = page.content()

            if "Loaded 500 instances" in page_text:
                print("✓ Loaded 500 instances")
            else:
                print("✗ Did not find 'Loaded 500 instances'")

            # Check for multiselect
            if "Tasks to Run" in page_text:
                print("✓ Found 'Tasks to Run' multiselect")
            else:
                print("✗ Did not find 'Tasks to Run' multiselect")

            # Take screenshot
            page.screenshot(path="tests/screenshots/swebench_task_selector.png")
            print("✓ Screenshot saved")

            # Try to open the multiselect to see tasks
            task_selectboxes = page.locator('[data-baseweb="select"]').all()
            print(f"Found {len(task_selectboxes)} selectboxes total")

            if len(task_selectboxes) >= 2:
                # The task selectbox should be after the benchmark selectbox
                task_selectbox = task_selectboxes[-1]  # Last one
                task_selectbox.click()
                time.sleep(2)

                # Count options
                task_options = page.locator('[role="option"]').all()
                print(f"✓ Found {len(task_options)} task options in dropdown")

                # Show first few
                for i, option in enumerate(task_options[:5]):
                    print(f"  Task {i+1}: {option.text_content()}")

                # Take another screenshot
                page.screenshot(path="tests/screenshots/swebench_task_dropdown.png")
                print("✓ Dropdown screenshot saved")

        browser.close()

if __name__ == "__main__":
    test_task_selector()
