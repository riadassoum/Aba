# -*- coding: utf-8 -*-
"""
abaAcademy.dictionary_ar
========================

A small offline Arabic word validator, used by word games (anagrams, and any
future word game) to judge whether a typed word is a real Arabic word — with no
internet needed.

The word list is bundled at ``resources/dictionary/arabic_words.json``. Its
``words`` set is a cleaned, de-diacritized list of several thousand common
Arabic words drawn from an open-source Arabic frequency corpus (Hermit Dave's
FrequencyWords, MIT-licensed) combined with this add-on's own vetted teaching
vocabulary. ``anagram_pool`` is a hand-curated list of common concrete nouns
that make good anagram puzzles.

We deliberately did NOT use the Qur'anic morphology corpus as the dictionary:
it is classical/Qur'anic vocabulary carrying full diacritics, so it is a poor
judge of everyday modern words and would reject common ones while accepting rare
archaic forms. A cleaned modern frequency list is the right tool for this job.
"""

from __future__ import annotations

import json
import os

# Arabic diacritics to strip so "مَدْرَسَة" and "مدرسة" compare equal.
_TASHKEEL = set(
    [chr(c) for c in range(0x0610, 0x061B)]
    + [chr(c) for c in range(0x064B, 0x0653)]
    + [chr(0x0670)]
)

_ALEF_VARIANTS = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"}


def _letter_counts(word):
    """A plain dict of letter -> count; faster to build than collections.Counter
    across hundreds of thousands of short words."""
    d = {}
    for ch in word:
        d[ch] = d.get(ch, 0) + 1
    return d


def normalize(word: str) -> str:
    """Strip diacritics and tatweel and unify alef forms, so comparisons are
    about the letters, not the spelling accidents."""
    if not word:
        return ""
    out = []
    for ch in word.strip():
        if ch in _TASHKEEL or ch == "\u0640":   # tatweel
            continue
        out.append(_ALEF_VARIANTS.get(ch, ch))
    return "".join(out)


class ArabicDictionary:
    """Loads the bundled word list once and answers membership questions.

    The word list is a full open-source Arabic dictionary (~294,000 words),
    stored gzipped as newline text so it stays small on disk yet loads fast into
    an in-memory set for O(1) lookups. The anagram pool (common concrete nouns
    that make good puzzles) is a separate small file."""

    _instance = None

    def __init__(self, resource_dir: str):
        import gzip
        base = os.path.join(resource_dir, "dictionary")
        self._words = set()
        self._normalized = set()
        self._anagram_pool = []
        self._short = None          # built lazily on first anagram scan
        # full validator dictionary (gzipped newline text). Loading + normalizing
        # is enough for word validation (is_word), which is all most word games
        # need; the heavier anagram index is deferred until a game asks for it.
        try:
            with gzip.open(os.path.join(base, "arabic_words.txt.gz"),
                           "rt", encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    if w:
                        self._words.add(w)
            self._normalized = {normalize(w) for w in self._words}
        except Exception:
            pass
        # anagram puzzle pool
        try:
            with open(os.path.join(base, "anagram_pool.json"), encoding="utf-8") as f:
                self._anagram_pool = json.load(f).get("anagram_pool", [])
        except Exception:
            pass

    def _build_short_index(self):
        """Prepare the short-word list used for anagram scanning: just the
        normalized words of 2-7 letters. Built once, lazily, in about 30ms — far
        cheaper than precomputing per-word letter maps, and the per-source scan
        below is still well under a fifth of a second."""
        self._short = [w for w in self._normalized if 2 <= len(w) <= 7]

    def findable_from(self, source: str):
        """Every dictionary word (normalized) that can be spelled from the
        letters of ``source`` — used by the anagram game to know when the player
        has found them all. Builds the short-word list on first use, then scans
        it (a subset check rejects most candidates cheaply)."""
        if self._short is None:
            self._build_short_index()
        src = normalize(source)
        have = _letter_counts(src)
        have_set = set(have)
        out = set()
        for w in self._short:
            if not set(w) <= have_set:
                continue
            ok = True
            seen = {}
            for ch in w:
                seen[ch] = seen.get(ch, 0) + 1
                if seen[ch] > have.get(ch, 0):
                    ok = False
                    break
            if ok:
                out.add(w)
        out.add(src)
        return out

    @classmethod
    def get(cls, resource_dir: str) -> "ArabicDictionary":
        if cls._instance is None:
            cls._instance = ArabicDictionary(resource_dir)
        return cls._instance

    def is_word(self, word: str) -> bool:
        """True if ``word`` is a known Arabic word (diacritics/alef-form
        insensitive)."""
        w = word.strip()
        if not w:
            return False
        return w in self._words or normalize(w) in self._normalized

    def anagram_pool(self):
        return list(self._anagram_pool)

    def size(self) -> int:
        return len(self._words)
