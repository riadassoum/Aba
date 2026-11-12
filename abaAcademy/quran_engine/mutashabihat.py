# -*- coding: utf-8 -*-
"""
abaAcademy.quran_engine.mutashabihat
====================================

Find *mutashabihat* — the near-identical verses of the Qur'an that memorisers
most often confuse (e.g. البقرة ٢٦٤ لا يهدي القوم الكافرين beside آل عمران ٨٦
لا يهدي القوم الظالمين). The trainer built on this drills the exact
difference between two real verses.

Why this is computed, not hand-typed
-------------------------------------
The mutashabihat are a property of the actual Qur'anic text, so we derive them
directly from the bundled Uthmani text (``resources/quran/quran_data.json``)
rather than transcribing a list by hand. This matters for correctness: every pair
this produces is two verses that genuinely exist in the mushaf, and the
"difference" shown to the learner is computed from the real words of those two
verses — never invented. A wrong hand-typed difference could mislead someone
memorising Qur'an; deriving it from the text removes that risk.

Method
------
1. Normalise each ayah (strip diacritics and tatweel, unify alef/hamza forms) so
   that near-identical wording lines up regardless of vowel marks.
2. Index ayat by shared word-n-grams (shingles). Two ayat that share a long
   run of words are candidate mutashabihat.
3. For each candidate pair, compute a word-level similarity and the exact diff
   (which words differ). Keep pairs that are highly similar but *not identical*
   (a small, drillable difference) and long enough to be worth testing.

The result is a deterministic list of pairs, each with the two locations, the two
original (diacritised) texts, and the differing words — everything the trainer
needs, all traceable to the real text.
"""

from __future__ import annotations

import json
import os
import unicodedata
from collections import defaultdict


def _normalise(text):
    """Strip diacritics/tatweel and unify letter forms for comparison."""
    out = []
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.category(ch) == "Mn":
            continue
        out.append(ch)
    s = "".join(out)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
                 ("ة", "ه"), ("ى", "ي"), ("ـ", ""), ("ؤ", "و"), ("ئ", "ي")):
        s = s.replace(a, b)
    return s.strip()


def _words(text):
    return [w for w in _normalise(text).split() if w]


def _diff_words(words_a, words_b):
    """Return a list of difference operations between two word lists using a
    longest-common-subsequence alignment, so an inserted or removed word shifts
    the rest correctly instead of misreporting every following word as changed.

    Each diff is (kind, word_a, word_b) where kind is 'sub' (substitution),
    'ins' (extra word in B), or 'del' (extra word in A). Correct alignment
    matters here: the learner is told the exact real difference between two
    Qur'an verses."""
    n, m = len(words_a), len(words_b)
    # LCS table
    lcs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if words_a[i] == words_b[j]:
                lcs[i][j] = lcs[i + 1][j + 1] + 1
            else:
                lcs[i][j] = max(lcs[i + 1][j], lcs[i][j + 1])
    diffs = []
    i = j = 0
    while i < n and j < m:
        if words_a[i] == words_b[j]:
            i += 1
            j += 1
        elif lcs[i + 1][j] >= lcs[i][j + 1]:
            diffs.append(("del", words_a[i], ""))
            i += 1
        else:
            diffs.append(("ins", "", words_b[j]))
            j += 1
    while i < n:
        diffs.append(("del", words_a[i], ""))
        i += 1
    while j < m:
        diffs.append(("ins", "", words_b[j]))
        j += 1
    # merge an adjacent del+ins into a single substitution for nicer phrasing
    merged = []
    k = 0
    while k < len(diffs):
        if (k + 1 < len(diffs) and diffs[k][0] == "del"
                and diffs[k + 1][0] == "ins"):
            merged.append(("sub", diffs[k][1], diffs[k + 1][2]))
            k += 2
        else:
            merged.append(diffs[k])
            k += 1
    return merged


class MutashabihatFinder:
    """Lazily builds the pair index from the bundled Qur'an text and serves the
    trainer. Cached as a singleton so the (few-second) scan runs once."""

    _instance = None

    def __init__(self, resource_dir):
        self.resource_dir = resource_dir
        self._ayat = []            # list of dicts: surah, ayah, text, norm, words
        self._surah_names = {}
        self._pairs = []           # built on demand
        self._loaded = False
        self._built = False

    @classmethod
    def get(cls, resource_dir):
        if cls._instance is None:
            cls._instance = MutashabihatFinder(resource_dir)
        return cls._instance

    # -- load text --------------------------------------------------------
    def _ensure_loaded(self):
        if self._loaded:
            return
        qdir = os.path.join(self.resource_dir, "quran")
        try:
            qd = json.load(open(os.path.join(qdir, "quran_data.json"), encoding="utf-8"))
        except Exception:
            qd = {"ayat": [], "surahs": []}
        for surah in qd.get("surahs", []):
            self._surah_names[surah["n"]] = surah["name"]
        for row in qd.get("ayat", []):
            surah, ayah, text = row[0], row[1], row[-1]
            words = _words(text)
            self._ayat.append({
                "surah": surah, "ayah": ayah, "text": text,
                "norm": " ".join(words), "words": words,
            })
        self._loaded = True

    # -- build pairs ------------------------------------------------------
    def _ensure_built(self, min_words=4, min_similarity=0.7, max_pairs=4000):
        if self._built:
            return
        self._ensure_loaded()
        # index ayat by 4-word shingles of their normalised words
        shingle_size = 4
        buckets = defaultdict(list)
        for idx, a in enumerate(self._ayat):
            w = a["words"]
            if len(w) < min_words:
                continue
            for i in range(len(w) - shingle_size + 1):
                key = " ".join(w[i:i + shingle_size])
                buckets[key].append(idx)

        seen = set()
        pairs = []
        for key, idxs in buckets.items():
            if len(idxs) < 2:
                continue
            # consider unique unordered pairs sharing this shingle
            for i in range(len(idxs)):
                for j in range(i + 1, len(idxs)):
                    a, b = idxs[i], idxs[j]
                    if (a, b) in seen:
                        continue
                    seen.add((a, b))
                    pair = self._evaluate_pair(a, b, min_similarity)
                    if pair:
                        pairs.append(pair)
                        if len(pairs) >= max_pairs:
                            break
                if len(pairs) >= max_pairs:
                    break
            if len(pairs) >= max_pairs:
                break

        # sort by similarity descending (closest confusions first), then by length
        pairs.sort(key=lambda p: (-p["similarity"], -p["length"]))
        self._pairs = pairs
        self._built = True

    def _evaluate_pair(self, ia, ib, min_similarity):
        a, b = self._ayat[ia], self._ayat[ib]
        wa, wb = a["words"], b["words"]
        # length filter: comparable lengths
        if abs(len(wa) - len(wb)) > max(2, min(len(wa), len(wb)) // 3):
            return None
        # word-level Jaccard-ish similarity on ordered position + set overlap
        set_a, set_b = set(wa), set(wb)
        overlap = len(set_a & set_b)
        union = len(set_a | set_b)
        sim = overlap / union if union else 0.0
        if sim < min_similarity or sim >= 1.0:
            return None            # not similar enough, or identical
        diffs = _diff_words(wa, wb)
        if not diffs:
            return None            # identical after normalisation — skip
        # keep only genuinely drillable: few differing words
        if len(diffs) > max(3, len(wa) // 3):
            return None
        return {
            "a": {"surah": a["surah"], "ayah": a["ayah"], "text": a["text"]},
            "b": {"surah": b["surah"], "ayah": b["ayah"], "text": b["text"]},
            "similarity": round(sim, 3),
            "length": min(len(wa), len(wb)),
            "diff_count": len(diffs),
            "diffs": diffs,
        }

    # -- public API -------------------------------------------------------
    def pairs(self, limit=500):
        self._ensure_built()
        return self._pairs[:limit]

    def count(self):
        self._ensure_built()
        return len(self._pairs)

    def location_name(self, surah, ayah):
        self._ensure_loaded()
        name = self._surah_names.get(surah, f"سورة {surah}")
        return f"{name}، الآية {ayah}"

    def random_pair(self, rng):
        self._ensure_built()
        if not self._pairs:
            return None
        return rng.choice(self._pairs)

    def describe_difference(self, pair):
        """A spoken Arabic description of how the two verses differ."""
        parts = []
        for kind, wa, wb in pair["diffs"]:
            if kind == "sub":
                parts.append(f"{wa} تصبح {wb}")
            elif kind == "del":
                parts.append(f"{wa} موجودة في الأولى فقط")
            elif kind == "ins":
                parts.append(f"{wb} موجودة في الثانية فقط")
        return "الفرق: " + "، ".join(parts) + "."
