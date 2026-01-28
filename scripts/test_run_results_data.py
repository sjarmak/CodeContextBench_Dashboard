#!/usr/bin/env python3
"""
Test that the Run Results view shows our imported SWEBench evaluation data.
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright not installed")
    sys.exit(1)


def test_run_results_data(base_url: str = "http://localhost:8501"):
    """Test that Run Results displays SWEBench imported data."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to dashboard
        print("Navigating to dashboard...")
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Click Run Results
        print("Navigating to Run Results...")
        button = page.locator("button:has-text('Run Results')").first
        button.click()
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Check for our imported runs
        content = page.content()
        
        checks = {
            "SWEBenchPro run visible": "swebench" in content.lower(),
            "Navidrome task visible": "navidrome" in content.lower(),
            "Run selector present": "Select Run" in content,
        }
        
        print("\n" + "="*60)
        print("RUN RESULTS DATA CHECK")
        print("="*60)
        
        all_passed = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
        
        # Take screenshot
        screenshot_path = Path(__file__).parent.parent / "dashboard" / "tests" / "screenshots" / "run_results_data_check.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\nScreenshot saved: {screenshot_path}")
        
        # Try to select a specific run
        print("\nTrying to interact with run selector...")
        
        # Look for selectbox and check options
        selectboxes = page.locator("div[data-testid='stSelectbox']").all()
        if selectboxes:
            print(f"  Found {len(selectboxes)} selectbox(es)")
            
            # Get the text content to see run options
            for i, box in enumerate(selectboxes):
                text = box.text_content()
                if "swebench" in text.lower():
                    print(f"  ✅ Selectbox {i} contains SWEBench runs")
        else:
            print("  ⚠️ No selectboxes found")
        
        browser.close()
        
        return all_passed


if __name__ == "__main__":
    success = test_run_results_data()
    sys.exit(0 if success else 1)
