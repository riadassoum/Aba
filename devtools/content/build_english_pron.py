# -*- coding: utf-8 -*-
"""Build resources/english/cmudict.txt.gz from the CMU Pronouncing
Dictionary (cmudict.dict, BSD-style licence, https://github.com/cmusphinx/cmudict),
keeping the words that occur in the academy's English sentences or English
dictionary, with their first pronunciation and their frequency in the
sentence bank. Data only: nothing from the source is executed."""

import gzip
import json
import re
import sys
from collections import Counter


def main(cmu, sentences, en_dict, out):
    tok = Counter()
    for line in open(sentences, encoding="utf-8"):
        tok.update(re.findall(r"[a-z']+", line.split("\t")[0].lower()))
    heads = set()
    for line in open(en_dict, encoding="utf-8"):
        try:
            w = json.loads(line)
        except ValueError:
            continue
        h = (w.get("en") or w.get("word") or w.get("w") or "") if isinstance(w, dict) else ""
        if isinstance(h, str) and h.isalpha():
            heads.add(h.lower())
    seen, rows = set(), []
    for line in open(cmu, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line:
            continue
        word, phones = line.split(" ", 1)
        if "(" in word or word in seen or not re.fullmatch(r"[a-z']+", word):
            continue
        if word in tok or word in heads:
            seen.add(word)
            rows.append(f"{word}\t{phones}\t{tok[word]}")
    with gzip.open(out, "wt", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print(len(rows), "words")


if __name__ == "__main__":
    main(*sys.argv[1:5])
