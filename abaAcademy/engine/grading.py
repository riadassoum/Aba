# -*- coding: utf-8 -*-
"""
abaAcademy.engine.grading
=========================

Answer normalization and grading — the one place that decides whether a
learner's typed response counts as correct.

Design goal: be as forgiving as reasonably possible without accepting truly
wrong answers. A learner should never be marked wrong over a detail the lesson
wasn't testing. So for typed answers we:

* fold case (Hello == hello),
* strip Arabic diacritics and tatweel (a missing fatha never fails),
* remove all punctuation and collapse whitespace (I'm late == im late),
* ignore a leading article (English the/a/an, Arabic al-) and Arabic tanwin
  endings (latifan == latif),
* accept any answer listed in Question.accepted, and
* accept a synonym of the expected word via curated synonym groups
  (جميل / لطيف / رائع / حسن / ممتاز, or big / large / huge, ...).

Multi-word answers (dictation, full sentences) are compared after the same
folding, so punctuation and capitalisation never cost a mark there either.

Strict mode (keep_diacritics=True) remains for tashkeel lessons.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, List, Set

from .models import Question, QuestionType

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[.,;:!?'\"`~^*_\-\u2013\u2014\u2026()\[\]{}<>\u00ab\u00bb\u2039\u203a\u201c\u201d\u2018\u2019\u060c\u061b\u061f\u066a\u00bf\u00a1\u201e\u201a\u202f\u00a0/\\|@#&+=]")

_EN_ARTICLES = {"the", "a", "an"}


def strip_arabic_diacritics(text: str) -> str:
    return _ARABIC_DIACRITICS.sub("", text)


# Orthographic variants that Arabic writers use interchangeably and that a
# learner must not be marked wrong for: the alef/hamza family (أ إ آ ٱ -> ا),
# ta-marbuta vs ha (ة -> ه), alef-maqsura vs ya (ى -> ي), and the hamza seats
# (ؤ ئ -> و ي). Applying these means أبو ظبي, ابو ظبي, أبوظبي and
# ابوظبي all compare equal, as do مكة/مكه.
_LETTER_FOLDS = {
    "\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",
    "\u0629": "\u0647",
    "\u0649": "\u064a",
    "\u0624": "\u0648", "\u0626": "\u064a",
}
_LETTER_FOLD_TABLE = {ord(k): v for k, v in _LETTER_FOLDS.items()}


def fold_arabic_letters(text: str) -> str:
    return text.translate(_LETTER_FOLD_TABLE)


def normalize_text(text: str, *, keep_diacritics: bool = False,
                   fold_letters: bool = True) -> str:
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text)).strip()
    # apostrophes vanish so contractions collapse (I'm -> im); other marks
    # become spaces so word boundaries are preserved.
    text = re.sub(r"['\u2019\u2018\u02bc]", "", text)
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    text = text.casefold()
    if not keep_diacritics:
        text = strip_arabic_diacritics(text)
    # Letter folding (hamza/alef, ta-marbuta/ha, alef-maqsura/ya) is independent
    # of diacritics: even a strict-tashkeel lesson should accept أبو/ابو.
    # It's controlled by its own flag so a learner who truly wants exact spelling
    # can turn it off.
    if fold_letters:
        text = fold_arabic_letters(text)
    return text


def _despace(text: str) -> str:
    """A space-insensitive form for comparison, so أبو ظبي == أبوظبي. Only
    used as a fallback equality check, never for display."""
    return text.replace(" ", "")


def _strip_article(word: str) -> str:
    w = word
    for art in _EN_ARTICLES:
        if w.startswith(art + " "):
            w = w[len(art) + 1:]
    if w.startswith("\u0627\u0644") and len(w) > 3:
        w = w[2:]
    if len(w) > 3 and w.endswith("\u0627"):
        w = w[:-1]
    if len(w) > 3 and w.endswith("\u0629"):
        w = w[:-1]
    return w.strip()


SYNONYM_GROUPS: List[Set[str]] = [
    {"\u062c\u0645\u064a\u0644", "\u0644\u0637\u064a\u0641", "\u0631\u0627\u0626\u0639", "\u062d\u0633\u0646", "\u0645\u0645\u062a\u0627\u0632", "\u0628\u062f\u064a\u0639", "\u062c\u064a\u062f", "\u0628\u0647\u064a\u062c"},
    {"\u0643\u0628\u064a\u0631", "\u0636\u062e\u0645", "\u0639\u0638\u064a\u0645", "\u0647\u0627\u0626\u0644", "\u062c\u0633\u064a\u0645"},
    {"\u0635\u063a\u064a\u0631", "\u0636\u0626\u064a\u0644", "\u062f\u0642\u064a\u0642"},
    {"\u0633\u0631\u064a\u0639", "\u0639\u0627\u062c\u0644"},
    {"\u0633\u0639\u064a\u062f", "\u0645\u0633\u0631\u0648\u0631", "\u0641\u0631\u062d", "\u0645\u0628\u062a\u0647\u062c"},
    {"\u062d\u0632\u064a\u0646", "\u0643\u0626\u064a\u0628", "\u0645\u063a\u0645\u0648\u0645"},
    {"\u0637\u064a\u0628", "\u0644\u0630\u064a\u0630", "\u0634\u0647\u064a"},
    {"nice", "good", "great", "lovely", "wonderful", "excellent", "fine", "pleasant"},
    {"big", "large", "huge", "enormous"},
    {"small", "little", "tiny"},
    {"fast", "quick", "rapid"},
    {"happy", "glad", "pleased", "joyful"},
    {"sad", "unhappy"},
    {"beautiful", "pretty", "lovely", "gorgeous"},
    {"smart", "clever", "intelligent", "bright"},
    {"bon", "bien", "agr\u00e9able", "beau", "joli", "magnifique", "excellent"},
    {"grand", "gros", "\u00e9norme"},
    {"petit", "minuscule"},
    {"rapide", "vite"},
    {"content", "heureux", "joyeux"},
    {"triste", "malheureux"},
]

_SYN_INDEX = {}
for _grp in SYNONYM_GROUPS:
    _norm_grp = frozenset(_strip_article(normalize_text(w)) for w in _grp)
    for _w in _norm_grp:
        _SYN_INDEX.setdefault(_w, set()).update(_norm_grp)


def _synonyms_of(norm_word: str) -> Set[str]:
    return _SYN_INDEX.get(norm_word, {norm_word})


def _typing_matches(correct: str, given: str, keep_diacritics: bool,
                    fold_letters: bool = True) -> bool:
    ng = normalize_text(given, keep_diacritics=keep_diacritics,
                        fold_letters=fold_letters)
    nc = normalize_text(correct, keep_diacritics=keep_diacritics,
                        fold_letters=fold_letters)
    if not ng:
        return False
    if ng == nc:
        return True
    sg, sc = _strip_article(ng), _strip_article(nc)
    if sg and sg == sc:
        return True
    # space-insensitive: أبوظبي == أبو ظبي, عبد الله == عبدالله
    if _despace(ng) and _despace(ng) == _despace(nc):
        return True
    if sg and _despace(sg) == _despace(sc):
        return True
    if " " not in sg and " " not in sc:
        if sg in _synonyms_of(sc) or sc in _synonyms_of(sg):
            return True
    return False


def _grade_typing(q: Question, given: str, keep_diacritics: bool,
                  fold_letters: bool = True) -> bool:
    for cand in [q.correct] + list(q.accepted):
        if _typing_matches(str(cand), given, keep_diacritics, fold_letters):
            return True
    return False


def grade(q: Question, given: Any, *, keep_diacritics: bool = False,
          fold_letters: bool = True) -> bool:
    qt = q.qtype
    if qt is QuestionType.MCQ:
        return given == q.correct
    if qt is QuestionType.TRUE_FALSE:
        return bool(given) == bool(q.correct)
    if qt is QuestionType.MULTI_SELECT:
        try:
            return set(given) == set(q.correct)
        except TypeError:
            return False
    if qt is QuestionType.TYPING:
        return _grade_typing(q, given if given is not None else "", keep_diacritics,
                             fold_letters)
    if qt is QuestionType.MATCHING:
        if not isinstance(given, dict):
            return False
        return given == q.correct
    if qt is QuestionType.ORDERING:
        try:
            g = [normalize_text(x) for x in given]
            c = [normalize_text(x) for x in q.correct]
            return g == c
        except TypeError:
            return False
    return False
