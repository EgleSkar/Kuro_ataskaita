"""
CK / Orlen LT scraperis.
1. Atsisiunčia naujausią kainų protokolą (PDF) iš orlenlietuva.lt
2. Ištraukia "Dyzelinas E kl. su RRME" bazinę kainą su akcizu (Juodeikių terminalas)
3. Nuskaito CK AdBlue kainą iš circlek.lt puslapio
"""
import re
import requests
from bs4 import BeautifulSoup
import pdfplumber
import tempfile
import os
from datetime import datetime

import config


def get_latest_pdf_url():
    """
    Eina į Orlen LT kainų puslapį ir suranda naujausio PDF nuorodą.
    """
    resp = requests.get(config.CK_PDF_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Ieškome PDF nuorodų puslapyje
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            # Jei santykinė nuoroda — pridedame domeną
            if href.startswith("/"):
                href = "https://www.orlenlietuva.lt" + href
            pdf_links.append(href)

    if not pdf_links:
        raise ValueError("Nerasta PDF nuorodų Orlen LT puslapyje")

    # Imame naujausią (pirmą sąraše — paprastai naujausi viršuje)
    return pdf_links[0]


def parse_diesel_from_pdf(pdf_path):
    """
    Ištraukia dyzelino kainą iš Orlen LT PDF.
    Ieško pirmo Juodeikių terminalo sekcijoje esančio
    "Dyzelinas E kl. su RRME" ir ima "Bazinė kaina su akcizo mokesčiu" stulpelį.

    PDF struktūra (stulpeliai):
    Produkto pavadinimas | Bazinė pardavimo kaina | Akcizas | Bazinė kaina su akcizo mokesčiu | PVM 21% | Pardavimo kaina su PVM

    Reikia: "Bazinė kaina su akcizo mokesčiu" (3-ias stulpelis, indeksas 2)
    Vertė yra EUR/1000l, pvz. 1 636.35 → konvertuojame į EUR/l: 1.63635
    """
    price = None
    date_str = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Bandome ištraukti datą iš PDF
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
            if date_match and not date_str:
                date_str = date_match.group(1)

            # Ieškome lentelių
            tables = page.extract_tables()
            if not tables:
                continue

            # Pirmas terminalas (Juodeikių) — pirma lentelė su dyzelinu
            found_first_terminal = False
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    row_text = " ".join(str(cell) for cell in row if cell)

                    # Tikriname ar tai pirmo terminalo (Orlen Lietuva / Juodeikių) sekcija
                    if "Orlen Lietuva" in row_text and "Juodeiki" in row_text:
                        found_first_terminal = True
                        continue

                    # Jei dar neradome pirmo terminalo, tikriname ar tai kitas terminalas
                    if found_first_terminal and any(
                        t in row_text for t in ["Okseta", "KN Energies", "Subačiaus"]
                    ):
                        # Jau perėjome į kitą terminalą — stabdome
                        if price is not None:
                            break

                    if found_first_terminal and "Dyzelinas" in row_text and "RRME" in row_text:
                        # Ieškome skaičių stulpelyje "Bazinė kaina su akcizo mokesčiu"
                        # Tai turėtų būti 4-as elementas (indeksas 3) arba
                        # ieškome reikšmės formato "X XXX.XX"
                        numbers = []
                        for cell in row:
                            if cell is None:
                                continue
                            cell_str = str(cell).replace(" ", "").replace("\xa0", "")
                            try:
                                numbers.append(float(cell_str.replace(",", ".")))
                            except ValueError:
                                continue

                        # Bazinė kaina su akcizu turėtų būti 3-ia reikšmė
                        # (po bazinės kainos ir akcizo)
                        if len(numbers) >= 3:
                            price = numbers[2]  # Bazinė kaina su akcizo mokesčiu
                            break

                if price is not None:
                    break

    if price is None:
        raise ValueError("Nepavyko rasti dyzelino kainos Orlen LT PDF")

    # Konvertuojame iš EUR/1000l į EUR/l
    price_per_liter = round(price / 1000, 6)

    return {
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "price": price_per_liter,
    }


def scrape_ck_diesel():
    """
    Pagrindinė funkcija — atsisiunčia PDF ir grąžina dyzelino kainą.
    """
    pdf_url = get_latest_pdf_url()
    print(f"[CK] Atsisiunčiamas PDF: {pdf_url}")

    resp = requests.get(pdf_url, timeout=60)
    resp.raise_for_status()

    # Išsaugome laikinai
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
    Nuskaito CK AdBlue kainą iš circlek.lt puslapio.
    Kaina rodoma su PVM — saugome kaip yra (nereikia perskaičiuoti).
    """
    if not config.CK_ADBLUE_URL:
        print("[CK] AdBlue URL nenustatytas, praleidžiama")
        return None

    resp = requests.get(config.CK_ADBLUE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Ieškome AdBlue kainos puslapyje
    # Tikėtina struktūra: lentelė su produktais ir kainomis
    price = None

    # Bandome rasti "AdBlue" ir šalia esantį skaičių
    text = soup.get_text()
    # Ieškome paternų tipo "AdBlue ... 0,756" arba "Adblue ... 0.756"
    adblue_pattern = re.compile(
        r"[Aa]d\s*[Bb]lue[^\d]*?([\d]+[,.][\d]+)", re.IGNORECASE
    )
    match = adblue_pattern.search(text)
    if match:
        price_str = match.group(1).replace(",", ".")
        price = float(price_str)

    if price is None:
        # Bandome ieškoti lentelėse
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                row_text = " ".join(c.get_text() for c in cells)
                if "adblue" in row_text.lower():
                    for cell in cells:
                        cell_text = cell.get_text().strip().replace(",", ".")
                        try:
                            val = float(cell_text)
                            if 0.1 < val < 5.0:  # Tikėtinas kainos diapazonas
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
