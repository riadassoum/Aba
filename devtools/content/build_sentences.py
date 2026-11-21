# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/sentences/<lang>.tsv: every Tatoeba sentence pair
between Arabic and English, French, Spanish, German, Italian or Turkish,
direct or through an English translation, as prepared for the courses by
course_builder/pairs.py (Tatoeba, CC BY 2.0 FR, https://tatoeba.org), one pair per line:
foreign<TAB>arabic. Pairs that fall under the academy's content rules
(local_rules.py, when present) are left out, and guillemets are removed.

Usage: python3 build_sentences.py TATOEBA_DIR OUT_DIR
"""

import bz2
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "course_builder"))
try:
    from grade import local_rules
    RULES = local_rules()
except Exception:
    RULES = None

LANGS = {"eng": "en", "fra": "fr", "spa": "es", "deu": "de", "ita": "it", "tur": "tr"}


def sentences(path):
    out = {}
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                out[p[0]] = p[2].replace("«", "").replace("»", "").strip()
    return out


def main(src, out):
    import json
    try:
        from grade import plausible
    except Exception:
        plausible = None
    for short in LANGS.values():
        path = os.path.join(src, f"pairs_{short}.json")
        if not os.path.exists(path):
            continue
        pairs, seen = [], set()
        for r in json.load(open(path, encoding="utf-8")):
            fo = r["t"].replace("«", "").replace("»", "").replace("\t", " ").strip()
            ar = r["ar"].replace("«", "").replace("»", "").replace("\t", " ").strip()
            if (fo, ar) in seen or (RULES is not None and RULES.blocked(short, fo, ar)):
                continue
            if plausible is not None and not plausible(fo, ar):
                continue
            seen.add((fo, ar))
            pairs.append((fo, ar))
        pairs.sort(key=lambda p: (len(p[0]), p[0]))
        with open(os.path.join(out, f"{short}.tsv"), "w", encoding="utf-8") as f:
            for fo, ar in pairs:
                f.write(f"{fo}\t{ar}\n")
        print(short, len(pairs))


def main_direct(src, out):
    ara = sentences(os.path.join(src, "ara_sentences.tsv.bz2"))
    for code, short in LANGS.items():
        sp = os.path.join(src, f"{code}_sentences.tsv.bz2")
        lp = os.path.join(src, f"ara-{code}_links.tsv.bz2")
        if not (os.path.exists(sp) and os.path.exists(lp)):
            print("missing", code)
            continue
        foreign = sentences(sp)
        pairs, seen = [], set()
        with bz2.open(lp, "rt", encoding="utf-8") as f:
            for line in f:
                a, b = line.split()[:2]
                if a in ara and b in foreign:
                    fo, ar = foreign[b], ara[a]
                    if (fo, ar) in seen or "\t" in fo + ar:
                        continue
                    if RULES is not None and RULES.blocked(short, fo, ar):
                        continue
                    seen.add((fo, ar))
                    pairs.append((fo, ar))
        pairs.sort(key=lambda p: (len(p[0]), p[0]))
        with open(os.path.join(out, f"{short}.tsv"), "w", encoding="utf-8") as f:
            for fo, ar in pairs:
                f.write(f"{fo}\t{ar}\n")
        print(short, len(pairs))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
