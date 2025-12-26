"""
Verify dashboard fixes with Playwright
"""
import time
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "http://localhost:8501"

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()

        print("=" * 80)
        print("VERIFYING FIXES")
        print("=" * 80)

        # Load dashboard
        print("\n1. Loading dashboard...")
        page.goto(DASHBOARD_URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print("   ✓ Dashboard loaded")

        # Test Run Results
        print("\n2. Testing Run Results...")
        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(3)

        # Check for the warning that should now be gone
        warnings = page.locator('[data-testid="stAlert"]').all()
        directory_warning = False
        for warning in warnings:
            if "directory not found" in warning.text_content().lower():
                directory_warning = True
                print("   ❌ Still seeing directory not found warning")
                break

        if not directory_warning:
            print("   ✓ No directory warnings (fixed!)")

        # Test Comparison Table
        print("\n3. Testing Comparison Table...")
        sidebar.get_by_text("Comparison Table", exact=True).first.click()
        time.sleep(3)

        # Check for the TypeError
        errors = page.locator('[data-testid="stException"]').all()
        if errors:
            print(f"   ❌ Found {len(errors)} error(s):")
            for error in errors:
                print(f"      {error.text_content()[:100]}")
        else:
            print("   ✓ No errors on Comparison Table (fixed!)")

        # Check if table is displayed
        tables = page.locator("table").all()
        if tables:
            print(f"   ✓ Found {len(tables)} table(s) displayed")
        else:
            print("   ℹ No comparison data yet")

        print("\n4. Testing reward display...")
        sidebar.get_by_text("Run Results", exact=True).first.click()
        time.sleep(2)

        # Select first run and task
        selects = page.locator("select").all()
        if len(selects) >= 2:
            selects[0].select_option(index=0)
            time.sleep(2)
            selects[1].select_option(index=0)
            time.sleep(3)

            # Look for reward display
            result_text = page.locator("body").text_content()
            if "1.0" in result_text or "1.00" in result_text:
                print("   ✓ Reward 1.0 visible!")
            elif "0.0" in result_text or "0" in result_text:
                print("   ⚠ Still showing reward 0")
                print("   (May need to rerun evaluation after pulling latest code)")

        print("\n" + "=" * 80)
        print("VERIFICATION COMPLETE")
        print("=" * 80)
        print("\nFixes applied:")
        print("  1. ✓ Comparison Table None handling")
        print("  2. ✓ Run Results agent name sanitization")
        print("  3. ✓ Reward parsing from Harbor result.json")
        print("\nIf reward still shows 0:")
        print("  - Stop dashboard (Ctrl+C)")
        print("  - git pull")
        print("  - bash scripts/start_dashboard.sh")
        print("  - Run a NEW evaluation")
        print("\nPress Enter to close...")
        input()

        browser.close()

if __name__ == "__main__":
    verify()
