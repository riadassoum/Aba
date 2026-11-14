# -*- coding: utf-8 -*-
"""
abaAcademy.tools.feature_search
===============================

Ranked search over the academy's features for the hub's quick-jump box.

The query and the feature names are folded the same way (alif and hamza
forms, ta marbuta, alif maqsura, diacritics, the article ال and the
prefixes و/ف/ب), words may match by prefix, one-letter typos are
tolerated, and common synonyms map everyday words to features (صلاة →
مواقيت الصلاة، excel → الجدول الناطق).
"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

_TASHKEEL = re.compile("[ً-ْٰـ]")

SYNONYMS = {
    "excel": "جدول", "اكسل": "جدول", "spreadsheet": "جدول",
    "صلاه": "مواقيت", "اذان": "مواقيت", "قبله": "قبلة",
    "ختمه": "ختم", "ورد": "ختم",
    "مسبحه": "مسبحة", "تسبيح": "مسبحة", "اذكار": "مسبحة",
    "زكاه": "زكاة", "تاريخ": "التقويم", "هجري": "التقويم",
    "كيمياء": "الكيمياء", "فيزياء": "الفيزياء", "عناصر": "الدوري",
    "شعر": "العروض", "بحور": "العروض", "جذر": "الجذور", "وزن": "الأوزان",
    "regex": "النمطية", "python": "البرمجة", "بايثون": "البرمجة", "html": "الويب",
    "debugger": "متتبّع", "تتبع": "متتبّع", "sudoku": "سودوكو", "2048": "٢٠٤٨",
    "احصاء": "الإحصاء", "متوسط": "الإحصاء", "معادله": "المعادلات",
    "ضرب": "الضرب", "كسور": "الكسور", "روماني": "الرومانية", "عمر": "المعدّل",
    "معدل": "المعدّل", "امتحان": "المذاكرة", "واجب": "المذاكرة", "منبه": "الساعة",
    "مؤقت": "الساعة", "stopwatch": "الإيقاف", "اختبار": "الاختبارات", "quiz": "الاختبارات",
    "morse": "مورس", "برايل": "برايل", "braille": "برايل", "دول": "الدول",
    "عواصم": "الدول", "عاصمه": "الدول", "تقرير": "التقرير", "ملف": "ملفّات",
    "متعلم": "المتعلّمين", "انكي": "أنكي", "anki": "أنكي", "بطاقات": "البطاقات",
}


def fold(text: str) -> str:
    t = _TASHKEEL.sub("", text or "").casefold()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ة", "ه"), ("ى", "ي"),
                 ("ؤ", "و"), ("ئ", "ي"), ("ّ", "")):
        t = t.replace(a, b)
    return re.sub(r"[^\w\s٠-٩]", " ", t)


def _words(text: str) -> List[str]:
    out = []
    for w in fold(text).split():
        for p in ("وال", "فال", "بال", "ال", "و", "ف", "ب"):
            if w.startswith(p) and len(w) - len(p) >= 3:
                w = w[len(p):]
                break
        out.append(w)
    return out


def _close(a: str, b: str) -> bool:
    """Equal, or one edit apart (for words of four letters or more)."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def score(query: str, label: str) -> float:
    q = fold(query).strip()
    if not q:
        return 0.0
    lab = fold(label)
    if q in lab:
        return 100.0 + len(q) / max(1, len(lab))
    qw = _words(query)
    expanded = []
    for w in qw:
        expanded.append(w)
        if w in SYNONYMS:
            expanded += _words(SYNONYMS[w])
    lw = _words(label)
    hits = 0.0
    for w in qw:
        cands = [w] + (_words(SYNONYMS[w]) if w in SYNONYMS else [])
        best = 0.0
        for c in cands:
            for x in lw:
                if x == c:
                    best = max(best, 1.0)
                elif x.startswith(c) and len(c) >= 2:
                    best = max(best, 0.85)
                elif _close(x, c):
                    best = max(best, 0.7)
        hits += best
    return 80.0 * hits / len(qw) if qw else 0.0


def search(query: str, labels: Sequence[str], limit: int = 5) -> List[Tuple[float, int]]:
    """[(score, index)] best first, only reasonable matches."""
    ranked = sorted(((score(query, l), i) for i, l in enumerate(labels)), reverse=True)
    return [(s, i) for s, i in ranked[:limit] if s >= 40.0]
