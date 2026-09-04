# -*- coding: utf-8 -*-
"""
abaAcademy.tools.hijri
======================

Convert between the Islamic (Hijri) and Gregorian calendars, offline, using the
standard tabular/arithmetic algorithm (Kuwaiti algorithm via Julian Day Number).
A practical everyday tool for a student: knowing today's Hijri date, or turning a
Hijri date into its Gregorian equivalent, without a network lookup.

Honest note: this is the *arithmetic* (tabular) Hijri calendar, which can differ
by a day from the *observational* (moon-sighting) calendar used for religious
dates in a given country. It is exactly right for everyday conversion and study;
for a religious ruling on a specific day's date, the local moon sighting is the
authority. The GUI states this.

Pure standard library.
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


def gregorian_to_hijri(y, m, d):
    return _jdn_to_hijri(_gregorian_to_jdn(y, m, d))


def hijri_to_gregorian(y, m, d):
    return _jdn_to_gregorian(int(_hijri_to_jdn(y, m, d)))


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
