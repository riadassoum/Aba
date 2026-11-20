# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.collocations
==================================

معجم المتلازمات اللفظية — about 20,000 vowelled Arabic collocations (words
that habitually go together: آثار الوضوء، دار الإسلام، صلاة الجماعة) with
their grammatical relation, from the Maskouk collocation dictionary by Taha
Zerrouki (GPL, https://github.com/linuxscout/maskouk). The database is read
directly, one short-lived read-only connection per call, so it works from
any thread.
"""

from __future__ import annotations

import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "thirdparty", "maskouk", "data", "collocations.sqlite")
HARAKAT = re.compile("[ً-ْٰـ]")
EXCLUDE = {"اللَّهُ الْيَهُودَ"}           # a sentence fragment, not a collocation


def strip(s: str) -> str:
    return HARAKAT.sub("", s or "").strip()


@dataclass
class Collocation:
    vocalized: str
    plain: str
    relation: str
    first: str
    second: str


def available() -> bool:
    return os.path.exists(DB)


def _rows(sql: str, args=()) -> List[Collocation]:
    if not available():
        return []
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        out = []
        for voc, unv, cat, note, a, b in con.execute(sql, args):
            if note and note.startswith("Confused;;;"):
                voc = note.split(";;;", 1)[1]
            if voc in EXCLUDE:
                continue
            out.append(Collocation(voc.strip(), unv or strip(voc), cat or "", a or "", b or ""))
        return out
    finally:
        con.close()


COLS = "select vocalized, unvocalized, category, note, first, second from collocations"


def search(word: str, limit: int = 200) -> List[Collocation]:
    w = strip(word)
    if not w:
        return []
    base = w[2:] if w.startswith("ال") and len(w) > 3 else w
    return _rows(f"{COLS} where first = ? or second = ? or second = ? or first like ? or second like ? "
                 f"order by length(unvocalized) limit ?", (w, w, "ال" + base, w + " %", "% " + w, limit))


def count() -> int:
    if not available():
        return 0
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return con.execute("select count(*) from collocations").fetchone()[0]
    finally:
        con.close()


def random_sample(n: int, rng: Optional[random.Random] = None) -> List[Collocation]:
    rng = rng or random.Random()
    total = count()
    if not total:
        return []
    ids = rng.sample(range(1, total + 1), min(total, n * 3))
    rows = _rows(f"{COLS} where id in ({','.join('?' * len(ids))}) and category is not null "
                 f"and first <> '' and second <> ''", ids)
    rng.shuffle(rows)
    return rows[:n]


@dataclass
class Question:
    prompt: str
    options: List[str]
    answer: str
    explanation: str


def make_question(rng: Optional[random.Random] = None) -> Optional[Question]:
    """Which word completes the collocation? The wrong options are second
    words of other collocations of the same relation."""
    rng = rng or random.Random()
    for _ in range(10):
        pool = random_sample(12, rng)
        if not pool:
            return None
        target = pool[0]
        words = target.vocalized.split()
        if len(words) != 2:
            continue
        right = words[1]
        wrong = []
        for c in pool[1:]:
            ws = c.vocalized.split()
            if len(ws) == 2 and strip(ws[1]) != strip(right) and ws[1] not in wrong:
                wrong.append(ws[1])
        if len(wrong) < 3:
            continue
        opts = wrong[:3] + [right]
        rng.shuffle(opts)
        rel = f" ({target.relation})" if target.relation else ""
        return Question(f"أكمل المتلازمة: {words[0]} ...", opts, right, f"{target.vocalized}{rel}.")
    return None
