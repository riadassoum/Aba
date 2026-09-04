# -*- coding: utf-8 -*-
"""
abaAcademy.tools.tafqit
=======================

Convert a number to its Arabic words (تفقيط) — "١٢٣" → "مئة وثلاثة وعشرون". This
is a genuinely useful, deterministic tool: reading amounts, cheque-style figures,
quantities, and quiz answers aloud correctly is awkward for a screen-reader user
otherwise, and the grammatical form of Arabic numbers (agreement, the reversed
units-then-tens order, the special forms for 11-19 and the hundreds) is
error-prone to do by hand.

Scope: non-negative integers up to the trillions, plus an optional currency
wording. Pure standard library. The grammar implemented here is the common
masculine citation form used for counting; full gender/case agreement with a
counted noun is beyond a single helper and is not claimed.
"""

from __future__ import annotations


_ONES = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة",
         "ثمانية", "تسعة"]
_TENS = ["", "عشرة", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون",
         "سبعون", "ثمانون", "تسعون"]
_TEENS = ["عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر",
          "خمسة عشر", "ستة عشر", "سبعة عشر", "ثمانية عشر", "تسعة عشر"]
_HUNDREDS = ["", "مئة", "مئتان", "ثلاثمئة", "أربعمئة", "خمسمئة",
             "ستمئة", "سبعمئة", "ثمانمئة", "تسعمئة"]

# scale words with their dual and plural forms (singular, dual, plural)
_SCALES = [
    ("", "", ""),
    ("ألف", "ألفان", "آلاف"),
    ("مليون", "مليونان", "ملايين"),
    ("مليار", "ملياران", "مليارات"),
    ("تريليون", "تريليونان", "تريليونات"),
]


def _three(n):
    """Words for a number 0-999."""
    assert 0 <= n < 1000
    parts = []
    h = n // 100
    rem = n % 100
    if h:
        parts.append(_HUNDREDS[h])
    if rem:
        if rem < 10:
            parts.append(_ONES[rem])
        elif rem < 20:
            parts.append(_TEENS[rem - 10])
        else:
            u = rem % 10
            t = rem // 10
            if u:
                parts.append(f"{_ONES[u]} و{_TENS[t]}")
            else:
                parts.append(_TENS[t])
    return " و".join(parts)


def _scale_word(count, scale_index):
    """The scale word (ألف/مليون…) inflected for the count preceding it."""
    sing, dual, plural = _SCALES[scale_index]
    if scale_index == 0:
        return ""
    if count == 1:
        return sing
    if count == 2:
        return dual
    if 3 <= count <= 10:
        return plural
    return sing            # 11+ takes the singular in Arabic


def number_to_arabic_words(n):
    """Return the Arabic words for a non-negative integer ``n``."""
    if n < 0:
        return "سالب " + number_to_arabic_words(-n)
    if n == 0:
        return "صفر"
    # split into groups of three digits
    groups = []
    while n > 0:
        groups.append(n % 1000)
        n //= 1000
    # groups[0] is the lowest (units) group
    chunks = []
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            continue
        if idx == 0:
            chunks.append(_three(g))
        elif g in (1, 2) and idx >= 1:
            # ألف/ألفان, مليون/مليونان… stand alone (لا نقول "واحد مليون")
            chunks.append(_scale_word(g, idx))
        else:
            chunks.append(f"{_three(g)} {_scale_word(g, idx)}")
    return " و".join(chunks)


def number_to_currency_words(n, unit="ريال", subunit=None, sub_value=0):
    """Words for a currency amount, e.g. 'مئة وخمسون ريالاً'. ``subunit`` and
    ``sub_value`` optionally add fractional units (halalas, piastres…)."""
    main = number_to_arabic_words(n) + f" {unit}"
    if subunit and sub_value:
        main += " و" + number_to_arabic_words(sub_value) + f" {subunit}"
    return main
