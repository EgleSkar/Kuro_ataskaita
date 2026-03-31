"""
AS24 scraperis (Playwright).
1. Prisijungia prie AS24 portalo (kliento nr + email + slaptazodis)
2. Eina i "Degalines ir kainos"
3. Dyzelinas: "Kaina pagal degaline" -> kiekvienai degalinei filtruoja ->
   ima "Suma po nuolaidu be PVM" stulpeli, eilute "Dyzelinas"
4. AdBlue: "Kaina pagal sali" -> kiekvienai saliai filtruoja AdBlue ->
   ima konkrecios zonos "Suma po nuolaidu be PVM" stulpeli
"""
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright

import config


async def login_as24(page):
    """Prisijungia prie AS24 portalo."""
    await page.goto(config.AS24_URL, wait_until="networkidle", timeout=60000)

    await page.fill(
        'input[name*="client"], input[id*="client"], input[placeholder*="Kliento"]',
        config.AS24_CLIENT_ID,
    )
    await page.fill(
        'input[type="email"], input[name*="email"], input[placeholder*="pasto"]',
        config.AS24_EMAIL,
    )
    await page.fill(
        'input[type="password"]',
        config.AS24_PASSWORD,
    )

    await page.click('button:has-text("PRISIJUNGIMAS"), button[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=30000)
    print("[AS24] Prisijungta")


async def navigate_to_prices(page):
    """Naviguoja i 'Degalines ir kainos' skilti."""
    await page.click('text="Degalines ir kainos"', timeout=10000)
    await page.wait_for_load_state("networkidle")
    print("[AS24] Atidaryta 'Degalines ir kainos'")


async def scrape_diesel_station(page, station):
    """
    Nuskaito dyzelino kaina konkreciai degalinei.
    """
    try:
        await page.click('text="Kaina pagal degaline"', timeout=10000)
        await page.wait_for_load_state("networkidle")

        try:
            await page.click('text="Degalines pavadinimas"', timeout=3000)
            await page.wait_for_timeout(500)
            await page.fill(
                'input[type="search"], input[placeholder*="paieska"], input[placeholder*="Ieskoti"]',
                station["filter"],
            )
            await page.wait_for_timeout(1000)
            await page.click(f'text="{station["filter"]}"', timeout=5000)
        except Exception:
            try:
                await page.click("text=Filtrai", timeout=3000)
                await page.fill("input", station["filter"])
                await page.keyboard.press("Enter")
            except Exception:
                pass

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        price = await extract_price_from_table(
            page, "Dyzelinas", "Suma po nuolaid"
        )

        print(f"[AS24] {station['name']}: Dyzelinas = {price} EUR/l")
        return price

    except Exception as e:
        print(f"[AS24] Klaida su {station['name']}: {e}")
        return None


async def scrape_adblue_country(page, country):
    """
    Nuskaito AdBlue kaina konkreciai saliai.
    """
    try:
        await page.click('text="Kaina pagal sali"', timeout=10000)
        await page.wait_for_load_state("networkidle")

        try:
            await page.click('text="Salis"', timeout=3000)
            await page.wait_for_timeout(500)
            await page.click(f'text="{country["country_filter"]}"', timeout=5000)
        except Exception:
            pass

        try:
            await page.click('text="Degalai"', timeout=3000)
            await page.wait_for_timeout(500)
            await page.click('text="AdBlue"', timeout=5000)
        except Exception:
            pass

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        price = await extract_adblue_price_by_zone(page, country["zone"])

        print(f"[AS24] {country['name']}: AdBlue (zona {country['zone']}) = {price} EUR/l")
        return price

    except Exception as e:
        print(f"[AS24] Klaida su {country['name']}: {e}")
        return None


async def extract_price_from_table(page, product_name, price_column):
    """
    Universali funkcija — iesko lenteleje eilutes su produktu ir
    grazina reiksme is nurodyto stulpelio.
    """
    rows = await page.query_selector_all("tr")

    headers = []
    for row in rows:
        ths = await row.query_selector_all("th")
        if ths:
            for th in ths:
                text = (await th.inner_text()).strip()
                headers.append(text)
            break

    price_col_idx = None
    for i, h in enumerate(headers):
        if price_column.lower() in h.lower():
            price_col_idx = i
            break

    for row in rows:
        text = await row.inner_text()
        if product_name.lower() in text.lower():
            cells = await row.query_selector_all("td")
            if price_col_idx is not None and price_col_idx < len(cells):
                cell_text = (await cells[price_col_idx].inner_text()).strip()
                return parse_price(cell_text)
            else:
                for cell in cells:
                    cell_text = (await cell.inner_text()).strip()
                    val = parse_price(cell_text)
                    if val and 0.1 < val < 5.0:
                        return val

    return None


async def extract_adblue_price_by_zone(page, target_zone):
    """
    Iesko AdBlue kainos konkrechioje zonoje.
    """
    rows = await page.query_selector_all("tr")

    headers = []
    for row in rows:
        ths = await row.query_selector_all("th")
        if ths:
            for th in ths:
                text = (await th.inner_text()).strip()
                headers.append(text)
            break

    price_col_idx = None
    zone_col_idx = None
    for i, h in enumerate(headers):
        if "suma po nuolaid" in h.lower() and "be pvm" in h.lower():
            price_col_idx = i
        if "zona" in h.lower() or "kainos zona" in h.lower():
            zone_col_idx = i

    for row in rows:
        cells = await row.query_selector_all("td")
        if not cells:
            continue

        row_text = await row.inner_text()
        if "adblue" not in row_text.lower():
            continue

        if zone_col_idx is not None and zone_col_idx < len(cells):
            zone_text = (await cells[zone_col_idx].inner_text()).strip()
            if target_zone and target_zone != zone_text:
                continue

        if price_col_idx is not None and price_col_idx < len(cells):
            cell_text = (await cells[price_col_idx].inner_text()).strip()
            return parse_price(cell_text)

    return None


def parse_price(text):
    """Konvertuoja teksto formata '1,5131 EUR/L' i float."""
    if not text:
        return None
    cleaned = re.sub(r"[€/L\s]", "", text).replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


async def scrape_as24():
    """
    Pagrindine AS24 scrapinimo funkcija.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    diesel_results = []
    adblue_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = None
        if os.path.exists(config.AS24_COOKIES):
            try:
                context = await browser.new_context(
                    storage_state=config.AS24_COOKIES
                )
            except Exception:
                context = None

        if context is None:
            context = await browser.new_context()

        page = await context.new_page()

        try:
            await login_as24(page)

            os.makedirs(config.COOKIES_DIR, exist_ok=True)
            await context.storage_state(path=config.AS24_COOKIES)

            await navigate_to_prices(page)

            # -- Dyzelino kainos pagal degalines --
            for station in config.AS24_DIESEL_STATIONS:
                price = await scrape_diesel_station(page, station)
                diesel_results.append(
                    {
                        "name": station["name"],
                        "country": station["country"],
                        "date": today,
                        "price": price,
                    }
                )

            # -- AdBlue kainos pagal salis --
            for country in config.AS24_ADBLUE_COUNTRIES:
                price = await scrape_adblue_country(page, country)
                adblue_results.append(
                    {
                        "name": country["name"],
                        "code": country["code"],
                        "date": today,
                        "price": price,
                    }
                )

        except Exception as e:
            print(f"[AS24] Bendra klaida: {e}")
            os.makedirs("debug", exist_ok=True)
            await page.screenshot(path="debug/as24_error.png")
            raise

        finally:
            await browser.close()

    return {"diesel": diesel_results, "adblue": adblue_results}


def run_as24_scraper():
    """Sinchroninis wrapperis."""
    import asyncio
    return asyncio.run(scrape_as24())


if __name__ == "__main__":
    print("=== AS24 Scraper testas ===")
    try:
        result = run_as24_scraper()
        print(f"Dyzelinas: {json.dumps(result['diesel'], indent=2, ensure_ascii=False)}")
        print(f"AdBlue: {json.dumps(result['adblue'], indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Klaida: {e}")
