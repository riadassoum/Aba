# -*- coding: utf-8 -*-
"""
abaAcademy.tools.hijri
======================

Convert between the Hijri and Gregorian calendars, offline.

Inside 1343–1500 AH (1924–2077 CE) conversions follow the official Umm al-Qura
calendar table (``ummalqura_data``), the calendar Saudi Arabia publishes and
most of the Gulf uses. Outside that range the standard tabular (arithmetic)
calendar is used. Either can differ by a day from a local moon sighting, which
remains the authority for religious dates; the screen says so.

Also provides month grids for the calendar screen and the main Islamic
occasions of the year. Pure standard library.
"""

from __future__ import annotations

import datetime


_HIJRI_MONTHS = [
    "", "محرّم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى",
    "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوّال", "ذو القعدة", "ذو الحجّة",
]

_GREG_MONTHS = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
    "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

_WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة",
             "السبت", "الأحد"]


def _gregorian_to_jdn(y, m, d):
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return (d + (153 * mm + 2) // 5 + 365 * yy + yy // 4
            - yy // 100 + yy // 400 - 32045)


def _jdn_to_gregorian(jdn):
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    dd = (4 * c + 3) // 1461
    e = c - (1461 * dd) // 4
    mm = (5 * e + 2) // 153
    day = e - (153 * mm + 2) // 5 + 1
    month = mm + 3 - 12 * (mm // 10)
    year = 100 * b + dd - 4800 + mm // 10
    return year, month, day


def _hijri_to_jdn(y, m, d):
    return int((11 * y + 3) // 30 + 354 * y + 30 * m
               - (m - 1) // 2 + d + 1948440 - 385)


def _jdn_to_hijri(jdn):
    jdn = int(jdn)
    l = jdn - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
    l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    m = (24 * l) // 709
    d = l - (709 * m) // 24
    y = 30 * n + j - 30
    return int(y), int(m), int(d)


def tabular_gregorian_to_hijri(y, m, d):
    return _jdn_to_hijri(_gregorian_to_jdn(y, m, d))


def tabular_hijri_to_gregorian(y, m, d):
    return _jdn_to_gregorian(int(_hijri_to_jdn(y, m, d)))


# ---------------------------------------------------------------------------
# Umm al-Qura
# ---------------------------------------------------------------------------

_RJD = 2400000


def _uq():
    from . import ummalqura_data
    return ummalqura_data


def in_ummalqura_range_hijri(y, m=1, d=1):
    lo, hi = _uq().HIJRI_RANGE
    return lo <= (y, m, d) <= hi


def in_ummalqura_range_gregorian(y, m, d):
    lo, hi = _uq().GREGORIAN_RANGE
    return lo <= (y, m, d) <= hi


def _uq_index(y, m):
    return (y - 1) * 12 + m - 1 - _uq().HIJRI_OFFSET


def month_length(y, m):
    """Days in Hijri month ``m`` of year ``y`` (29 or 30)."""
    if not 1 <= m <= 12:
        raise ValueError("month must be 1-12")
    if in_ummalqura_range_hijri(y, m, 1):
        starts = _uq().MONTH_STARTS
        i = _uq_index(y, m)
        if i + 1 < len(starts):
            return starts[i + 1] - starts[i]
    # tabular: odd months 30, even 29, Dhu al-Hijjah 30 in leap years
    if m % 2 == 1:
        return 30
    if m == 12 and (11 * y + 14) % 30 < 11:
        return 30
    return 29


def gregorian_to_hijri(y, m, d):
    """Gregorian date -> (year, month, day) Hijri."""
    if in_ummalqura_range_gregorian(y, m, d):
        from bisect import bisect
        rjd = _gregorian_to_jdn(y, m, d) - _RJD
        starts = _uq().MONTH_STARTS
        index = bisect(starts, rjd) - 1
        months = index + _uq().HIJRI_OFFSET
        years = months // 12
        return years + 1, months - years * 12 + 1, rjd - starts[index] + 1
    return tabular_gregorian_to_hijri(y, m, d)


def hijri_to_gregorian(y, m, d):
    """Hijri date -> (year, month, day) Gregorian. Raises ValueError on an
    impossible day (e.g. the 30th of a 29-day month)."""
    if not 1 <= m <= 12:
        raise ValueError("month must be 1-12")
    if not 1 <= d <= month_length(y, m):
        raise ValueError("day out of range for this month")
    if in_ummalqura_range_hijri(y, m, d):
        rjd = _uq().MONTH_STARTS[_uq_index(y, m)] + d - 1
        return _jdn_to_gregorian(rjd + _RJD)
    return tabular_hijri_to_gregorian(y, m, d)


def calendar_source(y_hijri):
    return ("تقويم أم القرى" if in_ummalqura_range_hijri(y_hijri)
            else "التقويم الهجري الحسابي")


def weekday_of_gregorian(y, m, d):
    """0 = Monday … 6 = Sunday (Python convention)."""
    return datetime.date(y, m, d).weekday()


def hijri_month_days(y, m):
    """Every day of a Hijri month as dicts with the Gregorian equivalent."""
    out = []
    gy, gm, gd = hijri_to_gregorian(y, m, 1)
    start = datetime.date(gy, gm, gd)
    for i in range(month_length(y, m)):
        g = start + datetime.timedelta(days=i)
        out.append({"hijri": (y, m, i + 1),
                    "gregorian": (g.year, g.month, g.day),
                    "weekday": g.weekday(),
                    "occasion": occasion_of(m, i + 1)})
    return out


def add_hijri_months(y, m, delta):
    total = (y * 12 + (m - 1)) + delta
    return total // 12, total % 12 + 1


# The main occasions of the Hijri year, by (month, day).
OCCASIONS = {
    (1, 1): "رأس السنة الهجرية",
    (1, 10): "يوم عاشوراء",
    (3, 12): "ذكرى المولد النبوي في كثير من البلدان",
    (7, 27): "ذكرى الإسراء والمعراج في كثير من البلدان",
    (8, 15): "ليلة النصف من شعبان (مساء الرابع عشر)",
    (9, 1): "أول أيام شهر رمضان",
    (9, 27): "ليلة السابع والعشرين من رمضان",
    (10, 1): "عيد الفطر",
    (12, 8): "يوم التروية",
    (12, 9): "يوم عرفة",
    (12, 10): "عيد الأضحى",
    (12, 11): "أول أيام التشريق",
    (12, 12): "ثاني أيام التشريق",
    (12, 13): "ثالث أيام التشريق",
}


def occasion_of(m, d):
    return OCCASIONS.get((m, d), "")


def upcoming_occasions(from_date=None, count=6):
    """The next ``count`` occasions on or after a Gregorian date, as
    (days_away, label, hijri_tuple, gregorian_tuple)."""
    today = from_date or datetime.date.today()
    hy, _, _ = gregorian_to_hijri(today.year, today.month, today.day)
    found = []
    for year in (hy, hy + 1):
        for (m, d), label in sorted(OCCASIONS.items()):
            try:
                g = hijri_to_gregorian(year, m, d)
            except ValueError:
                continue
            gdate = datetime.date(*g)
            delta = (gdate - today).days
            if delta >= 0:
                found.append((delta, label, (year, m, d), g))
    found.sort()
    return found[:count]


def hijri_month_name(m):
    return _HIJRI_MONTHS[m] if 1 <= m <= 12 else str(m)


def gregorian_month_name(m):
    return _GREG_MONTHS[m] if 1 <= m <= 12 else str(m)


def weekday_name(i):
    return _WEEKDAYS[i % 7]


def _ar_digits(s):
    return str(s).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def format_hijri(y, m, d, weekday=None):
    name = _HIJRI_MONTHS[m] if 1 <= m <= 12 else str(m)
    base = f"{_ar_digits(d)} {name} {_ar_digits(y)} هـ"
    if weekday is not None:
        base = f"{_WEEKDAYS[weekday]} {base}"
    return base


def format_gregorian(y, m, d, weekday=None):
    name = _GREG_MONTHS[m] if 1 <= m <= 12 else str(m)
    base = f"{_ar_digits(d)} {name} {_ar_digits(y)} م"
    if weekday is not None:
        base = f"{_WEEKDAYS[weekday]} {base}"
    return base


def today_both():
    """Return (gregorian_str, hijri_str) for today."""
    now = datetime.date.today()
    wd = now.weekday()
    g = format_gregorian(now.year, now.month, now.day, wd)
    hy, hm, hd = gregorian_to_hijri(now.year, now.month, now.day)
    h = format_hijri(hy, hm, hd, wd)
    return g, h
