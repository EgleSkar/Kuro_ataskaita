"""
Lietuvos valstybines sventes (ne darbo dienos).
Naudojama nustatyti ar diena yra darbo diena.
"""
from datetime import date, timedelta


def _easter(year):
    """Apskaiciuoja Velyku sekmadieniu data pagal Anonymous Gregorian algoritma."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def lt_holidays(year):
    """Grazina LT ne darbo dienu aibe nurodytais metais."""
    easter = _easter(year)
    holidays = [
        date(year, 1, 1),              # Naujieji metai
        date(year, 2, 16),             # Valstybes atkurimo diena
        date(year, 3, 11),             # Nepriklausomybes atkurimo diena
        easter,                        # Velykos
        easter + timedelta(days=1),    # Velyku pirmadienis
        date(year, 5, 1),              # Taptautine darbo diena
        date(year, 6, 24),             # Rasou ir Joniniu diena
        date(year, 7, 6),              # Valstybes diena
        date(year, 8, 15),             # Zoline
        date(year, 11, 1),             # Visu Sventuju diena
        date(year, 11, 2),             # Velinos
        date(year, 12, 24),            # Kucios
        date(year, 12, 25),            # Kaledos
        date(year, 12, 26),            # Antroji Kaledu diena
    ]
    return set(holidays)


def is_lt_working_day(d):
    """Grazina True jei d yra darbo diena (ne savaitgalis ir ne LT svente)."""
    if d.weekday() >= 5:
        return False
    return d not in lt_holidays(d.year)
