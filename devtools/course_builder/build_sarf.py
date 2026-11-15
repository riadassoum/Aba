# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/arabic/sarf.json from the Arramooz Arabic
dictionary by Taha Zerrouki (GPL-2.0, https://github.com/linuxscout/arramooz):
nouns with root, pattern, kind, the verb they come from, gender, broken
plural and definition; and triliteral verbs with root, conjugation class
(bab) and transitivity.

The files are tab-separated text and are only read, never run.
Entries whose word or definition falls under the academy's content rules
(local_rules.py, when present beside these scripts) are left out.

Usage: python3 build_sarf.py ARRAMOOZ_DATA_DIR OUT_JSON
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade import local_rules  # noqa: E402

KINDS = {"jamid.csv": "اسم جامد", "masdar.csv": "مصدر", "fa3il.csv": "اسم فاعل", "maf3oul.csv": "اسم مفعول",
         "moubalagha.csv": "صيغة مبالغة", "mouchabbaha.csv": "صفة مشبّهة", "tafdil.csv": "اسم تفضيل",
         "sifates.csv": "صفة"}
HARAKAT = re.compile("[ً-ْٰ]")
TRANS = {"م": "متعدٍّ", "ل": "لازم", "ك": "لازم ومتعدٍّ"}


def clean(s: str) -> str:
    return (s or "").strip().strip("﻿")


def plain(s: str) -> str:
    return HARAKAT.sub("", s)


def main(src, out):
    rules = local_rules()

    def bad(*texts):
        if rules is None:
            return False
        return any(rules.blocked("en", "", t) for t in texts if t)

    freq = {}
    for name, ucol, fcol in (("nouns/wordfreq.csv", 1, 4), ("verbs/freq_verbs.csv", 1, 2)):
        for r in csv.reader(open(os.path.join(src, name), encoding="utf-8"), delimiter="\t"):
            if len(r) > fcol and r[fcol].isdigit():
                freq[clean(r[ucol])] = max(freq.get(clean(r[ucol]), 0), int(r[fcol]))
    words, seen = [], set()
    for fname, kind in KINDS.items():
        path = os.path.join(src, "nouns", fname)
        rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="\t"))
        head = [clean(h).lstrip("#") for h in rows[0]]
        col = {h: i for i, h in enumerate(head)}

        def get(r, name):
            i = col.get(name)
            return clean(r[i]) if i is not None and i < len(r) else ""

        for r in rows[1:]:
            w = get(r, "مشكول") or get(r, "الكلمة")
            if not w or not re.search("[ء-ي]", w):
                continue
            num = get(r, "عدد")
            plural_col = get(r, "الجمع")
            if not get(r, "عدد") and get(r, "مفرده"):
                plural_col = get(r, "مفرده")
            definition = get(r, "شرح").replace('""', '"').strip('"')
            if bad(w, definition):
                continue
            entry = {"w": w, "u": plain(w), "root": get(r, "جذر"), "wazn": get(r, "وزن"), "kind": kind,
                     "origin": get(r, "أصل"), "gender": get(r, "جنس"), "def": definition[:400],
                     "f": freq.get(plain(w).rstrip("ٌ"), 0)}
            plural_col = re.sub(r"\([^)]*\)?", "", plural_col)
            broken = [p.strip() for p in re.split("[;؛،]", plural_col)
                      if len(plain(p.strip())) >= 2 and not p.strip().startswith("+") and plain(p.strip()) != plain(w)
                      and not re.search("[()\\d]", p) and " " not in p.strip()]
            if broken:
                if num == "جمع" or definition.startswith("جمع"):
                    entry["singular"] = broken[0]
                    entry["number"] = "جمع"
                else:
                    entry["plural"] = broken
                    if num:
                        entry["number"] = num
            elif num:
                entry["number"] = num
            key = (entry["w"], kind)
            if key in seen:
                continue
            seen.add(key)
            words.append({k: v for k, v in entry.items() if v})
    verbs = []
    rows = list(csv.reader(open(os.path.join(src, "verbs", "verb_triliteral.csv"), encoding="utf-8"), delimiter="\t"))
    for r in rows[1:]:
        if len(r) < 4 or not clean(r[2]).isdigit():
            continue
        v = clean(r[0])
        if bad(v):
            continue
        verbs.append({"v": v, "root": clean(r[1]), "bab": int(clean(r[2])), "trans": TRANS.get(clean(r[3]), ""),
                      "f": freq.get(plain(v), 0)})
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write('{"source": "Arramooz by Taha Zerrouki, GPL-2.0",\n"words": [\n')
        f.write(",\n".join(json.dumps(w, ensure_ascii=False) for w in words))
        f.write('\n],\n"verbs": [\n')
        f.write(",\n".join(json.dumps(v, ensure_ascii=False) for v in verbs))
        f.write("\n]}\n")
    print(len(words), "nouns;", sum("plural" in w for w in words), "with broken plurals;", len(verbs), "verbs")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
