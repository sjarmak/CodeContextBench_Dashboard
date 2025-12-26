"""
Show the task multiselect with actual instance IDs
"""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("http://localhost:8502")
    time.sleep(5)

    # Navigate to Evaluation Runner
    page.get_by_text("Evaluation Runner").click()
    time.sleep(3)

    # Select SWE-bench Verified
    selectboxes = page.locator('[data-baseweb="select"]').all()
    selectboxes[0].click()
    time.sleep(1)

    page.locator('[role="option"]').filter(has_text="SWE-bench Verified").click()
    time.sleep(8)  # Wait for instances to load

    # Scroll down to see the task multiselect
    page.evaluate("window.scrollTo(0, 400)")
    time.sleep(2)

    # Take screenshot showing the whole task selection section
    page.screenshot(path="tests/screenshots/swebench_full_ui.png", full_page=True)
    print("✓ Full page screenshot saved")

    # Now click on the Tasks to Run multiselect
    # It should be the LAST selectbox on the page (after benchmark and MCP type)
    all_selects = page.locator('[data-baseweb="select"]').all()
    print(f"Found {len(all_selects)} selectboxes")

    # The last one should be the task multiselect
    task_multiselect = all_selects[-1]
    task_multiselect.click()
    time.sleep(2)

    # Take screenshot of the dropdown
    page.screenshot(path="tests/screenshots/swebench_tasks_open.png")
    print("✓ Task dropdown screenshot saved")

    # Get the first few options
    options = page.locator('[role="option"]').all()
    print(f"Found {len(options)} task options")
    for i, opt in enumerate(options[:10]):
        text = opt.text_content()
        if text:
            print(f"  {i+1}. {text}")

    browser.close()
