# -*- coding: utf-8 -*-
"""
abaAcademy.tools.num_words
==========================

الأعداد في اللغات — whole numbers from 0 to 999,999,999 written out in
English, French, Spanish, German, Italian and Turkish (plus Arabic through
the academy's tafqit), following each language's standard rules: French
soixante-dix and quatre-vingts with their s, Spanish veintiún mil and
quinientos, German einundzwanzig, Italian ventotto and ventitré, Turkish
bin and yüz without bir. Written from the grammar books, no dependency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

LANGS = {"en": "الإنجليزية", "fr": "الفرنسية", "es": "الإسبانية", "de": "الألمانية", "it": "الإيطالية",
         "tr": "التركية", "ar": "العربية"}
MAX = 999_999_999


def _check(n: int) -> None:
    if not isinstance(n, int) or n < 0 or n > MAX:
        raise ValueError("اكتب عددًا صحيحًا من صفر إلى 999999999.")


# -- English ----------------------------------------------------------------
EN1 = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
      "seventeen eighteen nineteen".split()
EN10 = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _en99(n):
    if n < 20:
        return EN1[n]
    t, u = divmod(n, 10)
    return EN10[t] + (f"-{EN1[u]}" if u else "")


def _en999(n):
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts.append(f"{EN1[h]} hundred")
    if r:
        parts.append(("and " if h else "") + _en99(r))
    return " ".join(parts)


def en(n: int) -> str:
    _check(n)
    if n == 0:
        return "zero"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append(f"{_en999(m)} million")
    if k:
        parts.append(f"{_en999(k)} thousand")
    if u:
        parts.append(("and " if u < 100 and (m or k) else "") + _en999(u))
    return " ".join(parts)


# -- French -----------------------------------------------------------------
FR1 = "zéro un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize dix-sept " \
      "dix-huit dix-neuf".split()
FR10 = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _fr99(n, final=True):
    if n < 20:
        return FR1[n]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base = "soixante" if t == 7 else "quatre-vingt"
        rest = 10 + u
        if t == 7 and u == 1:
            return "soixante et onze"
        return f"{base}-{FR1[rest]}"
    if t == 8:
        return "quatre-vingts" if u == 0 and final else ("quatre-vingt" if u == 0 else f"quatre-vingt-{FR1[u]}")
    if u == 0:
        return FR10[t]
    if u == 1:
        return f"{FR10[t]} et un"
    return f"{FR10[t]}-{FR1[u]}"


def _fr999(n, final=True):
    h, r = divmod(n, 100)
    if not h:
        return _fr99(r, final)
    if h == 1:
        head = "cent"
    else:
        head = f"{FR1[h]} cent" + ("s" if r == 0 and final else "")
    return head + (f" {_fr99(r, final)}" if r else "")


def fr(n: int) -> str:
    _check(n)
    if n == 0:
        return "zéro"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append(("un million" if m == 1 else f"{_fr999(m)} millions"))
    if k:
        parts.append("mille" if k == 1 else f"{_fr999(k, final=False)} mille")
    if u:
        parts.append(_fr999(u))
    return " ".join(parts)


# -- Spanish ----------------------------------------------------------------
ES1 = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis "
       "diecisiete dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco veintiséis "
       "veintisiete veintiocho veintinueve").split()
ES10 = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
ES100 = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
         7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _es99(n):
    if n < 30:
        return ES1[n]
    t, u = divmod(n, 10)
    return ES10[t] + (f" y {ES1[u]}" if u else "")


def _es999(n):
    h, r = divmod(n, 100)
    if not h:
        return _es99(r)
    if h == 1 and r == 0:
        return "cien"
    return ES100[h] + (f" {_es99(r)}" if r else "")


def _apocope(s: str) -> str:
    """uno → un before a noun (mil, millones); veintiuno → veintiún."""
    if s.endswith("veintiuno"):
        return s[:-9] + "veintiún"
    if s.endswith("uno"):
        return s[:-3] + "un"
    return s


def es(n: int) -> str:
    _check(n)
    if n == 0:
        return "cero"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append("un millón" if m == 1 else f"{_apocope(_es999(m))} millones")
    if k:
        parts.append("mil" if k == 1 else f"{_apocope(_es999(k))} mil")
    if u:
        parts.append(_es999(u))
    return " ".join(parts)


# -- German -----------------------------------------------------------------
DE1 = "null eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf dreizehn vierzehn fünfzehn sechzehn " \
      "siebzehn achtzehn neunzehn".split()
DE10 = "_ _ zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig".split()


def _de99(n, final=True):
    if n == 1:
        return "eins" if final else "ein"
    if n < 20:
        return DE1[n]
    t, u = divmod(n, 10)
    if not u:
        return DE10[t]
    return ("ein" if u == 1 else DE1[u]) + "und" + DE10[t]


def _de999(n, final=True):
    h, r = divmod(n, 100)
    out = ""
    if h:
        out = ("ein" if h == 1 else DE1[h]) + "hundert"
    if r:
        out += _de99(r, final)
    return out


def de(n: int) -> str:
    _check(n)
    if n == 0:
        return "null"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append("eine Million" if m == 1 else f"{_de999(m, False)} Millionen")
    tail = ""
    if k:
        tail = ("ein" if k == 1 else _de999(k, False)) + "tausend"
    if u:
        tail += _de999(u)
    if tail:
        parts.append(tail)
    return " ".join(parts)


# -- Italian ----------------------------------------------------------------
IT1 = "zero uno due tre quattro cinque sei sette otto nove dieci undici dodici tredici quattordici quindici sedici " \
      "diciassette diciotto diciannove".split()
IT10 = "_ _ venti trenta quaranta cinquanta sessanta settanta ottanta novanta".split()


def _it99(n):
    if n < 20:
        return IT1[n]
    t, u = divmod(n, 10)
    base = IT10[t]
    if not u:
        return base
    if u in (1, 8):
        base = base[:-1]
    return base + ("tré" if u == 3 else IT1[u])


def _it999(n):
    h, r = divmod(n, 100)
    out = "" if not h else ("cento" if h == 1 else IT1[h] + "cento")
    if r:
        tail = _it99(r)
        if h and r == 8 or (h and 80 <= r < 90):
            out = out[:-1]                       # centotto, centottanta
        if h and r == 3:
            tail = "tré"
        out += tail
    return out


def it(n: int) -> str:
    _check(n)
    if n == 0:
        return "zero"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append("un milione" if m == 1 else f"{_it999(m)} milioni")
    tail = ""
    if k:
        tail = "mille" if k == 1 else _it999(k) + "mila"
    if u:
        tail += _it999(u)
    if tail:
        parts.append(tail)
    return " ".join(parts)


# -- Turkish ----------------------------------------------------------------
TR1 = "sıfır bir iki üç dört beş altı yedi sekiz dokuz".split()
TR10 = "_ on yirmi otuz kırk elli altmış yetmiş seksen doksan".split()


def _tr999(n, drop_one=False):
    h, r = divmod(n, 100)
    t, u = divmod(r, 10)
    parts = []
    if h:
        parts.append("yüz" if h == 1 else f"{TR1[h]} yüz")
    if t:
        parts.append(TR10[t])
    if u:
        parts.append(TR1[u])
    s = " ".join(parts)
    return "" if drop_one and n == 1 else s


def tr(n: int) -> str:
    _check(n)
    if n == 0:
        return "sıfır"
    m, rest = divmod(n, 1_000_000)
    k, u = divmod(rest, 1000)
    parts = []
    if m:
        parts.append(f"{_tr999(m)} milyon")
    if k:
        parts.append(("bin" if k == 1 else f"{_tr999(k)} bin"))
    if u:
        parts.append(_tr999(u))
    return " ".join(parts)


def ar(n: int) -> str:
    _check(n)
    from .tafqit import number_to_arabic_words
    return number_to_arabic_words(n)


CONVERT: Dict[str, Callable[[int], str]] = {"en": en, "fr": fr, "es": es, "de": de, "it": it, "tr": tr, "ar": ar}


def words(n: int, lang: str) -> str:
    return CONVERT[lang](n)


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def _pick(rng: random.Random, level: int) -> int:
    hi = [20, 100, 1000, 10000, 1_000_000][max(0, min(4, level))]
    return rng.randint(0, hi)


def make_question(lang: str, level: int = 1, rng: Optional[random.Random] = None,
                  direction: str = "to_number") -> Question:
    """to_number: hear the words, choose the digits; to_words: the reverse."""
    rng = rng or random.Random()
    n = _pick(rng, level)
    wrong = set()
    while len(wrong) < 3:
        d = rng.choice([1, 2, 10, 11, 20, 100, 9, 90]) * rng.choice([-1, 1])
        m = n + d if rng.random() < .7 else _pick(rng, level)
        if m != n and 0 <= m <= MAX:
            wrong.add(m)
    nums = list(wrong) + [n]
    rng.shuffle(nums)
    w = words(n, lang)
    if direction == "to_number":
        return Question(f"ما العدد المكتوب: {w}؟", [str(x) for x in nums], str(n), f"{w} = {n}.")
    return Question(f"كيف يُكتب العدد {n} بـ{LANGS[lang]}؟", [words(x, lang) for x in nums], w, f"{n} = {w}.")
