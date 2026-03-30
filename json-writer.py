"""
JSON writer — nuskaito esamą kuro_kainos.json, prideda naujas kainas, išsaugo.
"""
import json
import os
from datetime import datetime

import config


def load_existing_data():
    """Nuskaito esamą JSON failą arba sukuria tuščią struktūrą."""
    if os.path.exists(config.JSON_FILE):
        with open(config.JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # Tuščia struktūra
    return {
        "updated": "",
        "ck_dz": {"dates": [], "data": []},
        "neste_dz": {"dates": [], "data": []},
        "ck_ab": {"dates": [], "data": []},
        "neste_ab": {"dates": [], "data": []},
        "as24_dz": [],
        "as24_ab": [],
    }


def add_single_value(series, date_str, value):
    """
    Prideda vieną reikšmę į seriją (dates + data masyvus).
    Jei ta data jau yra — atnaujina reikšmę.
    Jei reikšmė None — praleidžia.
    """
    if value is None:
        return

    if date_str in series["dates"]:
        idx = series["dates"].index(date_str)
        series["data"][idx] = value
    else:
        # Įterpiame chronologine tvarka
        inserted = False
        for i, d in enumerate(series["dates"]):
            if date_str < d:
                series["dates"].insert(i, date_str)
                series["data"].insert(i, value)
                inserted = True
                break
        if not inserted:
            series["dates"].append(date_str)
            series["data"].append(value)


def find_or_create_as24_entry(as24_list, name, key_field="name", extra_fields=None):
    """
    Ieško AS24 sąraše įrašo pagal pavadinimą. Jei neranda — sukuria naują.
    """
    for entry in as24_list:
        if entry.get(key_field) == name or entry.get("name") == name:
            return entry

    new_entry = {"name": name, "dates": [], "data": []}
    if extra_fields:
        new_entry.update(extra_fields)
    as24_list.append(new_entry)
    return new_entry


def update_json(ck_diesel=None, ck_adblue=None, neste=None, as24=None):
    """
    Atnaujina JSON failą su naujomis kainomis.

    Parametrai:
        ck_diesel: {"date": "2026-03-27", "price": 1.63635}
        ck_adblue: {"date": "2026-03-27", "price": 0.756}
        neste: {"diesel": 1.6859, "adblue": 0.684, "date": "2026-03-27"}
        as24: {
            "diesel": [{"name": "Gliwice", "country": "PL", "date": "...", "price": 1.5131}, ...],
            "adblue": [{"name": "Liuksemburgas", "code": "LUX", "date": "...", "price": 0.7541}, ...]
        }
    """
    data = load_existing_data()

    # ── CK Dyzelinas ────────────────────────────────────────────
    if ck_diesel and ck_diesel.get("price"):
        add_single_value(data["ck_dz"], ck_diesel["date"], ck_diesel["price"])
        print(f"[JSON] CK Dyzelinas: {ck_diesel['price']} ({ck_diesel['date']})")

    # ── CK AdBlue ───────────────────────────────────────────────
    if ck_adblue and ck_adblue.get("price"):
        add_single_value(data["ck_ab"], ck_adblue["date"], ck_adblue["price"])
        print(f"[JSON] CK AdBlue: {ck_adblue['price']} ({ck_adblue['date']})")

    # ── Neste ───────────────────────────────────────────────────
    if neste:
        if neste.get("diesel"):
            add_single_value(data["neste_dz"], neste["date"], neste["diesel"])
            print(f"[JSON] Neste Diesel: {neste['diesel']} ({neste['date']})")
        if neste.get("adblue"):
            add_single_value(data["neste_ab"], neste["date"], neste["adblue"])
            print(f"[JSON] Neste AdBlue: {neste['adblue']} ({neste['date']})")

    # ── AS24 Dyzelinas ──────────────────────────────────────────
    if as24 and as24.get("diesel"):
        if not data["as24_dz"]:
            data["as24_dz"] = []

        for station in as24["diesel"]:
            if station.get("price") is None:
                continue
            entry = find_or_create_as24_entry(
                data["as24_dz"],
                station["name"],
                extra_fields={"country": station["country"]},
            )
            add_single_value(entry, station["date"], station["price"])

    # ── AS24 AdBlue ─────────────────────────────────────────────
    if as24 and as24.get("adblue"):
        if not data["as24_ab"]:
            data["as24_ab"] = []

        for country in as24["adblue"]:
            if country.get("price") is None:
                continue
            entry = find_or_create_as24_entry(
                data["as24_ab"],
                country["name"],
                extra_fields={"code": country["code"]},
            )
            add_single_value(entry, country["date"], country["price"])

    # ── Atnaujinimo data ────────────────────────────────────────
    data["updated"] = datetime.now().strftime("%Y-%m-%d")

    # ── Išsaugome ───────────────────────────────────────────────
    with open(config.JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[JSON] Failas atnaujintas: {config.JSON_FILE}")
    return data
