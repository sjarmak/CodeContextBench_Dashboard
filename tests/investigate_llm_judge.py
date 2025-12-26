"""
Investigate LLM Judge issues with Playwright

Issues to check:
1. Reward showing 0 when it was actually 1.0
2. Code diffs showing as truncated instead of full diffs
3. Whether diffs are being extracted from test comparison
"""
import time
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://localhost:8501"

def investigate():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        print("=" * 80)
        print("LLM JUDGE INVESTIGATION")
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

        # Select first run
        print("\n3. Selecting first completed run...")
        run_selects = page.locator("select").all()
        if len(run_selects) > 0:
            first_select = run_selects[0]
            options = first_select.locator("option").all_text_contents()
            print(f"   Available runs: {options[:3]}")

            first_select.select_option(index=0)
            time.sleep(2)

            # Select first task
            if len(run_selects) > 1:
                task_select = run_selects[1]
                task_options = task_select.locator("option").all_text_contents()
                print(f"   Available tasks: {task_options}")

                task_select.select_option(index=0)
                time.sleep(3)

                # Check displayed reward
                print("\n4. Checking displayed reward...")
                page_text = page.locator("body").text_content()

                # Look for reward in Result section
                if "Result" in page_text or "Reward" in page_text:
                    # Try to find specific reward value
                    reward_section = page.locator("text=/Result|Reward/i")
                    if reward_section.count() > 0:
                        # Get surrounding text
                        for i in range(reward_section.count()):
                            elem = reward_section.nth(i)
                            parent_text = elem.locator("..").text_content()
                            print(f"   Reward section {i+1}: {parent_text[:200]}")

                # Navigate to LLM Judge tab
                print("\n5. Navigating to LLM Judge tab...")
                tabs = page.locator('[data-testid="stTab"]').all()
                print(f"   Found {len(tabs)} tabs")

                # Click on "LLM Judge" tab (should be 3rd tab, index 2)
                for i, tab in enumerate(tabs):
                    tab_text = tab.text_content()
                    print(f"   Tab {i}: {tab_text}")
                    if "LLM Judge" in tab_text or "Judge" in tab_text:
                        print(f"   Clicking on tab {i}: {tab_text}")
                        tab.click()
                        time.sleep(3)
                        break

                # Check LLM Judge content
                print("\n6. Checking LLM Judge content...")

                # Look for "Generate Evaluation" button
                generate_btns = page.locator("button:has-text('Generate')").all()
                print(f"   Found {len(generate_btns)} generate buttons")

                # Check for existing evaluations
                eval_text = page.locator("body").text_content()

                if "No LLM judge evaluation found" in eval_text:
                    print("   ⚠ No existing evaluation found")
                    print("   Need to generate one first")

                    if generate_btns:
                        print("\n7. Generating LLM evaluation...")
                        generate_btns[0].click()
                        print("   Clicked generate button, waiting for evaluation...")
                        time.sleep(5)  # Wait for generation

                        # Refresh to see results
                        page.reload()
                        time.sleep(3)

                # Check evaluation content
                print("\n8. Checking evaluation content...")

                # Look for reward value in LLM judge
                if "Reward" in eval_text or "Score" in eval_text:
                    reward_elems = page.locator("text=/Reward|Score/i").all()
                    for i, elem in enumerate(reward_elems):
                        parent_text = elem.locator("..").text_content()
                        print(f"   Reward element {i+1}: {parent_text[:150]}")

                # Check for code diffs
                print("\n9. Checking code diffs visibility...")

                # Look for "diff" or "code" sections
                diff_sections = page.locator("text=/diff|code|solution/i").all()
                print(f"   Found {len(diff_sections)} potential diff sections")

                # Check for truncation
                if "truncated" in eval_text.lower():
                    print("   ⚠ FOUND 'truncated' in evaluation!")
                    # Find context around truncated
                    truncated_elems = page.locator("text=/truncated/i").all()
                    for i, elem in enumerate(truncated_elems):
                        context = elem.locator("..").text_content()
                        print(f"   Truncated context {i+1}: {context[:200]}")

                # Check for expanders that might contain diffs
                expanders = page.locator('[data-testid="stExpander"]').all()
                print(f"\n   Found {len(expanders)} expanders")
                for i, expander in enumerate(expanders[:5]):  # Check first 5
                    header = expander.locator("summary").text_content()
                    print(f"   Expander {i+1}: {header}")

                    # Expand if it mentions code/diff/solution
                    if any(word in header.lower() for word in ["code", "diff", "solution", "test"]):
                        print(f"      Expanding to check content...")
                        expander.locator("summary").click()
                        time.sleep(1)

                        content = expander.text_content()
                        print(f"      Content length: {len(content)} chars")
                        print(f"      Preview: {content[:200]}")

                # Check for test results
                print("\n10. Checking test results...")
                if "test" in eval_text.lower():
                    test_sections = page.locator("text=/test.*result|test.*output/i").all()
                    print(f"   Found {len(test_sections)} test-related sections")
                    for i, elem in enumerate(test_sections[:3]):
                        context = elem.locator("..").text_content()
                        print(f"   Test section {i+1}: {context[:200]}")

        print("\n" + "=" * 80)
        print("INVESTIGATION COMPLETE")
        print("=" * 80)
        print("\nKey things to check:")
        print("1. Is reward displayed correctly in LLM Judge tab?")
        print("2. Are code diffs visible or just showing 'truncated'?")
        print("3. Are test results being shown?")
        print("4. What data is available in expanders?")
        print("\nPress Enter to close browser...")
        input()

        browser.close()

if __name__ == "__main__":
    investigate()
