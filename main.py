"""
Kuro kainu stebesenos sistema - pagrindinis paleidimo failas.
Paleidzia visus scraperius, atnaujina JSON faila.
Pritaikyta veikti su esamu failu pavadinimu repozitorijoje.
"""
import sys
import importlib
import traceback
from datetime import datetime

# Importuojame modulius su bruksneliais per importlib
config = importlib.import_module("config-py")
ck_scraper = importlib.import_module("ck-scraper")
neste_scraper = importlib.import_module("neste-scraper")
as24_scraper = importlib.import_module("as24-scraper")
json_writer = importlib.import_module("json-writer")

def main():
    print("=" * 60)
    print(f"Kuro kainu surinkimas - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    errors = []
    ck_diesel = None
    ck_adblue = None
    neste = None
    as24 = None

    # 1. CK / Orlen LT
    print("\n-- CK / Orlen LT --")
    try:
        ck_diesel = ck_scraper.scrape_ck_diesel()
    except Exception as e:
        errors.append(f"CK Dyzelinas: {e}")
        traceback.print_exc()

    try:
        ck_adblue = ck_scraper.scrape_ck_adblue()
    except Exception as e:
        errors.append(f"CK AdBlue: {e}")
        traceback.print_exc()

    # 2. Neste
    print("\n-- Neste --")
    try:
        neste = neste_scraper.run_neste_scraper()
    except Exception as e:
        errors.append(f"Neste: {e}")
        traceback.print_exc()

    # 3. AS24
    print("\n-- AS24 --")
    try:
        as24 = as24_scraper.run_as24_scraper()
    except Exception as e:
        errors.append(f"AS24: {e}")
        traceback.print_exc()

    # 4. JSON atnaujinimas
    print("\n-- JSON atnaujinimas --")
    try:
        json_writer.update_json(
            ck_diesel=ck_diesel,
            ck_adblue=ck_adblue,
            neste=neste,
            as24=as24,
        )
    except Exception as e:
        errors.append(f"JSON: {e}")
        traceback.print_exc()

    # Suvestine
    print("\n" + "=" * 60)
    if errors:
        print(f"Baigta su klaidomis ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")
        if ck_diesel is None and neste is None and as24 is None:
            print("Ne vienas scraperis neveike!")
            sys.exit(1)
    else:
        print("Viskas surinkta sekmingai!")
    print("=" * 60)

if __name__ == "__main__":
    main()
