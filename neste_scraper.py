"""
Neste scraperis (Playwright).
1. Prisijungia prie neste.lt
2. Eina i "Sutarties kainos ir nuolaidos"
3. Pasirenka klienta, sali, data
4. Formuoja ataskaita be PVM
5. Istraukia Diesel Futura ir AdBlue kainas
"""
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

import config

DEBUG_DIR = "debug"


def get_report_date():
    today = datetime.now()
    weekday = today.weekday()
    if weekday == 0:
        report_date = today - timedelta(days=3)
    else:
        report_date = today - timedelta(days=1)
    return report_date.strftime("%d.%m.%Y")


async def debug_screenshot(page, name):
    """Issaugo debug screenshot."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        await page.screenshot(path=path, full_page=False)
        print(f"[Neste] Debug screenshot: {path}")
    except Exception as e:
        print(f"[Neste] Screenshot klaida: {e}")


async def scrape_neste():
    report_date = get_report_date()
    print(f"[Neste] Ataskaitos data: {report_date}")

    results = {"diesel": None, "adblue": None, "date": None}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            # -- 1. Einame i prisijungimo puslapi --
            print(f"[Neste] Einame i {config.NESTE_URL}")
            await page.goto(config.NESTE_URL, wait_until="networkidle", timeout=60000)
            await debug_screenshot(page, "01_neste_landing")

            # Bandome rasti ir paspausti "Prisijungti"
            prisijungti = page.locator('a:has-text("Prisijungti"), button:has-text("Prisijungti")')
            count = await prisijungti.count()
            print(f"[Neste] Rasta 'Prisijungti' elementu: {count}")

            if count > 0:
                await prisijungti.first.click()
                await page.wait_for_load_state("networkidle", timeout=30000)
                await debug_screenshot(page, "02_neste_login_form")

                # Bandome ivesti email
                email_input = page.locator('input[type="email"], input[name*="mail"], input[id*="mail"], input[placeholder*="mail"], input[placeholder*="pašt"]')
                email_count = await email_input.count()
                print(f"[Neste] Email lauku rasta: {email_count}")

                if email_count > 0:
                    await email_input.first.fill(config.NESTE_EMAIL)
                else:
                    # Bandome bet koki teksto lauka
                    all_inputs = page.locator('input[type="text"], input:not([type])')
                    input_count = await all_inputs.count()
                    print(f"[Neste] Visu input lauku: {input_count}")
                    if input_count > 0:
                        await all_inputs.first.fill(config.NESTE_EMAIL)

                # Password
                pwd_input = page.locator('input[type="password"]')
                pwd_count = await pwd_input.count()
                print(f"[Neste] Password lauku rasta: {pwd_count}")
                if pwd_count > 0:
                    await pwd_input.first.fill(config.NESTE_PASSWORD)

                await debug_screenshot(page, "03_neste_credentials_filled")

                # Submit
                submit = page.locator('button[type="submit"], input[type="submit"], button:has-text("Prisijungti"), button:has-text("Login")')
                submit_count = await submit.count()
                print(f"[Neste] Submit mygtuku: {submit_count}")
                if submit_count > 0:
                    await submit.first.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)

                await debug_screenshot(page, "04_neste_after_login")
                print(f"[Neste] URL po prisijungimo: {page.url}")

            # -- 2. Navigacija --
            # Bandome rasti meniu
            await page.wait_for_timeout(3000)
            await debug_screenshot(page, "05_neste_looking_for_menu")

            # Isspausdiname visus matomus nuorodu tekstus
            links = await page.query_selector_all("a")
            link_texts = []
            for link in links[:50]:
                text = (await link.inner_text()).strip()
                if text and len(text) > 2:
                    link_texts.append(text)
            print(f"[Neste] Matomos nuorodos: {link_texts[:20]}")

            # Bandome rasti "Sutarties kainos" arba panasu
            kainos_link = page.locator('a:has-text("kainos"), a:has-text("Kainos"), a:has-text("Sutarties"), a[href*="kainos"], a[href*="price"]')
            kainos_count = await kainos_link.count()
            print(f"[Neste] 'Kainos' nuorodu rasta: {kainos_count}")

            if kainos_count > 0:
                await kainos_link.first.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await debug_screenshot(page, "06_neste_kainos_page")
            else:
                # Bandome Ekstraneta
                ekstranetas = page.locator('a:has-text("Ekstranetas"), a:has-text("ekstranetas"), a[href*="extranetas"], a[href*="ekstra"]')
                ekstra_count = await ekstranetas.count()
                print(f"[Neste] 'Ekstranetas' nuorodu: {ekstra_count}")
                if ekstra_count > 0:
                    await ekstranetas.first.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await debug_screenshot(page, "06_neste_ekstranetas")

                # Dar karta bandome rasti kainos
                kainos_link2 = page.locator('a:has-text("kainos"), a:has-text("Kainos"), a:has-text("Sutarties")')
                kainos_count2 = await kainos_link2.count()
                print(f"[Neste] 'Kainos' nuorodu (2 bandymas): {kainos_count2}")
                if kainos_count2 > 0:
                    await kainos_link2.first.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)

            await debug_screenshot(page, "07_neste_final_state")
            print(f"[Neste] Galutinis URL: {page.url}")

            # -- 3. Bandome rasti kainas puslapyje --
            page_text = await page.inner_text("body")

            # Ieskom "Diesel Futura"
            if "Diesel Futura" in page_text or "diesel" in page_text.lower():
                print("[Neste] Rastas 'Diesel' tekste!")
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

            date_parts = report_date.split(".")
            results["date"] = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

        except Exception as e:
            print(f"[Neste] Klaida: {e}")
            await debug_screenshot(page, "99_neste_error")
            raise
        finally:
            await browser.close()

    return results


def run_neste_scraper():
    import asyncio
    return asyncio.run(scrape_neste())


if __name__ == "__main__":
    print("=== Neste Scraper testas ===")
    try:
        result = run_neste_scraper()
        print(f"Rezultatas: {result}")
    except Exception as e:
        print(f"Klaida: {e}")
