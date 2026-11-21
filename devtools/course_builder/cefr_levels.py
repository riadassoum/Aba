"""CEFR levels for course vocabulary.

English words take their level from the CEFR-J Vocabulary Profile 1.5 (A1-B2,
Tono Laboratory, TUFS) and the Octanove Vocabulary Profile C1/C2 1.0 (CC BY-SA
4.0). A word of another language takes the level of its English equivalent
in the Wiktionary translation tables (``lex[word]["en"]``), so «fruta»,
«meyve» and «Obst» are A1 like fruit. Core function words (``core``) are A1.
Words with no level fall back to their frequency; very rare words are never
placed early whatever their translation says.
"""
import csv
import json
import os

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def load_english(work):
    d = {}
    for name in ("cefrj-vocabulary-profile-1.5.csv", "octanove-vocabulary-profile-c1c2-1.0.csv"):
        path = os.path.join(work, "cefrj", name)
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                lv = (row.get("CEFR") or "").strip().upper()
                if lv not in LEVELS:
                    continue
                for head in row["headword"].split("/"):
                    h = head.strip().lower()
                    if h and (h not in d or LEVELS.index(lv) < d[h]):
                        d[h] = LEVELS.index(lv)
    return d


def frequency_level(rank):
    """Fallback for words with no CEFR source. Frequency alone never claims
    C2: only the C1/C2 list does."""
    for lim, lv in ((700, 0), (1500, 1), (3000, 2), (5000, 3)):
        if rank < lim:
            return lv
    return 4


class Leveller:
    def __init__(self, work, lang, freq, lex):
        self.en = load_english(work)
        self.lang = lang
        self.lex = lex
        self.rank = {}
        for i, w in enumerate(freq):
            self.rank.setdefault(w.lower(), i)
        self.formof = {}
        if lang == "en":
            try:
                with open(os.path.join(work, "wikt", "en_formof.json"), encoding="utf-8") as f:
                    self.formof = json.load(f)
            except OSError:
                self.formof = {}
        self.source = {"cefr": 0, "core": 0, "frequency": 0}

    def _english_level(self, word):
        w = (word or "").lower().strip()
        if not w:
            return None
        if w in self.en:
            return self.en[w]
        for lemma, _ in self.formof.get(w, []):
            if lemma.lower() in self.en:
                return self.en[lemma.lower()]
        # simple English inflections not in the form table
        for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e")):
            if w.endswith(suf) and w[: -len(suf)] + rep in self.en:
                return self.en[w[: -len(suf)] + rep]
        return None

    def sourced(self, word):
        """True when the word's level comes from a CEFR list (directly or
        through its English equivalent) or the core list, not from frequency."""
        w = word.lower()
        info = self.lex.get(w) or {}
        if info.get("core"):
            return True
        en = w if self.lang == "en" else info.get("en", "")
        return self._english_level(en) is not None

    def level(self, word):
        w = word.lower()
        rank = self.rank.get(w, 10 ** 6)
        info = self.lex.get(w) or {}
        if info.get("core"):
            self.source["core"] += 1
            return 0
        lv = self._english_level(w) if self.lang == "en" else self._english_level(info.get("en", ""))
        if lv is None:
            self.source["frequency"] += 1
            return frequency_level(rank)
        self.source["cefr"] += 1
        # a rare word is not taught early even if its English equivalent is basic
        if rank > 6000:
            lv = max(lv, 2)
        elif rank > 3000:
            lv = max(lv, 1)
        return lv
