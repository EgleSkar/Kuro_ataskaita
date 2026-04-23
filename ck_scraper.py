"""
CK / Orlen LT scraperis.
1. Atsisiuncia naujiausia kainu protokola (PDF) is orlenlietuva.lt
2. Istraukia "Dyzelinas E kl. su RRME" bazine kaina su akcizu (Juodeikiu terminalas)
3. Nuskaito CK AdBlue kaina is circlek.lt puslapio
"""
import re
import requests
from bs4 import BeautifulSoup
import pdfplumber
import tempfile
import os
from datetime import datetime, timedelta, date

import config
from lt_holidays import is_lt_working_day

# Bendras User-Agent kad svetaines neblokuotu
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.8",
}


def build_pdf_url(d):
    """
    Sukonstruoja Orlen LT PDF URL pagal data.
    Pattern: Kainos YYYY MM DD realizacija internet.pdf
    """
    base = "https://www.orlenlietuva.lt/LT/Wholesale/Prices/"
    filename = f"Kainos {d.strftime('%Y %m %d')} realizacija internet.pdf"
    return base + requests.utils.quote(filename, safe="/")


def get_last_working_day():
    """Grazina paskutine darbo diena (vakar arba anksciau, praleisdama savaitgalius ir LT sventes)."""
    d = datetime.now().date() - timedelta(days=1)
    while not is_lt_working_day(d):
        d -= timedelta(days=1)
    return d


def get_pdf_url(d_work):
    """
    Tikrina ar egzistuoja Orlen LT PDF konkrecia data.
    Grazina URL jei rastas, None jei nerastas.
    """
    url = build_pdf_url(d_work)
    print(f"[CK] Bandome PDF: {url}")
    try:
        resp = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            print(f"[CK] PDF rastas: {d_work}")
            return url
    except Exception as e:
        print(f"[CK] Klaida tikrinant URL: {e}")
    print(f"[CK] Protokolas nerastas: {d_work}")
    return None


def parse_diesel_from_pdf(pdf_path):
    """
    Istraukia dyzelino kaina is Orlen LT PDF (teksto metodas).
    Juodeikiu terminalas, "Dyzelinas C kl. su RRME" (arba E kl.),
    stulpelis "Bazine kaina su akcizo mokesciu" (3-ias skaicius eiluteje).
    Verte EUR/1000l -> konvertuojame i EUR/l.

    Eilutes formatas:
      Dyzelinas C kl. su RRME 925.71 503.60 1 429.31 300.16 1 729.47
    Stulpeliai: bazine | akcizas | bazine+akcizas | PVM | su PVM
    Imame bazine+akcizas (3-ias skaicius).
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text:
                continue

            lines = text.splitlines()
            in_juodeikiai = False

            for line in lines:
                # Randame Juodeikiu terminalo sekcija
                if "Juodeiki" in line:
                    in_juodeikiai = True
                    continue

                # Sekantis terminalas — baigiame
                if in_juodeikiai and any(t in line for t in ["Okseta", "KN Energies", "Subaciaus", "Klaipeda"]):
                    break

                # Ieskom dyzelino eilutes
                if in_juodeikiai and "Dyzelinas" in line and "RRME" in line and "kl." in line:
                    # Isskaiciuojame visus skaicius is eilutes
                    # Skaiciai gali buti su tarpu kaip tukstanciu skyriklis: "1 429.31"
                    # Pirma pasaliname produkto pavadinima
                    name_end = line.find("RRME") + len("RRME")
                    numbers_part = line[name_end:].strip()

                    # Regex: pirma ieskom "1 000.00" tipo (su tarpo skyriklio),
                    # tada paprastu "000.00" tipo
                    numbers = []
                    remaining = numbers_part
                    pattern = re.compile(r'(\d{1,3})\s+(\d{3}\.\d+)|(\d+\.\d+)')
                    for m in pattern.finditer(remaining):
                        if m.group(1) and m.group(2):
                            # "1 429.31" tipo
                            val = float(m.group(1) + m.group(2))
                        else:
                            # "925.71" tipo
                            val = float(m.group(3))
                        numbers.append(val)

                    print(f"[CK] Dyzelino eilute: {line.strip()}")
                    print(f"[CK] Rasti skaiciai: {numbers}")

                    # 3-ias skaicius = Bazine kaina su akcizo mokesciu (EUR/1000L)
                    if len(numbers) >= 3:
                        price_1000l = numbers[2]
                        price_per_liter = round(price_1000l / 1000, 6)
                        print(f"[CK] Kaina: {price_1000l} EUR/1000L = {price_per_liter} EUR/L")
                        return {"date": datetime.now().strftime("%Y-%m-%d"), "price": price_per_liter}

    raise ValueError("Nepavyko rasti dyzelino kainos Orlen LT PDF")


def scrape_ck_diesel():
    """
    Pagrindine funkcija — atsisiuncia PDF ir grazina dyzelino kainu sarasa.
    Grazina sarasa irasu: pagrindinis (protokolo data) + backfill savaitgaliai/sventes.
    Jei protokolas nerastas — grazina [{"date": ..., "price": None}].
    """
    today = datetime.now().date()
    d_work = get_last_working_day()
    pdf_url = get_pdf_url(d_work)

    if pdf_url is None:
        return [{"date": d_work.strftime("%Y-%m-%d"), "price": None}]

    print(f"[CK] Atsisiunchiamas PDF: {pdf_url}")
    resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        tmp_path = f.name

    try:
        result = parse_diesel_from_pdf(tmp_path)
        price = result["price"]
    finally:
        os.unlink(tmp_path)

    entries = [{"date": d_work.strftime("%Y-%m-%d"), "price": price}]

    # Backfill: visos ne darbo dienos tarp d_work+1 ir vakar (imtinai)
    yesterday = today - timedelta(days=1)
    d = d_work + timedelta(days=1)
    while d <= yesterday:
        if not is_lt_working_day(d):
            entries.append({"date": d.strftime("%Y-%m-%d"), "price": price})
        d += timedelta(days=1)

    for e in entries:
        status = f"{e['price']} EUR/l" if e["price"] is not None else "nerastas"
        print(f"[CK] Dyzelinas: {status} ({e['date']})")

    return entries


def scrape_ck_adblue():
    """
    Nuskaito CK AdBlue kaina is circlek.lt puslapio.
    Kaina rodoma su PVM — saugome kaip yra.
    """
    if not config.CK_ADBLUE_URL:
        print("[CK] AdBlue URL nenustatytas, praleidziama")
        return None

    resp = requests.get(config.CK_ADBLUE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    price = None

    text = soup.get_text()
    adblue_pattern = re.compile(
        r"[Aa]d\s*[Bb]lue[^\d]*?([\d]+[,.][\d]+)", re.IGNORECASE
    )
    match = adblue_pattern.search(text)
    if match:
        price_str = match.group(1).replace(",", ".")
        price = float(price_str)

    if price is None:
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                row_text = " ".join(c.get_text() for c in cells)
                if "adblue" in row_text.lower():
                    for cell in cells:
                        cell_text = cell.get_text().strip().replace(",", ".")
                        try:
                            val = float(cell_text)
                            if 0.1 < val < 5.0:
                                price = val
                                break
                        except ValueError:
                            continue

    if price is None:
        raise ValueError("Nepavyko rasti AdBlue kainos CK puslapyje")

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[CK] AdBlue: {price} EUR/l ({today})")
    return {"date": today, "price": price}


if __name__ == "__main__":
    print("=== CK Scraper testas ===")
    try:
        diesel = scrape_ck_diesel()
        print(f"Dyzelinas: {diesel}")
    except Exception as e:
        print(f"Dyzelino klaida: {e}")

    try:
        adblue = scrape_ck_adblue()
        print(f"AdBlue: {adblue}")
    except Exception as e:
        print(f"AdBlue klaida: {e}")
