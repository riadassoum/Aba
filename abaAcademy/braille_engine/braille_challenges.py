# -*- coding: utf-8 -*-
"""
abaAcademy.braille_engine.braille_challenges
============================================

Word challenges for learning Arabic Grade-2 braille contractions (الاختصارات),
drawn from the bundled ~294k-word Arabic dictionary.

The teaching idea
-----------------
A learner is taught contractions gradually. At any point they know a *subset*
(e.g. من but not yet ال). A good challenge word is one that exercises a
contraction they've learned — like منال, which contains من. Crucially, the
grader must accept every spelling that is correct *for what the learner knows*:

* a learned contraction inside the word MAY be written as its contraction cell,
  OR spelled out letter by letter — both are correct;
* a contraction they have NOT yet learned MUST be spelled out letter by letter
  (they can't be expected to use a sign they were never taught), and writing it
  out letter by letter is accepted as correct.

So for منال when the learner knows من but not ال:
  - من sign + ا + ل ✓ (used the learned contraction)
  - م + ن + ا + ل                ✓ (spelled everything out)
  - من sign + ال sign ✗ (used ال, which they weren't taught)

This module produces such words and validates a learner's cell sequence against
all acceptable encodings, given their known-contraction set. Pure Python; the
dictionary is loaded lazily and cached.
"""

from __future__ import annotations

import gzip
import os
import random

from .arabic_braille import (
    ARABIC_LETTERS, GRADE2_WORDSIGNS, contraction_can_be_substring,
)


class BrailleChallengeEngine:
    _instance = None

    def __init__(self, resource_dir):
        self.resource_dir = resource_dir
        self._words = None                 # lazy: list of dictionary words
        self._by_contraction = {}          # contraction -> list of words containing it

    @classmethod
    def get(cls, resource_dir):
        if cls._instance is None:
            cls._instance = BrailleChallengeEngine(resource_dir)
        return cls._instance

    # -- dictionary -------------------------------------------------------
    def _load_words(self):
        if self._words is not None:
            return
        path = os.path.join(self.resource_dir, "dictionary", "arabic_words.txt.gz")
        words = []
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    w = line.strip()
                    # keep short-to-medium common-length words for drills
                    if w and 2 <= len(w) <= 7:
                        words.append(w)
        except Exception:
            words = []
        self._words = words

    def _index_contraction(self, contraction):
        """Build (once) the list of dictionary words that contain a contraction
        as a substring, so we can quickly pick challenge words for it."""
        if contraction in self._by_contraction:
            return self._by_contraction[contraction]
        self._load_words()
        hits = []
        for w in self._words:
            if contraction in w and w != contraction:
                hits.append(w)
        self._by_contraction[contraction] = hits
        return hits

    # -- picking a challenge ---------------------------------------------
    def pick_word(self, known_contractions, rng=None):
        """Pick a dictionary word that contains at least one of the learner's
        *known* contractions, so the drill exercises what they've been taught.
        Returns the word, or None if nothing suitable is found."""
        rng = rng or random.Random()
        known = [c for c in known_contractions if c in GRADE2_WORDSIGNS]
        if not known:
            return None
        # try a few known contractions in random order for variety
        for contraction in rng.sample(known, len(known)):
            pool = self._index_contraction(contraction)
            if pool:
                return rng.choice(pool)
        return None

    def pick_plain_word(self, rng=None, min_len=2, max_len=6):
        """Pick any dictionary word for spelling practice WITHOUT contractions —
        the learner writes it letter by letter. Uses the bundled ~294k-word
        Arabic dictionary. Returns a word all of whose letters are in the braille
        table (so it's fully writable)."""
        rng = rng or random.Random()
        self._load_words()
        if not self._words:
            return None
        for _ in range(50):
            w = rng.choice(self._words)
            if min_len <= len(w) <= max_len and all(ch in ARABIC_LETTERS for ch in w):
                return w
        return None

    # -- encoding & validation -------------------------------------------
    def valid_encodings(self, word, known_contractions):
        """Return the set of acceptable braille-cell sequences for ``word`` given
        the learner's known contractions. Each encoding is a tuple of frozenset
        cells. A learned contraction found in the word may be used as its sign or
        spelled out; anything else is spelled out letter by letter.

        We enumerate encodings by walking the word left to right, at each
        position either emitting the next letter's cell, or — if a *known*
        contraction matches starting here — emitting that contraction's cell(s)
        and skipping its letters."""
        known = [c for c in known_contractions if c in GRADE2_WORDSIGNS]
        # sort by length desc so longer contractions are tried first at each pos
        known.sort(key=len, reverse=True)
        results = set()

        def letters_cells(segment):
            """Cells for spelling a segment letter by letter, or None if any
            letter is unknown to the braille table."""
            cells = []
            for ch in segment:
                if ch not in ARABIC_LETTERS:
                    return None
                cells.append(frozenset(ARABIC_LETTERS[ch]))
            return tuple(cells)

        def walk(pos, acc):
            if pos == len(word):
                results.add(tuple(acc))
                return
            # option 1: spell the current letter out
            ch = word[pos]
            if ch in ARABIC_LETTERS:
                walk(pos + 1, acc + [frozenset(ARABIC_LETTERS[ch])])
            # option 2: use any known contraction that matches here — but only if
            # it may legitimately appear at this position. A whole-word-only
            # contraction (e.g. أو) is allowed only when it spans the ENTIRE
            # word; a substring-capable one (e.g. من, ال) may appear anywhere.
            for c in known:
                if word.startswith(c, pos):
                    spans_whole = (pos == 0 and pos + len(c) == len(word))
                    if not spans_whole and not contraction_can_be_substring(c):
                        continue
                    cells = [frozenset(cell) for cell in GRADE2_WORDSIGNS[c]]
                    walk(pos + len(c), acc + cells)

        walk(0, [])
        return results

    def check(self, word, cell_sequence, known_contractions):
        """Is the learner's ``cell_sequence`` (list of sets of dot numbers) a
        valid encoding of ``word`` under their known contractions?"""
        norm = tuple(frozenset(c) for c in cell_sequence)
        return norm in self.valid_encodings(word, known_contractions)

    def canonical_hint(self, word, known_contractions):
        """A human-readable description of one accepted encoding (preferring the
        contraction form) for hints."""
        known = sorted((c for c in known_contractions if c in GRADE2_WORDSIGNS),
                       key=len, reverse=True)
        parts = []
        pos = 0
        while pos < len(word):
            used = None
            for c in known:
                if word.startswith(c, pos):
                    used = c
                    break
            if used:
                parts.append(f"اختصار {used}")
                pos += len(used)
            else:
                parts.append(word[pos])
                pos += 1
        return " ثم ".join(parts)
