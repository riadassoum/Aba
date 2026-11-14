# -*- coding: utf-8 -*-
"""
abaAcademy.quran_engine.morpho_search
=====================================

Search the Qur'an by trilateral/quadrilateral root (جذر), lemma, or word, over
the bundled word-by-word morphology (``resources/quran/word_analysis.json`` from
the Quranic Arabic Corpus). For any root it returns every occurrence: the word as
it appears, its lemma and part of speech, and the surah:ayah location with the
surah name — so a learner can explore how a root is used across the whole Qur'an.

This is built entirely on the real bundled data (50,268 morphologically-tagged
words, 1,651 roots); it invents nothing. The index is built lazily on first use
and cached, so opening the feature is instant and the first search is quick.
"""

from __future__ import annotations

import json
import os
import unicodedata
from collections import defaultdict


def _strip_diacritics(text):
    """Remove Arabic diacritics and tatweel and normalise alef/hamza forms, so a
    user can search 'رحم' or 'الرحمن' without worrying about exact vowelling."""
    out = []
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.category(ch) == "Mn":
            continue
        out.append(ch)
    s = "".join(out)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
                 ("ة", "ه"), ("ى", "ي"), ("ـ", "")):
        s = s.replace(a, b)
    return s


class MorphologySearch:
    """Lazily-indexed root/lemma/word search over the Qur'an morphology."""

    _instance = None

    def __init__(self, resource_dir):
        self.resource_dir = resource_dir
        self._by_root = defaultdict(list)     # root -> [occurrence dicts]
        self._by_lemma = defaultdict(list)
        self._roots_normalised = {}           # normalised root -> canonical root
        self._surah_names = {}
        self._loaded = False

    @classmethod
    def get(cls, resource_dir):
        if cls._instance is None:
            cls._instance = MorphologySearch(resource_dir)
        return cls._instance

    # -- lazy load --------------------------------------------------------
    def _ensure(self):
        if self._loaded:
            return
        qdir = os.path.join(self.resource_dir, "quran")
        # surah names for nice locations
        try:
            qd = json.load(open(os.path.join(qdir, "quran_data.json"), encoding="utf-8"))
            for surah in qd.get("surahs", []):
                self._surah_names[surah["n"]] = surah["name"]
        except Exception:
            pass
        # morphology
        try:
            wa = json.load(open(os.path.join(qdir, "word_analysis.json"), encoding="utf-8"))
        except Exception:
            wa = {}
        for loc, words in wa.items():
            try:
                surah, ayah = (int(x) for x in loc.split(":"))
            except ValueError:
                continue
            for pos_i, w in enumerate(words):
                root = w.get("root")
                lemma = w.get("lemma")
                entry = {
                    "word": w.get("w", ""),
                    "root": root,
                    "lemma": lemma,
                    "pos": w.get("pos", ""),
                    "surah": surah,
                    "ayah": ayah,
                }
                if root:
                    self._by_root[root].append(entry)
                    self._roots_normalised.setdefault(_strip_diacritics(root), root)
                if lemma:
                    self._by_lemma[_strip_diacritics(lemma)].append(entry)
        self._loaded = True

    # -- queries ----------------------------------------------------------
    def search_root(self, root):
        """All occurrences of a root. Accepts the root with or without exact
        vowelling; returns a list of occurrence dicts (possibly empty)."""
        self._ensure()
        if root in self._by_root:
            return self._by_root[root]
        canonical = self._roots_normalised.get(_strip_diacritics(root))
        return self._by_root.get(canonical, []) if canonical else []

    def search_lemma(self, lemma):
        self._ensure()
        return self._by_lemma.get(_strip_diacritics(lemma), [])

    def derived_forms(self, root):
        """The distinct surface words derived from a root, each with a count and
        an example location — a compact 'family' view of the root."""
        occ = self.search_root(root)
        forms = {}
        for e in occ:
            w = e["word"]
            if w not in forms:
                forms[w] = {"word": w, "lemma": e["lemma"], "pos": e["pos"],
                            "count": 0, "first": (e["surah"], e["ayah"])}
            forms[w]["count"] += 1
        return sorted(forms.values(), key=lambda f: -f["count"])

    def root_count(self, root):
        return len(self.search_root(root))

    def location_name(self, surah, ayah):
        name = self._surah_names.get(surah, f"سورة {surah}")
        return f"{name}، الآية {ayah}"

    def all_roots(self):
        """Every root, sorted by how often it occurs (for browsing)."""
        self._ensure()
        return sorted(self._by_root, key=lambda r: -len(self._by_root[r]))

    def summary_for_root(self, root):
        """A spoken Arabic summary: the root, how many times it occurs, and how
        many distinct derived forms it has."""
        occ = self.search_root(root)
        if not occ:
            return f"لم يُعثر على الجذر {root} في القرآن."
        forms = self.derived_forms(root)
        return (f"الجذر {root} يرد {len(occ)} مرة في القرآن، "
                f"بـ {len(forms)} صيغة مختلفة.")
