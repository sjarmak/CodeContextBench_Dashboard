#!/usr/bin/env python3
"""
Playwright test script for dashboard navigation and functionality.

Tests all major views and reports any errors encountered.
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


def test_dashboard(base_url: str = "http://localhost:8501", headless: bool = True):
    """Test dashboard navigation and functionality.
    
    Args:
        base_url: Dashboard URL
        headless: Run browser in headless mode
    
    Returns:
        dict with test results
    """
    results = {
        "pages_tested": [],
        "errors": [],
        "warnings": [],
        "passed": 0,
        "failed": 0,
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        # Track console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        def test_page(name: str, nav_action: callable, expected_text: str = None):
            """Test a single page."""
            print(f"\n{'='*60}")
            print(f"Testing: {name}")
            print(f"{'='*60}")
            
            try:
                nav_action()
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)  # Give Streamlit time to render
                
                # Check for Python errors in page content
                content = page.content()
                
                error_indicators = [
                    "ModuleNotFoundError",
                    "ImportError", 
                    "AttributeError",
                    "TypeError",
                    "NameError",
                    "KeyError",
                    "no such table",
                    "Traceback (most recent call last)",
                    "Error:",
                ]
                
                found_errors = []
                for indicator in error_indicators:
                    if indicator in content:
                        # Extract error context
                        idx = content.find(indicator)
                        snippet = content[max(0, idx-50):idx+200]
                        # Clean HTML
                        snippet = snippet.replace("<", " <").replace(">", "> ")
                        found_errors.append(f"{indicator}: ...{snippet[:150]}...")
                
                if found_errors:
                    results["errors"].append({
                        "page": name,
                        "errors": found_errors
                    })
                    results["failed"] += 1
                    print(f"  ❌ FAILED - Found errors:")
                    for err in found_errors[:3]:
                        print(f"     {err[:100]}")
                else:
                    results["passed"] += 1
                    print(f"  ✅ PASSED")
                
                # Take screenshot
                screenshot_dir = Path(__file__).parent.parent / "dashboard" / "tests" / "screenshots"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                safe_name = name.lower().replace(" ", "_").replace("/", "_")
                page.screenshot(path=str(screenshot_dir / f"{safe_name}.png"))
                
                results["pages_tested"].append(name)
                
            except PlaywrightTimeout as e:
                results["errors"].append({
                    "page": name,
                    "errors": [f"Timeout: {str(e)}"]
                })
                results["failed"] += 1
                print(f"  ❌ TIMEOUT")
            except Exception as e:
                results["errors"].append({
                    "page": name,
                    "errors": [str(e)]
                })
                results["failed"] += 1
                print(f"  ❌ ERROR: {e}")
        
        # Navigate to dashboard
        print(f"\nConnecting to {base_url}...")
        page.goto(base_url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)  # Initial load
        
        # Test Home page
        test_page("Home", lambda: None, "CodeContextBench")
        
        # Define sidebar navigation items to test
        nav_items = [
            ("Benchmark Manager", "Benchmark Manager"),
            ("Run Results", "Run Results"),
            ("Analysis Hub", "Analysis Hub"),
            ("Comparison Analysis", "Comparison Analysis"),
            ("Cost Analysis", "Cost Analysis"),
            ("Statistical Analysis", "Statistical Analysis"),
            ("Failure Analysis", "Failure Analysis"),
            ("Time Series", "Time Series"),
        ]
        
        def click_sidebar_button(button_text: str):
            """Click a button in the sidebar."""
            # Streamlit buttons are in the sidebar
            try:
                # Try to find button by text
                button = page.locator(f"button:has-text('{button_text}')")
                if button.count() > 0:
                    button.first.click()
                    return True
                
                # Try with partial match
                button = page.locator(f"button").filter(has_text=button_text)
                if button.count() > 0:
                    button.first.click()
                    return True
                
                # Try sidebar links
                link = page.locator(f"a:has-text('{button_text}')")
                if link.count() > 0:
                    link.first.click()
                    return True
                
                print(f"  Warning: Could not find button '{button_text}'")
                return False
            except Exception as e:
                print(f"  Warning: Click failed for '{button_text}': {e}")
                return False
        
        # Test each navigation item
        for nav_name, button_text in nav_items:
            test_page(nav_name, lambda bt=button_text: click_sidebar_button(bt))
        
        # Also test Evaluation Runner
        test_page("Evaluation Runner", lambda: click_sidebar_button("Evaluation Runner"))
        
        # Test Add Benchmark
        test_page("Add Benchmark", lambda: click_sidebar_button("Add Benchmark"))
        
        browser.close()
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Pages tested: {len(results['pages_tested'])}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    
    if results["errors"]:
        print(f"\nErrors found:")
        for error in results["errors"]:
            print(f"\n  Page: {error['page']}")
            for err in error["errors"][:2]:
                print(f"    - {err[:100]}")
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test dashboard with Playwright")
    parser.add_argument("--url", default="http://localhost:8501", help="Dashboard URL")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    
    args = parser.parse_args()
    
    results = test_dashboard(args.url, headless=not args.headed)
    
    # Exit with error code if failures
    return 1 if results["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
