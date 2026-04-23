"""
AS24 scraperis (Playwright).
1. Prisijungia prie AS24 portalo
2. Eina i "Degalines ir kainos"
3. Dyzelinas: kaina pagal degaline
4. AdBlue: kaina pagal sali
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
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        await page.screenshot(path=path, full_page=False)
        print(f"[AS24] Debug screenshot: {path}")
    except Exception as e:
        print(f"[AS24] Screenshot klaida: {e}")


async def close_cookies(page):
    """Uzdaro cookies/consent popup jei yra. AS24 naudoja Sourcepoint/Didomi consent."""
    try:
        # Laukiame kol atsiras consent popup
        try:
            await page.wait_for_selector(
                '#didomi-notice, [class*="consent"], [id*="consent"], [class*="didomi"], '
                '[class*="sp_message"], iframe[title*="consent" i], iframe[title*="privacy" i]',
                timeout=5000,
            )
            print("[AS24] Cookie/consent popup aptiktas")
        except Exception:
            print("[AS24] Cookie popup nepasirade per 5s, bandome toliau")

        # 1. Didomi framework mygtuku ID
        for selector in [
            '#didomi-notice-agree-button',
            '.didomi-continue-without-agreeing',
            '[data-testid="notice-agree-button"]',
        ]:
            btn = page.locator(selector)
            if await btn.count() > 0:
                await btn.first.click(force=True)
                print(f"[AS24] Cookies uzdarytas: {selector}")
                await page.wait_for_timeout(1000)
                return

        # 2. Per teksta — tiesiogiai puslapyje
        for text in [
            "Agree and close",
            "Continue without agreeing",
            "Accept all",
            "Accept",
            "Sutinku",
        ]:
            btn = page.locator(
                f'button:has-text("{text}"), a:has-text("{text}"), '
                f'[role="button"]:has-text("{text}"), span:has-text("{text}")'
            )
            if await btn.count() > 0:
                await btn.first.click(force=True)
                print(f"[AS24] Cookies uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                return

        # 3. Sourcepoint/CMP iframe — consent popup gali buti iframe viduje
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            for text in ["Agree and close", "Accept all", "Accept", "Continue without agreeing"]:
                try:
                    btn = frame.locator(
                        f'button:has-text("{text}"), a:has-text("{text}"), '
                        f'[role="button"]:has-text("{text}")'
                    )
                    if await btn.count() > 0:
                        await btn.first.click(force=True)
                        print(f"[AS24] Cookies uzdarytas (iframe): '{text}'")
                        await page.wait_for_timeout(1000)
                        return
                except Exception:
                    pass

        # 4. Bandome rasti iframe pagal src/title ir viduje spausti
        iframes = page.locator('iframe[title*="consent" i], iframe[title*="privacy" i], iframe[src*="consent"], iframe[src*="sourcepoint"], iframe[src*="didomi"]')
        iframe_count = await iframes.count()
        if iframe_count > 0:
            print(f"[AS24] Rasta {iframe_count} consent iframe(s)")
            for i in range(iframe_count):
                try:
                    frame_element = iframes.nth(i)
                    frame = await frame_element.content_frame()
                    if frame:
                        for text in ["Agree and close", "Accept", "Continue without agreeing"]:
                            btn = frame.locator(f'button:has-text("{text}")')
                            if await btn.count() > 0:
                                await btn.first.click(force=True)
                                print(f"[AS24] Cookies uzdarytas (iframe by title): '{text}'")
                                await page.wait_for_timeout(1000)
                                return
                except Exception:
                    pass

        print("[AS24] Cookies popup nerastas arba jau uzdarytas")
    except Exception as e:
        print(f"[AS24] Cookies klaida (nekritine): {e}")


async def login_as24(page):
    """Prisijungia prie AS24 portalo."""
    print(f"[AS24] Einame i {config.AS24_URL}")
    await page.goto(config.AS24_URL, wait_until="networkidle", timeout=60000)
    await debug_screenshot(page, "01_as24_login_page")

    # --- COOKIE HANDLING — butina pries pildant laukus ---
    await close_cookies(page)
    await debug_screenshot(page, "02_as24_after_cookies")

    # Isspausdiname visus input laukus
    inputs = await page.query_selector_all("input")
    for inp in inputs:
        inp_type = await inp.get_attribute("type") or ""
        inp_name = await inp.get_attribute("name") or ""
        inp_id = await inp.get_attribute("id") or ""
        inp_placeholder = await inp.get_attribute("placeholder") or ""
        print(f"[AS24] Input: type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

    all_inputs = page.locator("input:visible")
    input_count = await all_inputs.count()
    print(f"[AS24] Matomu input lauku: {input_count}")

    if input_count >= 3:
        await all_inputs.nth(0).fill(config.AS24_CLIENT_ID)
        await all_inputs.nth(1).fill(config.AS24_EMAIL)
        await all_inputs.nth(2).fill(config.AS24_PASSWORD)
    else:
        text_inputs = page.locator('input[type="text"]:visible, input[type="number"]:visible, input:not([type]):visible')
        text_count = await text_inputs.count()
        print(f"[AS24] Text input lauku: {text_count}")
        if text_count > 0:
            await text_inputs.first.fill(config.AS24_CLIENT_ID)

        email_inputs = page.locator('input[type="email"]:visible, input[type="text"]:visible')
        if await email_inputs.count() > 1:
            await email_inputs.nth(1).fill(config.AS24_EMAIL)

        pwd_inputs = page.locator('input[type="password"]:visible')
        if await pwd_inputs.count() > 0:
            await pwd_inputs.first.fill(config.AS24_PASSWORD)

    await debug_screenshot(page, "03_as24_credentials_filled")

    # Submit
    submit = page.locator('button[type="submit"], button:has-text("PRISIJUNGIMAS"), button:has-text("Prisijungimas"), button:has-text("Login")')
    submit_count = await submit.count()
    print(f"[AS24] Submit mygtuku: {submit_count}")
    if submit_count > 0:
        await submit.first.click()
    else:
        buttons = page.locator("button:visible")
        btn_count = await buttons.count()
        print(f"[AS24] Visu mygtuku: {btn_count}")
        for i in range(btn_count):
            text = (await buttons.nth(i).inner_text()).strip()
            print(f"[AS24] Mygtukas {i}: '{text}'")
        if btn_count > 0:
            await buttons.last.click()

    await page.wait_for_load_state("networkidle", timeout=30000)
    await debug_screenshot(page, "04_as24_after_login")
    print(f"[AS24] URL po prisijungimo: {page.url}")


async def navigate_to_prices(page):
    await page.wait_for_timeout(2000)
    await debug_screenshot(page, "05_as24_dashboard")

    # Isspausdiname visas nuorodas su href kad supratum struktura
    links = await page.query_selector_all("a")
    for link in links[:40]:
        text = (await link.inner_text()).strip()
        href = await link.get_attribute("href") or ""
        if text and len(text) > 2:
            print(f"[AS24] Nuoroda: '{text}' -> {href}")

    dashboard_url = page.url

    # 1. "Mano kainos" — kaire navigacija (specifiskiausias)
    mano_kainos = page.locator('a:has-text("Mano kainos")')
    if await mano_kainos.count() > 0:
        href = await mano_kainos.first.get_attribute("href") or ""
        print(f"[AS24] Mano kainos href: {href}")
        if href:
            base = "/".join(page.url.rstrip("/").split("/")[:3])
            await page.goto(base + href if href.startswith("/") else href, wait_until="networkidle", timeout=15000)
        else:
            await mano_kainos.first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(2000)
        print(f"[AS24] URL po 'Mano kainos': {page.url}")

    # Jei URL nepasikete, bandome "Degalines ir kainos" bloka
    if page.url == dashboard_url:
        degalines = page.locator('a:has-text("Degalin"), a[href*="station"], a[href*="price"], a[href*="kainos"]')
        count = await degalines.count()
        print(f"[AS24] 'Degalines' nuorodu: {count}")
        if count > 0:
            href = await degalines.first.get_attribute("href") or ""
            print(f"[AS24] Degalines href: {href}")
            await degalines.first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            await page.wait_for_timeout(2000)

    await debug_screenshot(page, "06_as24_prices_page")
    print(f"[AS24] Kainos puslapis URL: {page.url}")


async def scrape_diesel_station(page, station):
    try:
        print(f"[AS24] Ieskom degalines: {station['name']}")

        by_station = page.locator('a:has-text("pagal degalin"), button:has-text("pagal degalin"), a:has-text("by station"), a:has-text("par station")')
        if await by_station.count() > 0:
            await by_station.first.click()
            await page.wait_for_load_state("networkidle", timeout=10000)

        await page.wait_for_timeout(2000)

        search_input = page.locator('input[type="search"]:visible, input[placeholder*="search"]:visible, input[placeholder*="iesk"]:visible, input[placeholder*="paiesk"]:visible')
        if await search_input.count() > 0:
            await search_input.first.fill(station["filter"])
            await page.wait_for_timeout(2000)

        price = await extract_diesel_price(page)
        print(f"[AS24] {station['name']}: {price}")
        return price
    except Exception as e:
        print(f"[AS24] Klaida su {station['name']}: {e}")
        return None


async def extract_diesel_price(page):
    """Bando rasti dyzelino kaina lenteleje."""
    rows = await page.query_selector_all("tr")
    for row in rows:
        text = await row.inner_text()
        if "dyzelinas" in text.lower() or "diesel" in text.lower():
            cells = await row.query_selector_all("td")
            for cell in cells:
                cell_text = (await cell.inner_text()).strip()
                val = parse_price(cell_text)
                if val and 0.5 < val < 3.0:
                    return val
    return None


async def scrape_adblue_country(page, country):
    try:
        print(f"[AS24] Ieskom AdBlue: {country['name']}")

        by_country = page.locator('a:has-text("pagal sal"), button:has-text("pagal sal"), a:has-text("by country"), a:has-text("par pays")')
        if await by_country.count() > 0:
            await by_country.first.click()
            await page.wait_for_load_state("networkidle", timeout=10000)

        await page.wait_for_timeout(2000)

        country_select = page.locator('select:near(:text("Salis")), select:near(:text("Country"))')
        if await country_select.count() > 0:
            await country_select.first.select_option(label=country["country_filter"])

        product_select = page.locator('select:near(:text("Degalai")), select:near(:text("Product"))')
        if await product_select.count() > 0:
            await product_select.first.select_option(label="AdBlue")

        await page.wait_for_timeout(2000)

        price = await extract_adblue_price(page, country["zone"])
        print(f"[AS24] {country['name']}: AdBlue = {price}")
        return price
    except Exception as e:
        print(f"[AS24] Klaida su {country['name']}: {e}")
        return None


async def extract_adblue_price(page, target_zone):
    rows = await page.query_selector_all("tr")
    for row in rows:
        text = await row.inner_text()
        if "adblue" in text.lower():
            if target_zone and target_zone not in text:
                continue
            cells = await row.query_selector_all("td")
            for cell in cells:
                cell_text = (await cell.inner_text()).strip()
                val = parse_price(cell_text)
                if val and 0.1 < val < 3.0:
                    return val
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

            # Dyzelino kainos
            for station in config.AS24_DIESEL_STATIONS:
                price = await scrape_diesel_station(page, station)
                diesel_results.append({
                    "name": station["name"],
                    "country": station["country"],
                    "date": today,
                    "price": price,
                })

            # AdBlue kainos
            for country in config.AS24_ADBLUE_COUNTRIES:
                price = await scrape_adblue_country(page, country)
                adblue_results.append({
                    "name": country["name"],
                    "code": country["code"],
                    "date": today,
                    "price": price,
                })

        except Exception as e:
            print(f"[AS24] Bendra klaida: {e}")
            await debug_screenshot(page, "99_as24_error")
            raise
        finally:
            await browser.close()

    return {"diesel": diesel_results, "adblue": adblue_results}


def run_as24_scraper():
    import asyncio
    return asyncio.run(scrape_as24())


if __name__ == "__main__":
    print("=== AS24 Scraper testas ===")
    try:
        result = run_as24_scraper()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Klaida: {e}")
