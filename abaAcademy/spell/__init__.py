# -*- coding: utf-8 -*-
"""
abaAcademy.spell
================

المدقّق الإملائي — offline spell checking for Arabic, English and French with
the LibreOffice Hunspell dictionaries (Ayaspell for Arabic, SCOWL for
English, Grammalecte for French), read by the pure-Python engine in
``hunspell.py``. Each word is checked against the dictionary of its script:
Arabic letters against Arabic, Latin letters against English or French as
the learner chooses. Words the learner adds are kept in a personal list in
the settings, beside the program.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Dict, List, Optional, Tuple

from .hunspell import Dictionary, words_in

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "resources", "spell")

LANGS = {"ar": ("العربية", "ar"), "en": ("الإنجليزية", "en_US"), "fr": ("الفرنسية", "fr")}
PERSONAL_KEY = "spell_personal_words"

_cache: Dict[str, Dictionary] = {}
_lock = threading.Lock()


def available(lang: str) -> bool:
    base = LANGS.get(lang, (None, None))[1]
    return bool(base) and os.path.exists(os.path.join(DATA, base + ".dic"))


def dictionary(lang: str) -> Optional[Dictionary]:
    """The dictionary for ``lang``, loaded on first use (Arabic takes a couple
    of seconds) and kept for the session."""
    if not available(lang):
        return None
    with _lock:
        d = _cache.get(lang)
        if d is None:
            base = LANGS[lang][1]
            d = Dictionary(os.path.join(DATA, base + ".aff"), os.path.join(DATA, base + ".dic"))
            _cache[lang] = d
        return d


def preload(langs=("ar",)) -> None:
    """Load dictionaries in the background so the first check is quick."""
    def run():
        for lang in langs:
            try:
                dictionary(lang)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def script_of(word: str) -> str:
    return "ar" if any("؀" <= c <= "ۿ" for c in word) else "latin"


class Checker:
    def __init__(self, latin: str = "en", personal: Optional[List[str]] = None):
        self.latin = latin if latin in ("en", "fr") else "en"
        self.personal = set(personal or [])
        self.ignored: set = set()

    def lang_for(self, word: str) -> str:
        return "ar" if script_of(word) == "ar" else self.latin

    def check(self, word: str) -> bool:
        if word in self.personal or word in self.ignored:
            return True
        d = dictionary(self.lang_for(word))
        return True if d is None else d.check(word)

    def suggest(self, word: str, limit: int = 8) -> List[str]:
        d = dictionary(self.lang_for(word))
        return [] if d is None else d.suggest(word, limit)

    def errors(self, text: str, start: int = 0) -> List[Tuple[int, int, str]]:
        return [(s, e, w) for s, e, w in words_in(text) if s >= start and not self.check(w)]

    def next_error(self, text: str, start: int = 0) -> Optional[Tuple[int, int, str]]:
        for s, e, w in words_in(text):
            if s >= start and not self.check(w):
                return s, e, w
        return None


def load_personal(store) -> List[str]:
    try:
        return list(json.loads(store.get_setting(PERSONAL_KEY, "[]") or "[]"))
    except Exception:
        return []


def add_personal(store, word: str) -> None:
    words = load_personal(store)
    if word not in words:
        words.append(word)
        try:
            store.set_setting(PERSONAL_KEY, json.dumps(words, ensure_ascii=False))
        except Exception:
            pass
