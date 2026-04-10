"""
Neste scraperis (Playwright).
"""
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
    os.makedirs(DEBUG_DIR, exist_ok=True)
    try:
        await page.screenshot(path=f"{DEBUG_DIR}/{name}.png", full_page=False)
        print(f"[Neste] Screenshot: {name}")
    except Exception as e:
        print(f"[Neste] Screenshot klaida: {e}")

async def close_cookies(page):
    """Uzdaro cookies popup jei yra."""
    try:
        # Neste cookies popup - "Necessary cookies only" arba "Accept All Cookies"
        for text in ["Necessary cookies only", "Accept All Cookies", "Sutinku", "Priimti"]:
            btn = page.locator(f'button:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click()
                print(f"[Neste] Cookies uzdarytas: '{text}'")
                await page.wait_for_timeout(1000)
                return
        # Bandome generic cookie buttons
        cookie_btn = page.locator('button[id*="cookie"], button[class*="cookie"], #onetrust-accept-btn-handler')
        if await cookie_btn.count() > 0:
            await cookie_btn.first.click()
            print("[Neste] Cookies uzdarytas (generic)")
            await page.wait_for_timeout(1000)
    except Exception as e:
        print(f"[Neste] Cookies uzdarymo klaida: {e}")

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
            # 1. Einame i Neste
            print(f"[Neste] URL: {config.NESTE_URL}")
            await page.goto(config.NESTE_URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            await debug_screenshot(page, "01_neste_landing")

            # 2. Cookies popup
            await close_cookies(page)
            await debug_screenshot(page, "02_after_cookies")

            # 3. Prisijungimas - spaudziam "Prisijungti" virsuje desiniame kampe
            prisijungti = page.locator('a:has-text("Prisijungti")')
            if await prisijungti.count() > 0:
                await prisijungti.first.click()
                await page.wait_for_load_state("networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                await debug_screenshot(page, "03_login_page")

                # Dar kartą cookies jei atsidaro
                await close_cookies(page)

                # Ivedame email
                email_input = page.locator('input[type="email"], input[name*="mail"], input[id*="email"]')
                if await email_input.count() > 0:
                    await email_input.first.fill(config.NESTE_EMAIL)
                    print("[Neste] Email ivestas")

                # Ivedame password
                pwd_input = page.locator('input[type="password"]')
                if await pwd_input.count() > 0:
                    await pwd_input.first.fill(config.NESTE_PASSWORD)
                    print("[Neste] Password ivestas")

                await debug_screenshot(page, "04_credentials")

                # Submit
                submit = page.locator('button[type="submit"], button:has-text("Prisijungti"), button:has-text("Login")')
                if await submit.count() > 0:
                    await submit.first.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await page.wait_for_timeout(3000)

                await debug_screenshot(page, "05_after_login")
                print(f"[Neste] URL po login: {page.url}")
            else:
                # Bandome per Ekstraneta
                ekstra = page.locator('a:has-text("Ekstranetas"), a:has-text("PRISIJUNGTI")')
                if await ekstra.count() > 0:
                    await ekstra.first.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await debug_screenshot(page, "03_ekstranetas")

            # 4. Navigacija i kainu puslapi
            # Ieskom "Sutarties kainos ir nuolaidos" meniu
            kainos = page.locator('a:has-text("Sutarties kainos"), a:has-text("kainos ir nuolaidos"), a:has-text("Kainos")')
            kainos_count = await kainos.count()
            print(f"[Neste] Kainos nuorodu: {kainos_count}")

            if kainos_count > 0:
                await kainos.first.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(2000)
                await debug_screenshot(page, "06_kainos_page")
            else:
                # Isspausdiname matomus link tekstus
                links = await page.query_selector_all("a")
                for link in links[:30]:
                    text = (await link.inner_text()).strip()
                    if text and len(text) > 2:
                        print(f"[Neste] Link: '{text}'")
                await debug_screenshot(page, "06_no_kainos_found")

            # 5. Formos pildymas (jei esame kainu puslapyje)
            # Klientas - Delamode Baltics
            try:
                client_dd = page.locator('select, [role="listbox"], [class*="dropdown"]').first
                if await client_dd.count() > 0:
                    await client_dd.click()
                    await page.wait_for_timeout(500)
                    delamode = page.locator(f'text="{config.NESTE_CLIENT}", option:has-text("{config.NESTE_CLIENT}")')
                    if await delamode.count() > 0:
                        await delamode.first.click()
            except Exception:
                pass

            # Data
            try:
                date_inputs = page.locator('input[type="text"]')
                for i in range(await date_inputs.count()):
                    val = await date_inputs.nth(i).get_attribute("value") or ""
                    if "." in val and len(val) == 10:
                        await date_inputs.nth(i).click(click_count=3)
                        await date_inputs.nth(i).fill(report_date)
                        print(f"[Neste] Data: {report_date}")
                        break
            except Exception:
                pass

            # Formuoti ataskaita
            form_btn = page.locator('button:has-text("FORMUOTI"), button:has-text("Formuoti")')
            if await form_btn.count() > 0:
                await form_btn.first.click()
                await page.wait_for_load_state("networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                await debug_screenshot(page, "07_ataskaita")

            # 6. Kainu nuskaitymas
            rows = await page.query_selector_all("tr")
            for row in rows:
                text = await row.inner_text()
                if "Diesel Futura" in text:
                    cells = await row.query_selector_all("td")
                    for cell in cells:
                        ct = (await cell.inner_text()).strip().replace(",", ".")
                        try:
                            val = float(ct)
                            if 0.5 < val < 3.0:
                                results["diesel"] = val
                                print(f"[Neste] Diesel Futura: {val}")
                                break
                        except ValueError:
                            continue
                if "AdBlue" in text:
                    cells = await row.query_selector_all("td")
                    for cell in cells:
                        ct = (await cell.inner_text()).strip().replace(",", ".")
                        try:
                            val = float(ct)
                            if 0.1 < val < 3.0:
                                results["adblue"] = val
                                print(f"[Neste] AdBlue: {val}")
                                break
                        except ValueError:
                            continue

            date_parts = report_date.split(".")
            results["date"] = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
            await debug_screenshot(page, "08_final")

        except Exception as e:
            print(f"[Neste] Klaida: {e}")
            await debug_screenshot(page, "99_error")
            raise
        finally:
            await browser.close()

    return results

def run_neste_scraper():
    import asyncio
    return asyncio.run(scrape_neste())

if __name__ == "__main__":
    result = run_neste_scraper()
    print(f"Rezultatas: {result}")
