"""
Debug multiselect rendering for SWE-bench
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

    print("Waiting for instances to load...")
    time.sleep(8)

    # Take full page screenshot
    page.screenshot(path="tests/screenshots/debug_full_page.png", full_page=True)
    print("✓ Full page screenshot saved")

    # Check page content
    content = page.content()

    # Check if multiselect is present
    multiselects = page.locator('[data-baseweb="select"]').all()
    print(f"\nFound {len(multiselects)} selectboxes/multiselects")

    # Check for the "Tasks to Run" text
    if "Tasks to Run" in content:
        print("✓ Found 'Tasks to Run' label")
    else:
        print("✗ 'Tasks to Run' label not found")

    # Check for loaded message
    if "Loaded 500 instances" in content:
        print("✓ Found 'Loaded 500 instances' message")
    else:
        print("✗ 'Loaded 500 instances' message not found")

    # Look for multiselect specifically
    # Streamlit multiselects have a specific structure
    multiselect_divs = page.locator('[data-testid="stMultiSelect"]').all()
    print(f"\nFound {len(multiselect_divs)} st.multiselect components")

    if len(multiselect_divs) > 0:
        print("✓ Multiselect component exists")

        # Try to interact with it
        multiselect = multiselect_divs[0]

        # Click on the multiselect input area
        multiselect_input = multiselect.locator('input').first
        if multiselect_input.count() > 0:
            print("✓ Multiselect input found")

            # Type to search for django
            multiselect_input.click()
            time.sleep(1)

            # Take screenshot of opened multiselect
            page.screenshot(path="tests/screenshots/debug_multiselect_open.png")
            print("✓ Multiselect opened screenshot saved")

            # Type 'django' to filter
            multiselect_input.fill("django")
            time.sleep(2)

            # Take screenshot showing filtered results
            page.screenshot(path="tests/screenshots/debug_multiselect_filtered.png")
            print("✓ Filtered results screenshot saved")

            # Count visible options
            options = page.locator('[role="option"]').all()
            print(f"Found {len(options)} options after filtering for 'django'")
            for opt in options[:5]:
                print(f"  - {opt.text_content()}")
        else:
            print("✗ Multiselect input not found")
    else:
        print("✗ No multiselect component found")

    browser.close()
