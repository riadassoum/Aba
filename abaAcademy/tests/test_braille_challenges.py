# -*- coding: utf-8 -*-
"""Tests for the abbreviation-aware braille challenge engine. The central
requirement: a learner is only ever expected to use contractions they've been
taught, and both the contraction form and the spelled-out form are accepted."""

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.braille_engine.braille_challenges import BrailleChallengeEngine
from abaAcademy.braille_engine.arabic_braille import ARABIC_LETTERS, GRADE2_WORDSIGNS
from abaAcademy.braille_engine import braille_lessons as bl

_RES = os.path.abspath(os.path.join(_HERE, "..", "resources"))


def _cells(seq_of_words):
    """Helper: build a cell sequence from a mix of contraction names and letters."""
    out = []
    for token in seq_of_words:
        if token in GRADE2_WORDSIGNS:
            out.extend(set(c) for c in GRADE2_WORDSIGNS[token])
        else:
            out.append(set(ARABIC_LETTERS[token]))
    return out


class TestManalCase(unittest.TestCase):
    """The user's example: منال contains من. With من learned but not ال."""

    @classmethod
    def setUpClass(cls):
        cls.eng = BrailleChallengeEngine(_RES)

    def test_contraction_form_accepted(self):
        # «من» sign + ا + ل
        seq = _cells(["من", "ا", "ل"])
        self.assertTrue(self.eng.check("منال", seq, {"من"}))

    def test_spelled_out_accepted(self):
        # م + ن + ا + ل
        seq = _cells(["م", "ن", "ا", "ل"])
        self.assertTrue(self.eng.check("منال", seq, {"من"}))

    def test_unlearned_contraction_rejected(self):
        # «من» sign + «ال» sign — but ال was NOT taught
        seq = _cells(["من", "ال"])
        self.assertFalse(self.eng.check("منال", seq, {"من"}))

    def test_learned_both_accepts_both_contractions(self):
        seq = _cells(["من", "ال"])
        self.assertTrue(self.eng.check("منال", seq, {"من", "ال"}))

    def test_wrong_letters_rejected(self):
        seq = _cells(["م", "ن", "ا", "م"])   # last letter wrong
        self.assertFalse(self.eng.check("منال", seq, {"من"}))


class TestPickWord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eng = BrailleChallengeEngine(_RES)

    def test_picks_word_containing_known_contraction(self):
        import random
        w = self.eng.pick_word({"من"}, random.Random(3))
        self.assertIsNotNone(w)
        self.assertIn("من", w)

    def test_no_known_returns_none(self):
        self.assertIsNone(self.eng.pick_word(set()))


class TestLessonProgression(unittest.TestCase):
    def test_contractions_grow(self):
        first = set(bl.contractions_up_to("bl1"))
        later = set(bl.contractions_up_to("bl3"))
        self.assertTrue(first.issubset(later))
        self.assertGreater(len(later), len(first))

    def test_all_lessons_have_valid_signs(self):
        for lid, title, signs in bl.all_lessons():
            for s in signs:
                self.assertIn(s, GRADE2_WORDSIGNS, f"{lid}: {s}")


class TestLiblouisAccuracy(unittest.TestCase):
    """Lock in that the contractions match the official liblouis Unified Arabic
    Braille dots, and that the count reflects the full table (200+)."""

    def test_correct_dots(self):
        # من = dots 3,5,6 and في = 2,3,5 per the liblouis ar-ar-g2 table
        self.assertEqual(set(GRADE2_WORDSIGNS["من"][0]), {3, 5, 6})
        self.assertEqual(set(GRADE2_WORDSIGNS["في"][0]), {2, 3, 5})
        self.assertEqual(set(GRADE2_WORDSIGNS["ال"][0]), {1, 4})

    def test_many_contractions(self):
        # the full Unified Arabic Braille set is 200+, not a handful
        self.assertGreater(len(GRADE2_WORDSIGNS), 200)

    def test_substring_rule(self):
        from abaAcademy.braille_engine.arabic_braille import contraction_can_be_substring
        # من may appear inside a word (begmidword); أو is whole-word only
        self.assertTrue(contraction_can_be_substring("من"))
        self.assertFalse(contraction_can_be_substring("أو"))


class TestPlainWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eng = BrailleChallengeEngine(_RES)

    def test_plain_word_pick(self):
        import random
        w = self.eng.pick_plain_word(random.Random(2))
        self.assertIsNotNone(w)
        self.assertTrue(all(ch in ARABIC_LETTERS for ch in w))


if __name__ == "__main__":
    unittest.main(verbosity=2)
