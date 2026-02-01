#!/usr/bin/env python3
"""Simple dashboard test to check tabs."""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto("http://localhost:8501")
        await page.wait_for_timeout(5000)

        # Click Evaluation Runner
        print("Looking for Evaluation Runner button...")
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = await btn.inner_text()
            if "Evaluation Runner" in text:
                print(f"Found button: {text}")
                await btn.click()
                break

        await page.wait_for_timeout(3000)

        # Look for tabs
        print("\nLooking for tabs...")
        tabs = await page.query_selector_all("[role='tab']")
        print(f"Found {len(tabs)} tabs")
        for tab in tabs:
            text = await tab.inner_text()
            print(f"  Tab: {text}")

        # Check page content
        print("\nPage content contains:")
        content = await page.content()
        if "Profile Run" in content:
            print("  ✓ 'Profile Run' found in page")
        else:
            print("  ✗ 'Profile Run' NOT found in page")

        if "Single Run" in content:
            print("  ✓ 'Single Run' found in page")
        else:
            print("  ✗ 'Single Run' NOT found in page")

        # Take screenshot
        await page.screenshot(path="/tmp/dashboard_test.png")
        print("\nScreenshot: /tmp/dashboard_test.png")

        print("\nKeeping browser open for 20 seconds...")
        await page.wait_for_timeout(20000)

        await browser.close()

asyncio.run(test())
