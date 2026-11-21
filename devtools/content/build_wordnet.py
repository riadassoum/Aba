# -*- coding: utf-8 -*-
"""
Build abaAcademy/resources/dictionary/wordnet.jsonl from Open English
WordNet 2024 (CC BY 4.0, https://en-word.net): one line per English word
with, for each sense, its part of speech, definition, an example and the
other words of the same meaning. Lets the dictionary give English
definitions without an internet connection.

Usage: python3 build_wordnet.py english-wordnet-2024.xml.gz OUT_JSONL
"""

import gzip
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "course_builder"))
try:
    from grade import local_rules
    RULES = local_rules()
except Exception:
    RULES = None

POS = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}


def main(src, out):
    synsets, members, entries = {}, {}, {}
    for ev, el in ET.iterparse(gzip.open(src), events=("end",)):
        if el.tag == "LexicalEntry":
            lemma = el.find("Lemma")
            w = lemma.get("writtenForm")
            pos = POS.get(lemma.get("partOfSpeech"), "")
            for s in el.findall("Sense"):
                entries.setdefault(w, []).append((pos, s.get("synset")))
                members.setdefault(s.get("synset"), []).append(w)
            el.clear()
        elif el.tag == "Synset":
            d = el.find("Definition")
            ex = el.find("Example")
            synsets[el.get("id")] = ((d.text or "") if d is not None else "",
                                      (ex.text or "").strip('"') if ex is not None else "")
            el.clear()
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for w in sorted(entries, key=str.lower):
            if not w[:1].isalpha():
                continue
            senses = []
            for pos, sid in entries[w][:8]:
                d, ex = synsets.get(sid, ("", ""))
                if not d:
                    continue
                if RULES is not None and RULES.blocked("en", f"{w} {d} {ex}", ""):
                    continue
                syn = [m for m in members.get(sid, []) if m != w][:5]
                sense = {"p": pos, "d": d}
                if ex:
                    sense["x"] = ex
                if syn:
                    sense["s"] = syn
                senses.append(sense)
            if senses:
                f.write(json.dumps({"w": w, "s": senses}, ensure_ascii=False) + "\n")
                n += 1
    print(n, "words")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
