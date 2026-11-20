# -*- coding: utf-8 -*-
"""
abaAcademy.arabic_lab.analyzer
==============================

المحلّل الصرفي للكلمات — every possible reading of an Arabic word (its
vowelled form, root, lemma, type, prefixes and suffixes, tense, person,
number and gender) and the lemmas of a whole text, from Qalsadi by Taha
Zerrouki (GPL, https://github.com/linuxscout/qalsadi), the analyser that
Mishkal itself uses. It runs on Mishkal's worker thread because the
dictionaries are SQLite connections tied to the thread that opened them.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import List

from . import diacritizer as dz

_analex = None
_lemm = None


@dataclass
class Reading:
    vocalized: str
    kind: str
    root: str
    lemma: str
    details: List[str] = field(default_factory=list)

    def text(self) -> str:
        parts = [self.vocalized, self.kind]
        if self.root:
            parts.append(f"الجذر {self.root}")
        if self.lemma:
            parts.append(f"الأصل {self.lemma}")
        return "، ".join(parts + self.details)


KIND = {"Verb": "فعل", "Noun": "اسم", "STOPWORD": "أداة", "Stopword": "أداة", "punct": "علامة ترقيم",
        "POUNCT": "علامة ترقيم", "unknown": "كلمة غير معروفة"}


def _load():
    global _analex, _lemm
    if _analex is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dz._orjson_fallback()
            import qalsadi.analex as qa
            import qalsadi.lemmatizer as ql
            _analex = qa.Analex()
            _lemm = ql.Lemmatizer()
    return _analex


def _kind(raw: str) -> str:
    parts = [p for p in (raw or "").split(":") if p]
    if not parts:
        return ""
    head = KIND.get(parts[0], parts[0])
    if len(parts) > 2:
        sub = parts[2]
        return sub if sub.startswith(head) else f"{head} {sub}"
    return head


def _reading(d: dict) -> Reading:
    det = []
    aff = d.get("affix") or ()
    if isinstance(aff, (list, tuple)) and len(aff) == 4:
        if aff[0]:
            det.append(f"السوابق {aff[0]}")
        if aff[3]:
            det.append(f"اللواحق {aff[3]}")
    for key, label in (("tense", ""), ("pronoun", "الضمير"), ("person", ""), ("number", ""), ("gender", ""),
                       ("mood", "")):
        v = d.get(key)
        if v and isinstance(v, str):
            det.append(f"{label} {v}".strip())
    if not d.get("tense"):
        tags = [t for t in (d.get("tags") or "").split(":") if t and t not in ("y", "n")]
        det.extend(dict.fromkeys(tags))
    return Reading(d.get("vocalized") or d.get("word", ""), _kind(d.get("type", "")), d.get("root") or "",
                   d.get("lemma") or d.get("original") or "", list(dict.fromkeys(det)))


def _analyse(word: str) -> List[Reading]:
    a = _load()
    out, seen = [], set()
    dicts = [s.get_dict() if hasattr(s, "get_dict") else dict(s.__dict__) for s in a.check_word(word.strip())]
    dicts.sort(key=lambda d: -(d.get("freq") or 0) if isinstance(d.get("freq"), int) else 0)
    for d in dicts:
        r = _reading(d)
        key = (r.vocalized, r.kind, r.lemma)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def analyse(word: str) -> List[Reading]:
    if not word.strip() or " " in word.strip():
        raise ValueError("اكتب كلمة واحدة.")
    return dz._worker.submit(_analyse, word).result()


def _lemmas(text: str) -> List[str]:
    _load()
    return _lemm.lemmatize_text(text)


def lemmas(text: str) -> List[str]:
    return dz._worker.submit(_lemmas, text).result()
