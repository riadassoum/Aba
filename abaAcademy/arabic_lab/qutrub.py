# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.qutrub
============================

مصرّف الأفعال — conjugates any Arabic verb in every tense with Qutrub, the
open conjugator by Taha Zerrouki (libqutrub, GPL), bundled in
abaAcademy/thirdparty. A triliteral verb needs the vowel of its present
tense (its bab); the academy takes it from the Arramooz verb list
(arabic_lab.sarf) so the learner can type the verb without vowels.
"""

from __future__ import annotations

import os
import random
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_TP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "thirdparty")
if _TP not in sys.path:
    sys.path.insert(0, _TP)

HARAKAT = re.compile("[ً-ْٰ]")
# Qutrub's tense names, in teaching order
TENSES = ["الماضي المعلوم", "المضارع المعلوم", "المضارع المنصوب", "المضارع المجزوم", "الأمر",
          "المضارع المؤكد الثقيل", "الأمر المؤكد", "الماضي المجهول", "المضارع المجهول",
          "المضارع المجهول المنصوب", "المضارع المجهول المجزوم", "المضارع المؤكد الثقيل المجهول"]
PRONOUNS = ["أنا", "نحن", "أنت", "أنتِ", "أنتما", "أنتما مؤ", "أنتم", "أنتن", "هو", "هي", "هما", "هما مؤ", "هم", "هن"]
SPOKEN = {"أنتما مؤ": "أنتما للمؤنّث", "هما مؤ": "هما للمؤنّث", "أنتما": "أنتما للمذكّر", "هما": "هما للمذكّر"}
BAB_HARAKA = {1: "ضمة", 2: "كسرة", 3: "فتحة", 4: "فتحة", 5: "ضمة", 6: "كسرة"}


def plain(s: str) -> str:
    return HARAKAT.sub("", s or "")


def available() -> bool:
    try:
        from libqutrub import mosaref_main  # noqa: F401
        return True
    except Exception:
        return False


@dataclass
class VerbChoice:
    verb: str           # vocalized past tense
    haraka: str         # present-tense vowel name, or "" for non-triliteral
    note: str


def candidates(text: str) -> List[VerbChoice]:
    """The verbs the learner may mean. A three-letter verb is looked up in
    Arramooz for its vowels and bab (there may be several); a longer verb is
    conjugated as written."""
    t = text.strip()
    if not t:
        return []
    from .sarf import BABS, Sarf
    letters = plain(t).replace("ّ", "")
    out: List[VerbChoice] = []
    s = Sarf.get()
    if len(letters) <= 3 or s.verbs_by_plain.get(plain(t)):
        for v in s.verbs_by_plain.get(plain(t), []):
            if re.search("[\u064e\u064f\u0650\u0652]", t) and t.replace("\u0651", "") != v["v"].replace("\u0651", ""):
                continue            # the learner typed different vowels
            name, _, _, model = BABS[v["bab"]]
            ch = VerbChoice(v["v"], BAB_HARAKA[v["bab"]], f"{v['v']} من باب {name} مثل {model}")
            if all(c.verb != ch.verb or c.haraka != ch.haraka for c in out):
                out.append(ch)
        if not out and re.search("[\u064e\u064f\u0650]", t):
            for h in ("فتحة", "ضمة", "كسرة"):
                out.append(VerbChoice(t, h, f"{t} وعين مضارعه {h}"))
        return out
    return [VerbChoice(t, "فتحة", t)]


def conjugate(verb: str, haraka: str = "فتحة", transitive: bool = True) -> Optional[Dict[str, Dict[str, str]]]:
    from libqutrub import mosaref_main
    try:
        r = mosaref_main.do_sarf(verb, haraka or "فتحة", display_format="DICT", transitive=transitive)
    except Exception:
        return None
    if not r:
        return None
    return {k.strip(): {p: f for p, f in v.items()} for k, v in r.items()}


def table_text(table: Dict[str, Dict[str, str]], tense: str) -> str:
    rows = table.get(tense, {})
    lines = []
    for p in PRONOUNS:
        f = rows.get(p, "")
        if f:
            lines.append(f"{SPOKEN.get(p, p)}: {f}")
    return "\n".join(lines)


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(rng: Optional[random.Random] = None, tense: Optional[str] = None,
                  pool: int = 400) -> Optional[Question]:
    """A frequent verb, a tense and a pronoun; the options are that tense's
    forms for other pronouns, so the learner has to tell them apart."""
    from .sarf import Sarf
    rng = rng or random.Random()
    s = Sarf.get()
    verbs = sorted(s.verbs, key=lambda v: -v.get("f", 0))
    seen, top = set(), []
    for v in verbs:
        if v["v"] in seen:
            continue
        seen.add(v["v"])
        if len([x for x in verbs[:3000] if x["v"] == v["v"]]) == 1:
            top.append(v)
        if len(top) >= pool:
            break
    for _ in range(20):
        v = rng.choice(top)
        table = conjugate(v["v"], BAB_HARAKA[v["bab"]], v.get("trans") != "لازم")
        if not table:
            continue
        t = tense or rng.choice(TENSES[:5])
        rows = {p: f for p, f in table.get(t, {}).items() if f}
        forms = {}
        for p, f in rows.items():
            forms.setdefault(f, []).append(p)
        unique = [p for p, f in rows.items() if len(forms[f]) == 1]
        if len(unique) < 4:
            continue
        p = rng.choice(unique)
        right = rows[p]
        wrong = list({rows[x] for x in unique if rows[x] != right})
        rng.shuffle(wrong)
        opts = wrong[:3] + [right]
        rng.shuffle(opts)
        return Question(f"صرّف الفعل {v['v']} في {t} مع {SPOKEN.get(p, p)}", opts, right,
                        f"{SPOKEN.get(p, p)} {right}، في {t} من {v['v']}.")
    return None
