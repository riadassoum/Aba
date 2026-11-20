# -*- coding: utf-8 -*-
"""
abaAcademy.science.solar_system
===============================

المجموعة الشمسية — the Sun, the eight planets, the Moon and two dwarf
planets with figures from Wikidata (CC0): mass, radius, surface gravity, the
length of their year and their distance from the Sun, read in Arabic in
units a learner can picture (Earth masses, kilometres, days and years,
millions of kilometres), with comparison quizzes.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import List, Optional

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "resources", "science", "solar_system.json")
AU = 149_597_870_700.0
DAY = 86_400.0


def load(path: str = DATA) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["bodies"]
    for r in rows:
        if r["id"] == "Q405":
            r["name"] = "القمر"
    return rows


def _n(x: float, digits: int = 3) -> str:
    if x >= 100:
        s = f"{x:,.0f}"
    elif x >= 10:
        s = f"{x:.1f}"
    elif x >= 0.1:
        s = f"{x:.{digits - 1}f}".rstrip("0").rstrip(".")
    else:
        s = f"{x:.2g}"
    return s.replace(",", "٬")


def describe(b: dict, bodies: List[dict]) -> str:
    earth = next((x for x in bodies if x["id"] == "Q2"), None)
    lines = [f"{b['name']}: {b['kind']}."]
    if b.get("radius_m"):
        km = b["radius_m"] / 1000
        rel = f"، أي {_n(b['radius_m'] / earth['radius_m'])} مرّة نصف قطر الأرض" if earth and b is not earth else ""
        lines.append(f"نصف القطر نحو {_n(km)} كيلومتر{rel}.")
    if b.get("mass_kg") and earth:
        lines.append(f"الكتلة نحو {_n(b['mass_kg'] / earth['mass_kg'])} مرّة كتلة الأرض." if b is not earth
                     else f"الكتلة نحو {b['mass_kg']:.2e} كيلوغرام.".replace("e+", " × 10 أس "))
    if b.get("gravity"):
        lines.append(f"الجاذبية على سطحه {_n(b['gravity'])} متر في الثانية المربّعة"
                     + (f"، فمن يزن على الأرض ستين كيلوغرامًا يزن هناك كأنّه {_n(60 * b['gravity'] / 9.81)} كيلوغرامًا." if b["id"] != "Q2" else "."))
    if b.get("period_s"):
        days = b["period_s"] / DAY
        around = "حول الأرض" if b["id"] == "Q405" else "حول الشمس"
        if days < 400:
            lines.append(f"يدور {around} في نحو {_n(days)} يومًا.")
        else:
            lines.append(f"يدور {around} في نحو {_n(days / 365.25)} سنة أرضية.")
    if b.get("distance_m"):
        if b["id"] == "Q405":
            lines.append(f"يبعد عن الأرض نحو {_n(b['distance_m'] / 1000)} كيلومتر.")
        else:
            lines.append(f"يبعد عن الشمس نحو {_n(b['distance_m'] / 1e9)} مليون كيلومتر، "
                         f"أي {_n(b['distance_m'] / AU)} وحدة فلكية (بعد الأرض عن الشمس).")
    return "\n".join(lines)


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


COMPARE = [("radius_m", "أكبر حجمًا"), ("mass_kg", "أثقل كتلة"), ("gravity", "أقوى جاذبية على سطحه"),
           ("distance_m", "أبعد عن الشمس")]


def make_question(bodies: List[dict], rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    planets = [b for b in bodies if b["kind"] == "كوكب"]
    if rng.random() < 0.25:
        p = rng.choice(planets)
        order = sorted(planets, key=lambda b: b["distance_m"])
        right = str(order.index(p) + 1)
        opts = sorted({right} | set(rng.sample([str(i) for i in range(1, 9) if str(i) != right], 3)), key=int)
        return Question(f"ما ترتيب {p['name']} بين الكواكب من الشمس؟", opts, right,
                        "ترتيب الكواكب من الشمس: " + "، ".join(b["name"] for b in order) + ".")
    field, phrase = rng.choice(COMPARE)
    pool = [b for b in bodies if b.get(field) and b["id"] != "Q525" and (field != "distance_m" or b["id"] != "Q405")]
    a, b = rng.sample(pool, 2)
    big = a if a[field] > b[field] else b
    opts = [a["name"], b["name"]]
    return Question(f"أيّهما {phrase}: {a['name']} أم {b['name']}؟", opts, big["name"],
                    f"{big['name']} {phrase}.")
