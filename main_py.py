"""
Kuro kainų stebėjimo sistema — pagrindinis paleidimo failas.
Paleidžia visus scraperius, atnaujina JSON failą.
"""
import sys
import traceback
from datetime import datetime

from scrapers.ck_scraper import scrape_ck_diesel, scrape_ck_adblue
from scrapers.neste_scraper import run_neste_scraper
from scrapers.as24_scraper import run_as24_scraper
from json_writer import update_json


def main():
    print("=" * 60)
    print(f"Kuro kainų surinkimas — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    errors = []
    ck_diesel = None
    ck_adblue = None
    neste = None
    as24 = None

    # ── 1. CK / Orlen LT ───────────────────────────────────────
    print("\n── CK / Orlen LT ──")
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

    # ── 2. Neste ────────────────────────────────────────────────
    print("\n── Neste ──")
    try:
        neste = run_neste_scraper()
    except Exception as e:
        errors.append(f"Neste: {e}")
        traceback.print_exc()

    # ── 3. AS24 ─────────────────────────────────────────────────
    print("\n── AS24 ──")
    try:
        as24 = run_as24_scraper()
    except Exception as e:
        errors.append(f"AS24: {e}")
        traceback.print_exc()

    # ── 4. JSON atnaujinimas ────────────────────────────────────
    print("\n── JSON atnaujinimas ──")
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

    # ── Suvestinė ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"⚠️  Baigta su klaidomis ({len(errors)}):")
        for err in errors:
            print(f"   • {err}")
        # Negrąžiname klaidos kodo jei bent kažkas pavyko
        if ck_diesel is None and neste is None and as24 is None:
            print("❌ Nė vienas scraperis neveikė!")
            sys.exit(1)
    else:
        print("✅ Viskas surinkta sėkmingai!")

    print("=" * 60)


if __name__ == "__main__":
    main()
