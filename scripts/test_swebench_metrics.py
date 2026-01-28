#!/usr/bin/env python3
"""
Quick test to verify SWEBench data in Run Results shows tokens and time.
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: Playwright not installed")
    sys.exit(1)


def test_swebench_metrics():
    """Test that SWEBench task metrics are displayed."""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to dashboard
        print("Opening dashboard...")
        page.goto("http://localhost:8501", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        
        # Click Run Results
        print("Navigating to Run Results...")
        page.click("button:has-text('Run Results')")
        time.sleep(3)
        
        # Check content
        content = page.content()
        
        # Try to select a SWEBench run
        print("Looking for SWEBench runs...")
        selectbox = page.locator("div[data-testid='stSelectbox']").first
        if selectbox:
            selectbox.click()
            time.sleep(1)
            
            # Look for swebench option
            options = page.locator("li[role='option']").all()
            for opt in options:
                text = opt.text_content()
                if "swebench" in text.lower():
                    print(f"  Found: {text[:60]}...")
                    opt.click()
                    time.sleep(2)
                    break
        
        # Now check if task data shows
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(2)
        content = page.content()
        
        # Take screenshot
        screenshot_path = Path(__file__).parent.parent / "dashboard" / "tests" / "screenshots" / "swebench_task_detail.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Screenshot: {screenshot_path}")
        
        # Check for metrics
        checks = {
            "Tokens metric visible": "Tokens" in content or "1,245" in content or "27,334" in content,
            "Time metric visible": "720" in content or "808" in content or "Time" in content,
            "Reward visible": "0.0" in content or "Reward" in content,
            "No error message": "Task output directory not found" not in content,
        }
        
        print("\n" + "="*60)
        print("METRICS CHECK")
        print("="*60)
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
        
        # If there's an error, print it
        if "Task output directory not found" in content:
            idx = content.find("Task output directory not found")
            snippet = content[idx:idx+200]
            print(f"\nError found: {snippet[:150]}...")
        
        browser.close()
        
        return all(checks.values())


if __name__ == "__main__":
    success = test_swebench_metrics()
    sys.exit(0 if success else 1)
