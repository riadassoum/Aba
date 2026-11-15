# -*- coding: utf-8 -*-
"""
Build the offline Arabic-English dictionary from Wiktionary (the kaikki.org
machine-readable extracts, CC BY-SA 4.0):

* resources/dictionary/ar_en.jsonl: the Arabic entries of English Wiktionary,
  with vocalised form, root, plural, part of speech and English meanings;
* resources/dictionary/en_ar.jsonl: English words with their Arabic
  equivalents, from Wiktionary's English translation tables and from the
  English meanings of the Arabic entries (a short meaning such as "book"
  points back to كِتَاب).

Inflected forms ("form of" entries) are skipped. Entries that fall under the
academy's content rules (local_rules.py, when present) are left out.

Usage: python3 build_dictionary.py ARABIC_JSONL ENGLISH_JSONL OUT_DIR
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "course_builder"))
try:
    from grade import local_rules
    RULES = local_rules()
except Exception:
    RULES = None

ARABIC = re.compile("[ء-ي]")
SKIP_POS = {"character", "symbol", "suffix", "prefix", "infix", "romanization", "punct", "abbrev", "root"}


def bad(*texts):
    return RULES is not None and any(RULES.blocked("en", t or "", t or "") for t in texts)


def glosses_of(d):
    out = []
    for s in d.get("senses", []):
        if s.get("form_of") or s.get("alt_of"):
            continue
        g = (s.get("glosses") or [""])[-1].strip()
        if g and not re.search(r"\b(form|plural|singular|dual|verbal noun|participle) of\b", g) and g not in out:
            out.append(g)
    return out[:8]


def short_terms(gloss):
    g = re.sub(r"\([^)]*\)", "", gloss)
    for part in re.split("[,;]", g):
        p = part.strip().lower()
        p = re.sub(r"^(to|a|an|the) ", "", p)
        if p and len(p.split()) <= 3 and re.fullmatch(r"[a-z][a-z' -]*", p):
            yield p


def main(ar_src, en_src, out_dir):
    ar, en = {}, {}
    with open(ar_src, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("lang_code") != "ar" or d.get("pos") in SKIP_POS:
                continue
            word = d.get("word", "")
            gl = glosses_of(d)
            if not gl or not ARABIC.search(word) or bad(word, " ".join(gl)):
                continue
            voc = next((fm["form"] for fm in d.get("forms", []) if "canonical" in fm.get("tags", [])
                        and ARABIC.search(fm.get("form", ""))), word)
            plural = [fm["form"] for fm in d.get("forms", []) if "plural" in fm.get("tags", [])
                      and not fm.get("source") and ARABIC.search(fm.get("form", ""))][:3]
            root = ""
            for t in d.get("etymology_templates", []) + d.get("head_templates", []):
                a = t.get("args", {})
                if t.get("name") in ("ar-root", "ar-rootbox"):
                    root = " ".join(v for k, v in sorted(a.items()) if k.isdigit())
                elif t.get("name") == "etymon" and a.get("2") == ":root":
                    root = a.get("3", "").split("<")[0]
                if root:
                    break
            tr = next((fm.get("form") for fm in d.get("forms", []) if "romanization" in fm.get("tags", [])), "")
            entry = {"pos": d["pos"], "voc": voc, "gl": gl}
            if root:
                entry["root"] = root
            if plural:
                entry["pl"] = plural
            if tr:
                entry["tr"] = tr
            ar.setdefault(word, []).append(entry)
            for g in gl[:4]:
                for term in short_terms(g):
                    lst = en.setdefault(term, [])
                    if voc not in lst and len(lst) < 12:
                        lst.append(voc)
    tables = 0
    if en_src and os.path.exists(en_src):
        with open(en_src, encoding="utf-8") as f:
            for line in f:
                if '"lang_code": "ar"' not in line:
                    continue
                d = json.loads(line)
                if d.get("lang_code") != "en":
                    continue
                w = d.get("word", "").lower()
                for t in d.get("translations", []):
                    if t.get("lang_code") == "ar" and ARABIC.search(t.get("word", "")) and not bad(t["word"]):
                        lst = en.setdefault(w, [])
                        plain = re.sub("[\u064b-\u0652]", "", t["word"])
                        if all(re.sub("[\u064b-\u0652]", "", x) != plain for x in lst) and len(lst) < 12:
                            lst.append(t["word"])
                            tables += 1
    en = {k: v for k, v in en.items() if not bad(k)}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "ar_en.jsonl"), "w", encoding="utf-8") as f:
        for w in sorted(ar):
            f.write(json.dumps({"w": w, "e": ar[w]}, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "en_ar.jsonl"), "w", encoding="utf-8") as f:
        for w in sorted(en):
            f.write(json.dumps({"w": w, "ar": en[w]}, ensure_ascii=False) + "\n")
    print("arabic entries", len(ar), "english terms", len(en), "from translation tables", tables)


if __name__ == "__main__":
    main(*sys.argv[1:])
