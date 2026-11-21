# -*- coding: utf-8 -*-
"""
abaAcademy.offline_dict
=======================

The offline Arabic-English dictionary: about 20,000 Arabic entries (vocalised,
with root, plural and English meanings) and about 34,000 English words with
their Arabic equivalents, built from Wiktionary (CC BY-SA 4.0) by
devtools/content/build_dictionary.py; and English definitions, examples and
synonyms for about 147,000 English words from Open English WordNet 2024
(CC BY 4.0). Loaded on first use.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "resources", "dictionary")
HARAKAT = re.compile("[ً-ْٰ]")
POS = {"noun": "اسم", "verb": "فعل", "adj": "صفة", "adv": "ظرف", "pron": "ضمير", "prep": "حرف جرّ",
       "conj": "حرف عطف", "intj": "تعجّب", "num": "عدد", "name": "اسم علم", "phrase": "عبارة",
       "particle": "أداة", "proverb": "مثل", "det": "محدِّد"}


def plain(s: str) -> str:
    return HARAKAT.sub("", s or "")


class OfflineDictionary:
    _inst = None

    def __init__(self, d: str = DIR):
        self.ar: Dict[str, List[dict]] = {}
        self.en: Dict[str, List[str]] = {}
        p = os.path.join(d, "ar_en.jsonl")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    self.ar.setdefault(plain(r["w"]), []).extend(r["e"])
        p = os.path.join(d, "en_ar.jsonl")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    self.en[r["w"]] = r["ar"]

        self._wn_path = os.path.join(d, "wordnet.jsonl")
        self._wn_index: Optional[Dict[str, int]] = None

    def _wordnet_index(self) -> Dict[str, int]:
        if self._wn_index is None:
            idx: Dict[str, int] = {}
            if os.path.exists(self._wn_path):
                with open(self._wn_path, "rb") as f:
                    pos = 0
                    for raw in f:
                        k = raw.find(b'", "s"')
                        if raw.startswith(b'{"w": "') and k > 0:
                            w = json.loads(raw[6:k + 1])
                            idx[w] = pos
                            if w == w.lower() or w.lower() not in idx:
                                idx[w.lower()] = pos
                        pos += len(raw)
            self._wn_index = idx
        return self._wn_index

    def english_senses(self, word: str) -> List[dict]:
        idx = self._wordnet_index()
        off = idx.get(word.strip().lower(), idx.get(word.strip()))
        if off is None:
            return []
        with open(self._wn_path, "rb") as f:
            f.seek(off)
            return json.loads(f.readline())["s"]

    def english_text(self, word: str, limit: int = 6) -> List[str]:
        names = {"noun": "اسم", "verb": "فعل", "adj": "صفة", "adv": "ظرف"}
        out = []
        for s in self.english_senses(word)[:limit]:
            line = f"({names.get(s['p'], s['p'])}) {s['d']}"
            if s.get("x"):
                line += f". مثال: {s['x']}"
            if s.get("s"):
                line += ". مرادفات: " + ", ".join(s["s"])
            out.append(line)
        return out

    @classmethod
    def get(cls) -> "OfflineDictionary":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def available(self) -> bool:
        return bool(self.ar or self.en)

    def describe_ar(self, e: dict) -> str:
        text = f"{e['voc']} ({POS.get(e['pos'], e['pos'])})"
        if e.get("root"):
            text += f"، الجذر {e['root']}"
        if e.get("pl"):
            text += "، الجمع " + " أو ".join(e["pl"])
        return text + ": " + "؛ ".join(e["gl"])

    def lookup(self, query: str) -> List[str]:
        q = query.strip()
        if not q:
            return []
        if re.search("[ء-ي]", q):
            key = plain(q)
            entries = self.ar.get(key) or (self.ar.get(key[2:]) if key.startswith("ال") else None) or []
            return [self.describe_ar(e) for e in entries]
        words = self.en.get(q.lower(), [])
        out = []
        for w in words:
            entries = self.ar.get(plain(w), [])
            if entries:
                e = entries[0]
                out.append(f"{w}: " + "؛ ".join(e["gl"][:3]))
            else:
                out.append(w)
        return out
