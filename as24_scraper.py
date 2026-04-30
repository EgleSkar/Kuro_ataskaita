"""
AS24 scraperis — naudoja JSON API tiesiogiai (be Playwright/Excel).
Autentifikacija per sesijos cookies (AS24_STORAGE_STATE env kintamasis arba as24_storage.json).
"""
import base64
import json
import os
import sys
import requests
from datetime import datetime

# Windows konsolei - UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config

AS24_PRICES_API = "https://extranet.as24.com/myas24/secured/prices/getListPricesStations"


def load_cookies():
    """Įkelia sesijos cookies iš AS24_STORAGE_STATE env kintamojo arba failo."""
    # 1. Iš GitHub Secret (base64 koduotas Playwright storage state)
    storage_b64 = os.getenv("AS24_STORAGE_STATE", "")
    if storage_b64:
        try:
            storage = json.loads(base64.b64decode(storage_b64).decode())
            cookies = {c["name"]: c["value"] for c in storage.get("cookies", [])}
            print(f"[AS24] Cookies įkelti iš AS24_STORAGE_STATE ({len(cookies)} vnt.)")
            return cookies
        except Exception as e:
            print(f"[AS24] Klaida skaitant AS24_STORAGE_STATE: {e}")

    # 2. Iš lokalaus failo
    for path in ["as24_storage.json", "cookies/as24_cookies.json"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    storage = json.load(f)
                cookies = {c["name"]: c["value"] for c in storage.get("cookies", [])}
                print(f"[AS24] Cookies įkelti iš {path} ({len(cookies)} vnt.)")
                return cookies
            except Exception as e:
                print(f"[AS24] Klaida skaitant {path}: {e}")

    print("[AS24] Perspėjimas: sesijos cookies nerasti!")
    return {}


def parse_price(val):
    """Konvertuoja kainą į float."""
    if val is None:
        return None
    try:
        v = float(val)
        return v if 0.3 < v < 5.0 else None
    except (ValueError, TypeError):
        return None


def fetch_all_prices(session):
    """Gauna visas kainas iš JSON API (viena užklausa)."""
    body = {
        "applicationDate": int(datetime.now().timestamp() * 1000),
        "clientCurrency": "EUR",
        "countriesId": [],
        "priceZones": [],
        "productsId": ["01", "03", "GL", "06", "9A", "95", "GC", "GE", "10", "GF", "AB"],
        "regionsId": [],
        "stationTypes": [],
        "flgFavorite": False,
        "langueId": "LT",
    }
    resp = session.post(AS24_PRICES_API, json=body, timeout=30)
    resp.raise_for_status()
    rows = resp.json()
    print(f"[AS24] Gauta {len(rows)} eilučių iš API")
    return rows


def scrape_diesel(rows, today):
    """Iš API atsakymo ištraukia dyzelino kainas pagal konfigūruotas stotis."""
    results = []

    for station_cfg in config.AS24_DIESEL_STATIONS:
        name = station_cfg["name"]
        flt = station_cfg["filter"].upper()
        cfg_country = station_cfg.get("country", "").upper()
        found_price = None
        found_station = None

        for row in rows:
            pid = (row.get("productId") or "")
            product = (row.get("productName") or "").lower().replace(" ", "")
            if pid != "03" and "gazole" not in product and "diesel" not in product:
                continue

            station_name = (row.get("stationName") or "").upper()
            row_country = (row.get("country") or "").upper()

            # Specialus atvejis: filter == country (pvz. "ITA") — filtruojame tik pagal šalį
            if flt == cfg_country and cfg_country:
                if row_country == cfg_country:
                    p = parse_price(row.get("clientCurrencyDiscountPriceVATExcl"))
                    if p:
                        found_price = p
                        found_station = row.get("stationName")
                        break
            else:
                # Standartinis: stoties pavadinimas turi sutapti
                name_match = (station_name == flt) or (flt in station_name)
                country_match = (not cfg_country) or (row_country == cfg_country)
                if name_match and country_match:
                    p = parse_price(row.get("clientCurrencyDiscountPriceVATExcl"))
                    if p:
                        found_price = p
                        found_station = row.get("stationName")
                        break

        if found_price:
            print(f"[AS24] {name}: {found_price} EUR/l (stotis: {found_station})")
        else:
            print(f"[AS24] {name}: nerasta")

        results.append({
            "name": name,
            "country": station_cfg.get("country", ""),
            "date": today,
            "price": found_price,
        })

    return results


def scrape_adblue(rows, today):
    """Iš API atsakymo ištraukia AdBlue kainas pagal šalis ir zonas."""
    results = []

    for country_cfg in config.AS24_ADBLUE_COUNTRIES:
        name = country_cfg["name"]
        code = country_cfg["code"].upper()
        zone = country_cfg.get("zone", "").upper()
        found_price = None

        for row in rows:
            pid = (row.get("productId") or "")
            product = (row.get("productName") or "").lower().replace(" ", "")
            if pid != "10" and "adblue" not in product:
                continue

            row_country = (row.get("country") or "").upper()
            row_zone = (row.get("priceZone") or "").upper()

            if row_country != code:
                continue
            if zone and row_zone != zone:
                continue

            p = parse_price(row.get("clientCurrencyDiscountPriceVATExcl"))
            if p:
                found_price = p
                break

        if found_price:
            print(f"[AS24] {name} AdBlue: {found_price} EUR/l")
        else:
            print(f"[AS24] {name} AdBlue: nerasta")

        results.append({
            "name": name,
            "code": country_cfg["code"],
            "date": today,
            "price": found_price,
        })

    return results


def scrape_as24():
    today = datetime.now().strftime("%Y-%m-%d")

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://extranet.as24.com/extranet/lt/network/prices-by-station/multi-energy",
        "Origin": "https://extranet.as24.com",
    })

    cookies = load_cookies()
    for cname, cvalue in cookies.items():
        session.cookies.set(cname, cvalue, domain=".extranet.as24.com")

    rows = fetch_all_prices(session)

    diesel_results = scrape_diesel(rows, today)
    adblue_results = scrape_adblue(rows, today)

    return {"diesel": diesel_results, "adblue": adblue_results}


def run_as24_scraper():
    return scrape_as24()


if __name__ == "__main__":
    print("=== AS24 Scraper testas ===")
    try:
        result = run_as24_scraper()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Klaida: {e}")
        import traceback
        traceback.print_exc()
