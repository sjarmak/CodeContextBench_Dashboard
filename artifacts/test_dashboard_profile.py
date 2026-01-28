#!/usr/bin/env python3
"""Test dashboard profile runner with Playwright."""
import asyncio
from playwright.async_api import async_playwright
import sys

async def test_profile_runner():
    """Navigate to profile runner and check for errors."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to dashboard
        print("Navigating to dashboard...")
        await page.goto("http://localhost:8501")

        # Wait for page to load
        await page.wait_for_timeout(3000)

        # Click on Evaluation Runner
        print("Clicking Evaluation Runner...")
        try:
            await page.get_by_role("button", name="Evaluation Runner").click()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Error clicking Evaluation Runner: {e}")
            # Try alternative selector
            await page.click("text=Evaluation Runner")
            await page.wait_for_timeout(2000)

        # Click on Profile Run tab
        print("Clicking Profile Run tab...")
        try:
            await page.get_by_role("tab", name="Profile Run").click()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Error clicking Profile Run tab: {e}")
            # Try alternative
            await page.click("text=Profile Run")
            await page.wait_for_timeout(2000)

        # Check for error messages
        print("\nChecking for error messages...")
        error_elements = await page.query_selector_all("[data-testid='stException']")
        if error_elements:
            print(f"Found {len(error_elements)} error(s):")
            for i, elem in enumerate(error_elements, 1):
                text = await elem.inner_text()
                print(f"\nError {i}:")
                print(text)
        else:
            print("No errors found!")

        # Check for warning messages
        warning_elements = await page.query_selector_all("[data-testid='stAlert']")
        if warning_elements:
            print(f"\nFound {len(warning_elements)} warning/info message(s):")
            for i, elem in enumerate(warning_elements, 1):
                text = await elem.inner_text()
                print(f"\nMessage {i}:")
                print(text)

        # Check if profile selector exists
        print("\nChecking for profile selector...")
        try:
            selector = await page.query_selector("select")
            if selector:
                options = await selector.inner_text()
                print(f"Selector found with options:\n{options}")
            else:
                print("No selector found")
        except Exception as e:
            print(f"Error checking selector: {e}")

        # Take screenshot
        await page.screenshot(path="/tmp/dashboard_profile_runner.png")
        print("\nScreenshot saved to /tmp/dashboard_profile_runner.png")

        # Keep browser open for inspection
        print("\nBrowser will stay open for 30 seconds for inspection...")
        await page.wait_for_timeout(30000)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_profile_runner())
