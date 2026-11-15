# -*- coding: utf-8 -*-
"""
abaAcademy.geo_countries
========================

أطلس دول العالم — the member states of the United Nations and the two
observer states: Arabic name, capital, currency, region, area, population,
neighbours and calling code, with quizzes.

Data: mledoze/countries (ODbL-1.0) and Wikidata (CC0), combined by
devtools/course_builder/build_countries.py. Populations are the latest
figures on Wikidata when the data was built, so they are rounded when read.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import List, Optional

from .tools.ar_count import count

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "resources", "geo", "countries.json")

ARAB_LEAGUE = {"DZA", "BHR", "COM", "DJI", "EGY", "IRQ", "JOR", "KWT", "LBN", "LBY", "MRT", "MAR", "OMN", "PSE",
               "QAT", "SAU", "SOM", "SDN", "SYR", "TUN", "ARE", "YEM"}


def load(path: str = DATA) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)["countries"]


def _num(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f} مليار".replace(".00", "")
    if n >= 1_000_000:
        return f"{n / 1e6:.1f} مليون".replace(".0 ", " ")
    return f"{n:,}".replace(",", "٬")


def describe(c: dict) -> str:
    lines = [c["name"] + (f" ({c['official']})" if c.get("official") and c["official"] != c["name"] else "")]
    if c.get("capital"):
        many = "، " in c["capital"]
        lines.append(("العواصم: " if many else "العاصمة: ") + c["capital"])
    elif c.get("capital_note"):
        lines.append(c["capital_note"])
    if c.get("region"):
        lines.append("المنطقة: " + c["region"] + (f"، {c['subregion']}" if c.get("subregion") else ""))
    if c.get("currency"):
        lines.append("العملة: " + c["currency"])
    if c.get("population"):
        lines.append("عدد السكان: نحو " + _num(c["population"]) + " نسمة")
    if c.get("area"):
        lines.append(f"المساحة: {_num(int(c['area']))} كيلومتر مربّع")
    if c.get("borders"):
        lines.append(f"تحدّها {count(len(c['borders']), 'country')}: " + "، ".join(c["borders"]))
    else:
        lines.append("ليس لها حدود برّية مع دولة أخرى." if not c.get("landlocked") else "")
    if c.get("landlocked"):
        lines.append("دولة حبيسة لا تطلّ على بحر.")
    if c.get("iso") in ARAB_LEAGUE:
        lines.append("عضو في جامعة الدول العربية.")
    if c.get("calling"):
        lines.append("رمز الاتصال الدولي: " + c["calling"])
    return "\n".join(l for l in lines if l)


def find(countries: List[dict], text: str) -> List[dict]:
    t = text.strip()
    if not t:
        return countries
    return [c for c in countries if t in c["name"] or t in (c.get("capital") or "") or t in c.get("official", "")]


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


KINDS = ["capital", "country_of_capital", "currency", "region", "neighbour", "bigger"]


def make_question(countries: List[dict], kind: Optional[str] = None, region: Optional[str] = None,
                  rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    pool = [c for c in countries if not region or c.get("region") == region or
            (region == "العربية" and c["iso"] in ARAB_LEAGUE)]
    if len(pool) < 4:
        return None
    kind = kind or rng.choice(KINDS)
    for _ in range(40):
        c = rng.choice(pool)
        near = [x for x in pool if x is not c and x.get("subregion") == c.get("subregion")]
        far = [x for x in pool if x is not c and x not in near]
        rng.shuffle(near)
        rng.shuffle(far)
        others = near + far

        def pick(field):
            seen = []
            for x in others:
                v = x.get(field)
                if v and v != c.get(field) and v not in seen:
                    seen.append(v)
                if len(seen) == 3:
                    break
            return seen

        if kind == "capital" and c.get("capital"):
            wrong = pick("capital")
            opts = wrong + [c["capital"]]
            rng.shuffle(opts)
            return Question(f"ما عاصمة {c['name']}؟", opts, c["capital"], describe(c).split("\n")[1] + ".")
        if kind == "country_of_capital" and c.get("capital"):
            wrong = pick("name")
            opts = wrong + [c["name"]]
            rng.shuffle(opts)
            return Question(f"{c['capital']} عاصمة أيّ دولة؟", opts, c["name"], f"{c['capital']} عاصمة {c['name']}.")
        if kind == "currency" and c.get("currency"):
            wrong = pick("currency")
            if len(wrong) < 3:
                continue
            opts = wrong + [c["currency"]]
            rng.shuffle(opts)
            return Question(f"ما عملة {c['name']}؟", opts, c["currency"], f"عملة {c['name']}: {c['currency']}.")
        if kind == "region" and c.get("subregion"):
            regs = sorted({x["subregion"] for x in countries if x.get("subregion")} - {c["subregion"]})
            rng.shuffle(regs)
            opts = regs[:3] + [c["subregion"]]
            rng.shuffle(opts)
            return Question(f"أين تقع {c['name']}؟", opts, c["subregion"], f"تقع {c['name']} في {c['subregion']}.")
        if kind == "neighbour" and c.get("borders"):
            right = rng.choice(c["borders"])
            wrong = [x["name"] for x in others if x["name"] not in c["borders"] and x["name"] != c["name"]][:3]
            opts = wrong + [right]
            rng.shuffle(opts)
            return Question(f"أيّ هذه الدول تحدّ {c['name']}؟", opts, right,
                            f"جيران {c['name']}: " + "، ".join(c["borders"]) + ".")
        if kind == "bigger" and c.get("population"):
            rivals = [x for x in others if x.get("population") and abs(x["population"] - c["population"]) > 0.2 * c["population"]][:1]
            if not rivals:
                continue
            r = rivals[0]
            big = c if c["population"] > r["population"] else r
            opts = [c["name"], r["name"]]
            rng.shuffle(opts)
            return Question(f"أيّهما أكثر سكانًا: {opts[0]} أم {opts[1]}؟", opts, big["name"],
                            f"{c['name']} نحو {_num(c['population'])}، و{r['name']} نحو {_num(r['population'])}.")
        kind = rng.choice(KINDS)
    return None
