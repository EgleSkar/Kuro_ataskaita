"""
AS24 scraperis (Playwright).
"""
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
import config

DEBUG_DIR = "debug"

async def debug_screenshot(page, name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    try:
        await page.screenshot(path=f"{DEBUG_DIR}/{name}.png", full_page=False)
        print(f"[AS24] Screenshot: {name}")
    except Exception as e:
        print(f"[AS24] Screenshot klaida: {e}")

async def close_cookies(page):
    """Uzdaro cookies/consent popup jei yra."""
    try:
        # AS24 consent popup - "Agree and close"
        for text in ["Agree and close", "Continue without agreeing", "Accept", "Sutinku", "Accept all"]:
            btn = page.locator(f'button:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[AS24] Cookies uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                return
        # Generic consent
        consent = page.locator('button[id*="consent"], button[id*="agree"], .consent-accept, #didomi-notice-agree-button')
        if await consent.count() > 0:
            await consent.first.click()
            print("[AS24] Cookies uzdarytas (generic)")
            await page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[AS24] Cookies klaida: {e}")

async def login_as24(page):
    print(f"[AS24] URL: {config.AS24_URL}")
    await page.goto(config.AS24_URL, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(2000)
    await debug_screenshot(page, "01_as24_landing")

    # Cookies popup
    await close_cookies(page)
    await page.wait_for_timeout(1000)
    await debug_screenshot(page, "02_after_cookies")

    # Ieskom input lauku
    all_inputs = page.locator("input:visible")
    input_count = await all_inputs.count()
    print(f"[AS24] Matomu input: {input_count}")

    # Isspausdiname input laukus
    for i in range(min(input_count, 10)):
        inp = all_inputs.nth(i)
        inp_type = await inp.get_attribute("type") or ""
        inp_name = await inp.get_attribute("name") or ""
        inp_placeholder = await inp.get_attribute("placeholder") or ""
        inp_label = await inp.get_attribute("aria-label") or ""
        print(f"[AS24] Input[{i}]: type={inp_type} name={inp_name} ph={inp_placeholder} label={inp_label}")

    if input_count >= 3:
        # Pirmas - kliento numeris, antras - email, trecias - password
        await all_inputs.nth(0).fill(config.AS24_CLIENT_ID)
        await all_inputs.nth(1).fill(config.AS24_EMAIL)
        await all_inputs.nth(2).fill(config.AS24_PASSWORD)
        print("[AS24] Kredencialai ivesti (pagal eiliskuma)")
    elif input_count >= 1:
        # Bandome pagal tipa
        for i in range(input_count):
            inp_type = await all_inputs.nth(i).get_attribute("type") or ""
            if inp_type == "password":
                await all_inputs.nth(i).fill(config.AS24_PASSWORD)
            elif "email" in inp_type or "mail" in (await all_inputs.nth(i).get_attribute("name") or ""):
                await all_inputs.nth(i).fill(config.AS24_EMAIL)
            elif inp_type in ["text", "number", "tel", ""]:
                await all_inputs.nth(i).fill(config.AS24_CLIENT_ID)

    await debug_screenshot(page, "03_credentials")

    # Submit
    submit = page.locator('button:has-text("PRISIJUNGIMAS"), button:has-text("Prisijungimas"), button:has-text("Login"), button[type="submit"]')
    if await submit.count() > 0:
        await submit.first.click()
        print("[AS24] Submit paspaustas")
    else:
        # Bandome bet koki mygtuka puslapyje
        buttons = page.locator("button:visible")
        for i in range(await buttons.count()):
            text = (await buttons.nth(i).inner_text()).strip()
            if text and len(text) > 2 and text not in ["Learn More", "Agree and close"]:
                print(f"[AS24] Mygtukas: '{text}'")

    await page.wait_for_load_state("networkidle", timeout=30000)
    await page.wait_for_timeout(3000)
    await debug_screenshot(page, "04_after_login")
    print(f"[AS24] URL po login: {page.url}")

async def navigate_to_prices(page):
    await page.wait_for_timeout(2000)
    
    # Ieskom "Degalines ir kainos"
    prices = page.locator('a:has-text("Degalin"), a:has-text("kainos"), a:has-text("Prices"), a:has-text("Station")')
    count = await prices.count()
    print(f"[AS24] Kainos nuorodu: {count}")
    
    if count > 0:
        # Spausdiname visas rastas nuorodas
        for i in range(count):
            text = (await prices.nth(i).inner_text()).strip()
            print(f"[AS24] Kainos link[{i}]: '{text}'")
        await prices.first.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(2000)
    
    await debug_screenshot(page, "05_prices_page")
    print(f"[AS24] Kainos URL: {page.url}")

    # Dar karta links
    links = await page.query_selector_all("a")
    for link in links[:40]:
        text = (await link.inner_text()).strip()
        if text and len(text) > 2:
            print(f"[AS24] Link: '{text}'")

async def scrape_diesel_station(page, station):
    try:
        # Kaina pagal degaline
        by_station = page.locator('a:has-text("pagal degalin"), button:has-text("pagal degalin")')
        if await by_station.count() > 0:
            await by_station.first.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.wait_for_timeout(1000)

        # Filtras
        search = page.locator('input[type="search"]:visible, input[placeholder*="iesk"]:visible')
        if await search.count() > 0:
            await search.first.fill(station["filter"])
            await page.wait_for_timeout(2000)

        # Kaina
        rows = await page.query_selector_all("tr")
        for row in rows:
            text = await row.inner_text()
            if "dyzelinas" in text.lower() or "diesel" in text.lower():
                cells = await row.query_selector_all("td")
                for cell in cells:
                    ct = (await cell.inner_text()).strip()
                    val = parse_price(ct)
                    if val and 0.5 < val < 3.0:
                        print(f"[AS24] {station['name']}: {val}")
                        return val
        print(f"[AS24] {station['name']}: kaina nerasta")
        return None
    except Exception as e:
        print(f"[AS24] {station['name']} klaida: {e}")
        return None

async def scrape_adblue_country(page, country):
    try:
        by_country = page.locator('a:has-text("pagal sal"), button:has-text("pagal sal")')
        if await by_country.count() > 0:
            await by_country.first.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.wait_for_timeout(1000)

        rows = await page.query_selector_all("tr")
        for row in rows:
            text = await row.inner_text()
            if "adblue" in text.lower():
                if country["zone"] and country["zone"] not in text:
                    continue
                cells = await row.query_selector_all("td")
                for cell in cells:
                    ct = (await cell.inner_text()).strip()
                    val = parse_price(ct)
                    if val and 0.1 < val < 3.0:
                        print(f"[AS24] {country['name']}: AdBlue={val}")
                        return val
        print(f"[AS24] {country['name']}: AdBlue nerasta")
        return None
    except Exception as e:
        print(f"[AS24] {country['name']} klaida: {e}")
        return None

def parse_price(text):
    if not text:
        return None
    cleaned = re.sub(r"[€/L\s]", "", text).replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None

async def scrape_as24():
    today = datetime.now().strftime("%Y-%m-%d")
    diesel_results = []
    adblue_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            await login_as24(page)
            await navigate_to_prices(page)

            # Pirma degaline - debug
            if config.AS24_DIESEL_STATIONS:
                await debug_screenshot(page, "06_before_diesel")

            for station in config.AS24_DIESEL_STATIONS:
                price = await scrape_diesel_station(page, station)
                diesel_results.append({
                    "name": station["name"],
                    "country": station["country"],
                    "date": today,
                    "price": price,
                })

            await debug_screenshot(page, "07_after_diesel")

            for country in config.AS24_ADBLUE_COUNTRIES:
                price = await scrape_adblue_country(page, country)
                adblue_results.append({
                    "name": country["name"],
                    "code": country["code"],
                    "date": today,
                    "price": price,
                })

            await debug_screenshot(page, "08_final")

        except Exception as e:
            print(f"[AS24] Bendra klaida: {e}")
            await debug_screenshot(page, "99_error")
            raise
        finally:
            await browser.close()

    return {"diesel": diesel_results, "adblue": adblue_results}

def run_as24_scraper():
    import asyncio
    return asyncio.run(scrape_as24())

if __name__ == "__main__":
    result = run_as24_scraper()
    print(json.dumps(result, indent=2, ensure_ascii=False))
