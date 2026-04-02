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
from datetime import datetime

import config

# Bendras User-Agent kad svetaines neblokuotu
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.8",
}


def get_latest_pdf_url():
    """
    Eina i Orlen LT kainu puslapi ir suranda naujausio PDF nuoroda.
    """
    resp = requests.get(config.CK_PDF_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if href.startswith("/"):
                href = "https://www.orlenlietuva.lt" + href
            elif not href.startswith("http"):
                href = "https://www.orlenlietuva.lt/" + href
            pdf_links.append(href)

    if not pdf_links:
        raise ValueError("Nerasta PDF nuorodu Orlen LT puslapyje")

    # Imame naujiausia (pirma sarase — paprastai naujausi virsuje)
    return pdf_links[0]


def parse_diesel_from_pdf(pdf_path):
    """
    Istraukia dyzelino kaina is Orlen LT PDF.
    Juodeikiu terminalas, "Dyzelinas E kl. su RRME",
    stulpelis "Bazine kaina su akcizo mokesciu".
    Verte EUR/1000l -> konvertuojame i EUR/l.
    """
    price = None
    date_str = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Bandome istraukti data is PDF
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if date_match and not date_str:
                date_str = date_match.group(1)

            # Ieskom lenteliu
            tables = page.extract_tables()
            if not tables:
                continue

            # Pirmas terminalas (Juodeikiu)
            found_first_terminal = False
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    row_text = " ".join(str(cell) for cell in row if cell)

                    if "Orlen Lietuva" in row_text and "Juodeiki" in row_text:
                        found_first_terminal = True
                        continue

                    if found_first_terminal and any(
                        t in row_text for t in ["Okseta", "KN Energies", "Subaciaus"]
                    ):
                        if price is not None:
                            break

                    if found_first_terminal and "Dyzelinas" in row_text and "RRME" in row_text:
                        numbers = []
                        for cell in row:
                            if cell is None:
                                continue
                            cell_str = str(cell).replace(" ", "").replace("\xa0", "")
                            try:
                                numbers.append(float(cell_str.replace(",", ".")))
                            except ValueError:
                                continue

                        if len(numbers) >= 3:
                            price = numbers[2]
                            break

                if price is not None:
                    break

    if price is None:
        raise ValueError("Nepavyko rasti dyzelino kainos Orlen LT PDF")

    price_per_liter = round(price / 1000, 6)

    return {
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "price": price_per_liter,
    }


def scrape_ck_diesel():
    """
    Pagrindine funkcija — atsisiuncia PDF ir grazina dyzelino kaina.
    """
    pdf_url = get_latest_pdf_url()
    print(f"[CK] Atsisiunchiamas PDF: {pdf_url}")

    resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        tmp_path = f.name

    try:
        result = parse_diesel_from_pdf(tmp_path)
        print(f"[CK] Dyzelinas: {result['price']} EUR/l ({result['date']})")
        return result
    finally:
        os.unlink(tmp_path)


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
