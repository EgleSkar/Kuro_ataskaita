"""
AS24 cookies eksportavimas.
Paleidzia matoma narsykle - prisijunkite rankiniu budu,
skriptas pats aptiks prisijungima ir issaugos sesija.
"""
import asyncio
import base64
import json
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.async_api import async_playwright

AS24_LOGIN = "https://extranet.as24.com/extranet/lt/login"
AS24_HOME_PATTERN = "/extranet/lt/home"


async def main():
    print("=" * 60)
    print("AS24 sesijos eksportavimas")
    print("=" * 60)
    print()
    print("Naršyklė atsidaro — prisijunkite prie AS24 kaip įprastai.")
    print("Skriptas automatiškai aptiks prisijungimą.")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        print(f"Einame i: {AS24_LOGIN}")
        await page.goto(AS24_LOGIN, wait_until="networkidle", timeout=60000)

        # Uzdarome cookie/policy popup automatiskai
        await page.wait_for_timeout(2000)
        for selector in [
            '#didomi-notice-agree-button',
            'button#didomi-notice-agree-button',
            '[data-testid="notice-agree-button"]',
        ]:
            btn = page.locator(selector)
            if await btn.count() > 0:
                await btn.first.click(force=True)
                print("Cookie popup uzdarytas.")
                await page.wait_for_timeout(1000)
                break

        for text in ["Agree and close", "Accept all", "Accept", "Sutinku", "Pritariu"]:
            btn = page.locator(f'button:has-text("{text}"), a:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click(force=True)
                print(f"Cookie popup uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                break

        print("Laukiame prisijungimo (iki 5 min.)...")
        try:
            await page.wait_for_url(
                f"**{AS24_HOME_PATTERN}**",
                timeout=300000,  # 5 minutės
            )
            print(f"Prisijungimas aptiktas! URL: {page.url}")
        except Exception:
            print("Timeout — URL nepakito. Bandome eksportuoti bet kokiu atveju.")

        # Palaukiame sekundę kad sesija nusistovėtų
        await page.wait_for_timeout(2000)

        # Eksportuojame sesijos būseną (visi cookies įskaitant HttpOnly)
        storage = await context.storage_state()
        storage_json = json.dumps(storage)
        storage_b64 = base64.b64encode(storage_json.encode()).decode()

        cookies_count = len(storage.get("cookies", []))
        print(f"\nRasta cookies: {cookies_count}")

        # Išsaugome į failą
        with open("as24_storage_playwright.json", "w", encoding="utf-8") as f:
            f.write(storage_json)
        print("Išsaugota: as24_storage_playwright.json")

        # Išsaugome base64 į failą
        with open("as24_storage_b64.txt", "w", encoding="utf-8") as f:
            f.write(storage_b64)
        print("Išsaugota: as24_storage_b64.txt")
        print()
        print("=" * 60)
        print("NUKOPIJUOKITE as24_storage_b64.txt turinį į GitHub Secret:")
        print("Secret pavadinimas: AS24_STORAGE_STATE")
        print("=" * 60)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
