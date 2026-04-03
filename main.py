"""
Kuro kainu stebesenos sistema — pagrindinis paleidimo failas.
Paleidzia visus scraperius, atnaujina JSON faila.
"""
import sys
import traceback
from datetime import datetime

from ck_scraper import scrape_ck_diesel, scrape_ck_adblue
from neste_scraper import run_neste_scraper
from as24_scraper import run_as24_scraper
from json_writer import update_json


def main():
    print("=" * 60)
    print(f"Kuro kainu surinkimas — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    errors = []
    ck_diesel = None
    ck_adblue = None
    neste = None
    as24 = None

    # -- 1. CK / Orlen LT --
    print("\n-- CK / Orlen LT --")
    try:
        ck_diesel = scrape_ck_diesel()
    except Exception as e:
        errors.append(f"CK Dyzelinas: {e}")
        traceback.print_exc()

    try:
        ck_adblue = scrape_ck_adblue()
    except Exception as e:
        errors.append(f"CK AdBlue: {e}")
        traceback.print_exc()

    # -- 2. Neste --
    print("\n-- Neste --")
    try:
        neste = run_neste_scraper()
    except Exception as e:
        errors.append(f"Neste: {e}")
        traceback.print_exc()

    # -- 3. AS24 --
    print("\n-- AS24 --")
    try:
        as24 = run_as24_scraper()
    except Exception as e:
        errors.append(f"AS24: {e}")
        traceback.print_exc()

    # -- 4. JSON atnaujinimas --
    print("\n-- JSON atnaujinimas --")
    try:
        update_json(
            ck_diesel=ck_diesel,
            ck_adblue=ck_adblue,
            neste=neste,
            as24=as24,
        )
    except Exception as e:
        errors.append(f"JSON: {e}")
        traceback.print_exc()

    # -- Suvestine --
    print("\n" + "=" * 60)
    if errors:
        print(f"Baigta su klaidomis ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")
        if ck_diesel is None and neste is None and as24 is None:
            print("Ispejimas: ne vienas scraperis neveike — tikrinkite debug screenshots!")
    else:
        print("Viskas surinkta sekmingai!")
    print("=" * 60)


if __name__ == "__main__":
    main()
