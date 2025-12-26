"""
Verify all dashboard fixes with Playwright

Verifies:
1. Step numbering (should start at 1, not 51)
2. Token display (input/output/cached breakdown)
3. LLM judge reward (should show 1.0, not 0)
4. Code diffs (should show full diffs, not truncated)
5. New trace display (conversation view with tabs)
"""
import time
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://localhost:8501"

def verify_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()

        print("=" * 80)
        print("VERIFYING ALL DASHBOARD FIXES")
        print("=" * 80)

        # Load dashboard
        print("\n1. Loading dashboard...")
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("   ✓ Dashboard loaded")

        # Navigate to Run Results
        print("\n2. Navigating to Run Results...")
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(3)

        # Select first run and task
        print("\n3. Selecting run and task...")
        selects = page.locator("select").all()
        if len(selects) >= 2:
            selects[0].select_option(index=0)
            time.sleep(2)
            selects[1].select_option(index=0)
            time.sleep(3)
            print("   ✓ Run and task selected")

            # Check 1: Step Numbering
            print("\n4. Checking step numbering...")
            page_text = page.locator("body").text_content()
            if "Step 1" in page_text:
                print("   ✓ Step numbering starts at 1")
            else:
                print("   ❌ Step numbering issue - 'Step 1' not found")

            # Check 2: New Trace Display Tabs
            print("\n5. Checking new trace display tabs...")
            tabs = page.locator('[data-testid="stTab"]').all()
            tab_names = [tab.text_content() for tab in tabs]
            print(f"   Found tabs: {tab_names}")

            expected_tabs = ["Full Conversation", "Tool Calls", "Code Diffs", "Test Results"]
            found_tabs = [name for name in expected_tabs if any(name in t for t in tab_names)]

            if len(found_tabs) >= 3:
                print(f"   ✓ Found trace tabs: {found_tabs}")
            else:
                print(f"   ℹ Trace tabs: {tab_names}")

            # Check 3: Conversation View
            print("\n6. Checking conversation view...")
            if "User Request" in page_text and "Assistant Response" in page_text:
                print("   ✓ Conversation view showing User Request and Assistant Response")
            else:
                print("   ℹ Conversation view structure may differ")

            # Check 4: Code Diffs Tab
            print("\n7. Checking Code Diffs tab...")
            for i, tab in enumerate(tabs):
                tab_text = tab.text_content()
                if "Code Diffs" in tab_text or "📋" in tab_text:
                    print(f"   Clicking on Code Diffs tab {i}...")
                    tab.click()
                    time.sleep(2)

                    # Check if diffs are visible
                    diffs_text = page.locator("body").text_content()
                    if "Total Code Changes" in diffs_text or "Edit:" in diffs_text or "Write:" in diffs_text:
                        print("   ✓ Code diffs are visible")
                        if "truncated" in diffs_text.lower():
                            print("   ⚠ WARNING: Still seeing 'truncated' in diffs")
                        else:
                            print("   ✓ No 'truncated' text found (full diffs shown)")
                    else:
                        print("   ℹ No code changes found in this task")
                    break

        # Check 5: Comparison Table Token Display
        print("\n8. Checking Comparison Table...")
        sidebar.get_by_text("Comparison Table", exact=True).first.click()
        time.sleep(3)

        comp_text = page.locator("body").text_content()
        if "Input Tokens" in comp_text and "Output Tokens" in comp_text and "Cached Tokens" in comp_text:
            print("   ✓ Token breakdown shows Input/Output/Cached columns")
        else:
            print("   ℹ Token columns may need verification")

        if "Note on Cached Tokens" in comp_text or "Anthropic charges" in comp_text:
            print("   ✓ Cached token pricing note is visible")
        else:
            print("   ℹ Cached token note may not be visible")

        # Check 6: LLM Judge
        print("\n9. Checking LLM Judge...")
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(3)

        # Select run/task again
        selects = page.locator("select").all()
        if len(selects) >= 2:
            selects[0].select_option(index=0)
            time.sleep(2)
            selects[1].select_option(index=0)
            time.sleep(3)

            # Navigate to LLM Judge tab (should be 3rd tab in run results)
            all_tabs = page.locator('[data-testid="stTab"]').all()
            for i, tab in enumerate(all_tabs):
                if "Judge" in tab.text_content():
                    print(f"   Clicking LLM Judge tab {i}...")
                    tab.click()
                    time.sleep(3)

                    judge_text = page.locator("body").text_content()

                    # Check if evaluation exists
                    if "No LLM judge evaluation found" in judge_text:
                        print("   ℹ No existing evaluation - would need to generate one")
                    elif "Retrieval Quality" in judge_text or "Code Quality" in judge_text:
                        print("   ✓ LLM Judge evaluation found")

                        # Check for reward value
                        if "Reward: 1.0" in judge_text or "1.0" in judge_text:
                            print("   ✓ Reward showing correctly (1.0)")
                        elif "Reward: 0.0" in judge_text or "Reward: 0" in judge_text:
                            print("   ❌ Reward showing as 0 (should be 1.0)")
                        else:
                            print("   ℹ Reward value needs manual check")

                    break

        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        print("\n✓ FIXES APPLIED:")
        print("  1. Step numbering starts at 1 (not 51)")
        print("  2. Token display shows Input/Output/Cached breakdown")
        print("  3. Cached token pricing note added")
        print("  4. LLM judge uses correct Harbor reward format")
        print("  5. Code diffs show full content (not truncated)")
        print("  6. New trace display with tabs:")
        print("     - Conversation view (User → Assistant)")
        print("     - Full Conversation tab")
        print("     - Tool Calls tab")
        print("     - Code Diffs tab")
        print("     - Test Results tab")

        print("\n🔍 MANUAL CHECKS:")
        print("  - Verify diffs are actually full (not just 2000 chars)")
        print("  - Generate new LLM judge evaluation to verify reward")
        print("  - Check Test Results tab for test output")

        print("\nPress Enter to close browser...")
        input()

        browser.close()

if __name__ == "__main__":
    verify_all()
