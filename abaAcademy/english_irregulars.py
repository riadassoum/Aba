# -*- coding: utf-8 -*-
"""
abaAcademy.english_irregulars
=============================

الأفعال والجموع الشاذّة في الإنجليزية — the irregular verbs (base, past, past
participle) and irregular plurals a learner meets in the academy's English
sentences, from LemmInflect (MIT) / AGID, with the Arabic meaning from the
offline dictionary and an example sentence from the sentence bank.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "resources", "english", "irregulars.json")
_d = None


def data() -> dict:
    global _d
    if _d is None:
        if os.path.exists(DATA):
            with open(DATA, encoding="utf-8") as f:
                _d = json.load(f)
        else:
            _d = {"verbs": [], "nouns": []}
    return _d


def meaning(word: str) -> str:
    try:
        from .offline_dict import OfflineDictionary
        ar = OfflineDictionary.get().en.get(word.lower(), [])
        return "، ".join(ar[:3])
    except Exception:
        return ""


def example(*forms: str) -> str:
    try:
        from .gui.sentence_bank_view import load
    except Exception:
        return ""
    pat = re.compile(r"\b(" + "|".join(re.escape(f) for f in forms if f) + r")\b", re.I)
    for a, b in load("en"):
        if 4 <= len(a.split()) <= 10 and pat.search(a):
            return f"{a} ({b})"
    return ""


def describe_verb(v: dict) -> str:
    text = f"{v['base']}، الماضي {v['past']}، اسم المفعول {v['part']}"
    m = meaning(v["base"])
    if m:
        text += f". المعنى: {m}"
    return text + "."


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(rng: Optional[random.Random] = None, top: int = 120) -> Optional[Question]:
    rng = rng or random.Random()
    d = data()
    verbs = d["verbs"][:top]
    if rng.random() < 0.2 and len(d["nouns"]) >= 4:
        n = rng.choice(d["nouns"][:40])
        others = [x["pl"] for x in d["nouns"] if x is not n]
        rng.shuffle(others)
        regular = n["sing"] + "s"
        opts = list(dict.fromkeys([n["pl"], regular] + others))[:4]
        rng.shuffle(opts)
        return Question(f"ما جمع {n['sing']}؟", opts, n["pl"], f"{n['sing']}، والجمع {n['pl']}.")
    if len(verbs) < 4:
        return None
    v = rng.choice(verbs)
    which = rng.choice(["past", "part"])
    right = v[which].split(" أو ")[0]
    wrong = {v["base"] + "ed", v["base"] + "d" if v["base"].endswith("e") else v["base"] + "ed"}
    wrong |= {v["past" if which == "part" else "part"].split(" أو ")[0]}
    wrong |= {x[which].split(" أو ")[0] for x in rng.sample(verbs, 3)}
    wrong -= set(v[which].split(" أو "))      # every accepted form is right
    opts = list(wrong)[:3] + [right]
    rng.shuffle(opts)
    label = "الماضي" if which == "past" else "اسم المفعول (التصريف الثالث)"
    return Question(f"ما {label} من الفعل {v['base']}؟", opts, right, describe_verb(v))
