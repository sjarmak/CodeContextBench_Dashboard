"""
Test SWE-bench Verified integration in dashboard
"""
import sys
from playwright.sync_api import sync_playwright
import time

def test_swebench_integration():
    """Verify SWE-bench Verified shows instance ID input."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to dashboard
        page.goto("http://localhost:8502")
        time.sleep(5)

        # Check page loaded
        print(f"Page title: {page.title()}")
        print(f"URL: {page.url}")

        # Take screenshot of initial page
        page.screenshot(path="tests/screenshots/swebench_initial.png")
        print("Initial screenshot saved")

        # Try to find navigation - Streamlit uses st.page_link or st.navigation
        # Look for any text containing "Evaluation Runner"
        page_content = page.content()
        if "Evaluation Runner" in page_content:
            print("Found 'Evaluation Runner' text on page")
            # Try clicking on text
            try:
                page.get_by_text("Evaluation Runner").click()
                print("Clicked on Evaluation Runner text")
            except Exception as e:
                print(f"Could not click: {e}")
        else:
            print("'Evaluation Runner' not found in page content")

        time.sleep(3)
        page.screenshot(path="tests/screenshots/swebench_after_nav.png")
        print("After navigation screenshot saved")

        # Find benchmark selectbox (should be first selectbox)
        selectboxes = page.locator('[data-baseweb="select"]').all()
        print(f"Found {len(selectboxes)} selectboxes")

        if len(selectboxes) > 0:
            benchmark_selectbox = selectboxes[0]
            benchmark_selectbox.click()
            time.sleep(1)

            # Look for SWE-bench Verified in options
            menu_options = page.locator('[role="option"]').all()
            print(f"Found {len(menu_options)} options")

            swebench_found = False
            for option in menu_options:
                text = option.text_content()
                print(f"  Option: {text}")
                if "SWE-bench Verified" in text:
                    print("✓ Found SWE-bench Verified option")
                    option.click()
                    swebench_found = True
                    break

            if not swebench_found:
                print("✗ SWE-bench Verified not found")
                browser.close()
                sys.exit(1)

            time.sleep(2)

            # Check for instance ID input
            page_text = page.content()

            if "Instance IDs (one per line)" in page_text:
                print("✓ Instance ID input field found")
            else:
                print("✗ Instance ID input field NOT found")

            if "Harbor Dataset" in page_text:
                print("✓ Harbor Dataset indicator found")
            else:
                print("✗ Harbor Dataset indicator NOT found")

            # Take screenshot
            page.screenshot(path="tests/screenshots/swebench_integration.png")
            print("✓ Screenshot saved to tests/screenshots/swebench_integration.png")

        browser.close()

if __name__ == "__main__":
    test_swebench_integration()
