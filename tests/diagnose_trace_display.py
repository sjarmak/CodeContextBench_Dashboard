"""
Detailed diagnostics for trace display issues
"""
import time
from playwright.sync_api import sync_playwright
from pathlib import Path

DASHBOARD_URL = "http://localhost:8501"

def diagnose():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()

        # Create screenshots directory
        screenshots_dir = Path("tests/screenshots")
        screenshots_dir.mkdir(exist_ok=True)

        print("=" * 80)
        print("TRACE DISPLAY DIAGNOSTICS")
        print("=" * 80)

        # Load dashboard
        print("\n1. Loading dashboard...")
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        page.screenshot(path=str(screenshots_dir / "01_dashboard_loaded.png"))
        print("   Screenshot: 01_dashboard_loaded.png")

        # Navigate to Run Results
        print("\n2. Navigating to Run Results...")
        sidebar = page.locator('[data-testid="stSidebar"]')

        # List all sidebar items
        sidebar_text = sidebar.text_content()
        print(f"   Sidebar content preview: {sidebar_text[:200]}")

        run_results_btn = sidebar.get_by_text("Run Results", exact=True).first
        if run_results_btn.is_visible():
            print("   ✓ Run Results button found")
            run_results_btn.click()
            time.sleep(4)

            page.screenshot(path=str(screenshots_dir / "02_run_results.png"))
            print("   Screenshot: 02_run_results.png")
        else:
            print("   ❌ Run Results button not visible")
            return

        # Check what's on the page
        print("\n3. Analyzing page content...")
        page_text = page.locator("body").text_content()

        # Check for select elements
        selects = page.locator("select").all()
        print(f"   Found {len(selects)} select elements")

        for i, select in enumerate(selects):
            print(f"\n   Select {i}:")
            if select.is_visible():
                print(f"      Visible: Yes")
                options = select.locator("option").all_text_contents()
                print(f"      Options ({len(options)}): {options[:3]}")
            else:
                print(f"      Visible: No")

        # Check for any errors
        errors = page.locator('[data-testid="stException"]').all()
        if errors:
            print(f"\n   ❌ Found {len(errors)} errors:")
            for i, error in enumerate(errors):
                error_text = error.text_content()
                print(f"\n   Error {i+1}:")
                print(f"   {error_text[:300]}")

            page.screenshot(path=str(screenshots_dir / "03_errors.png"))
            print("   Screenshot: 03_errors.png")

        # If we have selects, try selecting
        if len(selects) >= 2:
            print("\n4. Selecting first run and task...")

            # Select first run
            selects[0].select_option(index=0)
            time.sleep(3)

            page.screenshot(path=str(screenshots_dir / "04_run_selected.png"))
            print("   Screenshot: 04_run_selected.png")

            # Select first task
            # Refresh selects list as it might have changed
            selects = page.locator("select").all()
            if len(selects) >= 2:
                selects[1].select_option(index=0)
                time.sleep(4)

                page.screenshot(path=str(screenshots_dir / "05_task_selected.png"))
                print("   Screenshot: 05_task_selected.png")

                # Check for errors after selection
                errors = page.locator('[data-testid="stException"]').all()
                if errors:
                    print(f"\n   ❌ Found {len(errors)} errors after selection:")
                    for i, error in enumerate(errors):
                        error_text = error.text_content()
                        print(f"\n   Error {i+1}:")
                        print(error_text)

                    page.screenshot(path=str(screenshots_dir / "06_errors_after_selection.png"))
                else:
                    print("\n   ✓ No errors after selection")

                # Look for trace tabs
                print("\n5. Looking for trace tabs...")
                all_tabs = page.locator('[data-testid="stTab"]').all()
                print(f"   Found {len(all_tabs)} tabs")

                for i, tab in enumerate(all_tabs):
                    tab_text = tab.text_content()
                    print(f"   Tab {i}: {tab_text}")

                # Try clicking on each trace tab
                trace_tabs = ["Full Conversation", "Tool Calls", "Code Diffs", "Test Results"]

                for tab_name in trace_tabs:
                    print(f"\n6. Testing '{tab_name}' tab...")

                    tab_found = False
                    for i, tab in enumerate(all_tabs):
                        if tab_name in tab.text_content():
                            tab_found = True
                            print(f"   Found at index {i}, clicking...")

                            tab.click()
                            time.sleep(3)

                            # Check for errors
                            tab_errors = page.locator('[data-testid="stException"]').all()
                            if tab_errors:
                                print(f"   ❌ ERRORS in '{tab_name}':")
                                for error in tab_errors:
                                    print(error.text_content())

                                page.screenshot(path=str(screenshots_dir / f"error_{tab_name.replace(' ', '_').lower()}.png"))
                            else:
                                print(f"   ✓ No errors in '{tab_name}'")
                                page.screenshot(path=str(screenshots_dir / f"success_{tab_name.replace(' ', '_').lower()}.png"))

                            break

                    if not tab_found:
                        print(f"   ⚠ Tab '{tab_name}' not found")

        print("\n" + "=" * 80)
        print("DIAGNOSTICS COMPLETE")
        print("=" * 80)
        print(f"\nScreenshots saved to: {screenshots_dir}")
        print("\nClosing browser in 5 seconds...")
        time.sleep(5)

        browser.close()

if __name__ == "__main__":
    diagnose()
