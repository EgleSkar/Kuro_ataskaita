"""
Neste scraperis (Playwright).
1. Prisijungia prie neste.lt
2. Eina i "Sutarties kainos ir nuolaidos"
3. Pasirenka klienta (Delamode Baltics), sali (Lietuva), data (vakar arba penktadienis)
4. Formuoja ataskaita be PVM
5. Istraukia Diesel Futura ir AdBlue kainas
"""
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

import config


def get_report_date():
    """
    Grazina data kuriai formuojame ataskaita:
    - Pirmadieniui -> penktadienio data
    - Kitomis dienomis -> vakarykste data
    """
    today = datetime.now()
    weekday = today.weekday()  # 0=pirmadienis

    if weekday == 0:  # Pirmadienis
        report_date = today - timedelta(days=3)  # Penktadienis
    else:
        report_date = today - timedelta(days=1)  # Vakar

    return report_date.strftime("%d.%m.%Y")


async def scrape_neste():
    """
    Prisijungia prie Neste portalo ir istraukia Diesel Futura bei AdBlue kainas.
    """
    report_date = get_report_date()
    print(f"[Neste] Ataskaitos data: {report_date}")

    results = {"diesel": None, "adblue": None, "date": None}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = None
        if os.path.exists(config.NESTE_COOKIES):
            try:
                context = await browser.new_context(
                    storage_state=config.NESTE_COOKIES
                )
                print("[Neste] Naudojamos issaugotos cookies")
            except Exception:
                context = None

        if context is None:
            context = await browser.new_context()

        page = await context.new_page()

        try:
            # -- 1. Prisijungimas --
            await page.goto(config.NESTE_URL, wait_until="networkidle", timeout=60000)

            try:
                await page.wait_for_selector(
                    'text="Prisijungti"', timeout=5000
                )
                print("[Neste] Reikia prisijungti...")

                await page.click('text="Prisijungti"')
                await page.wait_for_load_state("networkidle")

                await page.fill(
                    'input[type="email"], input[name="email"], input[id*="email"]',
                    config.NESTE_EMAIL,
                )
                await page.fill(
                    'input[type="password"], input[name="password"], input[id*="password"]',
                    config.NESTE_PASSWORD,
                )

                await page.click(
                    'button[type="submit"], input[type="submit"], button:has-text("Prisijungti")'
                )
                await page.wait_for_load_state("networkidle", timeout=30000)

                print("[Neste] Prisijungta sekmingai")

                os.makedirs(config.COOKIES_DIR, exist_ok=True)
                await context.storage_state(path=config.NESTE_COOKIES)

            except Exception:
                print("[Neste] Jau prisijungta arba kita struktura")

            # -- 2. Navigacija i "Sutarties kainos ir nuolaidos" --
            await page.click('text="Sutarties kainos ir nuolaidos"', timeout=10000)
            await page.wait_for_load_state("networkidle")
            print("[Neste] Atidaryta 'Sutarties kainos ir nuolaidos'")

            # -- 3. Formos pildymas --
            try:
                client_selector = page.locator(
                    'text="Pasirinkite kliento numeri"'
                ).locator("..")
                await client_selector.click()
                await page.click(f'text="{config.NESTE_CLIENT}"', timeout=5000)
            except Exception:
                print("[Neste] Klientas jau pasirinktas arba nera dropdown")

            try:
                country_selector = page.locator(
                    'text="Pasirinkite sali"'
                ).locator("..")
                await country_selector.click()
                await page.click(f'text="{config.NESTE_COUNTRY}"', timeout=5000)
            except Exception:
                print("[Neste] Salis jau pasirinkta")

            try:
                date_fields = await page.query_selector_all("input")
                for field in date_fields:
                    placeholder = await field.get_attribute("placeholder")
                    value = await field.get_attribute("value")
                    if placeholder and "data" in placeholder.lower() or (
                        value and "." in value and len(value) == 10
                    ):
                        await field.click(click_count=3)
                        await field.fill(report_date)
                        print(f"[Neste] Data nustatyta: {report_date}")
                        break
            except Exception as e:
                print(f"[Neste] Datos nustatymo klaida: {e}")

            try:
                pvm_checkbox = page.locator('text="Rodyti kainas su PVM"')
                if await pvm_checkbox.is_checked():
                    await pvm_checkbox.click()
                    print("[Neste] PVM nuimtas")
            except Exception:
                pass

            # -- 4. Formuoti ataskaita --
            await page.click('text="FORMUOTI ATASKAITA"', timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("[Neste] Ataskaita suformuota")

            # -- 5. Kainu nuskaitymas --
            await page.wait_for_selector("table, .price, .product", timeout=15000)

            rows = await page.query_selector_all("tr")
            for row in rows:
                text = await row.inner_text()
                if "Diesel Futura" in text:
                    cells = await row.query_selector_all("td")
                    for cell in cells:
                        cell_text = (await cell.inner_text()).strip().replace(",", ".")
                        try:
                            val = float(cell_text)
                            if 0.5 < val < 3.0:
                                results["diesel"] = val
                                print(f"[Neste] Diesel Futura: {val} EUR/l")
                                break
                        except ValueError:
                            continue

            for row in rows:
                text = await row.inner_text()
                if "AdBlue" in text:
                    cells = await row.query_selector_all("td")
                    for cell in cells:
                        cell_text = (await cell.inner_text()).strip().replace(",", ".")
                        try:
                            val = float(cell_text)
                            if 0.1 < val < 3.0:
                                results["adblue"] = val
                                print(f"[Neste] AdBlue: {val} EUR/l")
                                break
                        except ValueError:
                            continue

            # Data
            date_parts = report_date.split(".")
            results["date"] = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

        except Exception as e:
            print(f"[Neste] Klaida: {e}")
            os.makedirs("debug", exist_ok=True)
            await page.screenshot(path="debug/neste_error.png")
            raise

        finally:
            await browser.close()

    return results


def run_neste_scraper():
    """Sinchroninis wrapperis async funkcijai."""
    import asyncio
    return asyncio.run(scrape_neste())


if __name__ == "__main__":
    print("=== Neste Scraper testas ===")
    try:
        result = run_neste_scraper()
        print(f"Rezultatas: {result}")
    except Exception as e:
        print(f"Klaida: {e}")
