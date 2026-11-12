# -*- coding: utf-8 -*-
"""
abaAcademy.science.arab_countries
=================================

The twenty-two member states of the Arab League: capital, region,
continent, currency, international dialling code and Internet domain, with
an explorer and quiz questions. Every country is listed, so a review
question never asks about one the learner was never shown.

Palestine's capital is given as Jerusalem (القدس), as the Arab League lists
it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Country:
    key: str
    name: str
    capital: str
    region: str
    continent: str
    currency: str
    dial: str
    tld: str


COUNTRIES: Tuple[Country, ...] = (
    Country("dz", "الجزائر", "الجزائر", "المغرب العربي", "أفريقيا", "الدينار الجزائري", "213", ".dz"),
    Country("bh", "البحرين", "المنامة", "الخليج العربي", "آسيا", "الدينار البحريني", "973", ".bh"),
    Country("km", "جزر القمر", "موروني", "القرن الأفريقي والمحيط الهندي", "أفريقيا", "الفرنك القمري", "269", ".km"),
    Country("dj", "جيبوتي", "جيبوتي", "القرن الأفريقي والمحيط الهندي", "أفريقيا", "الفرنك الجيبوتي", "253", ".dj"),
    Country("eg", "مصر", "القاهرة", "وادي النيل", "أفريقيا", "الجنيه المصري", "20", ".eg"),
    Country("iq", "العراق", "بغداد", "المشرق العربي", "آسيا", "الدينار العراقي", "964", ".iq"),
    Country("jo", "الأردن", "عمّان", "المشرق العربي", "آسيا", "الدينار الأردني", "962", ".jo"),
    Country("kw", "الكويت", "الكويت", "الخليج العربي", "آسيا", "الدينار الكويتي", "965", ".kw"),
    Country("lb", "لبنان", "بيروت", "المشرق العربي", "آسيا", "الليرة اللبنانية", "961", ".lb"),
    Country("ly", "ليبيا", "طرابلس", "المغرب العربي", "أفريقيا", "الدينار الليبي", "218", ".ly"),
    Country("mr", "موريتانيا", "نواكشوط", "المغرب العربي", "أفريقيا", "الأوقية الموريتانية", "222", ".mr"),
    Country("ma", "المغرب", "الرباط", "المغرب العربي", "أفريقيا", "الدرهم المغربي", "212", ".ma"),
    Country("om", "عُمان", "مسقط", "الخليج العربي", "آسيا", "الريال العُماني", "968", ".om"),
    Country("ps", "فلسطين", "القدس", "المشرق العربي", "آسيا", "الشيكل والدينار الأردني متداولان", "970", ".ps"),
    Country("qa", "قطر", "الدوحة", "الخليج العربي", "آسيا", "الريال القطري", "974", ".qa"),
    Country("sa", "السعودية", "الرياض", "الخليج العربي", "آسيا", "الريال السعودي", "966", ".sa"),
    Country("so", "الصومال", "مقديشو", "القرن الأفريقي والمحيط الهندي", "أفريقيا", "الشلن الصومالي", "252", ".so"),
    Country("sd", "السودان", "الخرطوم", "وادي النيل", "أفريقيا", "الجنيه السوداني", "249", ".sd"),
    Country("sy", "سوريا", "دمشق", "المشرق العربي", "آسيا", "الليرة السورية", "963", ".sy"),
    Country("tn", "تونس", "تونس", "المغرب العربي", "أفريقيا", "الدينار التونسي", "216", ".tn"),
    Country("ae", "الإمارات", "أبو ظبي", "الخليج العربي", "آسيا", "الدرهم الإماراتي", "971", ".ae"),
    Country("ye", "اليمن", "صنعاء", "الخليج العربي", "آسيا", "الريال اليمني", "967", ".ye"),
)

BY_KEY = {c.key: c for c in COUNTRIES}
FIELDS = {"capital": "العاصمة", "currency": "العملة", "dial": "رمز الاتصال الدولي",
          "region": "الإقليم", "continent": "القارّة", "tld": "نطاق الإنترنت"}


def describe(c: Country) -> str:
    return (f"{c.name}: العاصمة {c.capital}، في {c.region} بقارّة {c.continent}. "
            f"العملة: {c.currency}. رمز الاتصال الدولي +{c.dial}، ونطاق الإنترنت {c.tld}.")


def regions() -> List[str]:
    out = []
    for c in COUNTRIES:
        if c.region not in out:
            out.append(c.region)
    return out


def in_region(region: str) -> List[Country]:
    return [c for c in COUNTRIES if c.region == region]


def _fold(s: str) -> str:
    return (s.strip().replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
            .replace("ى", "ي").replace("ّ", "").replace("ُ", ""))


def find(q: str) -> Optional[Country]:
    f = _fold(q)
    if f.startswith("ال") and len(f) > 3:
        alt = f[2:]
    else:
        alt = "ال" + f
    for c in COUNTRIES:
        for v in (c.name, c.capital, c.key, c.tld.strip(".")):
            if _fold(v) in (f, alt):
                return c
    if len(f) >= 4:
        for c in COUNTRIES:
            if f in _fold(c.name) or f in _fold(c.capital):
                return c
    return None


@dataclass
class Question:
    prompt: str
    answer: str
    options: List[str]
    explanation: str


QUIZ_KINDS = {"capital": "العاصمة", "country_of_capital": "الدولة من عاصمتها",
              "currency": "العملة", "dial": "رمز الاتصال", "region": "الإقليم"}


def make_question(kind: str, rng: Optional[random.Random] = None,
                  pool: Optional[List[Country]] = None) -> Question:
    rng = rng or random.Random()
    pool = list(pool or COUNTRIES)
    c = rng.choice(pool)
    others = [o for o in COUNTRIES if o is not c]
    rng.shuffle(others)
    if kind == "capital":
        # prefer capitals from the same region as distractors
        same = [o for o in others if o.region == c.region and o.capital != c.capital]
        opts = [c.capital] + [o.capital for o in (same + others) if o.capital != c.capital][:3]
        prompt = f"ما عاصمة {c.name}؟"
        ans = c.capital
    elif kind == "country_of_capital":
        same = [o for o in others if o.region == c.region]
        opts = [c.name] + [o.name for o in (same + others)][:3]
        prompt = f"{c.capital} عاصمة أيّ دولة؟"
        ans = c.name
    elif kind == "currency":
        opts = [c.currency] + [o.currency for o in others if o.currency != c.currency][:3]
        prompt = f"ما عملة {c.name}؟"
        ans = c.currency
    elif kind == "dial":
        opts = ["+" + c.dial] + ["+" + o.dial for o in others][:3]
        prompt = f"ما رمز الاتصال الدولي في {c.name}؟"
        ans = "+" + c.dial
    elif kind == "region":
        regs = regions()
        opts = [c.region] + [r for r in regs if r != c.region][:3]
        prompt = f"في أيّ إقليم تقع {c.name}؟"
        ans = c.region
    else:
        raise ValueError(kind)
    seen, uniq = set(), []
    for o in opts:
        if o not in seen:
            seen.add(o)
            uniq.append(o)
    rng.shuffle(uniq)
    return Question(prompt, ans, uniq, describe(c))
