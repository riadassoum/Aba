# -*- coding: utf-8 -*-
"""
abaAcademy.verb_tables
======================

تصريف الأفعال الفرنسية والإسبانية والإيطالية — the simple tenses of about
24,000 verbs (7,000 French, 9,700 Spanish, 7,800 Italian) from the
conjugation templates of verbecc by Brett Tolbert (LGPL-3.0), based on
Verbiste by Pierre Sarrazin (GPL-2.0-or-later). A verb's forms are its
radical (the infinitive less the template's ending) plus the template's
endings, exactly as those projects define them.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "resources", "verbs")

LANGS = {"fr": "الفرنسية", "es": "الإسبانية", "it": "الإيطالية"}
PERSONS = {
    "fr": ["je", "tu", "il / elle", "nous", "vous", "ils / elles"],
    "es": ["yo", "tú", "él / ella / usted", "nosotros", "vosotros", "ellos / ustedes"],
    "it": ["io", "tu", "lui / lei", "noi", "voi", "loro"],
}
IMPERATIVE_PERSONS = {
    "fr": ["(tu)", "(nous)", "(vous)"],
    "es": ["(tú)", "(usted)", "(nosotros)", "(vosotros)", "(ustedes)"],
    "it": ["", "(tu)", "(lui / lei)", "(noi)", "(voi)", "(loro)"],
}
# Arabic names of each mood/tense key
TENSE_NAMES = {
    "Indicatif/présent": "المضارع (الحاضر)", "Indicatif/imparfait": "الماضي الناقص",
    "Indicatif/futur-simple": "المستقبل البسيط", "Indicatif/passé-simple": "الماضي البسيط",
    "Conditionnel/présent": "الشرطي", "Subjonctif/présent": "صيغة الشكّ الحاضرة",
    "Subjonctif/imparfait": "صيغة الشكّ الماضية", "Imperatif/imperatif-présent": "الأمر",
    "Participe/participe-présent": "اسم الفاعل", "Participe/participe-passé": "اسم المفعول",
    "Indicativo/presente": "المضارع (الحاضر)", "Indicativo/pretérito-imperfecto": "الماضي الناقص",
    "Indicativo/pretérito-perfecto-simple": "الماضي البسيط", "Indicativo/futuro": "المستقبل",
    "Subjuntivo/presente": "صيغة الشكّ الحاضرة", "Subjuntivo/pretérito-imperfecto-1": "صيغة الشكّ الماضية (ra)",
    "Subjuntivo/pretérito-imperfecto-2": "صيغة الشكّ الماضية (se)", "Subjuntivo/futuro": "صيغة الشكّ المستقبلة",
    "Imperativo/afirmativo": "الأمر", "Imperativo/negativo": "النهي", "Condicional/presente": "الشرطي",
    "Gerundio/gerundio": "صيغة الاستمرار (gerundio)", "Participo/participo": "اسم المفعول",
    "Indicativo/imperfetto": "الماضي الناقص", "Indicativo/passato-remoto": "الماضي البعيد",
    "Congiuntivo/presente": "صيغة الشكّ الحاضرة", "Congiuntivo/imperfetto": "صيغة الشكّ الماضية",
    "Condizionale/presente": "الشرطي", "Imperativo/affermativo": "الأمر",
    "Infinito/gerundio": "صيغة الاستمرار (gerundio)", "Participio/participio-presente": "اسم الفاعل",
    "Participio/participio-passato": "اسم المفعول",
}
VOWELS = "aeiouhâàéèêëîïôûœ"
_data: Dict[str, dict] = {}


def load(lang: str) -> dict:
    if lang not in _data:
        p = os.path.join(DIR, f"{lang}.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            d["by_inf"] = {v[0]: v for v in d["verbs"]}
        else:
            d = {"templates": {}, "verbs": [], "by_inf": {}}
        _data[lang] = d
    return _data[lang]


def tenses(lang: str) -> List[str]:
    d = load(lang)
    if not d["templates"]:
        return []
    keys = list(next(iter(d["templates"].values())))
    return [k for k in keys if k in TENSE_NAMES]


def conjugate(lang: str, verb: str) -> Optional[Dict[str, List[List[str]]]]:
    d = load(lang)
    v = d["by_inf"].get(verb.strip().lower())
    if v is None:
        return None
    tpl = v[1]
    suffix = tpl.split(":", 1)[1] if ":" in tpl else ""
    rad = v[0][: len(v[0]) - len(suffix)] if suffix and v[0].endswith(suffix) else v[0]
    return {k: [[rad + e for e in p] for p in rows] for k, rows in d["templates"][tpl].items()}


def with_pronoun(lang: str, person: str, form: str) -> str:
    if lang == "fr" and person == "je" and form[:1].lower() in VOWELS:
        return "j'" + form
    return f"{person} {form}"


def table_text(lang: str, verb: str, tense: str) -> str:
    t = conjugate(lang, verb)
    if not t or tense not in t:
        return ""
    rows = t[tense]
    if len(rows) == 6 and "mperat" not in tense:
        persons = PERSONS[lang]
        return "\n".join(with_pronoun(lang, persons[i], " أو ".join(r)) for i, r in enumerate(rows) if r)
    if "mperat" in tense:
        names = IMPERATIVE_PERSONS[lang]
        return "\n".join(f"{' أو '.join(r)} {names[i] if i < len(names) else ''}".strip()
                         for i, r in enumerate(rows) if r and names[i] != "" and not r[0].endswith("-"))
    return "\n".join(" أو ".join(r) for r in rows if r)


def english(lang: str, verb: str) -> str:
    v = load(lang)["by_inf"].get(verb.strip().lower())
    return v[2] if v and len(v) > 2 else ""


def common(lang: str, n: int = 300) -> List[str]:
    vs = sorted(load(lang)["verbs"], key=lambda v: -(v[3] if len(v) > 3 else 0))
    return [v[0] for v in vs[:n]]


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


DRILL_TENSES = {"fr": ["Indicatif/présent", "Indicatif/imparfait", "Indicatif/futur-simple", "Conditionnel/présent",
                       "Subjonctif/présent"],
                "es": ["Indicativo/presente", "Indicativo/pretérito-perfecto-simple", "Indicativo/pretérito-imperfecto",
                       "Indicativo/futuro", "Condicional/presente", "Subjuntivo/presente"],
                "it": ["Indicativo/presente", "Indicativo/imperfetto", "Indicativo/futuro", "Condizionale/presente",
                       "Congiuntivo/presente"]}


def make_question(lang: str, rng: Optional[random.Random] = None, tense: Optional[str] = None,
                  pool: int = 150) -> Optional[Question]:
    rng = rng or random.Random()
    verbs = common(lang, pool)
    for _ in range(30):
        verb = rng.choice(verbs)
        t = conjugate(lang, verb)
        key = tense or rng.choice(DRILL_TENSES[lang])
        rows = t.get(key) if t else None
        if not rows or len(rows) != 6:
            continue
        forms = [r[0] for r in rows if r]
        unique = [i for i, r in enumerate(rows) if r and forms.count(r[0]) == 1]
        if len(unique) < 4:
            continue
        i = rng.choice(unique)
        right = rows[i][0]
        wrong = list({rows[j][0] for j in unique if j != i})
        rng.shuffle(wrong)
        opts = wrong[:3] + [right]
        rng.shuffle(opts)
        person = PERSONS[lang][i]
        meaning = english(lang, verb)
        return Question(f"صرّف {verb}" + (f" ({meaning})" if meaning else "") +
                        f" في {TENSE_NAMES[key]} مع {person}", opts, right,
                        f"{with_pronoun(lang, person.split(' /')[0], right)}، {TENSE_NAMES[key]} من {verb}.")
    return None
