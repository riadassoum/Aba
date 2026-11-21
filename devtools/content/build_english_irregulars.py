# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/english/irregulars.json: English irregular verbs
(base, past, past participle) and irregular noun plurals, from the
inflection table of LemmInflect by Brad Jascob (MIT,
https://github.com/bjascob/LemmInflect), itself derived from the AGID
inflection database. Only the CSV table is read. Words are ordered by how
often they occur in the academy's English sentence bank, and only those that
occur there are kept, so the list is of words learners actually meet.

Usage: python3 build_english_irregulars.py infl_lu.csv.gz SENTENCES_EN_TSV OUT_JSON
"""

import csv
import gzip
import json
import re
import sys
from collections import Counter


def regular_past(v):
    if v.endswith("e"):
        return v + "d"
    if re.search("[^aeiou]y$", v):
        return v[:-1] + "ied"
    return v + "ed"


def main(table, sentences, out):
    tok = Counter()
    for line in open(sentences, encoding="utf-8"):
        tok.update(re.findall(r"[a-z']+", line.split("\t")[0].lower()))
    verbs, nouns = [], []
    with gzip.open(table, "rt", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 3 or not row[0].isalpha() or not row[0].islower():
                continue
            base, pos = row[0], row[1]
            if pos == "verb" and len(row) >= 5:
                # base,verb,past,participle,ing,3sg; the participle column is
                # left out when it is the same as the past
                past_col = row[2]
                part_col = (row[3] if len(row) >= 6 else "") or row[2]
                past, part = past_col.split("/")[0], part_col.split("/")[0]
                if base in ("will", "can", "shall", "may", "must"):
                    continue
                # doubling a final consonant (stopped) is spelling, not irregularity
                regular = {regular_past(base), base + base[-1] + "ed"}
                if past in regular and part in regular:
                    continue
                freq = tok[base] + tok[past] + tok[part]
                if freq:
                    verbs.append({"base": base, "past": past_col.replace("/", " أو "),
                                  "part": part_col.replace("/", " أو "), "f": freq})
            elif pos == "noun" and len(row) >= 3:
                plurals = [p for p in row[2].split("/") if p != base]
                if not plurals:
                    continue
                pl = plurals[0]
                if pl in (base + "s", base + "es") or (base.endswith("y") and pl == base[:-1] + "ies"):
                    continue
                freq = tok[base] + tok[pl]
                if freq and pl.isalpha() and not base.endswith("s"):
                    nouns.append({"sing": base, "pl": pl, "f": freq})
    # "saw" counts as a verb only through the past of "see"
    pasts = {p for v in verbs for p in v["past"].split(" أو ")}
    verbs = [v for v in verbs if v["base"] not in pasts or v["base"] in ("read", "put", "let", "hurt", "cut", "set",
                                                                         "hit", "cost", "shut", "come", "become", "run")]
    verbs.sort(key=lambda v: -v["f"])
    nouns.sort(key=lambda v: -v["f"])
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"source": "LemmInflect (MIT) / AGID", "verbs": verbs, "nouns": nouns}, f, ensure_ascii=False, indent=0)
    print(len(verbs), "verbs", len(nouns), "nouns")


if __name__ == "__main__":
    main(*sys.argv[1:])
