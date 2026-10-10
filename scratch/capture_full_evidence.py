import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path(r"C:\Users\manid\.gemini\antigravity-ide\brain\f318dea3-d3bb-419d-9ed3-48ae0dc46f4a")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Landing Page
        print("Capturing Landing Page...")
        await page.goto("http://localhost:8100/", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_no_emoji_landing.png"))

        # 2. Cockpit Overview
        print("Capturing Cockpit Overview...")
        await page.click(".btn-cockpit-link")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_no_emoji_overview.png"))

        # 3. Station 01 Receiving
        print("Capturing Station 01 Receiving...")
        await page.click('[data-route="receiving"]')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_station_01_receiving.png"))

        # 4. Station 02 Prep (with Upstream Input from Receiving)
        print("Capturing Station 02 Prep...")
        await page.click('[data-route="prep"]')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_station_02_prep_upstream.png"))

        # 5. Station 03 Pack (with Upstream Input from Prep)
        print("Capturing Station 03 Pack...")
        await page.click('[data-route="pack"]')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_station_03_pack_upstream.png"))

        # 6. Station 04 Returns (with Upstream Baseline Proof from Prep & Pack)
        print("Capturing Station 04 Returns...")
        await page.click('[data-route="returns"]')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_station_04_returns_upstream.png"))

        # 7. Station 05 Recovery (with Complete 4-stage Upstream Synthesized Chain)
        print("Capturing Station 05 Recovery...")
        await page.click('[data-route="recovery"]')
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(ARTIFACT_DIR / "nexa_station_05_recovery_chain.png"))

        # 8. Mobile Scanner
        print("Capturing Mobile Handheld Scanner...")
        mobile_context = await browser.new_context(viewport={"width": 412, "height": 840}, user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
        mobile_page = await mobile_context.new_page()
        await mobile_page.goto("http://localhost:8100/scanner?stage=prep", wait_until="networkidle")
        await mobile_page.wait_for_timeout(800)
        await mobile_page.screenshot(path=str(ARTIFACT_DIR / "nexa_scanner_prep_selected.png"))

        await browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    asyncio.run(main())
