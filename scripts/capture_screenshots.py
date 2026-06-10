"""
scripts/capture_screenshots.py

Takes screenshots of the running AnalystIQ app and saves them to assets/
for use in the README.

Usage:
    1. Start the Streamlit app:  streamlit run ui/app.py
    2. Make sure a thread with answers exists (ask at least one question first)
    3. Run:  python scripts/capture_screenshots.py

The script uses Playwright to drive the browser headlessly.
Install once with:  pip install playwright && playwright install chromium
"""

import asyncio
import os
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install playwright first:  pip install playwright && playwright install chromium")
    raise

BASE_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
ASSETS   = Path(__file__).parent.parent / "assets"
ASSETS.mkdir(exist_ok=True)

QUESTIONS = [
    "What are the top 5 merchants by total transaction amount?",
]


async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page(viewport={"width": 1400, "height": 820})

        # ── 1. Welcome screen ──────────────────────────────────────────────────
        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        await page.screenshot(path=str(ASSETS / "01_welcome.png"), full_page=False)
        print("✓ 01_welcome.png")

        # ── 2. Ask a question and capture results ──────────────────────────────
        chat_input = page.locator("textarea[placeholder*='question']")
        if await chat_input.count() == 0:
            # Click first example button if no input visible
            btn = page.locator("button").filter(has_text="customers").first
            await btn.click()
            await asyncio.sleep(8)
        else:
            await chat_input.fill(QUESTIONS[0])
            await page.keyboard.press("Enter")
            await asyncio.sleep(10)

        await page.screenshot(path=str(ASSETS / "02_results.png"), full_page=False)
        print("✓ 02_results.png")

        # ── 3. Chart tab ───────────────────────────────────────────────────────
        chart_tab = page.locator("button[role='tab']").filter(has_text="Chart")
        if await chart_tab.count() > 0:
            await chart_tab.first.click()
            await asyncio.sleep(2)
        await page.screenshot(path=str(ASSETS / "03_chart.png"), full_page=False)
        print("✓ 03_chart.png")

        # ── 4. SQL tab ─────────────────────────────────────────────────────────
        sql_tab = page.locator("button[role='tab']").filter(has_text="SQL")
        if await sql_tab.count() > 0:
            await sql_tab.first.click()
            await asyncio.sleep(1)
        await page.screenshot(path=str(ASSETS / "04_sql.png"), full_page=False)
        print("✓ 04_sql.png")

        # ── 5. Explanation tab ─────────────────────────────────────────────────
        expl_tab = page.locator("button[role='tab']").filter(has_text="Explanation")
        if await expl_tab.count() > 0:
            await expl_tab.first.click()
            await asyncio.sleep(1)
        await page.screenshot(path=str(ASSETS / "05_explanation.png"), full_page=False)
        print("✓ 05_explanation.png")

        await browser.close()
        print(f"\nAll screenshots saved to {ASSETS}/")


if __name__ == "__main__":
    asyncio.run(capture())
