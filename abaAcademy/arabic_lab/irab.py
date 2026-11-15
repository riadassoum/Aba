# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.irab
==========================

مدرّب الإعراب — practise parsing (i'rab) on the words of the Qur'an, using
the i'rab edition the academy already carries (resources/quran/ed_ar.e3rab.json,
from the alquran.cloud catalogue). Each ayah's i'rab is a run of segments
of the form (word) explanation; a segment becomes a question only when its
explanation begins with one recognised grammatical role, so the answer is
the book's own words and never a guess. The full explanation is read after
each answer.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QURAN = os.path.join(HERE, "resources", "quran")

# role as it begins the explanation -> the name the learner chooses; longer
# phrases first so that مفعول به is not read as فاعل
ROLES: List[Tuple[str, str]] = [
    ("مفعول مطلق", "مفعول مطلق"), ("مفعول لأجله", "مفعول لأجله"), ("مفعول لاجله", "مفعول لأجله"),
    ("مفعول فيه", "مفعول فيه (ظرف)"), ("مفعول معه", "مفعول معه"), ("مفعول به", "مفعول به"),
    ("نائب فاعل", "نائب فاعل"), ("فاعل", "فاعل"), ("مبتدأ", "مبتدأ"), ("خبر", "خبر"),
    ("مضاف إليه", "مضاف إليه"), ("صفة", "صفة (نعت)"), ("نعت", "صفة (نعت)"), ("حال", "حال"),
    ("تمييز", "تمييز"), ("بدل", "بدل"), ("منادى", "منادى"), ("ظرف زمان", "ظرف زمان"),
    ("ظرف مكان", "ظرف مكان"), ("فعل ماض", "فعل ماضٍ"), ("فعل مضارع", "فعل مضارع"), ("فعل أمر", "فعل أمر"),
    ("اسم موصول", "اسم موصول"), ("اسم إشارة", "اسم إشارة"), ("اسم مجرور", "اسم مجرور"),
    ("حرف جر", "حرف جرّ"), ("لفظ الجلالة مضاف إليه", "مضاف إليه"),
]
SEG = re.compile(r"\(([^()]{1,30})\)\s*([^()]+)")
HARAKAT = re.compile("[ً-ْٰۖ-ۭ]")


def plain(s: str) -> str:
    return HARAKAT.sub("", s).replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")


@dataclass
class Item:
    surah: int
    ayah: int
    word: str
    role: str
    text: str


def role_of(expl: str) -> Optional[str]:
    t = expl.strip().lstrip("،.: ")
    for key, name in ROLES:
        if t.startswith(key):
            nxt = t[len(key):len(key) + 1]
            if nxt and "ء" <= nxt <= "ي":      # فاعلها, خبرية: part of a longer word
                continue
            return name
    return None


def parse(e3rab: List[str], ayat: Dict[Tuple[int, int], str], keys: List[Tuple[int, int]]) -> List[Item]:
    items = []
    for (s, a), text in zip(keys, e3rab):
        ayah = plain(ayat.get((s, a), ""))
        for m in SEG.finditer(text):
            word, expl = m.group(1).strip(), m.group(2).strip()
            if " " in word or len(plain(word)) < 2:
                continue
            role = role_of(expl)
            if not role or plain(word) not in ayah:
                continue
            items.append(Item(s, a, word, role, expl.rstrip("، ")))
    return items


class Irab:
    _inst = None

    def __init__(self):
        with open(os.path.join(QURAN, "quran_data.json"), encoding="utf-8") as f:
            q = json.load(f)
        self.surahs = q["surahs"]
        self.ayat = {(a[0], a[1]): a[6] for a in q["ayat"]}
        keys = [(a[0], a[1]) for a in q["ayat"]]
        path = os.path.join(QURAN, "ed_ar.e3rab.json")
        e3 = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                e3 = json.load(f)
        self.items = parse(e3, self.ayat, keys)
        self.roles = sorted({i.role for i in self.items})

    @classmethod
    def get(cls) -> "Irab":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def surah_name(self, n: int) -> str:
        name = HARAKAT.sub("", self.surahs[n - 1]["name"]).replace("ٱ", "ا")
        return name[5:] if name.startswith("سورة ") else name

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for i in self.items:
            out[i.role] = out.get(i.role, 0) + 1
        return out


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(ir: Irab, surah: Optional[int] = None, role: Optional[str] = None,
                  rng: Optional[random.Random] = None) -> Optional[Question]:
    rng = rng or random.Random()
    pool = [i for i in ir.items if (surah is None or i.surah == surah)]
    if role:
        pool = [i for i in pool if i.role == role] or pool
    if not pool:
        return None
    it = rng.choice(pool)
    # a role is right only once in the options: near confusions first
    near = {"فاعل": ["نائب فاعل", "مبتدأ", "مفعول به"], "مفعول به": ["فاعل", "مفعول مطلق", "تمييز"],
            "مبتدأ": ["خبر", "فاعل", "اسم موصول"], "خبر": ["مبتدأ", "صفة (نعت)", "حال"],
            "حال": ["تمييز", "صفة (نعت)", "مفعول مطلق"], "صفة (نعت)": ["بدل", "حال", "خبر"],
            "مضاف إليه": ["اسم مجرور", "صفة (نعت)", "بدل"]}
    def clash(r):          # a role the explanation also mentions would be right too
        keys = [k for k, n in ROLES if n == r]
        return any(k in it.text for k in keys)

    wrong = [r for r in near.get(it.role, []) if r in ir.roles and r != it.role and not clash(r)]
    rest = [r for r in ir.roles if r != it.role and r not in wrong and not clash(r)]
    rng.shuffle(rest)
    opts = (wrong + rest)[:3] + [it.role]
    rng.shuffle(opts)
    ayah = HARAKAT.sub("", ir.ayat[(it.surah, it.ayah)]).replace("ٱ", "ا")
    prompt = (f"سورة {ir.surah_name(it.surah)}، الآية {it.ayah}: {' '.join(ayah.split())}\n"
              f"ما إعراب كلمة {HARAKAT.sub('', it.word)}؟")
    return Question(prompt, opts, it.role, f"({HARAKAT.sub('', it.word)}) {it.text}")
