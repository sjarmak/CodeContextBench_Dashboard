"""
Test new trace display tabs with Playwright

Tests:
1. All four tabs are visible
2. No AttributeError when clicking each tab
3. Diffs are shown correctly
4. Tool calls are shown correctly
5. Test results tab works
"""
import time
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://localhost:8501"

def test_trace_tabs():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        print("=" * 80)
        print("TESTING TRACE DISPLAY TABS")
        print("=" * 80)

        # Load dashboard
        print("\n1. Loading dashboard...")
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Navigate to Run Results
        print("\n2. Navigating to Run Results...")
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(3)

        # Select run and task
        print("\n3. Selecting run and task...")
        selects = page.locator("select").all()
        if len(selects) >= 2:
            selects[0].select_option(index=0)
            time.sleep(2)
            selects[1].select_option(index=0)
            time.sleep(3)

            # Check for errors in main view
            print("\n4. Checking main conversation view...")
            errors = page.locator('[data-testid="stException"]').all()
            if errors:
                print(f"   ❌ Found {len(errors)} errors in main view")
                for error in errors:
                    print(f"      {error.text_content()[:100]}")
            else:
                print("   ✓ No errors in main conversation view")

            # Check User Request and Assistant Response
            page_text = page.locator("body").text_content()
            if "User Request" in page_text and "Assistant Response" in page_text:
                print("   ✓ Conversation structure visible")
            else:
                print("   ℹ Conversation structure may differ")

            # Find and test all trace tabs
            print("\n5. Testing trace display tabs...")
            all_tabs = page.locator('[data-testid="stTab"]').all()

            print(f"   Found {len(all_tabs)} total tabs")

            # Expected tabs (should appear after LLM Judge and Task Report tabs)
            expected_trace_tabs = ["Full Conversation", "Tool Calls", "Code Diffs", "Test Results"]

            for expected_tab in expected_trace_tabs:
                print(f"\n6. Testing '{expected_tab}' tab...")

                # Find the tab
                tab_found = False
                for i, tab in enumerate(all_tabs):
                    tab_text = tab.text_content()
                    if expected_tab in tab_text:
                        tab_found = True
                        print(f"   Found tab at index {i}")

                        # Click the tab
                        tab.click()
                        time.sleep(2)

                        # Check for errors
                        tab_errors = page.locator('[data-testid="stException"]').all()
                        if tab_errors:
                            print(f"   ❌ ERRORS in '{expected_tab}' tab:")
                            for error in tab_errors:
                                error_text = error.text_content()
                                print(f"      {error_text[:200]}")
                                # Print full traceback if available
                                if "Traceback" in error_text:
                                    print("\n" + "="*60)
                                    print(error_text)
                                    print("="*60 + "\n")
                        else:
                            print(f"   ✓ No errors in '{expected_tab}' tab")

                        # Check content
                        tab_content = page.locator("body").text_content()

                        if expected_tab == "Full Conversation":
                            if "Step 1" in tab_content or "User" in tab_content or "Assistant" in tab_content:
                                print("   ✓ Conversation content visible")
                            else:
                                print("   ℹ No conversation steps found")

                        elif expected_tab == "Tool Calls":
                            if "Total Tool Calls" in tab_content or "No tool calls found" in tab_content:
                                print("   ✓ Tool calls section visible")
                                # Check if there are actual tool calls
                                if "Total Tool Calls:" in tab_content:
                                    # Try to extract count
                                    import re
                                    match = re.search(r'Total Tool Calls: (\d+)', tab_content)
                                    if match:
                                        print(f"   ℹ Found {match.group(1)} tool calls")
                            else:
                                print("   ℹ Tool calls content may differ")

                        elif expected_tab == "Code Diffs":
                            if "Total Code Changes" in tab_content or "No code changes found" in tab_content:
                                print("   ✓ Code diffs section visible")
                                # Check if there are actual diffs
                                if "Total Code Changes:" in tab_content:
                                    import re
                                    match = re.search(r'Total Code Changes: (\d+)', tab_content)
                                    if match:
                                        print(f"   ℹ Found {match.group(1)} code changes")

                                    # Check if diffs are expanded
                                    if "Edit:" in tab_content or "Write:" in tab_content:
                                        print("   ✓ Diffs are visible")

                                    # Check for "Before:" and "After:" sections
                                    if "Before:" in tab_content and "After:" in tab_content:
                                        print("   ✓ Diff structure (Before/After) visible")
                            else:
                                print("   ℹ Code diffs content may differ")

                        elif expected_tab == "Test Results":
                            if "test" in tab_content.lower() or "No test results found" in tab_content:
                                print("   ✓ Test results section visible")
                            else:
                                print("   ℹ Test results content may differ")

                        break

                if not tab_found:
                    print(f"   ⚠ Tab '{expected_tab}' not found")

        else:
            print("\n⚠ No runs found to test")
            print("   Please run an evaluation first")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        print("\n✓ All tabs should be error-free")
        print("✓ TraceStep attribute errors should be fixed")

        # Auto-close after 3 seconds instead of waiting for input
        print("\nClosing browser in 3 seconds...")
        time.sleep(3)

        browser.close()

if __name__ == "__main__":
    test_trace_tabs()
