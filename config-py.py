"""
Kuro kainų stebėjimo sistema — nustatymai.
Visi slaptažodžiai ir prisijungimai imami iš aplinkos kintamųjų (GitHub Secrets).
"""
import os

# ── Orlen LT (CK) ──────────────────────────────────────────────
CK_PDF_URL = "https://www.orlenlietuva.lt/LT/Wholesale/Prices/"
CK_ADBLUE_URL = os.getenv("CK_ADBLUE_URL", "")  # Circle K AdBlue puslapis

# ── Neste ───────────────────────────────────────────────────────
NESTE_URL = os.getenv("NESTE_URL", "https://www.neste.lt/lt")
NESTE_EMAIL = os.getenv("NESTE_EMAIL", "")
NESTE_PASSWORD = os.getenv("NESTE_PASSWORD", "")
NESTE_CLIENT = "Delamode Baltics"
NESTE_COUNTRY = "Lietuva"

# ── AS24 ────────────────────────────────────────────────────────
AS24_URL = os.getenv("AS24_URL", "https://auth.as24.com")
AS24_CLIENT_ID = os.getenv("AS24_CLIENT_ID", "688701")
AS24_EMAIL = os.getenv("AS24_EMAIL", "")
AS24_PASSWORD = os.getenv("AS24_PASSWORD", "")

# AS24 dyzelino degalinės (Kaina pagal degalinę → Suma po nuolaidų be PVM)
AS24_DIESEL_STATIONS = [
    {"name": "Gliwice",          "filter": "GLIWICE",          "country": "PL"},
    {"name": "Niederzissen A61", "filter": "NIEDERZISSEN A61", "country": "DEU"},
    {"name": "Autohof Kufstein", "filter": "AUTOHOF KUFSTEIN", "country": "AUT"},
    {"name": "Turnhout",         "filter": "TURNHOUT",         "country": "BEL"},
    {"name": "Calais Port",      "filter": "CALAIS PORT",      "country": "FRA"},
    {"name": "La Jonquera 1",    "filter": "LA JONQUERA 1",    "country": "ESP"},
    {"name": "Rodange 2",        "filter": "RODANGE 2",        "country": "LUX"},
    {"name": "ITA",              "filter": "ITA",              "country": "ITA"},
]

# AS24 AdBlue šalys (Kaina pagal šalį → konkreti zona → Suma po nuolaidų be PVM)
AS24_ADBLUE_COUNTRIES = [
    {"name": "Liuksemburgas", "code": "LUX", "country_filter": "Liuksemburgas", "zone": "A"},
    {"name": "Čekija",        "code": "CZE", "country_filter": "Čekija",        "zone": "A"},
    {"name": "Prancūzija",    "code": "FRA", "country_filter": "Prancūzija",    "zone": "D"},
    {"name": "Belgija",       "code": "BEL", "country_filter": "Belgija",       "zone": "A"},
    {"name": "Italija",       "code": "ITA", "country_filter": "Italija",       "zone": "A"},
    {"name": "Vokietija",     "code": "DEU", "country_filter": "Vokietija",     "zone": "S"},
    {"name": "Lenkija",       "code": "POL", "country_filter": "Lenkija",       "zone": "A"},
    {"name": "Austrija",      "code": "AUT", "country_filter": "Austrija",      "zone": "A"},
    {"name": "Ispanija",      "code": "ESP", "country_filter": "Ispanija",      "zone": "A"},
    {"name": "Slovėnija",     "code": "SVN", "country_filter": "Slovėnija",     "zone": "A"},
    {"name": "Nyderlandai",   "code": "NLD", "country_filter": "Nyderlandai",   "zone": ""},
]

# ── JSON failas ─────────────────────────────────────────────────
JSON_FILE = "kuro_kainos.json"

# ── Cookies ─────────────────────────────────────────────────────
COOKIES_DIR = "cookies"
AS24_COOKIES = os.path.join(COOKIES_DIR, "as24_cookies.json")
NESTE_COOKIES = os.path.join(COOKIES_DIR, "neste_cookies.json")
