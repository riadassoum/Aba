# -*- coding: utf-8 -*-
"""
abaAcademy.quran_engine.surah_quiz
==================================

Questions about the surahs of the Qur'an, built from the bundled Qur'an data
itself (so every answer is the data's, not a hand-typed list): the number of
ayat, whether a surah is Makki or Madani, its order in the mushaf, the
juz' it begins in, which surah comes before or after, and which of several
surahs is the longest.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .khatma import QuranIndex, S, A, N, JUZ, PAGE


def clean_name(name: str) -> str:
    for p in ("سُورَةُ ", "سورة "):
        if name.startswith(p):
            return name[len(p):]
    return name


@dataclass
class SurahInfo:
    number: int
    name: str
    ayat: int
    kind: str
    juz: int
    page: int


def surah_table(ix: QuranIndex) -> List[SurahInfo]:
    first: Dict[int, Sequence] = {}
    for row in ix.ayat:
        first.setdefault(row[S], row)
    out = []
    for s in ix.surahs:
        r = first[s["n"]]
        out.append(SurahInfo(s["n"], clean_name(s["name"]), s["count"], s.get("type", ""), r[JUZ], r[PAGE]))
    return out


def describe(info: SurahInfo) -> str:
    return (f"سورة {info.name}: ترتيبها {info.number} في المصحف، {info.kind}، عدد آياتها {info.ayat}، "
            f"تبدأ في الجزء {info.juz} في الصفحة {info.page}.")


@dataclass
class Question:
    prompt: str
    answer: str
    options: List[str]
    explanation: str


KINDS = {"ayat": "عدد الآيات", "type": "مكية أم مدنية", "order": "ترتيب السورة",
         "juz": "الجزء الذي تبدأ فيه", "next": "السورة التالية", "prev": "السورة السابقة",
         "longest": "الأطول بين السور"}


def _num_options(right: int, rng, spread: int, low: int = 1, high: int = 10 ** 6) -> List[str]:
    opts = {right}
    tries = 0
    while len(opts) < 4 and tries < 100:
        tries += 1
        d = rng.randint(1, max(2, spread))
        v = right + (d if rng.random() < 0.5 else -d)
        if low <= v <= high:
            opts.add(v)
    out = [str(x) for x in opts]
    rng.shuffle(out)
    return out


def make_question(table: List[SurahInfo], kind: str, rng: Optional[random.Random] = None,
                  pool: Optional[Sequence[int]] = None) -> Question:
    rng = rng or random.Random()
    nums = list(pool) if pool else [t.number for t in table]
    info = table[rng.choice(nums) - 1]
    if kind == "ayat":
        spread = max(3, info.ayat // 5)
        return Question(f"كم عدد آيات سورة {info.name}؟", str(info.ayat),
                        _num_options(info.ayat, rng, spread, 3, 286), describe(info))
    if kind == "type":
        return Question(f"هل سورة {info.name} مكية أم مدنية؟", info.kind, ["مكية", "مدنية"], describe(info))
    if kind == "order":
        return Question(f"ما ترتيب سورة {info.name} في المصحف؟", str(info.number),
                        _num_options(info.number, rng, 6, 1, 114), describe(info))
    if kind == "juz":
        return Question(f"في أيّ جزء تبدأ سورة {info.name}؟", str(info.juz),
                        _num_options(info.juz, rng, 3, 1, 30), describe(info))
    if kind in ("next", "prev"):
        if kind == "next" and info.number == 114:
            info = table[112]
        if kind == "prev" and info.number == 1:
            info = table[1]
        target = table[info.number] if kind == "next" else table[info.number - 2]
        near = [t for t in table if t.number != target.number and abs(t.number - info.number) <= 4
                and t.number != info.number]
        rng.shuffle(near)
        opts = [target.name] + [t.name for t in near[:3]]
        rng.shuffle(opts)
        word = "بعد" if kind == "next" else "قبل"
        return Question(f"ما السورة التي {word} سورة {info.name} في المصحف؟", target.name, opts,
                        f"{word} سورة {info.name} (رقم {info.number}) تأتي سورة {target.name} "
                        f"(رقم {target.number}).")
    if kind == "longest":
        group = rng.sample(table, 4)
        while len({g.ayat for g in group}) < 4:
            group = rng.sample(table, 4)
        best = max(group, key=lambda g: g.ayat)
        return Question("أيّ هذه السور أكثر آيات؟", best.name, [g.name for g in group],
                        "، ".join(f"{g.name} {g.ayat} آية" for g in sorted(group, key=lambda g: -g.ayat)) + ".")
    raise ValueError(kind)


JUZ_AMMA = list(range(78, 115))
