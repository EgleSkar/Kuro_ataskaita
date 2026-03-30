"""
AS24 scraperis (Playwright).
1. Prisijungia prie AS24 portalo (kliento nr + email + slaptažodis)
2. Eina į "Degalinės ir kainos"
3. Dyzelinas: "Kaina pagal degalinę" → kiekvienai degalinei filtruoja → 
   ima "Suma po nuolaidų be PVM" stulpelį, eilutė "Dyzelinas"
4. AdBlue: "Kaina pagal šalį" → kiekvienai šaliai filtruoja AdBlue → 
   ima konkrečios zonos "Suma po nuolaidų be PVM" stulpelį
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

    # Pildome prisijungimo formą
    # Kliento numeris
    await page.fill(
        'input[name*="client"], input[id*="client"], input[placeholder*="Kliento"]',
        config.AS24_CLIENT_ID,
    )
    # El. paštas
    await page.fill(
        'input[type="email"], input[name*="email"], input[placeholder*="pašto"]',
        config.AS24_EMAIL,
    )
    # Slaptažodis
    await page.fill(
        'input[type="password"]',
        config.AS24_PASSWORD,
    )

    # Spaudžiame "PRISIJUNGIMAS"
    await page.click('button:has-text("PRISIJUNGIMAS"), button[type="submit"]')
    await page.wait_for_load_state("networkidle", timeout=30000)
    print("[AS24] Prisijungta")


async def navigate_to_prices(page):
    """Naviguoja į 'Degalinės ir kainos' skiltį."""
    await page.click('text="Degalinės ir kainos"', timeout=10000)
    await page.wait_for_load_state("networkidle")
    print("[AS24] Atidaryta 'Degalinės ir kainos'")


async def scrape_diesel_station(page, station):
    """
    Nuskaito dyzelino kainą konkrečiai degalinei.
    Eina: Kaina pagal degalinę → filtruoja degalinės pavadinimą →
    ima Dyzelinas eilutės "Suma po nuolaidų be PVM" reikšmę.
    """
    try:
        # Spaudžiame "Kaina pagal degalinę"
        await page.click('text="Kaina pagal degalinę"', timeout=10000)
        await page.wait_for_load_state("networkidle")

        # Filtruojame pagal degalinės pavadinimą
        # Ieškome "Degalinės pavadinimas" filtro
        filter_input = page.locator(
            'input[placeholder*="degalin"], select:near(:text("Degalinės pavadinimas"))'
        )

        # Bandome dropdown arba paieškos lauką
        try:
            # Pirmiausia bandome paspausti dropdown
            await page.click('text="Degalinės pavadinimas"', timeout=3000)
            await page.wait_for_timeout(500)

            # Ieškome ir pasirenkame degalinę
            await page.fill(
                'input[type="search"], input[placeholder*="paieška"], input[placeholder*="Ieškoti"]',
                station["filter"],
            )
            await page.wait_for_timeout(1000)

            # Pasirenkame iš sąrašo
            await page.click(f'text="{station["filter"]}"', timeout=5000)
        except Exception:
            # Alternatyvus būdas — per filtrą
            try:
                await page.click("text=Filtrai", timeout=3000)
                await page.fill('input', station["filter"])
                await page.keyboard.press("Enter")
            except Exception:
                pass

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Nuskaitome lentelę
        price = await extract_price_from_table(
            page, "Dyzelinas", "Suma po nuolaidų be PVM"
        )

        if price is None:
            # Alternatyvus bandymas — ieškome bet kokios eilutės su "Dyzelinas"
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
    Nuskaito AdBlue kainą konkrečiai šaliai.
    Eina: Kaina pagal šalį → filtruoja šalį + AdBlue →
    ima konkrečios zonos "Suma po nuolaidų be PVM" reikšmę.
    """
    try:
        # Spaudžiame "Kaina pagal šalį"
        await page.click('text="Kaina pagal šalį"', timeout=10000)
        await page.wait_for_load_state("networkidle")

        # Filtruojame šalį
        try:
            # Šalies dropdown
            await page.click('text="Šalis"', timeout=3000)
            await page.wait_for_timeout(500)

            # Pasirenkame šalį
            await page.click(f'text="{country["country_filter"]}"', timeout=5000)
        except Exception:
            pass

        # Filtruojame produktą — AdBlue
        try:
            await page.click('text="Degalai"', timeout=3000)
            await page.wait_for_timeout(500)
            await page.click('text="AdBlue"', timeout=5000)
        except Exception:
            pass

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Nuskaitome lentelę — ieškome konkrečios zonos
        price = await extract_adblue_price_by_zone(page, country["zone"])

        print(f"[AS24] {country['name']}: AdBlue (zona {country['zone']}) = {price} EUR/l")
        return price

    except Exception as e:
        print(f"[AS24] Klaida su {country['name']}: {e}")
        return None


async def extract_price_from_table(page, product_name, price_column):
    """
    Universali funkcija — ieško lentelėje eilutės su produktu ir
    grąžina reikšmę iš nurodyto stulpelio.
    """
    rows = await page.query_selector_all("tr")

    # Pirmiausia nustatome stulpelių indeksus iš antraštės
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

    # Ieškome produkto eilutės
    for row in rows:
        text = await row.inner_text()
        if product_name.lower() in text.lower():
            cells = await row.query_selector_all("td")
            if price_col_idx is not None and price_col_idx < len(cells):
                cell_text = (await cells[price_col_idx].inner_text()).strip()
                return parse_price(cell_text)
            else:
                # Bandome rasti kainą bet kuriame stulpelyje
                for cell in cells:
                    cell_text = (await cell.inner_text()).strip()
                    val = parse_price(cell_text)
                    if val and 0.1 < val < 5.0:
                        return val

    return None


async def extract_adblue_price_by_zone(page, target_zone):
    """
    Ieško AdBlue kainos konkrečioje zonoje.
    Lentelėje: Šalis | Produktas | Kainos zona | ... | Suma po nuolaidų be PVM
    """
    rows = await page.query_selector_all("tr")

    # Nustatome stulpelių indeksus
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

        # Tikriname zoną
        if zone_col_idx is not None and zone_col_idx < len(cells):
            zone_text = (await cells[zone_col_idx].inner_text()).strip()
            if target_zone and target_zone != zone_text:
                continue

        # Imame kainą
        if price_col_idx is not None and price_col_idx < len(cells):
            cell_text = (await cells[price_col_idx].inner_text()).strip()
            return parse_price(cell_text)

    return None


def parse_price(text):
    """Konvertuoja teksto formatą '1,5131 €/L' į float."""
    if not text:
        return None
    cleaned = re.sub(r"[€/L\s]", "", text).replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


async def scrape_as24():
    """
    Pagrindinė AS24 scrapinimo funkcija.
    Grąžina dict su dyzelino ir AdBlue kainomis.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    diesel_results = []
    adblue_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Bandome naudoti cookies
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
            # Prisijungimas
            await login_as24(page)

            # Išsaugome cookies
            os.makedirs(config.COOKIES_DIR, exist_ok=True)
            await context.storage_state(path=config.AS24_COOKIES)

            # Navigacija į kainų puslapį
            await navigate_to_prices(page)

            # ── Dyzelino kainos pagal degalines ─────────────────
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

            # ── AdBlue kainos pagal šalis ───────────────────────
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
